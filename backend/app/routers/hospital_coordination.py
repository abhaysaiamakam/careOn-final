"""
CareOn Milestone 7 — Hospital Readiness, Capacity & Emergency Coordination Router.

Endpoints:
- Facility Profiles (/api/hospital/facilities)
- Dynamic Hospital Capacity & Freshness (/api/hospital/facilities/{id}/capacity)
- Atomic Capacity Reservations (/api/hospital/facilities/{id}/reservations)
- Hospital Diversion Management (/api/hospital/facilities/{id}/diversion)
- Facility Readiness Assessment (/api/hospital/readiness/assess/{id})
- Ranked Destination Recommendations (/api/hospital/destinations/recommend)
- Pre-Arrival Incoming Patient Workflow (/api/hospital/incoming-requests)
- Mass-Casualty Incident (MCI) Distribution (/api/hospital/mci/distribute)
"""

import json
import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    User,
    Organization,
    OrganizationMembership,
    HospitalFacility,
    HospitalCapacity,
    HospitalCapacityReservation,
    IncomingPatientRequest,
    Incident,
    Assignment,
    utc_now,
)
from app.rbac.dependencies import get_current_user_flexible
from app.schemas import (
    HospitalFacilityCreate,
    HospitalFacilityUpdate,
    HospitalFacilityResponse,
    HospitalCapacityUpdateRequest,
    HospitalCapacityResponse,
    HospitalCapacityReservationRequest,
    HospitalCapacityReservationResponse,
    FacilityDiversionUpdateRequest,
    IncomingPatientCreateRequest,
    IncomingPatientResponseAction,
    IncomingPatientRequestResponse,
    FacilityReadinessAssessmentResponse,
    MCIDistributionRequest,
)
from app.hospital_ops import (
    update_facility_capacity,
    reserve_facility_capacity,
    release_capacity_reservation,
    sweep_expired_reservations,
    get_facility_capacity_summary,
    get_facility_diversion_status,
    set_facility_diversion_status,
    assess_facility_readiness,
    rank_hospital_destinations,
    create_incoming_patient_request,
    acknowledge_incoming_patient_request,
    accept_incoming_patient_request,
    decline_incoming_patient_request,
    clarify_incoming_patient_request,
    cancel_incoming_patient_request,
    sweep_incoming_request_timeouts,
    plan_mci_distribution,
    CapacityValidationError,
    InsufficientCapacityError,
    IncomingRequestStatus,
)

logger = logging.getLogger("careon.routers.hospital_coordination")

router = APIRouter(prefix="/api/hospital", tags=["Hospital Coordination"])


def _verify_facility_access(user: User, facility: HospitalFacility, db: Session) -> bool:
    """Verifies that user is authorized to manage this hospital facility."""
    role = (user.role or "").lower()
    if role in ("superadmin", "super_admin", "admin"):
        return True

    # Check active membership in the facility's organization
    membership = (
        db.query(OrganizationMembership)
        .filter(
            OrganizationMembership.user_id == user.id,
            OrganizationMembership.organization_id == facility.organization_id,
            OrganizationMembership.status == "active",
        )
        .first()
    )
    if membership:
        return True

    # Also check if user belongs to hospital organization
    return False


# ==============================================================================
# 1. Hospital Facility Profile Endpoints
# ==============================================================================

