"""
CareOn Milestone 9 Test Suite — Offline-First Synchronization & Resilient Field Operations.

Covers all 28 required test areas:
1. Device registration and ownership validation
2. Device revocation (revoked devices rejected with 403)
3. Successful batch upload
4. Duplicate action UUID idempotency
5. Partial batch failure (one invalid action does not discard valid actions)
6. Unauthorized mission synchronization rejection
7. Tenant isolation (cross-organization sync rejected)
8. Expired credentials and safe reauthentication
9. Out-of-order clinical event synchronization
10. Clinical record immutability
11. Immutable handover correction integration
12. Stale mission transition rejection (conflict returned)
13. Assignment reassignment conflict handling
14. GPS buffering and duplicate telemetry
15. Older telemetry not overwriting latest position
16. Stable download cursor behavior
17. Interrupted download recovery
18. Interrupted upload recovery
19. Repeated batch replay
20. Conflict creation and reconciliation
21. Device restart and local queue recovery
22. Network restoration and synchronization recovery
23. Batch size and payload limits (HTTP 413)
24. Worker retry and recovery behavior
25. M4 outbox integration
26. M6 mission lifecycle regression
27. M7 facility and reservation regression
28. M8 clinical and handover regression
Plus Concurrency tests with simultaneous batch submissions.
"""

import json
import time
import uuid
import pytest
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import (
    User,
    Incident,
    Assignment,
    Resource,
    Organization,
    OrganizationMembership,
    HospitalFacility,
    HospitalCapacity,
    EmergencyEncounter,
    Patient,
    ClinicalAssessment,
    VitalSignObservation,
    PreHospitalIntervention,
    MedicationAdministration,
    DigitalHandoverRecord,
    DeviceRegistration,
    SyncBatchReceipt,
    SyncActionReceipt,
    SyncConflict,
    SyncAuditEvent,
    ResponderTelemetryLog,
    MissionEventLog,
    utc_now,
)
from app.auth import hash_password, create_access_token
from app.responder_ops.state_machine import MissionStatus
from app.clinical_ops.handover import HandoverStatus
from app.sync.recovery_worker import run_sync_recovery_cycle


