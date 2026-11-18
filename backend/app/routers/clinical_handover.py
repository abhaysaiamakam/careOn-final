"""
CareOn Milestone 8 — Digital Patient Handover & Clinical Information Continuity Router.

Endpoints:
- Patient Identity & Provisional Registration (/api/clinical/patients)
- Emergency Encounters (/api/clinical/encounters)
- Clinical Assessments, Vitals & Interventions (/api/clinical/encounters/{id}/...)
- Chronological Clinical Timeline (/api/clinical/encounters/{id}/timeline)
- Deterministic Clinical Summary (/api/clinical/encounters/{id}/summary)
- Digital Handover Document Lifecycle (/api/clinical/handovers)
- Medical Attachments (/api/clinical/encounters/{id}/attachments)
"""

import json
import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    User,
    Patient,
    EmergencyEncounter,
    ClinicalAssessment,
    VitalSignObservation,
    PreHospitalIntervention,
    MedicationAdministration,
    ClinicalTimelineEvent,
    DigitalHandoverRecord,
    HandoverAttachment,
    Incident,
    HospitalFacility,
    OrganizationMembership,
    utc_now,
)
from app.rbac.dependencies import get_current_user_flexible
from app.schemas import (
    PatientCreate,
    PatientUpdate,
    PatientResponse,
    EmergencyEncounterCreate,
    EmergencyEncounterResponse,
    ClinicalAssessmentCreate,
    ClinicalAssessmentResponse,
    VitalSignObservationCreate,
    VitalSignObservationResponse,
    PreHospitalInterventionCreate,
    PreHospitalInterventionResponse,
    MedicationAdministrationCreate,
    MedicationAdministrationResponse,
    DigitalHandoverCreate,
    DigitalHandoverSubmit,
    DigitalHandoverActionRequest,
    DigitalHandoverRecordResponse,
    HandoverAttachmentCreate,
    HandoverAttachmentResponse,
    ClinicalTimelineEventResponse,
)
from app.clinical_ops import (
    create_or_register_patient,
    update_patient_identity,
    create_emergency_encounter,
    transition_encounter_status,
    record_clinical_assessment,
    record_vital_signs,
    record_prehospital_intervention,
    record_medication_administration,
    generate_deterministic_clinical_summary,
    create_handover_draft,
    submit_handover_document,
    receive_handover_document,
    acknowledge_handover_document,
    complete_transfer_of_care,
    request_handover_clarification,
    submit_handover_correction,
    register_attachment,
    ClinicalValidationError,
    HandoverStateError,
    AttachmentValidationError,
)

logger = logging.getLogger("careon.routers.clinical_handover")

router = APIRouter(prefix="/api/clinical", tags=["Clinical Operations & Handover"])


def _check_clinical_read_access(user: User, encounter: EmergencyEncounter, db: Session) -> bool:
    """Verifies that user is clinically or operationally authorized to access the encounter."""
    role = (user.role or "").lower()
    if role in ("superadmin", "super_admin", "admin", "dispatcher"):
        return True

    # Assigned responder
    if encounter.assigned_responder_id == user.id:
        return True

    # Receiving hospital staff
    if encounter.receiving_facility_id:
        facility = db.query(HospitalFacility).filter(HospitalFacility.id == encounter.receiving_facility_id).first()
        if facility and facility.organization_id:
            membership = (
                db.query(OrganizationMembership)
                .filter(
                    OrganizationMembership.user_id == user.id,
                    OrganizationMembership.organization_id == facility.organization_id,
                    OrganizationMembership.status == "active",
                )
                .first()
            )
            if membership or role == "hospital_staff":
                return True

    if role == "responder":
        return True

    return False


# ==============================================================================
# 1. Patient Identity & Encounters
# ==============================================================================

@router.post("/patients", response_model=PatientResponse, status_code=status.HTTP_201_CREATED)
def register_patient(
    payload: PatientCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_flexible),
):
    """Registers a patient identity (provisional or verified). Citizens blocked."""
    role = (current_user.role or "").lower()
    if role == "citizen":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Citizens cannot access clinical patient registry")

    patient = create_or_register_patient(
        db=db,
        full_name=payload.full_name,
        identity_status=payload.identity_status,
        date_of_birth=payload.date_of_birth,
        estimated_age=payload.estimated_age,
        gender=payload.gender,
        contact_phone=payload.contact_phone,
        emergency_contact_name=payload.emergency_contact_name,
        emergency_contact_phone=payload.emergency_contact_phone,
        blood_group=payload.blood_group,
        known_allergies=payload.known_allergies,
        known_medical_conditions=payload.known_medical_conditions,
        current_medications=payload.current_medications,
        history_verification_status=payload.history_verification_status,
    )
    return patient


