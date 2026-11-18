"""
CareOn Milestone 8 — Patient Identity & Emergency Encounter Manager.

Features:
- Distinguishes Patient from Incident and Encounter (one incident can involve multiple patients).
- Unknown patient handling (generates provisional IDs like PROV-PAT-XXXX).
- Identity verification and reconciliation without automated erroneous merging.
- Encounter lifecycle linking M5 incidents, M6 missions/assignments, and M7 receiving hospitals.
- Strict clinical privacy enforcement: Citizens tracking an incident cannot view internal clinical encounters.
"""

import logging
import uuid
from datetime import datetime, timezone, date
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from app.models import (
    Patient,
    EmergencyEncounter,
    ClinicalTimelineEvent,
    Incident,
    Assignment,
    HospitalFacility,
    User,
    utc_now,
)
from app.realtime.event_models import (
    EventTypes,
    get_incident_channel,
    get_org_channel,
)
from app.realtime.event_publisher import record_and_publish_event

logger = logging.getLogger("careon.clinical_ops.encounters")


class IdentityStatus:
    UNKNOWN = "unknown"
    PROVISIONAL = "provisional"
    VERIFIED = "verified"


class EncounterStatus:
    ACTIVE = "active"
    IN_TRANSPORT = "in_transport"
    HANDED_OVER = "handed_over"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


def create_or_register_patient(
    db: Session,
    full_name: Optional[str] = None,
    identity_status: str = IdentityStatus.UNKNOWN,
    date_of_birth: Optional[date] = None,
    estimated_age: Optional[int] = None,
    gender: str = "unknown",
    contact_phone: Optional[str] = None,
    emergency_contact_name: Optional[str] = None,
    emergency_contact_phone: Optional[str] = None,
    blood_group: Optional[str] = None,
    known_allergies: Optional[str] = None,
    known_medical_conditions: Optional[str] = None,
    current_medications: Optional[str] = None,
    history_verification_status: str = "unknown",
) -> Patient:
    """Creates a patient record. Uses provisional identifier if identity is unknown."""
    unique_suffix = uuid.uuid4().hex[:8].upper()
    prefix = "PAT" if identity_status == IdentityStatus.VERIFIED else "PROV-PAT"
    patient_identifier = f"{prefix}-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{unique_suffix}"

    now = utc_now()
    patient = Patient(
        patient_identifier=patient_identifier,
        full_name=full_name,
        identity_status=identity_status,
        date_of_birth=date_of_birth,
        estimated_age=estimated_age,
        gender=gender.lower(),
        contact_phone=contact_phone,
        emergency_contact_name=emergency_contact_name,
        emergency_contact_phone=emergency_contact_phone,
        blood_group=blood_group,
        known_allergies=known_allergies,
        known_medical_conditions=known_medical_conditions,
        current_medications=current_medications,
        history_verification_status=history_verification_status,
        created_at=now,
        updated_at=now,
    )
    db.add(patient)
    db.commit()
    db.refresh(patient)
    return patient


def update_patient_identity(
    db: Session,
    patient_id: int,
    full_name: Optional[str] = None,
    identity_status: Optional[str] = None,
    date_of_birth: Optional[date] = None,
    estimated_age: Optional[int] = None,
    gender: Optional[str] = None,
    contact_phone: Optional[str] = None,
    emergency_contact_name: Optional[str] = None,
    emergency_contact_phone: Optional[str] = None,
    blood_group: Optional[str] = None,
    known_allergies: Optional[str] = None,
    known_medical_conditions: Optional[str] = None,
    current_medications: Optional[str] = None,
    history_verification_status: Optional[str] = None,
    reconciled_by: Optional[User] = None,
) -> Patient:
    """Updates and reconciles patient identity and medical history."""
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise ValueError(f"Patient {patient_id} not found")

    if full_name is not None:
        patient.full_name = full_name
    if identity_status is not None:
        patient.identity_status = identity_status
    if date_of_birth is not None:
        patient.date_of_birth = date_of_birth
    if estimated_age is not None:
        patient.estimated_age = estimated_age
    if gender is not None:
        patient.gender = gender.lower()
    if contact_phone is not None:
        patient.contact_phone = contact_phone
    if emergency_contact_name is not None:
        patient.emergency_contact_name = emergency_contact_name
    if emergency_contact_phone is not None:
        patient.emergency_contact_phone = emergency_contact_phone
    if blood_group is not None:
        patient.blood_group = blood_group
    if known_allergies is not None:
        patient.known_allergies = known_allergies
    if known_medical_conditions is not None:
        patient.known_medical_conditions = known_medical_conditions
    if current_medications is not None:
        patient.current_medications = current_medications
    if history_verification_status is not None:
        patient.history_verification_status = history_verification_status

    patient.updated_at = utc_now()
    db.commit()
    db.refresh(patient)
    return patient