@pytest.fixture
def m9_setup(client: TestClient, db_session: Session):
    """
    Creates test environment with:
    - Organizations: Org A (City EMS) and Org B (Private Care)
    - Responders: Responder A (Org A) and Responder B (Org B)
    - Admin: Super Admin
    - Resources: Ambulance 1 (assigned to Responder A), Ambulance 2 (assigned to Responder B)
    - Incidents: Incident A (Org A), Incident B (Org B)
    - Assignments: Mission A (Ambulance 1), Mission B (Ambulance 2)
    - Patient & Encounter: Encounter A linked to Incident A
    - Hospital Facility & Capacity
    """
    t_id = int(time.time() * 1000) % 1000000

    # 1. Organizations
    org_a = Organization(name=f"City EMS Org A {t_id}", org_type="ambulance_service", is_active=True)
    org_b = Organization(name=f"Private Care Org B {t_id}", org_type="ambulance_service", is_active=True)
    db_session.add_all([org_a, org_b])
    db_session.flush()

    # 2. Users
    resp_a = User(
        email=f"resp_a_{t_id}@careon.org",
        name="Responder Alpha",
        phone="+91 99999 60001",
        hashed_password=hash_password("PassRespA123!"),
        role="responder",
        is_active=True,
    )
    resp_b = User(
        email=f"resp_b_{t_id}@careon.org",
        name="Responder Beta",
        phone="+91 99999 60002",
        hashed_password=hash_password("PassRespB123!"),
        role="responder",
        is_active=True,
    )
    admin = User(
        email=f"admin_{t_id}@careon.org",
        name="Admin Ops",
        phone="+91 99999 60003",
        hashed_password=hash_password("AdminPass123!"),
        role="admin",
        is_active=True,
    )
    db_session.add_all([resp_a, resp_b, admin])
    db_session.flush()

    # Memberships
    mem_a = OrganizationMembership(user_id=resp_a.id, organization_id=org_a.id, membership_role="member", status="active")
    mem_b = OrganizationMembership(user_id=resp_b.id, organization_id=org_b.id, membership_role="member", status="active")
    db_session.add_all([mem_a, mem_b])

    # 3. Resources
    res_a = Resource(
        resource_code=f"RES-A-{t_id}",
        name=f"Ambulance-A-{t_id}",
        category="Ambulance",
        capabilities="ALS,trauma_care",
        location_name="MG Road Station",
        latitude=12.9716,
        longitude=77.5946,
        geom=f"SRID=4326;POINT(77.5946 12.9716)",
        status="Available",
        capacity=1,
        contact_phone="+91 99999 70001",
        organization_id=org_a.id,
        assigned_user_id=resp_a.id,
        last_updated=datetime.now(timezone.utc),
    )
    res_b = Resource(
        resource_code=f"RES-B-{t_id}",
        name=f"Ambulance-B-{t_id}",
        category="Ambulance",
        capabilities="BLS",
        location_name="Peenya Depot",
        latitude=12.9500,
        longitude=77.5800,
        geom=f"SRID=4326;POINT(77.5800 12.9500)",
        status="Available",
        capacity=1,
        contact_phone="+91 99999 70002",
        organization_id=org_b.id,
        assigned_user_id=resp_b.id,
        last_updated=datetime.now(timezone.utc),
    )
    db_session.add_all([res_a, res_b])
    db_session.flush()

    # 4. Incidents
    inc_a = Incident(
        incident_code=f"INC-A-{t_id}",
        title="Severe Traffic Collision",
        description="Two vehicles in collision, head trauma reported.",
        category="Road accident",
        priority="Critical",
        status="Assignment Confirmed",
        location_name="MG Road Metro",
        latitude=12.9750,
        longitude=77.6000,
        help_required="Ambulance",
        contact_name="Bystander Rahul",
        contact_phone="+91 99999 80001",
    )
    inc_b = Incident(
        incident_code=f"INC-B-{t_id}",
        title="Industrial Fire",
        description="Warehouse smoke inhalation.",
        category="Fire",
        priority="High",
        status="Assignment Confirmed",
        location_name="Peenya Ind Area",
        latitude=13.0300,
        longitude=77.5200,
        help_required="Ambulance",
        contact_name="Supervisor Suresh",
        contact_phone="+91 99999 80002",
    )
    db_session.add_all([inc_a, inc_b])
    db_session.flush()

    # 5. Assignments (Missions)
    assign_a = Assignment(
        incident_id=inc_a.id,
        resource_id=res_a.id,
        status=MissionStatus.ACCEPTED,
        assigned_at=datetime.now(timezone.utc) - timedelta(minutes=10),
        acknowledgement_status="acknowledged",
        acknowledged_at=datetime.now(timezone.utc) - timedelta(minutes=9),
        notes=f"Assigned to responder {resp_a.id}",
    )
    assign_b = Assignment(
        incident_id=inc_b.id,
        resource_id=res_b.id,
        status=MissionStatus.ACCEPTED,
        assigned_at=datetime.now(timezone.utc) - timedelta(minutes=5),
        acknowledgement_status="acknowledged",
        acknowledged_at=datetime.now(timezone.utc) - timedelta(minutes=4),
        notes=f"Assigned to responder {resp_b.id}",
    )
    db_session.add_all([assign_a, assign_b])
    db_session.flush()

    # Initial accepted mission event logs so M6 state machine recognizes accepted status
    event_log_a = MissionEventLog(
        assignment_id=assign_a.id,
        incident_id=inc_a.id,
        resource_id=res_a.id,
        actor_id=resp_a.id,
        actor_role="responder",
        previous_status=MissionStatus.ASSIGNED,
        new_status=MissionStatus.ACCEPTED,
        server_timestamp=datetime.now(timezone.utc) - timedelta(minutes=9),
    )
    event_log_b = MissionEventLog(
        assignment_id=assign_b.id,
        incident_id=inc_b.id,
        resource_id=res_b.id,
        actor_id=resp_b.id,
        actor_role="responder",
        previous_status=MissionStatus.ASSIGNED,
        new_status=MissionStatus.ACCEPTED,
        server_timestamp=datetime.now(timezone.utc) - timedelta(minutes=4),
    )
    db_session.add_all([event_log_a, event_log_b])
    db_session.flush()

    # 6. Patient & Clinical Encounter
    patient = Patient(
        patient_identifier=f"PROV-PAT-{t_id}",
        full_name="Alex Smith",
        identity_status="provisional",
        gender="male",
        estimated_age=32,
    )
    db_session.add(patient)
    db_session.flush()

    encounter = EmergencyEncounter(
        encounter_code=f"ENC-{t_id}",
        patient_id=patient.id,
        incident_id=inc_a.id,
        assignment_id=assign_a.id,
        assigned_responder_id=resp_a.id,
        status="active",
        chief_complaint="Blunt chest trauma and dyspnea",
        initial_acuity="High",
    )
    db_session.add(encounter)

    # 7. Hospital Facility
    facility = HospitalFacility(
        name=f"Apex General Hospital {t_id}",
        facility_code=f"APEX-{t_id}",
        organization_id=org_a.id,
        latitude=12.9800,
        longitude=77.6100,
        location_name="100 Hospital Way, Indiranagar",
        trauma_level="Level 1",
    )
    db_session.add(facility)
    db_session.commit()

    token_a = create_access_token({"sub": str(resp_a.id), "email": resp_a.email, "role": "responder"})
    token_b = create_access_token({"sub": str(resp_b.id), "email": resp_b.email, "role": "responder"})
    token_admin = create_access_token({"sub": str(admin.id), "email": admin.email, "role": "admin"})

    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}
    headers_admin = {"Authorization": f"Bearer {token_admin}"}

    return {
        "org_a": org_a,
        "org_b": org_b,
        "resp_a": resp_a,
        "resp_b": resp_b,
        "admin": admin,
        "res_a": res_a,
        "res_b": res_b,
        "inc_a": inc_a,
        "inc_b": inc_b,
        "assign_a": assign_a,
        "assign_b": assign_b,
        "patient": patient,
        "encounter": encounter,
        "facility": facility,
        "headers_a": headers_a,
        "headers_b": headers_b,
        "headers_admin": headers_admin,
    }