@router.post("/facilities", response_model=HospitalFacilityResponse, status_code=status.HTTP_201_CREATED)
def create_facility(
    payload: HospitalFacilityCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_flexible),
):
    """Register a new hospital facility profile under an organization."""
    role = (current_user.role or "").lower()
    if role not in ("superadmin", "super_admin", "admin", "hospital_staff", "org_admin", "organization_admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized to create hospital facilities")

    org = db.query(Organization).filter(Organization.id == payload.organization_id).first()
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")

    existing = db.query(HospitalFacility).filter(HospitalFacility.facility_code == payload.facility_code).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Facility code '{payload.facility_code}' already exists")

    facility = HospitalFacility(
        organization_id=payload.organization_id,
        facility_code=payload.facility_code,
        name=payload.name,
        facility_type=payload.facility_type,
        location_name=payload.location_name,
        latitude=payload.latitude,
        longitude=payload.longitude,
        geom=f"POINT({payload.longitude} {payload.latitude})",
        trauma_level=payload.trauma_level,
        capabilities=payload.capabilities,
        specialist_services=payload.specialist_services,
        medical_equipment=payload.medical_equipment,
        ambulance_bays=payload.ambulance_bays,
        operating_status=payload.operating_status,
        emergency_phone=payload.emergency_phone,
        escalation_contact=payload.escalation_contact,
        is_active=True,
        last_verified_at=utc_now(),
        created_at=utc_now(),
    )
    db.add(facility)
    db.commit()
    db.refresh(facility)
    return facility


@router.get("/facilities", response_model=List[HospitalFacilityResponse])
def list_facilities(
    organization_id: Optional[int] = None,
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_flexible),
):
    """List hospital facilities with optional filtering."""
    query = db.query(HospitalFacility)
    if organization_id:
        query = query.filter(HospitalFacility.organization_id == organization_id)
    if is_active is not None:
        query = query.filter(HospitalFacility.is_active == is_active)

    return query.all()


@router.get("/facilities/{facility_id}", response_model=HospitalFacilityResponse)
def get_facility(
    facility_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_flexible),
):
    """Retrieve detailed hospital facility profile."""
    facility = db.query(HospitalFacility).filter(HospitalFacility.id == facility_id).first()
    if not facility:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hospital facility not found")
    return facility


@router.patch("/facilities/{facility_id}", response_model=HospitalFacilityResponse)
def update_facility(
    facility_id: int,
    payload: HospitalFacilityUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_flexible),
):
    """Update hospital facility profile."""
    facility = db.query(HospitalFacility).filter(HospitalFacility.id == facility_id).first()
    if not facility:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hospital facility not found")

    if not _verify_facility_access(current_user, facility, db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to modify this hospital facility")

    update_data = payload.model_dump(exclude_unset=True)
    for field, val in update_data.items():
        setattr(facility, field, val)

    if payload.latitude is not None and payload.longitude is not None:
        facility.geom = f"POINT({payload.longitude} {payload.latitude})"

    facility.last_verified_at = utc_now()
    db.commit()
    db.refresh(facility)
    return facility


# ==============================================================================
# 2. Dynamic Hospital Capacity & Reservations
# ==============================================================================

@router.get("/facilities/{facility_id}/capacity")
def get_facility_capacity(
    facility_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_flexible),
):
    """Retrieve multi-category hospital capacity summary and freshness tier."""
    facility = db.query(HospitalFacility).filter(HospitalFacility.id == facility_id).first()
    if not facility:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hospital facility not found")

    return get_facility_capacity_summary(db, facility_id)


@router.put("/facilities/{facility_id}/capacity", response_model=HospitalCapacityResponse)
def update_capacity(
    facility_id: int,
    payload: HospitalCapacityUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_flexible),
):
    """Update total, occupied, and unavailable capacity for a category."""
    facility = db.query(HospitalFacility).filter(HospitalFacility.id == facility_id).first()
    if not facility:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hospital facility not found")

    if not _verify_facility_access(current_user, facility, db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to update capacity for this facility")

    try:
        cap_row = update_facility_capacity(
            db=db,
            facility_id=facility_id,
            category=payload.category,
            total=payload.total,
            occupied=payload.occupied,
            unavailable=payload.unavailable,
            reporting_source=payload.reporting_source,
            user=current_user,
            notes=payload.notes,
        )
    except CapacityValidationError as cve:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(cve))

    return cap_row