def create_emergency_encounter(
    db: Session,
    incident_id: int,
    chief_complaint: str,
    patient_id: Optional[int] = None,
    assignment_id: Optional[int] = None,
    assigned_responder_id: Optional[int] = None,
    receiving_facility_id: Optional[int] = None,
    initial_acuity: str = "High",
    actor: Optional[User] = None,
) -> EmergencyEncounter:
    """
    Initializes an emergency clinical encounter for an incident.
    If patient_id is omitted, auto-registers an unknown/provisional patient.
    """
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise ValueError(f"Incident {incident_id} not found")

    if not patient_id:
        patient = create_or_register_patient(db, identity_status=IdentityStatus.UNKNOWN)
        patient_id = patient.id

    encounter_code = f"ENC-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
    now = utc_now()

    encounter = EmergencyEncounter(
        encounter_code=encounter_code,
        patient_id=patient_id,
        incident_id=incident_id,
        assignment_id=assignment_id,
        assigned_responder_id=assigned_responder_id,
        receiving_facility_id=receiving_facility_id,
        status=EncounterStatus.ACTIVE,
        chief_complaint=chief_complaint,
        initial_acuity=initial_acuity,
        started_at=now,
        created_at=now,
        updated_at=now,
    )
    db.add(encounter)
    db.commit()
    db.refresh(encounter)

    # Record initial timeline event
    timeline_event = ClinicalTimelineEvent(
        event_token=str(uuid.uuid4()),
        encounter_id=encounter.id,
        event_type="encounter_created",
        event_timestamp=now,
        server_receipt_timestamp=now,
        actor_id=actor.id if actor else None,
        actor_role=actor.role if actor else "System",
        structured_data_json=f'{{"chief_complaint": "{chief_complaint}", "acuity": "{initial_acuity}"}}',
        source_application="careon_backend",
        created_at=now,
    )
    db.add(timeline_event)

    # Publish real-time event to incident channel
    payload = {
        "encounter_id": encounter.id,
        "encounter_code": encounter.encounter_code,
        "incident_id": incident.id,
        "incident_code": incident.incident_code,
        "status": encounter.status,
        "initial_acuity": encounter.initial_acuity,
        "created_at": now.isoformat(),
    }
    record_and_publish_event(
        db=db,
        event_type="patient.encounter_created",
        channel=get_incident_channel(incident.id),
        payload=payload,
        actor_id=actor.id if actor else None,
        incident_id=incident.id,
    )
    db.commit()

    return encounter


def transition_encounter_status(
    db: Session,
    encounter_id: int,
    new_status: str,
    receiving_facility_id: Optional[int] = None,
    actor: Optional[User] = None,
    notes: Optional[str] = None,
) -> EmergencyEncounter:
    """Updates encounter status and logs a chronological clinical timeline event."""
    encounter = db.query(EmergencyEncounter).filter(EmergencyEncounter.id == encounter_id).first()
    if not encounter:
        raise ValueError(f"Encounter {encounter_id} not found")

    norm_status = new_status.lower().strip()
    valid_statuses = (
        EncounterStatus.ACTIVE,
        EncounterStatus.IN_TRANSPORT,
        EncounterStatus.HANDED_OVER,
        EncounterStatus.COMPLETED,
        EncounterStatus.CANCELLED,
    )
    if norm_status not in valid_statuses:
        raise ValueError(f"Invalid encounter status '{new_status}'. Allowed: {valid_statuses}")

    encounter.status = norm_status
    if receiving_facility_id:
        encounter.receiving_facility_id = receiving_facility_id

    now = utc_now()
    if norm_status in (EncounterStatus.COMPLETED, EncounterStatus.HANDED_OVER):
        encounter.ended_at = now
    encounter.updated_at = now

    # Record timeline event
    timeline_event = ClinicalTimelineEvent(
        event_token=str(uuid.uuid4()),
        encounter_id=encounter.id,
        event_type=f"encounter_{norm_status}",
        event_timestamp=now,
        server_receipt_timestamp=now,
        actor_id=actor.id if actor else None,
        actor_role=actor.role if actor else "System",
        structured_data_json=f'{{"status": "{norm_status}", "notes": "{notes or ""}"}}',
        source_application="careon_backend",
        created_at=now,
    )
    db.add(timeline_event)
    db.commit()
    db.refresh(encounter)

    # Publish real-time event
    payload = {
        "encounter_id": encounter.id,
        "encounter_code": encounter.encounter_code,
        "incident_id": encounter.incident_id,
        "status": norm_status,
        "updated_at": now.isoformat(),
    }
    record_and_publish_event(
        db=db,
        event_type=f"patient.{norm_status}",
        channel=get_incident_channel(encounter.incident_id),
        payload=payload,
        actor_id=actor.id if actor else None,
        incident_id=encounter.incident_id,
    )
    db.commit()

    return encounter