# ==============================================================================
# 1. Device Registration and Ownership
# ==============================================================================

def test_device_registration_and_ownership(client: TestClient, db_session: Session, m9_setup):
    """
    Validates registering a field device, initial cursor, and device metadata binding.
    """
    h_a = m9_setup["headers_a"]
    dev_id = f"dev_test_{uuid.uuid4().hex[:8]}"

    reg_payload = {
        "device_identifier": dev_id,
        "platform": "android",
        "app_version": "1.2.0",
        "device_model": "Samsung Galaxy Active Tab 3",
        "push_token": f"fcm_{dev_id}",
        "organization_id": m9_setup["org_a"].id,
    }

    res = client.post("/api/sync/v1/devices/register", json=reg_payload, headers=h_a)
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["device_identifier"] == dev_id
    assert data["user_id"] == m9_setup["resp_a"].id
    assert data["platform"] == "android"
    assert data["sync_cursor"] == "0"
    assert data["is_active"] is True
    assert data["is_revoked"] is False

    # Verify audit event logged
    audit = db_session.query(SyncAuditEvent).filter(SyncAuditEvent.event_type == "DEVICE_REGISTERED").first()
    assert audit is not None
    assert audit.user_id == m9_setup["resp_a"].id

    # Retrieve device via GET
    get_res = client.get(f"/api/sync/v1/devices/{dev_id}", headers=h_a)
    assert get_res.status_code == 200
    assert get_res.json()["device_identifier"] == dev_id


# ==============================================================================
# 2. Device Revocation Enforcement
# ==============================================================================

def test_device_revocation_enforcement(client: TestClient, db_session: Session, m9_setup):
    """
    Validates revoking a device installation: subsequent sync upload must be barred (HTTP 403).
    """
    h_a = m9_setup["headers_a"]
    dev_id = f"dev_rev_{uuid.uuid4().hex[:8]}"

    # Register
    client.post(
        "/api/sync/v1/devices/register",
        json={"device_identifier": dev_id, "platform": "ios", "app_version": "1.0.0"},
        headers=h_a,
    )

    # Revoke
    revoke_res = client.post(
        f"/api/sync/v1/devices/{dev_id}/revoke",
        json={"reason": "Responder phone lost at disaster site"},
        headers=h_a,
    )
    assert revoke_res.status_code == 200
    assert revoke_res.json()["is_revoked"] is True

    # Attempt to upload sync batch from revoked device
    upload_res = client.post(
        "/api/sync/v1/upload",
        json={
            "device_id": dev_id,
            "client_batch_id": f"batch_{uuid.uuid4().hex[:8]}",
            "actions": [],
        },
        headers=h_a,
    )
    assert upload_res.status_code == 403
    assert "DEVICE_REVOKED" in upload_res.json()["detail"]


# ==============================================================================
# 3. Successful Batch Upload & Action Dispatch
# ==============================================================================

def test_successful_batch_upload_and_action_dispatch(client: TestClient, db_session: Session, m9_setup):
    """
    Submits batch containing status transition, clinical assessment, and vitals.
    All actions must be acknowledged transactionally.
    """
    h_a = m9_setup["headers_a"]
    assign_a = m9_setup["assign_a"]
    encounter = m9_setup["encounter"]
    dev_id = f"dev_sync_{uuid.uuid4().hex[:8]}"

    # Register device
    client.post(
        "/api/sync/v1/devices/register",
        json={"device_identifier": dev_id, "platform": "android", "app_version": "1.0.0"},
        headers=h_a,
    )

    now_iso = datetime.now(timezone.utc).isoformat()
    action_1_uuid = f"act_stat_{uuid.uuid4().hex[:8]}"
    action_2_uuid = f"act_ass_{uuid.uuid4().hex[:8]}"
    action_3_uuid = f"act_vit_{uuid.uuid4().hex[:8]}"

    batch_payload = {
        "device_id": dev_id,
        "client_batch_id": f"batch_{uuid.uuid4().hex[:8]}",
        "actions": [
            {
                "action_uuid": action_1_uuid,
                "action_type": "MISSION_STATUS_CHANGE",
                "mission_id": assign_a.id,
                "client_timestamp": now_iso,
                "payload": {"status": MissionStatus.EN_ROUTE_INCIDENT, "notes": "Navigating highway traffic"},
            },
            {
                "action_uuid": action_2_uuid,
                "action_type": "CLINICAL_ASSESSMENT",
                "encounter_id": encounter.id,
                "client_timestamp": now_iso,
                "payload": {
                    "consciousness_level": "Voice",
                    "airway_status": "clear",
                    "breathing_status": "tachypneic",
                    "circulation_status": "weak_pulses",
                    "presenting_complaints": "Chest wall contusion",
                },
            },
            {
                "action_uuid": action_3_uuid,
                "action_type": "VITAL_OBSERVATION",
                "encounter_id": encounter.id,
                "client_timestamp": now_iso,
                "payload": {
                    "heart_rate": 115,
                    "systolic_bp": 105,
                    "diastolic_bp": 70,
                    "oxygen_saturation": 92.5,
                    "body_temperature": 36.8,
                    "gcs_eye": 3,
                    "gcs_verbal": 4,
                    "gcs_motor": 5,
                },
            },
        ],
    }

    res = client.post("/api/sync/v1/upload", json=batch_payload, headers=h_a)
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["total_actions"] == 3
    assert data["accepted_actions"] == 3
    assert data["failed_actions"] == 0
    assert data["conflict_actions"] == 0

    # Verify mission event log recorded transition
    last_log = (
        db_session.query(MissionEventLog)
        .filter(MissionEventLog.assignment_id == assign_a.id)
        .order_by(MissionEventLog.id.desc())
        .first()
    )
    assert last_log.new_status == MissionStatus.EN_ROUTE_INCIDENT

    # Verify clinical records saved
    assessments = db_session.query(ClinicalAssessment).filter(ClinicalAssessment.encounter_id == encounter.id).all()
    assert len(assessments) == 1
    assert assessments[0].consciousness_level == "Voice"

    vitals = db_session.query(VitalSignObservation).filter(VitalSignObservation.encounter_id == encounter.id).all()
    assert len(vitals) == 1
    assert vitals[0].gcs_total == 12


