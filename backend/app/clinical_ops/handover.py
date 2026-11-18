"""
CareOn Milestone 8 — Digital Handover State Machine & Transfer of Care Protocol.

Manages the formal transfer-of-care document lifecycle:
DRAFT -> READY_FOR_HANDOVER -> SUBMITTED -> RECEIVED -> ACKNOWLEDGED -> COMPLETED.
Handles:
- Versioning & immutable audit tracking (corrections append new versions)
- Dual-party sign-off (Sending Responder -> Receiving Hospital Staff)
- Clarification requests and discrepancy handling
- Integration with M6 responder missions and M7 hospital capacity reservations
- Transactional outbox event dissemination
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set
from sqlalchemy.orm import Session

from app.models import (
    DigitalHandoverRecord,
    EmergencyEncounter,
    HospitalFacility,
    HospitalCapacityReservation,
    Assignment,
    ClinicalTimelineEvent,
    User,
    utc_now,
)
from app.realtime.event_models import (
    EventTypes,
    get_incident_channel,
    get_org_channel,
    get_responder_channel,
)
from app.realtime.event_publisher import record_and_publish_event
from app.clinical_ops.records import generate_deterministic_clinical_summary
from app.hospital_ops.capacity import release_capacity_reservation

logger = logging.getLogger("careon.clinical_ops.handover")


class HandoverStatus:
    DRAFT = "draft"
    READY_FOR_HANDOVER = "ready_for_handover"
    SUBMITTED = "submitted"
    RECEIVED = "received"
    ACKNOWLEDGED = "acknowledged"
    CLARIFICATION_REQUESTED = "clarification_requested"
    CORRECTION_REQUIRED = "correction_required"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


VALID_HANDOVER_TRANSITIONS: Dict[str, Set[str]] = {
    HandoverStatus.DRAFT: {
        HandoverStatus.READY_FOR_HANDOVER,
        HandoverStatus.SUBMITTED,
        HandoverStatus.CANCELLED,
    },
    HandoverStatus.READY_FOR_HANDOVER: {
        HandoverStatus.SUBMITTED,
        HandoverStatus.DRAFT,
        HandoverStatus.CANCELLED,
    },
    HandoverStatus.SUBMITTED: {
        HandoverStatus.RECEIVED,
        HandoverStatus.CLARIFICATION_REQUESTED,
        HandoverStatus.CORRECTION_REQUIRED,
        HandoverStatus.CANCELLED,
    },
    HandoverStatus.RECEIVED: {
        HandoverStatus.ACKNOWLEDGED,
        HandoverStatus.CLARIFICATION_REQUESTED,
        HandoverStatus.CORRECTION_REQUIRED,
        HandoverStatus.CANCELLED,
    },
    HandoverStatus.ACKNOWLEDGED: {
        HandoverStatus.COMPLETED,
        HandoverStatus.CORRECTION_REQUIRED,
        HandoverStatus.CANCELLED,
    },
    HandoverStatus.CLARIFICATION_REQUESTED: {
        HandoverStatus.SUBMITTED,
        HandoverStatus.CORRECTION_REQUIRED,
        HandoverStatus.CANCELLED,
    },
    HandoverStatus.CORRECTION_REQUIRED: {
        HandoverStatus.CANCELLED,
    },
    HandoverStatus.COMPLETED: set(),  # Terminal
    HandoverStatus.CANCELLED: set(),  # Terminal
}


class HandoverStateError(ValueError):
    """Raised when an invalid state transition is requested."""
    pass


def create_handover_draft(
    db: Session,
    encounter_id: int,
    facility_id: int,
    sending_responder: User,
    receiving_department: Optional[str] = "Emergency Department",
    outstanding_clinical_concerns: Optional[str] = None,
) -> DigitalHandoverRecord:
    """Creates a new digital handover document in DRAFT state."""
    encounter = db.query(EmergencyEncounter).filter(EmergencyEncounter.id == encounter_id).first()
    if not encounter:
        raise ValueError(f"Encounter {encounter_id} not found")

    facility = db.query(HospitalFacility).filter(HospitalFacility.id == facility_id).first()
    if not facility:
        raise ValueError(f"Hospital facility {facility_id} not found")

    now = utc_now()
    summary = generate_deterministic_clinical_summary(db, encounter.id)

    handover = DigitalHandoverRecord(
        handover_token=str(uuid.uuid4()),
        encounter_id=encounter.id,
        facility_id=facility.id,
        version=1,
        status=HandoverStatus.DRAFT,
        sending_responder_id=sending_responder.id,
        receiving_department=receiving_department,
        clinical_summary_json=json.dumps(summary),
        outstanding_clinical_concerns=outstanding_clinical_concerns,
        is_final=False,
        created_at=now,
        updated_at=now,
    )
    db.add(handover)
    db.commit()
    db.refresh(handover)
    return handover


def submit_handover_document(
    db: Session,
    handover_token: str,
    sending_responder: User,
    receiving_department: Optional[str] = None,
    outstanding_clinical_concerns: Optional[str] = None,
) -> DigitalHandoverRecord:
    """Submits the digital handover document to the receiving hospital."""
    handover = (
        db.query(DigitalHandoverRecord)
        .filter(DigitalHandoverRecord.handover_token == handover_token)
        .first()
    )
    if not handover:
        raise ValueError("Handover document not found")

    allowed = VALID_HANDOVER_TRANSITIONS.get(handover.status, set())
    if HandoverStatus.SUBMITTED not in allowed:
        raise HandoverStateError(f"Cannot submit handover in '{handover.status}' status")

    now = utc_now()
    # Regenerate latest factual clinical summary
    summary = generate_deterministic_clinical_summary(db, handover.encounter_id)

    handover.status = HandoverStatus.SUBMITTED
    handover.submitted_at = now
    handover.sending_responder_id = sending_responder.id
    if receiving_department:
        handover.receiving_department = receiving_department
    if outstanding_clinical_concerns:
        handover.outstanding_clinical_concerns = outstanding_clinical_concerns
    handover.clinical_summary_json = json.dumps(summary)
    handover.updated_at = now

    # Record timeline event
    timeline_event = ClinicalTimelineEvent(
        event_token=str(uuid.uuid4()),
        encounter_id=handover.encounter_id,
        event_type="handover_submitted",
        event_timestamp=now,
        server_receipt_timestamp=now,
        actor_id=sending_responder.id,
        actor_role=sending_responder.role,
        structured_data_json=json.dumps({
            "handover_token": handover.handover_token,
            "version": handover.version,
            "facility_id": handover.facility_id,
        }),
        source_application="careon_responder",
        created_at=now,
    )
    db.add(timeline_event)
    db.commit()
    db.refresh(handover)

    # Broadcast event to receiving hospital organization channel
    facility = handover.facility
    payload = {
        "handover_token": handover.handover_token,
        "encounter_id": handover.encounter_id,
        "facility_id": handover.facility_id,
        "facility_name": facility.name if facility else "",
        "version": handover.version,
        "status": HandoverStatus.SUBMITTED,
        "submitted_at": now.isoformat(),
    }
    if facility and facility.organization_id:
        record_and_publish_event(
            db=db,
            event_type="handover.document_submitted",
            channel=get_org_channel(facility.organization_id),
            payload=payload,
            actor_id=sending_responder.id,
            organization_id=facility.organization_id,
        )
        db.commit()

    return handover


def receive_handover_document(
    db: Session,
    handover_token: str,
    receiving_staff: User,
) -> DigitalHandoverRecord:
    """Hospital triage staff marks the digital handover document as received for review."""
    handover = (
        db.query(DigitalHandoverRecord)
        .filter(DigitalHandoverRecord.handover_token == handover_token)
        .first()
    )
    if not handover:
        raise ValueError("Handover document not found")

    if handover.status == HandoverStatus.RECEIVED:
        return handover  # Idempotent replay

    allowed = VALID_HANDOVER_TRANSITIONS.get(handover.status, set())
    if HandoverStatus.RECEIVED not in allowed:
        raise HandoverStateError(f"Cannot receive handover in '{handover.status}' status")

    now = utc_now()
    handover.status = HandoverStatus.RECEIVED
    handover.receiving_staff_id = receiving_staff.id
    handover.received_at = now
    handover.updated_at = now
    db.commit()

    facility = handover.facility
    payload = {
        "handover_token": handover.handover_token,
        "encounter_id": handover.encounter_id,
        "status": HandoverStatus.RECEIVED,
        "receiving_staff": receiving_staff.name,
        "received_at": now.isoformat(),
    }
    if facility and facility.organization_id:
        record_and_publish_event(
            db=db,
            event_type="handover.received",
            channel=get_org_channel(facility.organization_id),
            payload=payload,
            actor_id=receiving_staff.id,
            organization_id=facility.organization_id,
        )
        db.commit()

    return handover


def acknowledge_handover_document(
    db: Session,
    handover_token: str,
    receiving_staff: User,
) -> DigitalHandoverRecord:
    """Receiving hospital physician/nurse acknowledges clinical receipt of patient."""
    handover = (
        db.query(DigitalHandoverRecord)
        .filter(DigitalHandoverRecord.handover_token == handover_token)
        .first()
    )
    if not handover:
        raise ValueError("Handover document not found")

    if handover.status == HandoverStatus.ACKNOWLEDGED:
        return handover  # Idempotent replay

    allowed = VALID_HANDOVER_TRANSITIONS.get(handover.status, set())
    if HandoverStatus.ACKNOWLEDGED not in allowed:
        raise HandoverStateError(f"Cannot acknowledge handover in '{handover.status}' status")

    now = utc_now()
    handover.status = HandoverStatus.ACKNOWLEDGED
    handover.receiving_staff_id = receiving_staff.id
    handover.acknowledged_at = now
    handover.updated_at = now
    db.commit()

    facility = handover.facility
    payload = {
        "handover_token": handover.handover_token,
        "encounter_id": handover.encounter_id,
        "status": HandoverStatus.ACKNOWLEDGED,
        "receiving_staff": receiving_staff.name,
        "acknowledged_at": now.isoformat(),
    }
    if facility and facility.organization_id:
        record_and_publish_event(
            db=db,
            event_type="handover.acknowledged",
            channel=get_org_channel(facility.organization_id),
            payload=payload,
            actor_id=receiving_staff.id,
            organization_id=facility.organization_id,
        )
        db.commit()

    return handover


def complete_transfer_of_care(
    db: Session,
    handover_token: str,
    receiving_staff: User,
) -> DigitalHandoverRecord:
    """
    Finalizes the legal and clinical transfer of care.
    Locks document (is_final=True), updates Encounter status, and marks M7 capacity reservation fulfilled.
    """
    handover = (
        db.query(DigitalHandoverRecord)
        .filter(DigitalHandoverRecord.handover_token == handover_token)
        .first()
    )
    if not handover:
        raise ValueError("Handover document not found")

    if handover.status == HandoverStatus.COMPLETED:
        return handover  # Idempotent replay

    allowed = VALID_HANDOVER_TRANSITIONS.get(handover.status, set())
    if HandoverStatus.COMPLETED not in allowed:
        raise HandoverStateError(f"Cannot complete handover in '{handover.status}' status (must be acknowledged first)")

    now = utc_now()
    handover.status = HandoverStatus.COMPLETED
    handover.completed_at = now
    handover.is_final = True
    handover.updated_at = now

    # Update encounter status to handed_over
    encounter = handover.encounter
    if encounter:
        encounter.status = "handed_over"
        encounter.ended_at = now

    # Fulfill M7 capacity reservations associated with this encounter
    if encounter:
        active_reservations = (
            db.query(HospitalCapacityReservation)
            .filter(
                HospitalCapacityReservation.incident_id == encounter.incident_id,
                HospitalCapacityReservation.facility_id == handover.facility_id,
                HospitalCapacityReservation.status == "active",
            )
            .all()
        )
        for res in active_reservations:
            release_capacity_reservation(db, res.reservation_token, reason="fulfilled", user=receiving_staff)

    db.commit()

    # Timeline event
    timeline_event = ClinicalTimelineEvent(
        event_token=str(uuid.uuid4()),
        encounter_id=handover.encounter_id,
        event_type="transfer_of_care_completed",
        event_timestamp=now,
        server_receipt_timestamp=now,
        actor_id=receiving_staff.id,
        actor_role=receiving_staff.role,
        structured_data_json=json.dumps({
            "handover_token": handover.handover_token,
            "status": "completed",
        }),
        source_application="careon_hospital",
        created_at=now,
    )
    db.add(timeline_event)
    db.commit()

    # Real-time event
    facility = handover.facility
    payload = {
        "handover_token": handover.handover_token,
        "encounter_id": handover.encounter_id,
        "status": HandoverStatus.COMPLETED,
        "completed_by": receiving_staff.name,
        "completed_at": now.isoformat(),
    }
    if facility and facility.organization_id:
        record_and_publish_event(
            db=db,
            event_type="handover.completed",
            channel=get_org_channel(facility.organization_id),
            payload=payload,
            actor_id=receiving_staff.id,
            organization_id=facility.organization_id,
        )
        db.commit()

    return handover


def request_handover_clarification(
    db: Session,
    handover_token: str,
    hospital_staff: User,
    clarification_notes: str,
) -> DigitalHandoverRecord:
    """Hospital staff requests clarification regarding transfer information."""
    handover = (
        db.query(DigitalHandoverRecord)
        .filter(DigitalHandoverRecord.handover_token == handover_token)
        .first()
    )
    if not handover:
        raise ValueError("Handover document not found")

    if not clarification_notes or len(clarification_notes.strip()) < 3:
        raise ValueError("Clarification notes must be provided")

    now = utc_now()
    handover.status = HandoverStatus.CLARIFICATION_REQUESTED
    handover.clarification_notes = clarification_notes.strip()
    handover.updated_at = now
    db.commit()

    facility = handover.facility
    payload = {
        "handover_token": handover.handover_token,
        "encounter_id": handover.encounter_id,
        "status": HandoverStatus.CLARIFICATION_REQUESTED,
        "clarification_notes": clarification_notes,
        "requested_by": hospital_staff.name,
    }
    if facility and facility.organization_id:
        record_and_publish_event(
            db=db,
            event_type="handover.clarification_requested",
            channel=get_org_channel(facility.organization_id),
            payload=payload,
            actor_id=hospital_staff.id,
            organization_id=facility.organization_id,
        )
        db.commit()

    return handover


def submit_handover_correction(
    db: Session,
    handover_token: str,
    sending_responder: User,
    correction_reason: str,
    outstanding_clinical_concerns: Optional[str] = None,
) -> DigitalHandoverRecord:
    """
    Submits a correction to a previously submitted handover.
    Preserves the previous version as immutable and spawns a new version.
    """
    prior_handover = (
        db.query(DigitalHandoverRecord)
        .filter(DigitalHandoverRecord.handover_token == handover_token)
        .first()
    )
    if not prior_handover:
        raise ValueError("Prior handover document not found")

    if not correction_reason or len(correction_reason.strip()) < 3:
        raise ValueError("Mandatory correction reason required")

    now = utc_now()
    # Mark prior version as superseded / correction_required
    prior_handover.status = HandoverStatus.CORRECTION_REQUIRED
    prior_handover.correction_reason = correction_reason.strip()
    prior_handover.updated_at = now

    # Spawn new version
    summary = generate_deterministic_clinical_summary(db, prior_handover.encounter_id)
    new_version_record = DigitalHandoverRecord(
        handover_token=str(uuid.uuid4()),
        encounter_id=prior_handover.encounter_id,
        facility_id=prior_handover.facility_id,
        version=prior_handover.version + 1,
        previous_version_id=prior_handover.id,
        status=HandoverStatus.SUBMITTED,
        sending_responder_id=sending_responder.id,
        submitted_at=now,
        receiving_department=prior_handover.receiving_department,
        clinical_summary_json=json.dumps(summary),
        outstanding_clinical_concerns=outstanding_clinical_concerns or prior_handover.outstanding_clinical_concerns,
        correction_reason=correction_reason.strip(),
        is_final=False,
        created_at=now,
        updated_at=now,
    )
    db.add(new_version_record)
    db.commit()
    db.refresh(new_version_record)

    # Timeline event
    timeline_event = ClinicalTimelineEvent(
        event_token=str(uuid.uuid4()),
        encounter_id=new_version_record.encounter_id,
        event_type="handover_corrected",
        event_timestamp=now,
        server_receipt_timestamp=now,
        actor_id=sending_responder.id,
        actor_role=sending_responder.role,
        structured_data_json=json.dumps({
            "new_token": new_version_record.handover_token,
            "version": new_version_record.version,
            "reason": correction_reason,
        }),
        source_application="careon_responder",
        created_at=now,
    )
    db.add(timeline_event)
    db.commit()

    return new_version_record
