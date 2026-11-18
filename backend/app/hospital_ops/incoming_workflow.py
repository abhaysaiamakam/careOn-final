"""
CareOn Milestone 7 — Incoming Patient Pre-Arrival Notification & Response Workflow.

Manages the pre-arrival hospital coordination lifecycle:
1. Dispatcher creates incoming-patient notification request (PENDING).
2. Hospital staff acknowledges request (ACKNOWLEDGED).
3. Hospital staff accepts (ACCEPTED) -> triggers atomic capacity reservation.
4. Hospital staff declines (DECLINED) -> requires reason, alerts dispatcher without automatic rerouting.
5. Clarification loop (NEEDS_CLARIFICATION).
6. Timeout detection (EXPIRED) -> alerts dispatcher, prevents silent reassignment.
7. Mission cancellation or destination change (CANCELLED) -> releases capacity reservations.
"""

import json
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from app.models import (
    HospitalFacility,
    IncomingPatientRequest,
    HospitalCapacityReservation,
    Incident,
    Assignment,
    User,
    utc_now,
)
from app.realtime.event_models import (
    EventTypes,
    get_org_channel,
    get_incident_channel,
    get_global_channel,
)
from app.realtime.event_publisher import record_and_publish_event
from app.responder_ops.notifications import notification_service
from app.hospital_ops.capacity import (
    CapacityCategory,
    reserve_facility_capacity,
    release_capacity_reservation,
    get_facility_capacity_summary,
)

logger = logging.getLogger("careon.hospital_ops.incoming_workflow")

DEFAULT_HOSPITAL_ACK_DEADLINE_SEC = 600  # 10 minutes


class IncomingRequestStatus:
    PENDING = "pending"
    ACKNOWLEDGED = "acknowledged"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    NEEDS_CLARIFICATION = "needs_clarification"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


def create_incoming_patient_request(
    db: Session,
    facility_id: int,
    incident_id: int,
    assignment_id: Optional[int],
    dispatcher: User,
    emergency_severity: str = "High",
    patient_condition_summary: Optional[str] = None,
    eta_minutes: Optional[float] = None,
    eta_source: Optional[str] = None,
    deadline_seconds: int = DEFAULT_HOSPITAL_ACK_DEADLINE_SEC,
) -> IncomingPatientRequest:
    """
    Creates an incoming-patient pre-arrival notification request for a receiving hospital.
    Dispatches real-time WebSocket event and push notifications.
    """
    facility = db.query(HospitalFacility).filter(HospitalFacility.id == facility_id).first()
    if not facility:
        raise ValueError(f"Hospital facility {facility_id} not found")

    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise ValueError(f"Incident {incident_id} not found")

    now = utc_now()
    deadline = now + timedelta(seconds=deadline_seconds)
    token = str(uuid.uuid4())

    # Snapshot current capacity
    cap_summary = get_facility_capacity_summary(db, facility.id)

    req = IncomingPatientRequest(
        request_token=token,
        facility_id=facility.id,
        incident_id=incident.id,
        assignment_id=assignment_id,
        dispatcher_id=dispatcher.id,
        status=IncomingRequestStatus.PENDING,
        emergency_severity=emergency_severity,
        patient_condition_summary=patient_condition_summary,
        eta_minutes=eta_minutes,
        eta_source=eta_source,
        capacity_snapshot_json=json.dumps(cap_summary),
        acknowledgement_deadline=deadline,
        created_at=now,
        updated_at=now,
    )
    db.add(req)
    db.commit()
    db.refresh(req)

    # Broadcast real-time outbox event
    payload = {
        "request_token": token,
        "facility_id": facility.id,
        "facility_name": facility.name,
        "incident_id": incident.id,
        "incident_code": incident.incident_code,
        "assignment_id": assignment_id,
        "emergency_severity": emergency_severity,
        "patient_condition_summary": patient_condition_summary,
        "eta_minutes": eta_minutes,
        "status": IncomingRequestStatus.PENDING,
        "deadline": deadline.isoformat(),
        "created_at": now.isoformat(),
    }

    record_and_publish_event(
        db=db,
        event_type="hospital.incoming_patient_requested",
        channel=get_org_channel(facility.organization_id),
        payload=payload,
        actor_id=dispatcher.id,
        incident_id=incident.id,
        organization_id=facility.organization_id,
    )
    record_and_publish_event(
        db=db,
        event_type="hospital.incoming_patient_requested",
        channel=get_incident_channel(incident.id),
        payload=payload,
        actor_id=dispatcher.id,
        incident_id=incident.id,
        organization_id=facility.organization_id,
    )
    record_and_publish_event(
        db=db,
        event_type="hospital.incoming_patient_requested",
        channel=get_global_channel(),
        payload=payload,
        actor_id=dispatcher.id,
        incident_id=incident.id,
        organization_id=facility.organization_id,
    )
    db.commit()

    return req