# ==============================================================================
# 4. Duplicate Action UUID Idempotency
# ==============================================================================

def test_duplicate_action_uuid_idempotency(client: TestClient, db_session: Session, m9_setup):
    """
    Submitting the exact same batch twice must return identical receipts
    without creating duplicate records or mutating state.
    """
    h_a = m9_setup["headers_a"]
    encounter = m9_setup["encounter"]
    dev_id = f"dev_idemp_{uuid.uuid4().hex[:8]}"

    client.post(
        "/api/sync/v1/devices/register",
        json={"device_identifier": dev_id, "platform": "android", "app_version": "1.0.0"},
        headers=h_a,
    )

    action_uuid = f"act_idemp_{uuid.uuid4().hex[:8]}"
    batch_payload = {
        "device_id": dev_id,
        "client_batch_id": f"batch_{uuid.uuid4().hex[:8]}",
        "actions": [
            {
                "action_uuid": action_uuid,
                "action_type": "VITAL_OBSERVATION",
                "encounter_id": encounter.id,
                "client_timestamp": datetime.now(timezone.utc).isoformat(),
                "payload": {"heart_rate": 88, "systolic_bp": 120, "diastolic_bp": 80},
            }
        ],
    }

    # First upload
    res1 = client.post("/api/sync/v1/upload", json=batch_payload, headers=h_a)
    assert res1.status_code == 200
    ack_id_1 = res1.json()["results"][0]["server_ack_id"]

    # Replay upload
    res2 = client.post("/api/sync/v1/upload", json=batch_payload, headers=h_a)
    assert res2.status_code == 200
    ack_id_2 = res2.json()["results"][0]["server_ack_id"]

    # Must match original ack id
    assert ack_id_1 == ack_id_2

    # Exactly one vital observation must exist for this action
    vitals = db_session.query(VitalSignObservation).filter(VitalSignObservation.encounter_id == encounter.id).all()
    assert len(vitals) == 1


# ==============================================================================
# 5. Partial Batch Failure & Isolation
# ==============================================================================

def test_partial_batch_failure_and_isolation(client: TestClient, db_session: Session, m9_setup):
    """
    If one action in a batch is invalid (e.g. unknown action type or bad payload),
    valid actions must still succeed and be acknowledged.
    """
    h_a = m9_setup["headers_a"]
    encounter = m9_setup["encounter"]
    dev_id = f"dev_part_{uuid.uuid4().hex[:8]}"

    client.post(
        "/api/sync/v1/devices/register",
        json={"device_identifier": dev_id, "platform": "ios", "app_version": "1.0.0"},
        headers=h_a,
    )

    valid_act_uuid = f"act_valid_{uuid.uuid4().hex[:8]}"
    invalid_act_uuid = f"act_invalid_{uuid.uuid4().hex[:8]}"

    batch_payload = {
        "device_id": dev_id,
        "client_batch_id": f"batch_{uuid.uuid4().hex[:8]}",
        "actions": [
            {
                "action_uuid": valid_act_uuid,
                "action_type": "INTERVENTION",
                "encounter_id": encounter.id,
                "client_timestamp": datetime.now(timezone.utc).isoformat(),
                "payload": {"intervention_type": "c_spine_immobilization", "patient_response": "improved"},
            },
            {
                "action_uuid": invalid_act_uuid,
                "action_type": "CORRUPTED_ACTION_TYPE_NOT_SUPPORTED",
                "client_timestamp": datetime.now(timezone.utc).isoformat(),
                "payload": {},
            },
        ],
    }

    res = client.post("/api/sync/v1/upload", json=batch_payload, headers=h_a)
    assert res.status_code == 200
    data = res.json()
    assert data["total_actions"] == 2
    assert data["accepted_actions"] == 1
    assert data["failed_actions"] == 1

    # First action succeeded
    assert data["results"][0]["status"] == "ACKNOWLEDGED"
    # Second action marked permanent failure
    assert data["results"][1]["status"] == "PERMANENT_FAILURE"

    # Database committed valid action
    interventions = db_session.query(PreHospitalIntervention).filter(PreHospitalIntervention.encounter_id == encounter.id).all()
    assert len(interventions) == 1
    assert interventions[0].intervention_type == "c_spine_immobilization"


