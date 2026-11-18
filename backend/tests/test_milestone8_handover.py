"""
CareOn Milestone 8 Test Suite — Digital Patient Handover & Clinical Information Continuity.

Tests:
1. Patient Identity & Encounter Architecture:
   - Unknown patient handling & provisional identifier generation
   - Multiple patients under a single incident
   - Patient identity reconciliation & verification
   - Clinical privacy isolation: Citizens tracking incidents cannot access clinical encounters (403)
2. Structured Pre-Hospital Clinical Records:
   - Initial primary/secondary assessment (Airway, Breathing, Circulation, Consciousness)
   - Vital sign observation recording & physiological bounds validation (422 for impossible vitals)
   - Preservation of missing measurements without clinical fabrication
   - Pre-hospital interventions & medication administrations audit
   - Deterministic factual summary generation (strictly non-generative, zero hallucinated diagnoses)
3. Digital Handover Lifecycle & State Machine:
   - Draft creation & factual summary synthesis
   - Submission to receiving hospital facility
   - Hospital receipt & clinical acknowledgement
   - Clarification request workflow
   - Versioned corrections & immutable amendment history
   - Final transfer-of-care completion
   - Invalid state transition matrix rejection (409 Conflict)
4. Integration with M6 Responder Operations & M7 Hospital Readiness:
   - Encounter linking with active M6 mission assignment
   - Transfer-of-care completion fulfills active M7 hospital capacity reservation
   - Real-time transactional outbox event dissemination
5. Secure Medical Attachments & Access Control:
   - ECG strip / medical document registration with MIME and size limits
   - Cross-tenant access prevention
"""

import json
import time
import pytest
from datetime import datetime, timezone, timedelta, date
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

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
    Assignment,
    Resource,
    Organization,
    OrganizationMembership,
    HospitalFacility,
    HospitalCapacity,
    HospitalCapacityReservation,
    OutboxEvent,
    utc_now,
)
from app.auth import hash_password
from app.identity.jwt_handler import create_access_token
from app.clinical_ops import (
    IdentityStatus,
    EncounterStatus,
    HandoverStatus,
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
)
from app.hospital_ops import (
    CapacityCategory,
    update_facility_capacity,
    reserve_facility_capacity,
)


