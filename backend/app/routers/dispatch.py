"""
CareOn Milestone 5 — Intelligent Dispatch & Resource Optimization Router.

Provides endpoints for:
- Incident assessment (/api/dispatch/assess/{id})
- Ranked resource candidate generation (/api/dispatch/recommend/{id})
- Multi-incident resource optimization (/api/dispatch/optimize)
- Dispatcher approval (/api/dispatch/approve)
- Dispatcher override with mandatory reason (/api/dispatch/override)
- Dispatch decision audit history (/api/dispatch/decisions)
- Resource capability & eligibility inspection (/api/dispatch/resources/{id}/eligibility)
- Resource capability & equipment updates (/api/dispatch/resources/{id}/capabilities)
- Destination hospital recommendations (/api/dispatch/hospitals/recommend/{id})
- Hospital diversion state management (/api/dispatch/hospitals/{id}/diversion)
"""

import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Incident, Resource, Assignment, DispatchDecision, Organization, utc_now
from app.rbac.dependencies import get_current_user_flexible, require_role
from app.rbac.roles import UserRole
from app.schemas import (
    DispatchAssessmentResponse,
    CandidateScoreResponse,
    DispatchRecommendationResponse,
    DispatchOptimizationResponse,
    DispatchApproveRequest,
    DispatchOverrideRequest,
    DispatchDecisionResponse,
    HospitalDiversionUpdateRequest,
    HospitalDiversionResponse,
    HospitalRecommendationResponse,
    ResourceCapabilityUpdateRequest,
)
from app.dispatch.assessment import assess_incident
from app.dispatch.eligibility import check_resource_eligibility
from app.dispatch.scoring import rank_candidates_for_incident, ScoringWeights
from app.dispatch.optimizer import optimize_multi_incident_dispatch
from app.dispatch.diversion import (
    get_hospital_diversion_status,
    set_hospital_diversion_status,
    recommend_destination_hospitals,
)
from app.dispatch.approval import process_dispatch_decision
from app.realtime.event_models import EventTypes, get_global_channel, get_incident_channel
from app.realtime.event_publisher import record_and_publish_event

logger = logging.getLogger("careon.dispatch.router")

router = APIRouter(prefix="/api/dispatch", tags=["Intelligent Dispatch"])


# Helper: Check Dispatcher or Admin privileges
def verify_dispatcher_access(user):
    role_str = getattr(user, "role", "").lower()
    if role_str not in ("dispatcher", "admin", "super_admin", "organization_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Dispatch operations are restricted to authorized dispatchers and administrators.",
        )


# ==============================================================================
# 1. Incident Assessment
# ==============================================================================
@router.post("/assess/{incident_id}", response_model=DispatchAssessmentResponse)
def assess_incident_endpoint(
    incident_id: int,
    user=Depends(get_current_user_flexible),
    db: Session = Depends(get_db),
):
    """Deep incident assessment evaluating severity, priority, required capabilities, and equipment."""
    verify_dispatcher_access(user)

    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found.")

    assessment = assess_incident(incident, db)
    return assessment.to_dict()


# ==============================================================================
# 2. Candidate Recommendations for Incident
# ==============================================================================
@router.post("/recommend/{incident_id}", response_model=DispatchRecommendationResponse)
def recommend_candidates_endpoint(
    incident_id: int,
    user=Depends(get_current_user_flexible),
    db: Session = Depends(get_db),
):
    """
    Generate ranked resource candidates for an incident using hard capability constraints
    and explainable scoring.
    """
    verify_dispatcher_access(user)

    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found.")

    assessment = assess_incident(incident, db)
    resources = db.query(Resource).all()

    ranked = rank_candidates_for_incident(
        incident=incident,
        assessment=assessment,
        resources=resources,
        db=db,
    )

    top_candidate = ranked[0] if ranked and ranked[0].eligibility_status == "eligible" else None
    eligible_count = len([c for c in ranked if c.eligibility_status == "eligible"])

    # Publish M4 event: recommendation created
    record_and_publish_event(
        db=db,
        event_type="dispatch.recommendation_created",
        payload={
            "incident_id": incident.id,
            "incident_code": incident.incident_code,
            "recommended_priority": assessment.recommended_priority,
            "severity": assessment.severity,
            "top_candidate": top_candidate.to_dict() if top_candidate else None,
            "eligible_candidates_count": eligible_count,
            "timestamp": utc_now().isoformat(),
        },
        incident_id=incident.id,
        actor_id=user.id,
        channel=get_incident_channel(incident.id),
    )

    return {
        "incident_id": incident.id,
        "incident_code": incident.incident_code,
        "assessment": assessment.to_dict(),
        "top_recommendation": top_candidate.to_dict() if top_candidate else None,
        "ranked_candidates": [c.to_dict() for c in ranked],
        "total_candidates_evaluated": len(ranked),
        "eligible_count": eligible_count,
    }