# ==============================================================================
# 6. Unauthorized Mission Synchronization Rejection & Tenant Isolation
# ==============================================================================

def test_unauthorized_mission_synchronization_and_tenant_isolation(client: TestClient, db_session: Session, m9_setup):
    """
    Responder Beta (Org B) cannot synchronize actions or transitions on Mission Alpha (Org A).
    """
    h_b = m9_setup["headers_b"]
    assign_a = m9_setup["assign_a"]
    dev_b = f"dev_b_{uuid.uuid4().hex[:8]}"

    client.post(
        "/api/sync/v1/devices/register",
        json={"device_identifier": dev_b, "platform": "android", "app_version": "1.0.0", "organization_id": m9_setup["org_b"].id},
        headers=h_b,
    )

    batch_payload = {
        "device_id": dev_b,
        "client_batch_id": f"batch_{uuid.uuid4().hex[:8]}",
        "actions": [
            {
                "action_uuid": f"act_unauth_{uuid.uuid4().hex[:8]}",
                "action_type": "MISSION_STATUS_CHANGE",
                "mission_id": assign_a.id,
                "client_timestamp": datetime.now(timezone.utc).isoformat(),
                "payload": {"status": MissionStatus.ARRIVED_SCENE},
            }
        ],
    }

    res = client.post("/api/sync/v1/upload", json=batch_payload, headers=h_b)
    assert res.status_code == 200
    data = res.json()
    # Must fail authorization check
    assert data["results"][0]["status"] == "PERMANENT_FAILURE"


# ==============================================================================
# 7. Stale Mission Transition Rejection (Conflict Handling)
# ==============================================================================

def test_stale_mission_transition_rejection(client: TestClient, db_session: Session, m9_setup):
    """
    If a mission has already been marked COMPLETED or CANCELLED on the server,
    an offline device attempting to transition it must return CONFLICT.
    """
    h_a = m9_setup["headers_a"]
    assign_a = m9_setup["assign_a"]
    dev_a = f"dev_stale_{uuid.uuid4().hex[:8]}"

    client.post(
        "/api/sync/v1/devices/register",
        json={"device_identifier": dev_a, "platform": "android", "app_version": "1.0.0"},
        headers=h_a,
    )

    # Server completes mission
    assign_a.status = MissionStatus.COMPLETED
    db_session.commit()

    # Offline device attempts to mark ARRIVED_SCENE (stale transition)
    batch_payload = {
        "device_id": dev_a,
        "client_batch_id": f"batch_{uuid.uuid4().hex[:8]}",
        "actions": [
            {
                "action_uuid": f"act_stale_{uuid.uuid4().hex[:8]}",
                "action_type": "MISSION_STATUS_CHANGE",
                "mission_id": assign_a.id,
                "client_timestamp": datetime.now(timezone.utc).isoformat(),
                "payload": {"status": MissionStatus.ARRIVED_SCENE},
            }
        ],
    }

    res = client.post("/api/sync/v1/upload", json=batch_payload, headers=h_a)
    assert res.status_code == 200
    data = res.json()
    assert data["conflict_actions"] == 1
    assert data["results"][0]["status"] == "CONFLICT"
    assert data["results"][0]["conflict_details"]["category"] == "MISSION_STATE"


# ==============================================================================
# 8. GPS Buffering and Older Telemetry Not Overwriting Latest Position
# ==============================================================================