def acknowledge_incoming_patient_request(
    db: Session,
    request_token: str,
    hospital_user: User,
) -> IncomingPatientRequest:
    """Hospital staff acknowledges awareness of the incoming emergency."""
    req = db.query(IncomingPatientRequest).filter(IncomingPatientRequest.request_token == request_token).first()
    if not req:
        raise ValueError("Incoming patient request not found")

    if req.status in (IncomingRequestStatus.ACCEPTED, IncomingRequestStatus.DECLINED, IncomingRequestStatus.CANCELLED):
        return req  # Idempotent return

    now = utc_now()
    req.status = IncomingRequestStatus.ACKNOWLEDGED
    req.hospital_response_user_id = hospital_user.id
    req.updated_at = now
    db.commit()

    facility = req.facility
    payload = {
        "request_token": req.request_token,
        "facility_id": req.facility_id,
        "incident_id": req.incident_id,
        "status": IncomingRequestStatus.ACKNOWLEDGED,
        "acknowledged_by": hospital_user.name,
        "acknowledged_at": now.isoformat(),
    }
    record_and_publish_event(
        db=db,
        event_type="hospital.incoming_patient_acknowledged",
        channel=get_incident_channel(req.incident_id),
        payload=payload,
        actor_id=hospital_user.id,
        incident_id=req.incident_id,
        organization_id=facility.organization_id if facility else None,
    )
    db.commit()

    return req


def accept_incoming_patient_request(
    db: Session,
    request_token: str,
    hospital_user: User,
    reserve_er_bed: bool = True,
    reserve_trauma_bay: bool = False,
    reserve_icu_bed: bool = False,
) -> IncomingPatientRequest:
    """
    Hospital staff confirms acceptance of incoming emergency patient.
    Atomically creates capacity reservations for requested resources.
    """
    req = db.query(IncomingPatientRequest).filter(IncomingPatientRequest.request_token == request_token).first()
    if not req:
        raise ValueError("Incoming patient request not found")

    if req.status == IncomingRequestStatus.ACCEPTED:
        return req  # Idempotent replay

    if req.status in (IncomingRequestStatus.DECLINED, IncomingRequestStatus.CANCELLED):
        raise ValueError(f"Cannot accept request in '{req.status}' state")

    now = utc_now()

    # Automatically reserve trauma bay if Critical and not specified
    if req.emergency_severity in ("Critical", "1"):
        reserve_trauma_bay = True

    # 1. Capacity reservations
    if reserve_er_bed:
        try:
            reserve_facility_capacity(
                db=db,
                facility_id=req.facility_id,
                incident_id=req.incident_id,
                assignment_id=req.assignment_id,
                category=CapacityCategory.ER_BEDS,
                quantity=1,
                user=hospital_user,
            )
        except Exception as exc:
            logger.warning("ER bed reservation failed during acceptance: %s", exc)

    if reserve_trauma_bay:
        try:
            reserve_facility_capacity(
                db=db,
                facility_id=req.facility_id,
                incident_id=req.incident_id,
                assignment_id=req.assignment_id,
                category=CapacityCategory.TRAUMA_BAYS,
                quantity=1,
                user=hospital_user,
            )
        except Exception as exc:
            logger.warning("Trauma bay reservation failed during acceptance: %s", exc)

    if reserve_icu_bed:
        try:
            reserve_facility_capacity(
                db=db,
                facility_id=req.facility_id,
                incident_id=req.incident_id,
                assignment_id=req.assignment_id,
                category=CapacityCategory.ICU_BEDS,
                quantity=1,
                user=hospital_user,
            )
        except Exception as exc:
            logger.warning("ICU bed reservation failed during acceptance: %s", exc)

    # 2. Update request state
    req.status = IncomingRequestStatus.ACCEPTED
    req.hospital_response_user_id = hospital_user.id
    req.responded_at = now
    req.updated_at = now
    db.commit()

    facility = req.facility
    payload = {
        "request_token": req.request_token,
        "facility_id": req.facility_id,
        "facility_name": facility.name if facility else "",
        "incident_id": req.incident_id,
        "assignment_id": req.assignment_id,
        "status": IncomingRequestStatus.ACCEPTED,
        "accepted_by": hospital_user.name,
        "responded_at": now.isoformat(),
    }

    record_and_publish_event(
        db=db,
        event_type="hospital.incoming_patient_accepted",
        channel=get_incident_channel(req.incident_id),
        payload=payload,
        actor_id=hospital_user.id,
        incident_id=req.incident_id,
        organization_id=facility.organization_id if facility else None,
    )
    record_and_publish_event(
        db=db,
        event_type="hospital.incoming_patient_accepted",
        channel=get_global_channel(),
        payload=payload,
        actor_id=hospital_user.id,
        incident_id=req.incident_id,
        organization_id=facility.organization_id if facility else None,
    )
    db.commit()

    return req