# ==============================================================================
# 3. Multi-Incident Resource Optimization
# ==============================================================================
@router.post("/optimize", response_model=DispatchOptimizationResponse)
def optimize_multi_incident_endpoint(
    user=Depends(get_current_user_flexible),
    db: Session = Depends(get_db),
):
    """
    Evaluate multiple active pending incidents competing for scarce resources.
    Produces an explainable global allocation plan that preserves active missions.
    """
    verify_dispatcher_access(user)

    assigned_inc_ids = {
        a.incident_id for a in db.query(Assignment).filter(Assignment.status == "Active").all()
    }
    active_incidents = (
        db.query(Incident)
        .filter(Incident.status.notin_(["Resolved", "Cancelled", "Rejected"]), ~Incident.id.in_(assigned_inc_ids))
        .all()
    )

    available_resources = db.query(Resource).filter(Resource.status == "Available").all()

    plan = optimize_multi_incident_dispatch(
        incidents=active_incidents,
        available_resources=available_resources,
        db=db,
    )

    return plan.to_dict()


# ==============================================================================
# 4. Dispatcher Approval Workflow
# ==============================================================================
@router.post("/approve")
def approve_dispatch_endpoint(
    payload: DispatchApproveRequest,
    user=Depends(get_current_user_flexible),
    db: Session = Depends(get_db),
):
    """
    Human dispatcher approves a recommended candidate.
    Atomically verifies availability, claims resource, creates assignment, and logs decision.
    """
    verify_dispatcher_access(user)

    try:
        result = process_dispatch_decision(
            db=db,
            incident_id=payload.incident_id,
            selected_resource_id=payload.resource_id,
            dispatcher_id=user.id,
            dispatcher_name=user.name,
            decision_type="approved",
            recommended_resource_id=payload.resource_id,
            notes=payload.notes,
        )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


# ==============================================================================
# 5. Dispatcher Override Workflow
# ==============================================================================
@router.post("/override")
def override_dispatch_endpoint(
    payload: DispatchOverrideRequest,
    user=Depends(get_current_user_flexible),
    db: Session = Depends(get_db),
):
    """
    Human dispatcher overrides the recommendation and selects an alternative resource.
    Requires mandatory override_reason (minimum 5 characters).
    """
    verify_dispatcher_access(user)

    if not payload.override_reason or len(payload.override_reason.strip()) < 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mandatory override reason (min 5 characters) is required when overriding.",
        )

    try:
        result = process_dispatch_decision(
            db=db,
            incident_id=payload.incident_id,
            selected_resource_id=payload.resource_id,
            dispatcher_id=user.id,
            dispatcher_name=user.name,
            decision_type="overridden",
            override_reason=payload.override_reason,
            notes=payload.notes,
        )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


# ==============================================================================
# 6. Dispatch Decision Audit History
# ==============================================================================
@router.get("/decisions", response_model=List[DispatchDecisionResponse])
def list_dispatch_decisions_endpoint(
    incident_id: Optional[int] = Query(None),
    decision_type: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user=Depends(get_current_user_flexible),
    db: Session = Depends(get_db),
):
    """Retrieve immutable audit history of dispatch approvals and overrides."""
    verify_dispatcher_access(user)

    query = db.query(DispatchDecision)
    if incident_id:
        query = query.filter(DispatchDecision.incident_id == incident_id)
    if decision_type:
        query = query.filter(DispatchDecision.decision_type == decision_type)

    decisions = query.order_by(DispatchDecision.created_at.desc()).offset(offset).limit(limit).all()
    return decisions