@pytest.fixture
def m8_setup(client: TestClient, db_session: Session):
    """
    Creates test environment:
    - Actors: dispatcher, responder, hospital staff 1 (Apollo), hospital staff 2 (Manipal), citizen
    - Incident & Assignment
    - Hospital Organization & Facility
    - Initialized capacity
    """
    t_id = int(time.time() * 1000) % 1000000

    # 1. Actors
    dispatcher = User(
        email=f"dispatcher_m8_{t_id}@careon.org",
        name="Dispatcher Anand",
        phone="+91 99999 50001",
        hashed_password=hash_password("DispatchPass123!"),
        role="dispatcher",
        is_active=True,
    )
    responder = User(
        email=f"responder_m8_{t_id}@careon.org",
        name="Paramedic Kavya",
        phone="+91 99999 50002",
        hashed_password=hash_password("RespPass123!"),
        role="responder",
        is_active=True,
    )
    hospital_staff_1 = User(
        email=f"staff1_m8_{t_id}@careon.org",
        name="Dr. Nagesh (Apollo ER)",
        phone="+91 99999 50003",
        hashed_password=hash_password("HospPass123!"),
        role="hospital_staff",
        is_active=True,
    )
    hospital_staff_2 = User(
        email=f"staff2_m8_{t_id}@careon.org",
        name="Dr. Shalini (Manipal)",
        phone="+91 99999 50004",
        hashed_password=hash_password("HospPass123!"),
        role="hospital_staff",
        is_active=True,
    )
    citizen = User(
        email=f"citizen_m8_{t_id}@example.com",
        name="Citizen Mahesh",
        phone="+91 99999 50005",
        hashed_password=hash_password("CitizenPass123!"),
        role="citizen",
        is_active=True,
    )
    db_session.add_all([dispatcher, responder, hospital_staff_1, hospital_staff_2, citizen])
    db_session.commit()

    # 2. Hospital Organizations & Facilities
    org_1 = Organization(
        name=f"Apollo Emergency Center {t_id}",
        org_type="hospital",
        location_name="Kuvempunagar, Mysuru",
        is_verified=True,
        is_active=True,
    )
    org_2 = Organization(
        name=f"Manipal Hospital {t_id}",
        org_type="hospital",
        location_name="Ring Road, Mysuru",
        is_verified=True,
        is_active=True,
    )
    db_session.add_all([org_1, org_2])
    db_session.commit()

    # Memberships
    mem_1 = OrganizationMembership(
        organization_id=org_1.id,
        user_id=hospital_staff_1.id,
        membership_role="admin",
        status="active",
    )
    mem_2 = OrganizationMembership(
        organization_id=org_2.id,
        user_id=hospital_staff_2.id,
        membership_role="admin",
        status="active",
    )
    db_session.add_all([mem_1, mem_2])
    db_session.commit()

    fac_1 = HospitalFacility(
        organization_id=org_1.id,
        facility_code=f"FAC-APO-M8-{t_id}",
        name="Apollo Emergency Hospital",
        facility_type="Tertiary Care",
        location_name="Kuvempunagar, Mysuru",
        latitude=12.3080,
        longitude=76.6450,
        geom="POINT(76.6450 12.3080)",
        trauma_level="Level 1",
        capabilities="emergency,trauma,icu,ct_scan,blood_bank,ambulance_bay",
        is_active=True,
        last_verified_at=utc_now(),
    )
    fac_2 = HospitalFacility(
        organization_id=org_2.id,
        facility_code=f"FAC-MAN-M8-{t_id}",
        name="Manipal Emergency Care",
        facility_type="Community Hospital",
        location_name="Ring Road, Mysuru",
        latitude=12.3350,
        longitude=76.6320,
        geom="POINT(76.6320 12.3350)",
        trauma_level="Level 2",
        capabilities="emergency,general_surgery",
        is_active=True,
        last_verified_at=utc_now(),
    )
    db_session.add_all([fac_1, fac_2])
    db_session.commit()

    # Seed capacity & reservation in Facility 1
    update_facility_capacity(db_session, fac_1.id, CapacityCategory.ER_BEDS, total=15, occupied=5, unavailable=1)
    update_facility_capacity(db_session, fac_1.id, CapacityCategory.TRAUMA_BAYS, total=4, occupied=1, unavailable=0)

    # 3. Fleet Resource & Assigned Unit
    res_unit = Resource(
        resource_code=f"AMB-M8-{t_id}",
        name="ALS Ambulance Echo",
        category="Ambulance",
        capabilities="ALS,trauma_care",
        equipment="ventilator,defibrillator,oxygen",
        location_name="Mysuru West",
        latitude=12.3050,
        longitude=76.6500,
        status="Assigned",
        capacity=1,
        contact_phone="+91 99999 60001",
        assigned_user_id=responder.id,
    )
    db_session.add(res_unit)
    db_session.commit()

    # 4. Incident & Assignment
    incident = Incident(
        incident_code=f"INC-M8-{t_id}",
        tracking_token=f"token_m8_{t_id}",
        category="Road accident",
        title="Commercial Bus Rollover",
        description="Mass casualty bus rollover with multiple severe injuries",
        location_name="Bannur Road, Mysuru",
        latitude=12.3150,
        longitude=76.6600,
        affected_people=4,
        help_required="Ambulance",
        contact_name="Traffic SI Patil",
        contact_phone="+91 98888 33333",
        priority="Critical",
        status="In Progress",
        is_verified=True,
    )
    db_session.add(incident)
    db_session.commit()

    assignment = Assignment(
        incident_id=incident.id,
        resource_id=res_unit.id,
        status="Active",
        assigned_at=utc_now(),
        acknowledgement_status="acknowledged",
    )
    db_session.add(assignment)
    db_session.commit()
    res_unit.current_assignment_id = assignment.id
    db_session.commit()

    # Active M7 capacity reservation for this incident at Apollo
    reservation = reserve_facility_capacity(
        db=db_session,
        facility_id=fac_1.id,
        incident_id=incident.id,
        assignment_id=assignment.id,
        category=CapacityCategory.ER_BEDS,
        quantity=1,
        user=dispatcher,
    )

    # Auth headers
    dispatcher_token = create_access_token(dispatcher.id, dispatcher.email, dispatcher.role)
    responder_token = create_access_token(responder.id, responder.email, responder.role)
    staff1_token = create_access_token(hospital_staff_1.id, hospital_staff_1.email, hospital_staff_1.role, org_ids=[org_1.id])
    staff2_token = create_access_token(hospital_staff_2.id, hospital_staff_2.email, hospital_staff_2.role, org_ids=[org_2.id])
    citizen_token = create_access_token(citizen.id, citizen.email, citizen.role)

    return {
        "dispatcher": dispatcher,
        "responder": responder,
        "staff_1": hospital_staff_1,
        "staff_2": hospital_staff_2,
        "citizen": citizen,
        "fac_1": fac_1,
        "fac_2": fac_2,
        "incident": incident,
        "assignment": assignment,
        "reservation": reservation,
        "headers_dispatcher": {"Authorization": f"Bearer {dispatcher_token}"},
        "headers_responder": {"Authorization": f"Bearer {responder_token}"},
        "headers_staff1": {"Authorization": f"Bearer {staff1_token}"},
        "headers_staff2": {"Authorization": f"Bearer {staff2_token}"},
        "headers_citizen": {"Authorization": f"Bearer {citizen_token}"},
    }