@router.get("/patients/{patient_id}", response_model=PatientResponse)
def get_patient(
    patient_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_flexible),
):
    """Retrieve patient record by ID."""
    role = (current_user.role or "").lower()
    if role == "citizen":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Citizens cannot access clinical records")

    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
    return patient


@router.patch("/patients/{patient_id}", response_model=PatientResponse)
def reconcile_patient(
    patient_id: int,
    payload: PatientUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_flexible),
):
    """Reconcile provisional patient identity or update verified medical history."""
    role = (current_user.role or "").lower()
    if role in ("citizen"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized")

    try:
        patient = update_patient_identity(
            db=db,
            patient_id=patient_id,
            full_name=payload.full_name,
            identity_status=payload.identity_status,
            date_of_birth=payload.date_of_birth,
            estimated_age=payload.estimated_age,
            gender=payload.gender,
            contact_phone=payload.contact_phone,
            emergency_contact_name=payload.emergency_contact_name,
            emergency_contact_phone=payload.emergency_contact_phone,
            blood_group=payload.blood_group,
            known_allergies=payload.known_allergies,
            known_medical_conditions=payload.known_medical_conditions,
            current_medications=payload.current_medications,
            history_verification_status=payload.history_verification_status,
            reconciled_by=current_user,
        )
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))

    return patient


@router.post("/encounters", response_model=EmergencyEncounterResponse, status_code=status.HTTP_201_CREATED)
def create_encounter(
    payload: EmergencyEncounterCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_flexible),
):
    """Creates an emergency care episode linked to an incident."""
    role = (current_user.role or "").lower()
    if role == "citizen":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Citizens cannot create clinical encounters")

    try:
        encounter = create_emergency_encounter(
            db=db,
            incident_id=payload.incident_id,
            chief_complaint=payload.chief_complaint,
            patient_id=payload.patient_id,
            assignment_id=payload.assignment_id,
            assigned_responder_id=current_user.id if role == "responder" else None,
            receiving_facility_id=payload.receiving_facility_id,
            initial_acuity=payload.initial_acuity,
            actor=current_user,
        )
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))

    return encounter


@router.get("/encounters/{encounter_id}", response_model=EmergencyEncounterResponse)
def get_encounter(
    encounter_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_flexible),
):
    """Retrieve emergency encounter."""
    encounter = db.query(EmergencyEncounter).filter(EmergencyEncounter.id == encounter_id).first()
    if not encounter:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Encounter not found")

    if not _check_clinical_read_access(current_user, encounter, db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to access this clinical encounter")

    return encounter


@router.get("/incidents/{incident_id}/encounters", response_model=List[EmergencyEncounterResponse])
def list_incident_encounters(
    incident_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_flexible),
):
    """List all patient encounters for an incident (supports mass casualties)."""
    role = (current_user.role or "").lower()
    if role == "citizen":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Citizens cannot access internal clinical encounters")

    encounters = db.query(EmergencyEncounter).filter(EmergencyEncounter.incident_id == incident_id).all()
    return encounters


# ==============================================================================
# 2. Clinical Records & Observations
# ==============================================================================

@router.post("/encounters/{encounter_id}/assessments", response_model=ClinicalAssessmentResponse, status_code=status.HTTP_201_CREATED)
def add_assessment(
    encounter_id: int,
    payload: ClinicalAssessmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_flexible),
):
    """Record primary and secondary physical assessment."""
    role = (current_user.role or "").lower()
    if role not in ("responder", "dispatcher", "admin", "superadmin", "super_admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only authorized clinical responders can record assessments")

    try:
        assessment = record_clinical_assessment(
            db=db,
            encounter_id=encounter_id,
            responder=current_user,
            consciousness_level=payload.consciousness_level,
            airway_status=payload.airway_status,
            breathing_status=payload.breathing_status,
            circulation_status=payload.circulation_status,
            presenting_complaints=payload.presenting_complaints,
            observed_injuries=payload.observed_injuries,
            symptoms=payload.symptoms,
            clinical_notes=payload.clinical_notes,
            assessed_at=payload.assessed_at,
        )
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))

    return assessment