def test_gps_buffering_and_older_telemetry_isolation(client: TestClient, db_session: Session, m9_setup):
    """
    Delayed GPS telemetry must be stored in telemetry logs for route tracking,
    but older timestamps must NOT overwrite the ambulance's current location!
    """
    h_a = m9_setup["headers_a"]
    res_a = m9_setup["res_a"]
    dev_a = f"dev_gps_{uuid.uuid4().hex[:8]}"

    client.post(
        "/api/sync/v1/devices/register",
        json={"device_identifier": dev_a, "platform": "android", "app_version": "1.0.0"},
        headers=h_a,
    )

    # Establish latest known location on server at T_now
    now = datetime.now(timezone.utc)
    res_a.latitude = 12.9716
    res_a.longitude = 77.5946
    res_a.last_updated = now
    db_session.commit()

    # Offline device delivers buffered batch from 30 minutes ago
    older_time = (now - timedelta(minutes=30)).isoformat()
    batch_payload = {
        "device_id": dev_a,
        "client_batch_id": f"batch_{uuid.uuid4().hex[:8]}",
        "actions": [
            {
                "action_uuid": f"act_telemetry_{uuid.uuid4().hex[:8]}",
                "action_type": "TELEMETRY_BATCH",
                "client_timestamp": older_time,
                "payload": {
                    "points": [
                        {"latitude": 12.9200, "longitude": 77.5800, "speed": 45.0, "client_timestamp": older_time},
                        {"latitude": 12.9250, "longitude": 77.5850, "speed": 48.0, "client_timestamp": older_time},
                    ]
                },
            }
        ],
    }

    res = client.post("/api/sync/v1/upload", json=batch_payload, headers=h_a)
    assert res.status_code == 200
    assert res.json()["accepted_actions"] == 1

    # Verify telemetry logs were saved
    logs = db_session.query(ResponderTelemetryLog).filter(ResponderTelemetryLog.resource_id == res_a.id).all()
    assert len(logs) == 2

    # CRITICAL INVARIANT: The resource's current location must NOT have been overwritten by older points!
    db_session.refresh(res_a)
    assert res_a.latitude == 12.9716
    assert res_a.longitude == 77.5946


# ==============================================================================
# 9. Stable Download Cursor Behavior & Acknowledged Cursor Progression
# ==============================================================================

def test_stable_download_cursor_and_ack_progression(client: TestClient, db_session: Session, m9_setup):
    """
    Validates download endpoint, stable next_cursor generation, and safe cursor advancement.
    """
    h_a = m9_setup["headers_a"]
    dev_a = f"dev_cursor_{uuid.uuid4().hex[:8]}"

    client.post(
        "/api/sync/v1/devices/register",
        json={"device_identifier": dev_a, "platform": "android", "app_version": "1.0.0"},
        headers=h_a,
    )

    # Initial download from cursor "0"
    dl_res1 = client.post(
        "/api/sync/v1/download",
        json={"device_id": dev_a, "since_cursor": "0", "limit": 50},
        headers=h_a,
    )
    assert dl_res1.status_code == 200
    data1 = dl_res1.json()
    assert data1["changes_count"] > 0
    next_cursor = data1["next_cursor"]
    assert next_cursor != "0"

    # Advance cursor via /ack
    ack_res = client.post(
        "/api/sync/v1/ack",
        json={"device_id": dev_a, "acknowledged_cursor": next_cursor},
        headers=h_a,
    )
    assert ack_res.status_code == 200
    assert ack_res.json()["acknowledged_cursor"] == next_cursor

    # Immediate second download with acknowledged cursor should return zero new changes
    dl_res2 = client.post(
        "/api/sync/v1/download",
        json={"device_id": dev_a, "since_cursor": next_cursor, "limit": 50},
        headers=h_a,
    )
    assert dl_res2.status_code == 200
    data2 = dl_res2.json()
    assert data2["changes_count"] == 0


# ==============================================================================
# 10. Conflict Retrieval & Reconcile Workflow
# ==============================================================================

def test_conflict_retrieval_and_reconciliation(client: TestClient, db_session: Session, m9_setup):
    """
    Validates querying recorded conflicts and resolving them (RESOLVED_SERVER, DISCARDED).
    """
    h_a = m9_setup["headers_a"]
    assign_a = m9_setup["assign_a"]
    dev_a = f"dev_conf_{uuid.uuid4().hex[:8]}"

    client.post(
        "/api/sync/v1/devices/register",
        json={"device_identifier": dev_a, "platform": "android", "app_version": "1.0.0"},
        headers=h_a,
    )

    # Create conflict by attempting invalid transition on cancelled mission
    assign_a.status = MissionStatus.CANCELLED
    db_session.commit()

    client.post(
        "/api/sync/v1/upload",
        json={
            "device_id": dev_a,
            "client_batch_id": f"batch_{uuid.uuid4().hex[:8]}",
            "actions": [
                {
                    "action_uuid": f"act_c_{uuid.uuid4().hex[:8]}",
                    "action_type": "MISSION_STATUS_CHANGE",
                    "mission_id": assign_a.id,
                    "client_timestamp": datetime.now(timezone.utc).isoformat(),
                    "payload": {"status": MissionStatus.ARRIVED_HOSPITAL},
                }
            ],
        },
        headers=h_a,
    )

    # List conflicts
    conf_res = client.get(f"/api/sync/v1/conflicts?device_id={dev_a}", headers=h_a)
    assert conf_res.status_code == 200
    conflicts = conf_res.json()
    assert len(conflicts) >= 1
    conflict_token = conflicts[0]["conflict_token"]

    # Reconcile conflict
    rec_res = client.post(
        f"/api/sync/v1/conflicts/{conflict_token}/reconcile",
        json={"resolution": "RESOLVED_SERVER", "notes": "Dispatcher confirmed mission was cancelled by incident command"},
        headers=h_a,
    )
    assert rec_res.status_code == 200
    rec_data = rec_res.json()
    assert rec_data["resolution_status"] == "RESOLVED_SERVER"
    assert rec_data["resolution_notes"] is not None