def decline_incoming_patient_request(
    db: Session,
    request_token: str,
    hospital_user: User,
    reason: str,
) -> IncomingPatientRequest:
    """
    Hospital staff declines incoming emergency patient.
    Requires mandatory reason, releases reservations, and alerts commanding dispatcher without auto-rerouting.
    """
    req = db.query(IncomingPatientRequest).filter(IncomingPatientRequest.request_token == request_token).first()
    if not req:
        raise ValueError("Incoming patient request not found")

    if not reason or len(reason.strip()) < 3:
        raise ValueError("A clear clinical or operational reason is required when declining an incoming emergency")

    now = utc_now()
    req.status = IncomingRequestStatus.DECLINED
    req.hospital_response_user_id = hospital_user.id
    req.hospital_response_reason = reason.strip()
    req.responded_at = now
    req.updated_at = now

    # Release any active reservations for this request / incident
    active_reservations = (
        db.query(HospitalCapacityReservation)
        .filter(
            HospitalCapacityReservation.facility_id == req.facility_id,
            HospitalCapacityReservation.incident_id == req.incident_id,
            HospitalCapacityReservation.status == "active",
        )
        .all()
    )
    for res in active_reservations:
        release_capacity_reservation(db, res.reservation_token, reason="declined_by_hospital", user=hospital_user)

    db.commit()

    facility = req.facility
    payload = {
        "request_token": req.request_token,
        "facility_id": req.facility_id,
        "facility_name": facility.name if facility else "",
        "incident_id": req.incident_id,
        "assignment_id": req.assignment_id,
        "status": IncomingRequestStatus.DECLINED,
        "declined_by": hospital_user.name,
        "reason": reason,
        "responded_at": now.isoformat(),
        "requires_dispatcher_reassignment": True,
    }

    record_and_publish_event(
        db=db,
        event_type="hospital.incoming_patient_declined",
        channel=get_incident_channel(req.incident_id),
        payload=payload,
        actor_id=hospital_user.id,
        incident_id=req.incident_id,
        organization_id=facility.organization_id if facility else None,
    )
    record_and_publish_event(
        db=db,
        event_type="hospital.incoming_patient_declined",
        channel=get_global_channel(),
        payload=payload,
        actor_id=hospital_user.id,
        incident_id=req.incident_id,
        organization_id=facility.organization_id if facility else None,
    )
    db.commit()

    return req