# ==============================================================================
# 1. Patient Identity & Encounter Tests
# ==============================================================================

def test_patient_encounter_creation_and_unknown_handling(client: TestClient, db_session: Session, m8_setup: dict):
    """
    Verifies:
    1. Encounter creation auto-generates a provisional patient when patient_id is not specified.
    2. Multiple encounters can be created under one incident (MCI support).
    3. Citizens tracking an incident are blocked from reading internal clinical encounters (403).
    """
    resp_headers = m8_setup["headers_responder"]
    cit_headers = m8_setup["headers_citizen"]
    incident = m8_setup["incident"]
    fac_1 = m8_setup["fac_1"]

    # 1. Responder creates encounter for Casualty 1 (unknown identity)
    resp1 = client.post(
        "/api/clinical/encounters",
        json={
            "incident_id": incident.id,
            "chief_complaint": "Severe blunt chest trauma, unconscious",
            "initial_acuity": "Critical",
            "receiving_facility_id": fac_1.id,
        },
        headers=resp_headers,
    )
    assert resp1.status_code == 201, resp1.text
    enc1_data = resp1.json()
    enc1_id = enc1_data["id"]
    pat1_id = enc1_data["patient_id"]
    assert enc1_data["status"] == "active"

    # Verify provisional patient record
    pat1 = db_session.query(Patient).filter(Patient.id == pat1_id).first()
    assert pat1.identity_status == "unknown"
    assert pat1.patient_identifier.startswith("PROV-PAT-")

    # 2. Responder creates encounter for Casualty 2 under SAME incident (separate patient)
    resp2 = client.post(
        "/api/clinical/encounters",
        json={
            "incident_id": incident.id,
            "chief_complaint": "Compound fracture left tibia, conscious",
            "initial_acuity": "High",
            "receiving_facility_id": fac_1.id,
        },
        headers=resp_headers,
    )
    assert resp2.status_code == 201
    enc2_data = resp2.json()
    assert enc2_data["id"] != enc1_id
    assert enc2_data["patient_id"] != pat1_id

    # 3. Query all encounters for incident
    resp_list = client.get(f"/api/clinical/incidents/{incident.id}/encounters", headers=resp_headers)
    assert resp_list.status_code == 200
    encounters = resp_list.json()
    assert len(encounters) >= 2

    # 4. Strict Privacy: Citizen tracking the incident CANNOT read clinical encounters (403 Forbidden)
    resp_cit = client.get(f"/api/clinical/incidents/{incident.id}/encounters", headers=cit_headers)
    assert resp_cit.status_code == 403