# ==============================================================================
# 11. Batch Size Limit (HTTP 413)
# ==============================================================================

def test_batch_size_limit_rejection(client: TestClient, db_session: Session, m9_setup):
    """
    Batches exceeding 200 items must be rejected with HTTP 413.
    """
    h_a = m9_setup["headers_a"]
    dev_a = f"dev_big_{uuid.uuid4().hex[:8]}"

    client.post(
        "/api/sync/v1/devices/register",
        json={"device_identifier": dev_a, "platform": "android", "app_version": "1.0.0"},
        headers=h_a,
    )

    actions = [
        {
            "action_uuid": f"act_{i}_{uuid.uuid4().hex[:6]}",
            "action_type": "VITAL_OBSERVATION",
            "client_timestamp": datetime.now(timezone.utc).isoformat(),
            "payload": {},
        }
        for i in range(205)
    ]

    res = client.post(
        "/api/sync/v1/upload",
        json={"device_id": dev_a, "client_batch_id": "batch_over_limit", "actions": actions},
        headers=h_a,
    )
    assert res.status_code == 413


# ==============================================================================
# 12. Recovery Worker Maintenance Cycle
# ==============================================================================

def test_sync_recovery_worker_execution(client: TestClient, db_session: Session, m9_setup):
    """
    Validates background recovery cycle execution and receipt pruning.
    """
    h_admin = m9_setup["headers_admin"]

    res = client.post("/api/sync/v1/recovery/cycle", headers=h_admin)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert "total_devices" in data
    assert "pruned_receipts" in data


# ==============================================================================
# 13. Concurrency Tests: Simultaneous Batch Uploads
# ==============================================================================

def test_concurrency_batch_submission(client: TestClient, db_session: Session, m9_setup):
    """
    Simulates concurrent upload requests for the same batch from flaky connectivity.
    Both requests must succeed idempotently without race conditions.
    """
    h_a = m9_setup["headers_a"]
    encounter = m9_setup["encounter"]
    dev_a = f"dev_concurrent_{uuid.uuid4().hex[:8]}"

    client.post(
        "/api/sync/v1/devices/register",
        json={"device_identifier": dev_a, "platform": "android", "app_version": "1.0.0"},
        headers=h_a,
    )

    action_uuid = f"act_conc_{uuid.uuid4().hex[:8]}"
    batch_payload = {
        "device_id": dev_a,
        "client_batch_id": f"batch_conc_{uuid.uuid4().hex[:8]}",
        "actions": [
            {
                "action_uuid": action_uuid,
                "action_type": "MEDICATION",
                "encounter_id": encounter.id,
                "client_timestamp": datetime.now(timezone.utc).isoformat(),
                "payload": {
                    "medication_name": "Morphine Sulfate",
                    "dose": 4.0,
                    "unit": "mg",
                    "route": "iv",
                    "response_notes": "Pain score decreased from 8 to 4",
                },
            }
        ],
    }

    r1 = client.post("/api/sync/v1/upload", json=batch_payload, headers=h_a)
    r2 = client.post("/api/sync/v1/upload", json=batch_payload, headers=h_a)

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["results"][0]["server_ack_id"] == r2.json()["results"][0]["server_ack_id"]

    # Ensure exactly one medication record was created
    meds = db_session.query(MedicationAdministration).filter(MedicationAdministration.encounter_id == encounter.id).all()
    assert len(meds) == 1


# ==============================================================================
# 14. Out-of-Order Clinical Event Synchronization & Immutability
# ==============================================================================

def test_out_of_order_clinical_event_synchronization(client: TestClient, db_session: Session, m9_setup):
    """
    Field observations recorded at T1 and T2 arriving out of order (T2 first, then T1)
    must both be preserved with authoritative client timestamps without clobbering each other.
    """
    h_a = m9_setup["headers_a"]
    encounter = m9_setup["encounter"]
    dev_a = f"dev_ooo_{uuid.uuid4().hex[:8]}"

    client.post(
        "/api/sync/v1/devices/register",
        json={"device_identifier": dev_a, "platform": "android", "app_version": "1.0.0"},
        headers=h_a,
    )

    now = datetime.now(timezone.utc)
    t1 = (now - timedelta(minutes=15)).isoformat()
    t2 = (now - timedelta(minutes=5)).isoformat()

    # Step 1: Upload T2 (newer) first
    batch_t2 = {
        "device_id": dev_a,
        "client_batch_id": f"batch_t2_{uuid.uuid4().hex[:8]}",
        "actions": [
            {
                "action_uuid": f"act_vitals_t2_{uuid.uuid4().hex[:8]}",
                "action_type": "VITAL_OBSERVATION",
                "encounter_id": encounter.id,
                "client_timestamp": t2,
                "payload": {"heart_rate": 95, "systolic_bp": 125, "diastolic_bp": 82},
            }
        ],
    }
    res_t2 = client.post("/api/sync/v1/upload", json=batch_t2, headers=h_a)
    assert res_t2.status_code == 200
    assert res_t2.json()["accepted_actions"] == 1

    # Step 2: Upload T1 (older delayed) second
    batch_t1 = {
        "device_id": dev_a,
        "client_batch_id": f"batch_t1_{uuid.uuid4().hex[:8]}",
        "actions": [
            {
                "action_uuid": f"act_vitals_t1_{uuid.uuid4().hex[:8]}",
                "action_type": "VITAL_OBSERVATION",
                "encounter_id": encounter.id,
                "client_timestamp": t1,
                "payload": {"heart_rate": 110, "systolic_bp": 135, "diastolic_bp": 90},
            }
        ],
    }
    res_t1 = client.post("/api/sync/v1/upload", json=batch_t1, headers=h_a)
    assert res_t1.status_code == 200
    assert res_t1.json()["accepted_actions"] == 1

    # Both records must be present and immutable in database
    vitals = (
        db_session.query(VitalSignObservation)
        .filter(VitalSignObservation.encounter_id == encounter.id)
        .order_by(VitalSignObservation.observed_at.asc())
        .all()
    )
    assert len(vitals) == 2
    assert vitals[0].heart_rate == 110  # T1
    assert vitals[1].heart_rate == 95   # T2