@router.post("/facilities/{facility_id}/reservations", response_model=HospitalCapacityReservationResponse)
def create_capacity_reservation(
    facility_id: int,
    payload: HospitalCapacityReservationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_flexible),
):
    """Atomically reserve hospital capacity for an incoming emergency."""
    role = (current_user.role or "").lower()
    if role not in ("dispatcher", "admin", "superadmin", "super_admin", "hospital_staff"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized to reserve hospital capacity")

    try:
        reservation = reserve_facility_capacity(
            db=db,
            facility_id=facility_id,
            incident_id=payload.incident_id,
            assignment_id=payload.assignment_id,
            category=payload.category,
            quantity=payload.quantity,
            expires_in_seconds=payload.expires_in_seconds,
            user=current_user,
        )
    except InsufficientCapacityError as ice:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(ice))
    except CapacityValidationError as cve:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(cve))

    return reservation


@router.delete("/reservations/{reservation_token}")
def release_reservation(
    reservation_token: str,
    reason: str = Query("released_by_user"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_flexible),
):
    """Explicitly release an active hospital capacity reservation."""
    success = release_capacity_reservation(db, reservation_token, reason=reason, user=current_user)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Active reservation not found or already released")
    return {"status": "released", "reservation_token": reservation_token}


@router.post("/reservations/sweep")
def sweep_reservations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_flexible),
):
    """Sweep and reconcile expired hospital capacity reservations."""
    reclaimed = sweep_expired_reservations(db)
    return {"reclaimed_count": len(reclaimed), "tokens": [r.reservation_token for r in reclaimed]}


# ==============================================================================
# 3. Hospital Diversion Management
# ==============================================================================

@router.get("/facilities/{facility_id}/diversion")
def get_diversion(
    facility_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_flexible),
):
    """Retrieve current diversion state and reason for a facility."""
    try:
        status_data = get_facility_diversion_status(facility_id, db)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    return status_data


@router.post("/facilities/{facility_id}/diversion")
def update_diversion(
    facility_id: int,
    payload: FacilityDiversionUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_flexible),
):
    """Update diversion status with mandatory operational reason."""
    facility = db.query(HospitalFacility).filter(HospitalFacility.id == facility_id).first()
    if not facility:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hospital facility not found")

    if not _verify_facility_access(current_user, facility, db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to modify diversion status for this facility")

    try:
        res = set_facility_diversion_status(
            db=db,
            facility_id=facility_id,
            new_status=payload.new_status,
            reason=payload.reason,
            diversion_type=payload.diversion_type,
            effective_until=payload.effective_until,
            user=current_user,
        )
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))

    return res


# ==============================================================================
# 4. Hospital Readiness Assessment & Destination Recommendation
# ==============================================================================

@router.get("/readiness/assess/{facility_id}", response_model=FacilityReadinessAssessmentResponse)
def assess_readiness(
    facility_id: int,
    incident_id: int = Query(...),
    assignment_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_flexible),
):
    """Evaluate a hospital facility against an emergency incident's requirements."""
    facility = db.query(HospitalFacility).filter(HospitalFacility.id == facility_id).first()
    if not facility:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hospital facility not found")

    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")

    assessment = assess_facility_readiness(db, facility, incident, assignment_id=assignment_id)
    return assessment.to_dict()


@router.get("/destinations/recommend", response_model=List[FacilityReadinessAssessmentResponse])
def recommend_destinations(
    incident_id: int = Query(...),
    assignment_id: Optional[int] = Query(None),
    limit: int = Query(5, ge=1, le=20),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_flexible),
):
    """Rank hospital facilities by readiness classification, road ETA, bed availability, and diversion."""
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")

    ranked = rank_hospital_destinations(db, incident, assignment_id=assignment_id, max_candidates=limit)
    return [r.to_dict() for r in ranked]


# ==============================================================================
# 5. Pre-Arrival Incoming Patient Workflow
# ==============================================================================