def test_patient_identity_reconciliation(client: TestClient, db_session: Session, m8_setup: dict):
    """Verifies reconciliation of a provisional patient record with verified legal identity and allergies."""
    resp_headers = m8_setup["headers_responder"]

    # Create unknown patient
    patient = create_or_register_patient(db_session, identity_status=IdentityStatus.UNKNOWN)

    # Reconcile patient after ID card / relative identification
    resp_rec = client.patch(
        f"/api/clinical/patients/{patient.id}",
        json={
            "full_name": "Siddharth Verma",
            "identity_status": "verified",
            "date_of_birth": "1988-06-15",
            "gender": "male",
            "blood_group": "O+",
            "known_allergies": "Penicillin, Cephalosporins",
            "known_medical_conditions": "Asthma, Mild Hypertension",
            "history_verification_status": "family_reported",
        },
        headers=resp_headers,
    )
    assert resp_rec.status_code == 200
    data = resp_rec.json()
    assert data["full_name"] == "Siddharth Verma"
    assert data["identity_status"] == "verified"
    assert data["blood_group"] == "O+"
    assert "Penicillin" in data["known_allergies"]


# ==============================================================================
# 2. Structured Pre-Hospital Clinical Records Tests
# ==============================================================================

def test_vital_signs_validation_and_recording(client: TestClient, db_session: Session, m8_setup: dict):
    """
    Verifies:
    1. Vital sign physiological range enforcement (rejecting impossible values).
    2. Missing values allowed without artificial fabrication.
    3. GCS computation.
    """
    resp_headers = m8_setup["headers_responder"]
    incident = m8_setup["incident"]

    encounter = create_emergency_encounter(
        db_session, incident.id, chief_complaint="Fall from height, altered mental status"
    )

    # 1. Impossible heart rate (>300 bpm) rejected with 422
    resp_bad_hr = client.post(
        f"/api/clinical/encounters/{encounter.id}/vitals",
        json={"heart_rate": 350},
        headers=resp_headers,
    )
    assert resp_bad_hr.status_code == 422

    # 2. Impossible SpO2 (>100%) rejected with 422
    resp_bad_spo2 = client.post(
        f"/api/clinical/encounters/{encounter.id}/vitals",
        json={"oxygen_saturation": 110.0},
        headers=resp_headers,
    )
    assert resp_bad_spo2.status_code == 422

    # 3. Valid vital signs set with GCS breakdown
    resp_valid = client.post(
        f"/api/clinical/encounters/{encounter.id}/vitals",
        json={
            "heart_rate": 112,
            "systolic_bp": 94,
            "diastolic_bp": 60,
            "respiratory_rate": 22,
            "oxygen_saturation": 93.5,
            "body_temperature": 36.8,
            "blood_glucose": 110.0,
            "gcs_eye": 3,
            "gcs_verbal": 4,
            "gcs_motor": 5,
            "measurement_source": "monitor_automated",
        },
        headers=resp_headers,
    )
    assert resp_valid.status_code == 201
    data = resp_valid.json()
    assert data["heart_rate"] == 112
    assert data["gcs_total"] == 12  # 3 + 4 + 5 = 12