def clarify_incoming_patient_request(
    db: Session,
    request_token: str,
    hospital_user: User,
    notes: str,
) -> IncomingPatientRequest:
    """Hospital staff requests clarification regarding patient condition or requirements."""
    req = db.query(IncomingPatientRequest).filter(IncomingPatientRequest.request_token == request_token).first()
    if not req:
        raise ValueError("Incoming patient request not found")

    if not notes or len(notes.strip()) < 3:
        raise ValueError("Clarification question or notes must be provided")

    now = utc_now()
    req.status = IncomingRequestStatus.NEEDS_CLARIFICATION
    req.clarification_notes = notes.strip()
    req.hospital_response_user_id = hospital_user.id
    req.updated_at = now
    db.commit()

    facility = req.facility
    payload = {
        "request_token": req.request_token,
        "facility_id": req.facility_id,
        "incident_id": req.incident_id,
        "status": IncomingRequestStatus.NEEDS_CLARIFICATION,
        "clarification_notes": notes,
        "requested_by": hospital_user.name,
        "requested_at": now.isoformat(),
    }
    record_and_publish_event(
        db=db,
        event_type="hospital.incoming_patient_clarification",
        channel=get_incident_channel(req.incident_id),
        payload=payload,
        actor_id=hospital_user.id,
        incident_id=req.incident_id,
        organization_id=facility.organization_id if facility else None,
    )
    db.commit()

    return req


def cancel_incoming_patient_request(
    db: Session,
    request_token: str,
    reason: str = "Mission cancelled or destination changed",
    user: Optional[User] = None,
) -> bool:
    """Cancels an incoming patient request and releases associated reservations."""
    req = db.query(IncomingPatientRequest).filter(IncomingPatientRequest.request_token == request_token).first()
    if not req:
        return False

    now = utc_now()
    req.status = IncomingRequestStatus.CANCELLED
    req.updated_at = now

    # Release reservations
    active_reservations = (
        db.query(HospitalCapacityReservation)
        .filter(
            HospitalCapacityReservation.facility_id == req.facility_id,
            HospitalCapacityReservation.incident_id == req.incident_id,
            HospitalCapacityReservation.status == "active",
        )
        .all()
    )
    for res in active_reservations:
        release_capacity_reservation(db, res.reservation_token, reason="request_cancelled", user=user)

    db.commit()

    facility = req.facility
    payload = {
        "request_token": req.request_token,
        "facility_id": req.facility_id,
        "incident_id": req.incident_id,
        "status": IncomingRequestStatus.CANCELLED,
        "reason": reason,
        "cancelled_at": now.isoformat(),
    }
    record_and_publish_event(
        db=db,
        event_type="hospital.incoming_patient_cancelled",
        channel=get_incident_channel(req.incident_id),
        payload=payload,
        actor_id=user.id if user else None,
        incident_id=req.incident_id,
        organization_id=facility.organization_id if facility else None,
    )
    db.commit()

    return True


def sweep_incoming_request_timeouts(db: Session) -> List[IncomingPatientRequest]:
    """
    Sweeps requests that exceeded acknowledgement deadline without a response.
    Marks status EXPIRED and alerts dispatchers without silent destination change.
    """
    now = utc_now()
    timed_out = (
        db.query(IncomingPatientRequest)
        .filter(
            IncomingPatientRequest.status.in_([IncomingRequestStatus.PENDING, IncomingRequestStatus.ACKNOWLEDGED]),
            IncomingPatientRequest.acknowledgement_deadline <= now,
        )
        .all()
    )

    reconciled: List[IncomingPatientRequest] = []
    for req in timed_out:
        req.status = IncomingRequestStatus.EXPIRED
        req.updated_at = now
        facility = req.facility

        payload = {
            "request_token": req.request_token,
            "facility_id": req.facility_id,
            "facility_name": facility.name if facility else "",
            "incident_id": req.incident_id,
            "status": IncomingRequestStatus.EXPIRED,
            "expired_at": now.isoformat(),
            "alert": "Hospital response timed out; dispatcher action required",
        }

        record_and_publish_event(
            db=db,
            event_type="hospital.response_timeout",
            channel=get_incident_channel(req.incident_id),
            payload=payload,
            incident_id=req.incident_id,
            organization_id=facility.organization_id if facility else None,
        )
        record_and_publish_event(
            db=db,
            event_type="hospital.response_timeout",
            channel=get_global_channel(),
            payload=payload,
            incident_id=req.incident_id,
            organization_id=facility.organization_id if facility else None,
        )
        reconciled.append(req)

    if reconciled:
        db.commit()

    return reconciled