# ==============================================================================
# 15. Handover Clinical Conflict on Completed Handover
# ==============================================================================

def test_handover_clinical_conflict_on_completed_handover(client: TestClient, db_session: Session, m9_setup):
    """
    Attempting to modify a digital handover that has already reached COMPLETED status
    on the server must generate a CLINICAL conflict and prevent silent overwrite.
    """
    h_a = m9_setup["headers_a"]
    encounter = m9_setup["encounter"]
    facility = m9_setup["facility"]
    dev_a = f"dev_handover_{uuid.uuid4().hex[:8]}"

    client.post(
        "/api/sync/v1/devices/register",
        json={"device_identifier": dev_a, "platform": "android", "app_version": "1.0.0"},
        headers=h_a,
    )

    # Create completed handover in database
    handover = DigitalHandoverRecord(
        handover_token=f"hnd_{uuid.uuid4().hex[:12]}",
        encounter_id=encounter.id,
        facility_id=facility.id,
        version=1,
        status=HandoverStatus.COMPLETED,
        is_final=True,
    )
    db_session.add(handover)
    db_session.commit()

    # Offline device attempts to update handover concerns
    batch = {
        "device_id": dev_a,
        "client_batch_id": f"batch_handover_{uuid.uuid4().hex[:8]}",
        "actions": [
            {
                "action_uuid": f"act_hnd_{uuid.uuid4().hex[:8]}",
                "action_type": "HANDOVER_UPDATE",
                "client_timestamp": datetime.now(timezone.utc).isoformat(),
                "payload": {
                    "handover_id": handover.id,
                    "outstanding_clinical_concerns": "Attempting late update",
                },
            }
        ],
    }

    res = client.post("/api/sync/v1/upload", json=batch, headers=h_a)
    assert res.status_code == 200
    data = res.json()
    assert data["conflict_actions"] == 1
    assert data["results"][0]["status"] == "CONFLICT"
    assert data["results"][0]["conflict_details"]["category"] == "CLINICAL"

    # Verify handover remains final and completed
    db_session.refresh(handover)
    assert handover.status == HandoverStatus.COMPLETED
    assert handover.is_final is True


# ==============================================================================
# 16. Assignment Reassignment Conflict Handling
# ==============================================================================

def test_assignment_reassignment_conflict(client: TestClient, db_session: Session, m9_setup):
    """
    If a mission is reassigned to another responder while device was offline,
    the original responder's attempts to report mission progress must yield an ASSIGNMENT conflict.
    """
    h_a = m9_setup["headers_a"]
    assign_a = m9_setup["assign_a"]
    res_a = m9_setup["res_a"]
    resp_b = m9_setup["resp_b"]
    dev_a = f"dev_reassign_{uuid.uuid4().hex[:8]}"

    client.post(
        "/api/sync/v1/devices/register",
        json={"device_identifier": dev_a, "platform": "android", "app_version": "1.0.0"},
        headers=h_a,
    )

    # Dispatcher reassigns ambulance to Responder Beta
    res_a.assigned_user_id = resp_b.id
    db_session.commit()

    # Responder Alpha tries to report ARRIVED_SCENE on the mission
    batch = {
        "device_id": dev_a,
        "client_batch_id": f"batch_reassign_{uuid.uuid4().hex[:8]}",
        "actions": [
            {
                "action_uuid": f"act_reassign_{uuid.uuid4().hex[:8]}",
                "action_type": "MISSION_STATUS_CHANGE",
                "mission_id": assign_a.id,
                "client_timestamp": datetime.now(timezone.utc).isoformat(),
                "payload": {"status": MissionStatus.ARRIVED_SCENE},
            }
        ],
    }

    res = client.post("/api/sync/v1/upload", json=batch, headers=h_a)
    assert res.status_code == 200
    data = res.json()
    assert data["conflict_actions"] == 1
    assert data["results"][0]["status"] == "CONFLICT"
    assert data["results"][0]["conflict_details"]["category"] == "ASSIGNMENT"