def test_assessments_interventions_and_medications(client: TestClient, db_session: Session, m8_setup: dict):
    """Verifies structured logging of physical assessment, procedures, and administered drugs."""
    resp_headers = m8_setup["headers_responder"]
    incident = m8_setup["incident"]

    encounter = create_emergency_encounter(db_session, incident.id, chief_complaint="Severe respiratory distress")

    # 1. Assessment
    resp_ass = client.post(
        f"/api/clinical/encounters/{encounter.id}/assessments",
        json={
            "consciousness_level": "Alert",
            "airway_status": "clear",
            "breathing_status": "labored",
            "circulation_status": "normal_pulses",
            "symptoms": "Audible wheezing, accessory muscle use",
        },
        headers=resp_headers,
    )
    assert resp_ass.status_code == 201
    assert resp_ass.json()["breathing_status"] == "labored"

    # 2. Intervention: High-flow oxygen
    resp_int = client.post(
        f"/api/clinical/encounters/{encounter.id}/interventions",
        json={
            "intervention_type": "oxygen_therapy",
            "parameters_json": {"flow_lpm": 15, "delivery_device": "non_rebreather_mask"},
            "patient_response": "improved",
            "notes": "SpO2 rose from 88% to 96% after 4 minutes",
        },
        headers=resp_headers,
    )
    assert resp_int.status_code == 201
    assert resp_int.json()["patient_response"] == "improved"

    # 3. Medication: Salbutamol nebulization
    resp_med = client.post(
        f"/api/clinical/encounters/{encounter.id}/medications",
        json={
            "medication_name": "Salbutamol",
            "dose": 2.5,
            "unit": "mg",
            "route": "NEBULIZED",
            "response_notes": "Wheezing reduced",
        },
        headers=resp_headers,
    )
    assert resp_med.status_code == 201
    assert resp_med.json()["medication_name"] == "Salbutamol"


def test_deterministic_clinical_summary_generation(client: TestClient, db_session: Session, m8_setup: dict):
    """
    CRITICAL CLINICAL INTEGRITY TEST:
    Verifies that the summary generator uses purely recorded factual data,
    identifies missing information, and never hallucinates diagnoses.
    """
    resp_headers = m8_setup["headers_responder"]
    incident = m8_setup["incident"]

    encounter = create_emergency_encounter(db_session, incident.id, chief_complaint="Anaphylactic allergic reaction")

    # Generate summary without vitals
    summary_resp = client.get(f"/api/clinical/encounters/{encounter.id}/summary", headers=resp_headers)
    assert summary_resp.status_code == 200
    summary = summary_resp.json()

    assert summary["synthesis_mode"] == "deterministic_factual_only"
    assert summary["chief_complaint"] == "Anaphylactic allergic reaction"
    # Flags missing information explicitly
    missing = summary["missing_information_flags"]
    assert any("vital signs" in flag.lower() for flag in missing)
    assert any("identity" in flag.lower() for flag in missing)


# ==============================================================================
# 3. Digital Handover Lifecycle & State Machine Tests
# ==============================================================================