@router.post("/encounters/{encounter_id}/vitals", response_model=VitalSignObservationResponse, status_code=status.HTTP_201_CREATED)
def add_vitals(
    encounter_id: int,
    payload: VitalSignObservationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_flexible),
):
    """Record vital signs observation with range validation."""
    role = (current_user.role or "").lower()
    if role not in ("responder", "dispatcher", "admin", "superadmin", "super_admin", "hospital_staff"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized")

    try:
        vitals = record_vital_signs(
            db=db,
            encounter_id=encounter_id,
            user=current_user,
            heart_rate=payload.heart_rate,
            systolic_bp=payload.systolic_bp,
            diastolic_bp=payload.diastolic_bp,
            respiratory_rate=payload.respiratory_rate,
            oxygen_saturation=payload.oxygen_saturation,
            body_temperature=payload.body_temperature,
            blood_glucose=payload.blood_glucose,
            gcs_eye=payload.gcs_eye,
            gcs_verbal=payload.gcs_verbal,
            gcs_motor=payload.gcs_motor,
            measurement_source=payload.measurement_source,
            observed_at=payload.observed_at,
        )
    except ClinicalValidationError as cve:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(cve))
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))

    return vitals


@router.post("/encounters/{encounter_id}/interventions", response_model=PreHospitalInterventionResponse, status_code=status.HTTP_201_CREATED)
def add_intervention(
    encounter_id: int,
    payload: PreHospitalInterventionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_flexible),
):
    """Record pre-hospital clinical intervention."""
    role = (current_user.role or "").lower()
    if role not in ("responder", "admin", "superadmin", "super_admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized")

    try:
        intervention = record_prehospital_intervention(
            db=db,
            encounter_id=encounter_id,
            performer=current_user,
            intervention_type=payload.intervention_type,
            parameters_json=payload.parameters_json,
            patient_response=payload.patient_response,
            notes=payload.notes,
            performed_at=payload.performed_at,
        )
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))

    return intervention


@router.post("/encounters/{encounter_id}/medications", response_model=MedicationAdministrationResponse, status_code=status.HTTP_201_CREATED)
def add_medication(
    encounter_id: int,
    payload: MedicationAdministrationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_flexible),
):
    """Record field medication administration audit."""
    role = (current_user.role or "").lower()
    if role not in ("responder", "admin", "superadmin", "super_admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized")

    try:
        med = record_medication_administration(
            db=db,
            encounter_id=encounter_id,
            administering_user=current_user,
            medication_name=payload.medication_name,
            dose=payload.dose,
            unit=payload.unit,
            route=payload.route,
            response_notes=payload.response_notes,
            administered_at=payload.administered_at,
        )
    except ClinicalValidationError as cve:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(cve))
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))

    return med


@router.get("/encounters/{encounter_id}/timeline", response_model=List[ClinicalTimelineEventResponse])
def get_encounter_timeline(
    encounter_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_flexible),
):
    """Retrieve complete chronological clinical and operational timeline."""
    encounter = db.query(EmergencyEncounter).filter(EmergencyEncounter.id == encounter_id).first()
    if not encounter:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Encounter not found")

    if not _check_clinical_read_access(current_user, encounter, db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized")

    timeline = (
        db.query(ClinicalTimelineEvent)
        .filter(ClinicalTimelineEvent.encounter_id == encounter_id)
        .order_by(ClinicalTimelineEvent.event_timestamp.asc())
        .all()
    )
    return timeline


@router.get("/encounters/{encounter_id}/summary")
def get_clinical_summary(
    encounter_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_flexible),
):
    """Generate deterministic factual clinical summary from recorded observations."""
    encounter = db.query(EmergencyEncounter).filter(EmergencyEncounter.id == encounter_id).first()
    if not encounter:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Encounter not found")

    if not _check_clinical_read_access(current_user, encounter, db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized")

    summary = generate_deterministic_clinical_summary(db, encounter_id)
    return summary


# ==============================================================================
# 3. Digital Handover Document Lifecycle
# ==============================================================================

@router.post("/handovers", response_model=DigitalHandoverRecordResponse, status_code=status.HTTP_201_CREATED)
def create_handover(
    payload: DigitalHandoverCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_flexible),
):
    """Create draft digital handover document."""
    role = (current_user.role or "").lower()
    if role not in ("responder", "admin", "superadmin", "super_admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only responders can draft handover records")

    try:
        handover = create_handover_draft(
            db=db,
            encounter_id=payload.encounter_id,
            facility_id=payload.facility_id,
            sending_responder=current_user,
            receiving_department=payload.receiving_department,
            outstanding_clinical_concerns=payload.outstanding_clinical_concerns,
        )
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))

    return handover