@router.post("/incoming-requests", response_model=IncomingPatientRequestResponse, status_code=status.HTTP_201_CREATED)
def create_request(
    payload: IncomingPatientCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_flexible),
):
    """Dispatcher creates an incoming-patient notification for a receiving hospital."""
    role = (current_user.role or "").lower()
    if role not in ("dispatcher", "admin", "superadmin", "super_admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only dispatchers can create incoming patient requests")

    try:
        req = create_incoming_patient_request(
            db=db,
            facility_id=payload.facility_id,
            incident_id=payload.incident_id,
            assignment_id=payload.assignment_id,
            dispatcher=current_user,
            emergency_severity=payload.emergency_severity,
            patient_condition_summary=payload.patient_condition_summary,
            eta_minutes=payload.eta_minutes,
            eta_source=payload.eta_source,
            deadline_seconds=payload.deadline_seconds,
        )
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))

    return req


@router.get("/incoming-requests", response_model=List[IncomingPatientRequestResponse])
def list_incoming_requests(
    facility_id: Optional[int] = None,
    status_filter: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_flexible),
):
    """Query incoming patient requests."""
    query = db.query(IncomingPatientRequest)
    if facility_id:
        query = query.filter(IncomingPatientRequest.facility_id == facility_id)
    if status_filter:
        query = query.filter(IncomingPatientRequest.status == status_filter.lower().strip())

    return query.order_by(IncomingPatientRequest.created_at.desc()).limit(100).all()


@router.post("/incoming-requests/{request_token}/respond", response_model=IncomingPatientRequestResponse)
def respond_incoming_request(
    request_token: str,
    payload: IncomingPatientResponseAction,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_flexible),
):
    """
    Hospital staff action on incoming emergency:
    - 'acknowledge': marks acknowledged
    - 'accept': confirms readiness and atomically reserves beds
    - 'decline': rejects with mandatory reason, alerts dispatcher
    - 'clarify': requests clinical notes
    """
    req = db.query(IncomingPatientRequest).filter(IncomingPatientRequest.request_token == request_token).first()
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incoming patient request not found")

    if not _verify_facility_access(current_user, req.facility, db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to respond on behalf of this hospital")

    action = payload.action.lower().strip()
    try:
        if action == "acknowledge":
            result = acknowledge_incoming_patient_request(db, request_token, current_user)
        elif action == "accept":
            result = accept_incoming_patient_request(
                db=db,
                request_token=request_token,
                hospital_user=current_user,
                reserve_er_bed=payload.reserve_er_bed,
                reserve_trauma_bay=payload.reserve_trauma_bay,
                reserve_icu_bed=payload.reserve_icu_bed,
            )
        elif action == "decline":
            if not payload.reason:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Reason is required when declining an incoming emergency")
            result = decline_incoming_patient_request(db, request_token, current_user, payload.reason)
        elif action == "clarify":
            if not payload.clarification_notes:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Clarification notes are required")
            result = clarify_incoming_patient_request(db, request_token, current_user, payload.clarification_notes)
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid action '{payload.action}'")
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))

    return result


@router.post("/incoming-requests/{request_token}/cancel")
def cancel_request(
    request_token: str,
    reason: str = Query("Mission cancelled or destination changed"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_flexible),
):
    """Cancel an incoming patient request and release reserved capacity."""
    success = cancel_incoming_patient_request(db, request_token, reason=reason, user=current_user)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incoming patient request not found")
    return {"status": "cancelled", "request_token": request_token}


@router.post("/incoming-requests/sweep")
def sweep_timeouts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_flexible),
):
    """Sweep incoming requests that have exceeded their response deadline."""
    expired = sweep_incoming_request_timeouts(db)
    return {"expired_count": len(expired), "tokens": [r.request_token for r in expired]}


# ==============================================================================
# 6. Mass-Casualty Incident (MCI) Distribution
# ==============================================================================

@router.post("/mci/distribute")
def distribute_mci(
    payload: MCIDistributionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_flexible),
):
    """
    Computes an optimal, balanced distribution of multiple MCI casualties across regional hospitals.
    Prevents single-facility saturation by matching trauma capabilities and travel time.
    """
    role = (current_user.role or "").lower()
    if role not in ("dispatcher", "admin", "superadmin", "super_admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only dispatchers can compute MCI distribution plans")

    try:
        plan = plan_mci_distribution(db, payload.incident_id, payload.patient_severities)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))

    return plan
