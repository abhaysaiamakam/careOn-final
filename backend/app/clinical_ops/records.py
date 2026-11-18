"""
CareOn Milestone 8 — Pre-Hospital Clinical Records & Deterministic Summary Generator.

Features:
- Structured Initial Assessment (Airway, Breathing, Circulation, Consciousness/AVPU).
- Vital signs recording with physiological range validations and original source preservation.
- Life-saving pre-hospital interventions and medication administrations.
- Chronological timeline provenance tracking.
- Deterministic Clinical Summary Generator (STRICTLY NON-GENERATIVE: synthesizes only recorded facts).
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from app.models import (
    EmergencyEncounter,
    ClinicalAssessment,
    VitalSignObservation,
    PreHospitalIntervention,
    MedicationAdministration,
    ClinicalTimelineEvent,
    User,
    utc_now,
)
from app.realtime.event_models import (
    EventTypes,
    get_incident_channel,
)
from app.realtime.event_publisher import record_and_publish_event

logger = logging.getLogger("careon.clinical_ops.records")


class ClinicalValidationError(ValueError):
    """Raised when vital signs or clinical measurements violate physiological bounds."""
    pass


def record_clinical_assessment(
    db: Session,
    encounter_id: int,
    responder: User,
    consciousness_level: str = "Alert",
    airway_status: str = "clear",
    breathing_status: str = "normal",
    circulation_status: str = "normal_pulses",
    presenting_complaints: Optional[str] = None,
    observed_injuries: Optional[str] = None,
    symptoms: Optional[str] = None,
    clinical_notes: Optional[str] = None,
    assessed_at: Optional[datetime] = None,
) -> ClinicalAssessment:
    """Records an initial primary/secondary physical and neurological assessment."""
    encounter = db.query(EmergencyEncounter).filter(EmergencyEncounter.id == encounter_id).first()
    if not encounter:
        raise ValueError(f"Encounter {encounter_id} not found")

    now = utc_now()
    event_time = assessed_at or now

    assessment = ClinicalAssessment(
        encounter_id=encounter.id,
        responder_id=responder.id,
        assessed_at=event_time,
        consciousness_level=consciousness_level,
        airway_status=airway_status,
        breathing_status=breathing_status,
        circulation_status=circulation_status,
        presenting_complaints=presenting_complaints,
        observed_injuries=observed_injuries,
        symptoms=symptoms,
        clinical_notes=clinical_notes,
        created_at=now,
    )
    db.add(assessment)

    # Log to chronological timeline
    timeline_event = ClinicalTimelineEvent(
        event_token=str(uuid.uuid4()),
        encounter_id=encounter.id,
        event_type="assessment_recorded",
        event_timestamp=event_time,
        server_receipt_timestamp=now,
        actor_id=responder.id,
        actor_role=responder.role,
        structured_data_json=json.dumps({
            "consciousness": consciousness_level,
            "airway": airway_status,
            "breathing": breathing_status,
            "circulation": circulation_status,
        }),
        source_application="careon_responder",
        created_at=now,
    )
    db.add(timeline_event)
    db.commit()
    db.refresh(assessment)

    # Outbox notification
    record_and_publish_event(
        db=db,
        event_type="patient.assessment_updated",
        channel=get_incident_channel(encounter.incident_id),
        payload={"encounter_id": encounter.id, "assessment_id": assessment.id},
        actor_id=responder.id,
        incident_id=encounter.incident_id,
    )
    db.commit()

    return assessment


def record_vital_signs(
    db: Session,
    encounter_id: int,
    user: User,
    heart_rate: Optional[int] = None,
    systolic_bp: Optional[int] = None,
    diastolic_bp: Optional[int] = None,
    respiratory_rate: Optional[int] = None,
    oxygen_saturation: Optional[float] = None,
    body_temperature: Optional[float] = None,
    blood_glucose: Optional[float] = None,
    gcs_eye: Optional[int] = None,
    gcs_verbal: Optional[int] = None,
    gcs_motor: Optional[int] = None,
    measurement_source: str = "manual",
    observed_at: Optional[datetime] = None,
) -> VitalSignObservation:
    """
    Records a vital sign observation set with physiological range checks.
    Allows partial observations without fabricating missing values.
    """
    encounter = db.query(EmergencyEncounter).filter(EmergencyEncounter.id == encounter_id).first()
    if not encounter:
        raise ValueError(f"Encounter {encounter_id} not found")

    # Range validations
    if heart_rate is not None and not (0 <= heart_rate <= 300):
        raise ClinicalValidationError(f"Heart rate {heart_rate} bpm is outside physiological bounds (0-300)")
    if systolic_bp is not None and not (0 <= systolic_bp <= 300):
        raise ClinicalValidationError(f"Systolic BP {systolic_bp} mmHg is outside physiological bounds (0-300)")
    if diastolic_bp is not None and not (0 <= diastolic_bp <= 200):
        raise ClinicalValidationError(f"Diastolic BP {diastolic_bp} mmHg is outside physiological bounds (0-200)")
    if respiratory_rate is not None and not (0 <= respiratory_rate <= 100):
        raise ClinicalValidationError(f"Respiratory rate {respiratory_rate} is outside physiological bounds (0-100)")
    if oxygen_saturation is not None and not (0.0 <= oxygen_saturation <= 100.0):
        raise ClinicalValidationError(f"Oxygen saturation {oxygen_saturation}% is invalid (0-100)")
    if body_temperature is not None and not (20.0 <= body_temperature <= 45.0):
        raise ClinicalValidationError(f"Body temperature {body_temperature}°C is outside physiological bounds (20-45)")
    if blood_glucose is not None and not (0.0 <= blood_glucose <= 1500.0):
        raise ClinicalValidationError(f"Blood glucose {blood_glucose} mg/dL is outside bounds (0-1500)")

    # GCS computation
    gcs_total = None
    if gcs_eye is not None or gcs_verbal is not None or gcs_motor is not None:
        eye = gcs_eye or 1
        verbal = gcs_verbal or 1
        motor = gcs_motor or 1
        gcs_total = eye + verbal + motor

    now = utc_now()
    event_time = observed_at or now

    vitals = VitalSignObservation(
        encounter_id=encounter.id,
        recorded_by_user_id=user.id,
        observed_at=event_time,
        heart_rate=heart_rate,
        systolic_bp=systolic_bp,
        diastolic_bp=diastolic_bp,
        respiratory_rate=respiratory_rate,
        oxygen_saturation=oxygen_saturation,
        body_temperature=body_temperature,
        blood_glucose=blood_glucose,
        gcs_eye=gcs_eye,
        gcs_verbal=gcs_verbal,
        gcs_motor=gcs_motor,
        gcs_total=gcs_total,
        measurement_source=measurement_source,
        data_quality="verified",
        created_at=now,
    )
    db.add(vitals)

    # Timeline event
    timeline_event = ClinicalTimelineEvent(
        event_token=str(uuid.uuid4()),
        encounter_id=encounter.id,
        event_type="vitals_recorded",
        event_timestamp=event_time,
        server_receipt_timestamp=now,
        actor_id=user.id,
        actor_role=user.role,
        structured_data_json=json.dumps({
            "hr": heart_rate,
            "bp": f"{systolic_bp}/{diastolic_bp}" if systolic_bp and diastolic_bp else None,
            "spo2": oxygen_saturation,
            "rr": respiratory_rate,
            "gcs": gcs_total,
        }),
        source_application="careon_responder",
        created_at=now,
    )
    db.add(timeline_event)
    db.commit()
    db.refresh(vitals)

    # Outbox event
    record_and_publish_event(
        db=db,
        event_type="patient.vitals_recorded",
        channel=get_incident_channel(encounter.incident_id),
        payload={"encounter_id": encounter.id, "vitals_id": vitals.id},
        actor_id=user.id,
        incident_id=encounter.incident_id,
    )
    db.commit()

    return vitals


def record_prehospital_intervention(
    db: Session,
    encounter_id: int,
    performer: User,
    intervention_type: str,
    parameters_json: Optional[Dict[str, Any]] = None,
    patient_response: str = "unchanged",
    notes: Optional[str] = None,
    performed_at: Optional[datetime] = None,
) -> PreHospitalIntervention:
    """Records a pre-hospital procedure or intervention."""
    encounter = db.query(EmergencyEncounter).filter(EmergencyEncounter.id == encounter_id).first()
    if not encounter:
        raise ValueError(f"Encounter {encounter_id} not found")

    now = utc_now()
    event_time = performed_at or now

    intervention = PreHospitalIntervention(
        encounter_id=encounter.id,
        performer_id=performer.id,
        intervention_type=intervention_type.lower().strip(),
        parameters_json=json.dumps(parameters_json) if parameters_json else None,
        patient_response=patient_response,
        notes=notes,
        performed_at=event_time,
        created_at=now,
    )
    db.add(intervention)

    timeline_event = ClinicalTimelineEvent(
        event_token=str(uuid.uuid4()),
        encounter_id=encounter.id,
        event_type="intervention_performed",
        event_timestamp=event_time,
        server_receipt_timestamp=now,
        actor_id=performer.id,
        actor_role=performer.role,
        structured_data_json=json.dumps({
            "intervention": intervention_type,
            "response": patient_response,
        }),
        source_application="careon_responder",
        created_at=now,
    )
    db.add(timeline_event)
    db.commit()
    db.refresh(intervention)

    record_and_publish_event(
        db=db,
        event_type="patient.intervention_recorded",
        channel=get_incident_channel(encounter.incident_id),
        payload={"encounter_id": encounter.id, "intervention_type": intervention_type},
        actor_id=performer.id,
        incident_id=encounter.incident_id,
    )
    db.commit()

    return intervention


def record_medication_administration(
    db: Session,
    encounter_id: int,
    administering_user: User,
    medication_name: str,
    dose: float,
    unit: str,
    route: str,
    response_notes: Optional[str] = None,
    verification_status: str = "administered",
    administered_at: Optional[datetime] = None,
) -> MedicationAdministration:
    """Records an administered medication (audit only; no automated prescribing)."""
    encounter = db.query(EmergencyEncounter).filter(EmergencyEncounter.id == encounter_id).first()
    if not encounter:
        raise ValueError(f"Encounter {encounter_id} not found")

    if dose <= 0:
        raise ClinicalValidationError("Medication dose must be strictly positive")

    now = utc_now()
    event_time = administered_at or now

    med = MedicationAdministration(
        encounter_id=encounter.id,
        administering_user_id=administering_user.id,
        medication_name=medication_name.strip(),
        dose=dose,
        unit=unit.strip(),
        route=route.strip().upper(),
        response_notes=response_notes,
        verification_status=verification_status,
        administered_at=event_time,
        created_at=now,
    )
    db.add(med)

    timeline_event = ClinicalTimelineEvent(
        event_token=str(uuid.uuid4()),
        encounter_id=encounter.id,
        event_type="medication_administered",
        event_timestamp=event_time,
        server_receipt_timestamp=now,
        actor_id=administering_user.id,
        actor_role=administering_user.role,
        structured_data_json=json.dumps({
            "medication": medication_name,
            "dose": f"{dose} {unit}",
            "route": route,
        }),
        source_application="careon_responder",
        created_at=now,
    )
    db.add(timeline_event)
    db.commit()
    db.refresh(med)

    return med


def generate_deterministic_clinical_summary(db: Session, encounter_id: int) -> Dict[str, Any]:
    """
    Synthesizes a structured clinical summary purely from recorded factual observations.
    NEVER hallucinates diagnoses, clinical opinions, or unrecorded treatments.
    """
    encounter = db.query(EmergencyEncounter).filter(EmergencyEncounter.id == encounter_id).first()
    if not encounter:
        raise ValueError(f"Encounter {encounter_id} not found")

    patient = encounter.patient
    incident = encounter.incident

    # Latest assessment
    latest_assessment = (
        db.query(ClinicalAssessment)
        .filter(ClinicalAssessment.encounter_id == encounter_id)
        .order_by(ClinicalAssessment.assessed_at.desc())
        .first()
    )

    # Vitals history (chronological)
    vitals_records = (
        db.query(VitalSignObservation)
        .filter(VitalSignObservation.encounter_id == encounter_id)
        .order_by(VitalSignObservation.observed_at.asc())
        .all()
    )

    # Interventions performed
    interventions = (
        db.query(PreHospitalIntervention)
        .filter(PreHospitalIntervention.encounter_id == encounter_id)
        .order_by(PreHospitalIntervention.performed_at.asc())
        .all()
    )

    # Medications administered
    meds = (
        db.query(MedicationAdministration)
        .filter(MedicationAdministration.encounter_id == encounter_id)
        .order_by(MedicationAdministration.administered_at.asc())
        .all()
    )

    # Missing information checklist
    missing_info: List[str] = []
    if not patient or patient.identity_status == "unknown":
        missing_info.append("Patient legal identity unverified (provisional tracking active).")
    if not patient or not patient.blood_group:
        missing_info.append("Blood group unknown.")
    if not patient or not patient.known_allergies:
        missing_info.append("Allergies not recorded / unverified.")
    if not vitals_records:
        missing_info.append("No vital signs recorded during pre-hospital phase.")
    if not latest_assessment:
        missing_info.append("Initial clinical assessment incomplete.")

    vitals_summary = []
    for v in vitals_records:
        vitals_summary.append({
            "timestamp": v.observed_at.isoformat(),
            "heart_rate_bpm": v.heart_rate,
            "bp_systolic_diastolic": f"{v.systolic_bp}/{v.diastolic_bp}" if v.systolic_bp and v.diastolic_bp else None,
            "respiratory_rate": v.respiratory_rate,
            "spo2_percent": v.oxygen_saturation,
            "temp_celsius": v.body_temperature,
            "glucose_mg_dl": v.blood_glucose,
            "gcs_total": v.gcs_total,
            "source": v.measurement_source,
        })

    interventions_summary = [
        {
            "intervention": i.intervention_type,
            "performed_at": i.performed_at.isoformat(),
            "response": i.patient_response,
            "notes": i.notes,
        }
        for i in interventions
    ]

    meds_summary = [
        {
            "medication": m.medication_name,
            "dose": f"{m.dose} {m.unit}",
            "route": m.route,
            "administered_at": m.administered_at.isoformat(),
            "verification": m.verification_status,
        }
        for m in meds
    ]

    return {
        "encounter_code": encounter.encounter_code,
        "incident_code": incident.incident_code if incident else None,
        "chief_complaint": encounter.chief_complaint,
        "initial_acuity": encounter.initial_acuity,
        "patient": {
            "identifier": patient.patient_identifier if patient else "UNKNOWN",
            "full_name": patient.full_name if patient else "Unidentified Patient",
            "identity_status": patient.identity_status if patient else "unknown",
            "estimated_age": patient.estimated_age if patient else None,
            "gender": patient.gender if patient else "unknown",
            "blood_group": patient.blood_group if patient else "unknown",
            "known_allergies": patient.known_allergies if patient else "None recorded",
            "medical_history": patient.known_medical_conditions if patient else "None recorded",
            "verification_status": patient.history_verification_status if patient else "unknown",
        },
        "assessment": {
            "consciousness": latest_assessment.consciousness_level if latest_assessment else "Not assessed",
            "airway": latest_assessment.airway_status if latest_assessment else "Not assessed",
            "breathing": latest_assessment.breathing_status if latest_assessment else "Not assessed",
            "circulation": latest_assessment.circulation_status if latest_assessment else "Not assessed",
            "observed_injuries": latest_assessment.observed_injuries if latest_assessment else None,
            "symptoms": latest_assessment.symptoms if latest_assessment else None,
            "clinical_notes": latest_assessment.clinical_notes if latest_assessment else None,
        },
        "vital_signs_timeline": vitals_summary,
        "interventions_performed": interventions_summary,
        "medications_administered": meds_summary,
        "missing_information_flags": missing_info,
        "generated_at": utc_now().isoformat(),
        "synthesis_mode": "deterministic_factual_only",
    }