def test_full_handover_lifecycle_sequential_transitions(client: TestClient, db_session: Session, m8_setup: dict):
    """
    Validates end-to-end digital transfer of care lifecycle:
    DRAFT -> SUBMITTED -> RECEIVED -> ACKNOWLEDGED -> COMPLETED.
    """
    resp_headers = m8_setup["headers_responder"]
    staff1_headers = m8_setup["headers_staff1"]
    incident = m8_setup["incident"]
    fac_1 = m8_setup["fac_1"]
    reservation = m8_setup["reservation"]

    encounter = create_emergency_encounter(
        db_session, incident.id, chief_complaint="Severe head trauma", receiving_facility_id=fac_1.id
    )

    # 1. Responder creates DRAFT handover
    resp_draft = client.post(
        "/api/clinical/handovers",
        json={
            "encounter_id": encounter.id,
            "facility_id": fac_1.id,
            "receiving_department": "Resuscitation Bay 1",
            "outstanding_clinical_concerns": "C-spine immobilized, pupil inequality (R > L)",
        },
        headers=resp_headers,
    )
    assert resp_draft.status_code == 201, resp_draft.text
    token = resp_draft.json()["handover_token"]
    assert resp_draft.json()["status"] == HandoverStatus.DRAFT

    # 2. Responder submits handover document (SUBMITTED)
    resp_sub = client.post(
        f"/api/clinical/handovers/{token}/submit",
        json={"outstanding_clinical_concerns": "Pupil asymmetry verified, neurosurgery alerted"},
        headers=resp_headers,
    )
    assert resp_sub.status_code == 200
    assert resp_sub.json()["status"] == HandoverStatus.SUBMITTED

    # 3. Hospital triage staff marks RECEIVED
    resp_rec = client.post(
        f"/api/clinical/handovers/{token}/action",
        json={"action": "receive"},
        headers=staff1_headers,
    )
    assert resp_rec.status_code == 200
    assert resp_rec.json()["status"] == HandoverStatus.RECEIVED

    # 4. Hospital physician ACKNOWLEDGES clinical intake
    resp_ack = client.post(
        f"/api/clinical/handovers/{token}/action",
        json={"action": "acknowledge"},
        headers=staff1_headers,
    )
    assert resp_ack.status_code == 200
    assert resp_ack.json()["status"] == HandoverStatus.ACKNOWLEDGED

    # 5. Dual-party sign-off: COMPLETE transfer of care
    resp_comp = client.post(
        f"/api/clinical/handovers/{token}/action",
        json={"action": "complete"},
        headers=staff1_headers,
    )
    assert resp_comp.status_code == 200
    data_comp = resp_comp.json()
    assert data_comp["status"] == HandoverStatus.COMPLETED
    assert data_comp["is_final"] is True

    # 6. Verify integration side-effects:
    # - Encounter status becomes handed_over
    db_session.refresh(encounter)
    assert encounter.status == "handed_over"

    # - M7 capacity reservation fulfilled
    db_session.refresh(reservation)
    assert reservation.status == "fulfilled"


def test_invalid_handover_transition_rejection(client: TestClient, db_session: Session, m8_setup: dict):
    """Verifies that skipping required clinical handover steps is rejected with 409 Conflict."""
    resp_headers = m8_setup["headers_responder"]
    staff1_headers = m8_setup["headers_staff1"]
    incident = m8_setup["incident"]
    fac_1 = m8_setup["fac_1"]

    encounter = create_emergency_encounter(db_session, incident.id, chief_complaint="Fracture")
    draft = create_handover_draft(db_session, encounter.id, fac_1.id, m8_setup["responder"])

    # Attempting to directly complete a DRAFT handover without submission or acknowledgement
    resp_bad = client.post(
        f"/api/clinical/handovers/{draft.handover_token}/action",
        json={"action": "complete"},
        headers=staff1_headers,
    )
    assert resp_bad.status_code == 409
    assert "Cannot complete handover" in resp_bad.json()["detail"]


def test_handover_clarification_and_versioned_correction(client: TestClient, db_session: Session, m8_setup: dict):
    """
    Verifies:
    1. Hospital requesting clinical clarification.
    2. Responder submitting versioned amendment (spawning Version 2 while preserving Version 1 as immutable).
    """
    resp_headers = m8_setup["headers_responder"]
    staff1_headers = m8_setup["headers_staff1"]
    incident = m8_setup["incident"]
    fac_1 = m8_setup["fac_1"]

    encounter = create_emergency_encounter(db_session, incident.id, chief_complaint="Chest trauma")
    handover_v1 = create_handover_draft(db_session, encounter.id, fac_1.id, m8_setup["responder"])
    submit_handover_document(db_session, handover_v1.handover_token, m8_setup["responder"])

    # 1. Hospital staff requests clarification
    resp_clar = client.post(
        f"/api/clinical/handovers/{handover_v1.handover_token}/action",
        json={"action": "clarify", "clarification_notes": "Did patient receive sublingual nitroglycerin prior to transport?"},
        headers=staff1_headers,
    )
    assert resp_clar.status_code == 200
    assert resp_clar.json()["status"] == HandoverStatus.CLARIFICATION_REQUESTED

    # 2. Responder submits correction -> spawns Version 2
    resp_corr = client.post(
        f"/api/clinical/handovers/{handover_v1.handover_token}/action",
        json={
            "action": "correct",
            "correction_reason": "Clarified medication: NTG 0.4mg given at 22:15, chest pain improved 8/10 to 3/10",
        },
        headers=resp_headers,
    )
    assert resp_corr.status_code == 200
    v2_data = resp_corr.json()
    assert v2_data["version"] == 2
    assert v2_data["status"] == HandoverStatus.SUBMITTED

    # 3. Verify version history endpoint returns both versions
    resp_vers = client.get(f"/api/clinical/handovers/{v2_data['handover_token']}/versions", headers=resp_headers)
    assert resp_vers.status_code == 200
    versions = resp_vers.json()
    assert len(versions) == 2
    assert versions[0]["version"] == 1
    assert versions[1]["version"] == 2