# ==============================================================================
# 7. Resource Eligibility Check
# ==============================================================================
@router.get("/resources/{resource_id}/eligibility")
def get_resource_eligibility_endpoint(
    resource_id: int,
    incident_id: int = Query(..., description="Target incident ID to test eligibility against"),
    user=Depends(get_current_user_flexible),
    db: Session = Depends(get_db),
):
    """Inspect detailed eligibility breakdown for a resource against an incident."""
    verify_dispatcher_access(user)

    resource = db.query(Resource).filter(Resource.id == resource_id).first()
    if not resource:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found.")

    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found.")

    assessment = assess_incident(incident, db)
    eligibility = check_resource_eligibility(resource, assessment, db)
    return eligibility.to_dict()


# ==============================================================================
# 8. Resource Capabilities & Equipment Management
# ==============================================================================
@router.put("/resources/{resource_id}/capabilities")
def update_resource_capabilities_endpoint(
    resource_id: int,
    payload: ResourceCapabilityUpdateRequest,
    user=Depends(get_current_user_flexible),
    db: Session = Depends(get_db),
):
    """Update capabilities, equipment, or status of a resource."""
    verify_dispatcher_access(user)

    resource = db.query(Resource).filter(Resource.id == resource_id).first()
    if not resource:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found.")

    if payload.capabilities is not None:
        resource.capabilities = payload.capabilities.strip()
    if payload.equipment is not None:
        resource.equipment = payload.equipment.strip()
    if payload.capacity is not None:
        resource.capacity = payload.capacity
    if payload.status is not None:
        resource.status = payload.status.strip()

    resource.last_updated = utc_now()
    db.commit()
    db.refresh(resource)

    # Publish M4 event: capabilities updated
    record_and_publish_event(
        db=db,
        event_type="resource.capabilities_updated",
        payload={
            "resource_id": resource.id,
            "resource_code": resource.resource_code,
            "capabilities": resource.capabilities,
            "equipment": resource.equipment,
            "status": resource.status,
            "timestamp": resource.last_updated.isoformat(),
        },
        actor_id=user.id,
        channel=get_global_channel(),
    )

    return {
        "status": "success",
        "resource_id": resource.id,
        "capabilities": resource.capabilities,
        "equipment": resource.equipment,
        "resource_status": resource.status,
    }


# ==============================================================================
# 9. Destination Hospital Recommendations
# ==============================================================================
@router.post("/hospitals/recommend/{incident_id}", response_model=List[HospitalRecommendationResponse])
def recommend_hospitals_endpoint(
    incident_id: int,
    user=Depends(get_current_user_flexible),
    db: Session = Depends(get_db),
):
    """Recommend destination hospitals factoring road travel times, ER capacity, and diversion status."""
    verify_dispatcher_access(user)

    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found.")

    candidates = recommend_destination_hospitals(incident, db)
    return [c.to_dict() for c in candidates]


# ==============================================================================
# 10. Hospital Diversion Management
# ==============================================================================
@router.get("/hospitals/{org_id}/diversion", response_model=HospitalDiversionResponse)
def get_diversion_endpoint(
    org_id: int,
    user=Depends(get_current_user_flexible),
    db: Session = Depends(get_db),
):
    """Retrieve hospital diversion status (Redis cache + PostgreSQL source of truth)."""
    verify_dispatcher_access(user)

    data = get_hospital_diversion_status(org_id, db)
    return data


@router.put("/hospitals/{org_id}/diversion", response_model=HospitalDiversionResponse)
def update_diversion_endpoint(
    org_id: int,
    payload: HospitalDiversionUpdateRequest,
    user=Depends(get_current_user_flexible),
    db: Session = Depends(get_db),
):
    """
    Update hospital diversion status with immediate Redis cache invalidation
    and real-time event publication.
    """
    role_str = getattr(user, "role", "").lower()
    if role_str not in ("hospital_staff", "dispatcher", "admin", "super_admin", "organization_admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized to change hospital diversion.")

    data = set_hospital_diversion_status(
        org_id=org_id,
        divert_status=payload.divert_status,
        divert_reason=payload.divert_reason,
        user_id=user.id,
        actor_name=user.name,
        db=db,
    )
    return data