@router.post("/handovers/{handover_token}/submit", response_model=DigitalHandoverRecordResponse)
def submit_handover(
    handover_token: str,
    payload: DigitalHandoverSubmit,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_flexible),
):
    """Responder submits digital handover document to receiving facility."""
    try:
        handover = submit_handover_document(
            db=db,
            handover_token=handover_token,
            sending_responder=current_user,
            receiving_department=payload.receiving_department,
            outstanding_clinical_concerns=payload.outstanding_clinical_concerns,
        )
    except HandoverStateError as hse:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(hse))
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))

    return handover


@router.get("/handovers/{handover_token}", response_model=DigitalHandoverRecordResponse)
def get_handover(
    handover_token: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_flexible),
):
    """Retrieve digital handover document."""
    handover = (
        db.query(DigitalHandoverRecord)
        .filter(DigitalHandoverRecord.handover_token == handover_token)
        .first()
    )
    if not handover:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Handover document not found")

    if not _check_clinical_read_access(current_user, handover.encounter, db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized")

    return handover


@router.get("/handovers/{handover_token}/versions", response_model=List[DigitalHandoverRecordResponse])
def get_handover_versions(
    handover_token: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_flexible),
):
    """Retrieve immutable version history for a handover document."""
    handover = (
        db.query(DigitalHandoverRecord)
        .filter(DigitalHandoverRecord.handover_token == handover_token)
        .first()
    )
    if not handover:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Handover document not found")

    versions = (
        db.query(DigitalHandoverRecord)
        .filter(DigitalHandoverRecord.encounter_id == handover.encounter_id)
        .order_by(DigitalHandoverRecord.version.asc())
        .all()
    )
    return versions


@router.post("/handovers/{handover_token}/action", response_model=DigitalHandoverRecordResponse)
def action_handover(
    handover_token: str,
    payload: DigitalHandoverActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_flexible),
):
    """
    Hospital staff & responder lifecycle actions:
    - 'receive': hospital staff marks received
    - 'acknowledge': receiving clinician acknowledges clinical intake
    - 'complete': dual-party transfer of care finalized
    - 'clarify': hospital clinician requests clinical clarification
    - 'correct': responder submits versioned amendment
    """
    action = payload.action.lower().strip()
    try:
        if action == "receive":
            return receive_handover_document(db, handover_token, current_user)
        elif action == "acknowledge":
            return acknowledge_handover_document(db, handover_token, current_user)
        elif action == "complete":
            return complete_transfer_of_care(db, handover_token, current_user)
        elif action == "clarify":
            if not payload.clarification_notes:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Clarification notes required")
            return request_handover_clarification(db, handover_token, current_user, payload.clarification_notes)
        elif action == "correct":
            if not payload.correction_reason:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Correction reason required")
            return submit_handover_correction(
                db, handover_token, current_user, payload.correction_reason, payload.outstanding_clinical_concerns
            )
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid action '{payload.action}'")
    except HandoverStateError as hse:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(hse))
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))


# ==============================================================================
# 4. Attachments
# ==============================================================================

@router.post("/encounters/{encounter_id}/attachments", response_model=HandoverAttachmentResponse, status_code=status.HTTP_201_CREATED)
def upload_attachment(
    encounter_id: int,
    payload: HandoverAttachmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_flexible),
):
    """Register and associate a medical attachment with an emergency encounter."""
    role = (current_user.role or "").lower()
    if role == "citizen":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Citizens cannot upload clinical attachments")

    try:
        att = register_attachment(
            db=db,
            encounter_id=encounter_id,
            file_name=payload.file_name,
            file_type=payload.file_type,
            mime_type=payload.mime_type,
            file_size_bytes=payload.file_size_bytes,
            storage_path=payload.storage_path,
            uploaded_by=current_user,
            handover_id=payload.handover_id,
            is_confidential=payload.is_confidential,
        )
    except AttachmentValidationError as ave:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(ave))
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))

    return att