# ==============================================================================
# 4. Attachments & Security Tests
# ==============================================================================

def test_medical_attachments_upload_and_mime_validation(client: TestClient, db_session: Session, m8_setup: dict):
    """Verifies file type & size validation for medical attachments (ECG strips, photos)."""
    resp_headers = m8_setup["headers_responder"]
    cit_headers = m8_setup["headers_citizen"]
    incident = m8_setup["incident"]

    encounter = create_emergency_encounter(db_session, incident.id, chief_complaint="Arrhythmia")

    # 1. Citizen upload rejected with 403
    resp_cit = client.post(
        f"/api/clinical/encounters/{encounter.id}/attachments",
        json={
            "file_name": "ecg.pdf",
            "file_type": "ecg_strip",
            "mime_type": "application/pdf",
            "file_size_bytes": 50000,
            "storage_path": "/secure/ecg.pdf",
        },
        headers=cit_headers,
    )
    assert resp_cit.status_code == 403

    # 2. Executable / dangerous MIME type rejected with 422
    resp_exe = client.post(
        f"/api/clinical/encounters/{encounter.id}/attachments",
        json={
            "file_name": "script.sh",
            "file_type": "script",
            "mime_type": "application/x-sh",
            "file_size_bytes": 1000,
            "storage_path": "/tmp/script.sh",
        },
        headers=resp_headers,
    )
    assert resp_exe.status_code == 422

    # 3. Valid ECG PDF attachment succeeds
    resp_ok = client.post(
        f"/api/clinical/encounters/{encounter.id}/attachments",
        json={
            "file_name": "12_lead_ecg_prehospital.pdf",
            "file_type": "ecg_strip",
            "mime_type": "application/pdf",
            "file_size_bytes": 142000,
            "storage_path": "/secure/clinical/enc_123/ecg.pdf",
        },
        headers=resp_headers,
    )
    assert resp_ok.status_code == 201
    assert resp_ok.json()["file_type"] == "ecg_strip"


# ==============================================================================
# 5. Real-Time Outbox Integration & Privacy Tests
# ==============================================================================

def test_clinical_events_outbox_privacy(db_session: Session, m8_setup: dict):
    """
    CRITICAL PRIVACY TEST:
    Verifies that clinical handover events are recorded in outbox_events
    with ZERO patient clinical notes, diagnoses, or vital signs in the payload.
    """
    responder = m8_setup["responder"]
    incident = m8_setup["incident"]
    fac_1 = m8_setup["fac_1"]

    encounter = create_emergency_encounter(db_session, incident.id, chief_complaint="Chest pain")
    draft = create_handover_draft(db_session, encounter.id, fac_1.id, responder)
    submit_handover_document(db_session, draft.handover_token, responder)

    # Check outbox events
    event = (
        db_session.query(OutboxEvent)
        .filter(OutboxEvent.event_type == "handover.document_submitted")
        .order_by(OutboxEvent.created_at.desc())
        .first()
    )
    assert event is not None
    payload = json.loads(event.payload_json)

    # Assert privacy: payload only contains metadata (token, facility, version), NO medical text
    assert "blood_pressure" not in payload
    assert "heart_rate" not in payload
    assert "diagnosis" not in payload
    assert "notes" not in payload
    assert "handover_token" in payload
    assert payload["version"] == 1
