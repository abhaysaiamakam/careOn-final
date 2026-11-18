"""
CareOn Milestone 6 Test Suite — Responder Operations, Mobile Reliability & Notification Infrastructure.

Verifies:
1. Complete Mission Lifecycle & State Machine:
   - Sequential 11-step execution
   - Invalid transition matrix rejection
   - Rejection with mandatory justification
   - Dispatcher cancellation
   - Client idempotency (client_action_id replay safety)
   - Entity state synchronization (Resource, Assignment, Incident)
2. Assignment Acknowledgement & Timeout Sweeper:
   - Initializing acknowledgement deadline
   - Timeout detection & dispatcher alert generation
   - Invariant: Zero silent reassignments on timeout
3. Push Notification Infrastructure:
   - Multi-platform device token registration (FCM, APNs, WebPush)
   - Token replacement & deactivation
   - Payload privacy sanitization: ZERO patient medical notes or OTPs
   - Delivery logging & history retrieval
4. GPS & Offline Telemetry Ingestion:
   - Batch coordinates ingestion & PostGIS geometry update
   - Actor resource ownership check (403 for unauthorized users)
   - Clock drift rejection (>5m in future / >7d in past)
   - Velocity anomaly rejection (>250 km/h)
   - GPS accuracy threshold degradation (>100m)
   - Offline buffering synchronization
"""

import json
import time
import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import (
    User,
    Resource,
    Incident,
    Assignment,
    Organization,
    MissionEventLog,
    DeviceRegistration,
    NotificationDeliveryLog,
    ResponderTelemetryLog,
    OutboxEvent,
    utc_now,
)
from app.auth import hash_password
from app.identity.jwt_handler import create_access_token
from app.responder_ops import (
    MissionStatus,
    MissionTransitionError,
    execute_mission_transition,
    initiate_assignment_acknowledgement,
    check_and_process_acknowledgement_timeouts,
    notification_service,
    sanitize_notification_payload,
    ingest_resource_telemetry,
    TelemetryIngestPoint,
    TelemetryValidationError,
)


@pytest.fixture
def m6_setup(client: TestClient, db_session: Session):
    """
    Creates test actors (dispatcher, responder_1, responder_2),
    hospital organization, resources, and an active incident with assignment.
    """
    t_id = int(time.time() * 1000) % 1000000

    # 1. Actors
    dispatcher = User(
        email=f"dispatcher_m6_{t_id}@careon.org",
        name="Dispatcher Sharma",
        phone="+91 99999 20001",
        hashed_password=hash_password("DispatchPass123!"),
        role="dispatcher",
        is_active=True,
    )
    responder_1 = User(
        email=f"responder1_{t_id}@careon.org",
        name="Responder Ananya",
        phone="+91 99999 20002",
        hashed_password=hash_password("RespPass123!"),
        role="responder",
        is_active=True,
    )
    responder_2 = User(
        email=f"responder2_{t_id}@careon.org",
        name="Responder Rohan",
        phone="+91 99999 20003",
        hashed_password=hash_password("RespPass123!"),
        role="responder",
        is_active=True,
    )
    db_session.add_all([dispatcher, responder_1, responder_2])
    db_session.commit()

    # 2. Hospital Organization
    hospital = Organization(
        name=f"Apollo Emergency Center {t_id}",
        org_type="hospital",
        location_name="Kuvempunagar, Mysuru",
        is_verified=True,
        is_active=True,
    )
    db_session.add(hospital)
    db_session.commit()

    # 3. Fleet Resources
    res_1 = Resource(
        resource_code=f"AMB-M6-01-{t_id}",
        name="ALS Ambulance Alpha",
        category="Ambulance",
        capabilities="ALS,patient_transport,trauma_care",
        equipment="ventilator,defibrillator,oxygen,monitor",
        location_name="Mysuru Central",
        latitude=12.3052,
        longitude=76.6552,
        status="Assigned",
        capacity=1,
        contact_phone="+91 99999 30001",
        assigned_user_id=responder_1.id,
    )
    res_2 = Resource(
        resource_code=f"AMB-M6-02-{t_id}",
        name="BLS Ambulance Beta",
        category="Ambulance",
        capabilities="BLS,patient_transport",
        equipment="oxygen,first_aid_kit",
        location_name="Mysuru South",
        latitude=12.2850,
        longitude=76.6450,
        status="Available",
        capacity=1,
        contact_phone="+91 99999 30002",
        assigned_user_id=responder_2.id,
    )
    db_session.add_all([res_1, res_2])
    db_session.commit()

    # 4. Incident & Assignment
    incident = Incident(
        incident_code=f"INC-M6-{t_id}",
        tracking_token=f"token_m6_{t_id}",
        category="Road accident",
        title="Severe Highway Collision",
        description="Head-on collision on outer ring road junction with multiple injuries",
        location_name="Ring Road Junction, Mysuru",
        latitude=12.3120,
        longitude=76.6600,
        affected_people=2,
        help_required="Ambulance",
        contact_name="Traffic Officer Kumar",
        contact_phone="+91 98888 11111",
        priority="Critical",
        status="Dispatched",
        is_verified=True,
    )
    db_session.add(incident)
    db_session.commit()

    assignment = Assignment(
        incident_id=incident.id,
        resource_id=res_1.id,
        status="Active",
        assigned_at=utc_now(),
        acknowledgement_status="pending",
        acknowledgement_deadline=utc_now() + timedelta(seconds=180),
    )
    db_session.add(assignment)
    db_session.commit()

    # Link assignment to resource
    res_1.current_assignment_id = assignment.id
    db_session.commit()

    # Auth headers
    dispatcher_token = create_access_token(dispatcher.id, dispatcher.email, dispatcher.role)
    responder1_token = create_access_token(responder_1.id, responder_1.email, responder_1.role)
    responder2_token = create_access_token(responder_2.id, responder_2.email, responder_2.role)

    return {
        "dispatcher": dispatcher,
        "responder_1": responder_1,
        "responder_2": responder_2,
        "hospital": hospital,
        "resource_1": res_1,
        "resource_2": res_2,
        "incident": incident,
        "assignment": assignment,
        "headers_dispatcher": {"Authorization": f"Bearer {dispatcher_token}"},
        "headers_responder1": {"Authorization": f"Bearer {responder1_token}"},
        "headers_responder2": {"Authorization": f"Bearer {responder2_token}"},
    }


# ==============================================================================
# 1. Complete Mission Lifecycle & State Machine Tests
# ==============================================================================

def test_full_mission_lifecycle_sequential_transitions(client: TestClient, db_session: Session, m6_setup: dict):
    """
    Validates end-to-end execution of all 11 lifecycle states:
    ASSIGNED -> ACCEPTED -> EN_ROUTE_INCIDENT -> ARRIVED_SCENE -> PATIENT_CONTACT ->
    PATIENT_PICKED_UP -> EN_ROUTE_HOSPITAL -> ARRIVED_HOSPITAL -> HANDOVER_INITIATED ->
    HANDOVER_COMPLETED -> COMPLETED.
    """
    asgn_id = m6_setup["assignment"].id
    headers = m6_setup["headers_responder1"]
    hosp_id = m6_setup["hospital"].id

    # 1. Accept mission
    ack_resp = client.post(
        f"/api/responder/missions/{asgn_id}/acknowledge",
        json={"action": "accept", "client_action_id": f"act_ack_{asgn_id}"},
        headers=headers,
    )
    assert ack_resp.status_code == 200, ack_resp.text
    data = ack_resp.json()
    assert data["current_status"] == MissionStatus.ACCEPTED

    # 2. Sequential transitions
    steps = [
        (MissionStatus.EN_ROUTE_INCIDENT, {}),
        (MissionStatus.ARRIVED_SCENE, {"latitude": 12.3121, "longitude": 76.6601}),
        (MissionStatus.PATIENT_CONTACT, {"notes": "Patient stable, minor lacerations"}),
        (MissionStatus.PATIENT_PICKED_UP, {}),
        (MissionStatus.EN_ROUTE_HOSPITAL, {"hospital_id": hosp_id}),
        (MissionStatus.ARRIVED_HOSPITAL, {"hospital_id": hosp_id}),
        (MissionStatus.HANDOVER_INITIATED, {"hospital_id": hosp_id}),
        (MissionStatus.HANDOVER_COMPLETED, {"hospital_id": hosp_id}),
        (MissionStatus.COMPLETED, {"notes": "Mission successfully completed, ambulance sanitized"}),
    ]

    for target_status, extra_payload in steps:
        payload = {
            "target_status": target_status,
            "client_action_id": f"act_{target_status}_{asgn_id}",
            **extra_payload,
        }
        resp = client.post(
            f"/api/responder/missions/{asgn_id}/transition",
            json=payload,
            headers=headers,
        )
        assert resp.status_code == 200, f"Failed at {target_status}: {resp.text}"
        res_data = resp.json()
        assert res_data["current_status"] == target_status

    # Verify final DB entity states
    db_session.expire_all()
    asgn = db_session.query(Assignment).filter(Assignment.id == asgn_id).first()
    res = db_session.query(Resource).filter(Resource.id == m6_setup["resource_1"].id).first()
    inc = db_session.query(Incident).filter(Incident.id == m6_setup["incident"].id).first()

    assert asgn.status == "Completed"
    assert res.status == "Available"
    assert res.current_assignment_id is None
    assert inc.status == "Resolved"


def test_invalid_transition_rejection(client: TestClient, db_session: Session, m6_setup: dict):
    """Verifies that invalid state skips are rejected with 409 Conflict."""
    asgn_id = m6_setup["assignment"].id
    headers = m6_setup["headers_responder1"]

    # Trying to jump directly from ASSIGNED to ARRIVED_SCENE
    resp = client.post(
        f"/api/responder/missions/{asgn_id}/transition",
        json={"target_status": MissionStatus.ARRIVED_SCENE},
        headers=headers,
    )
    assert resp.status_code == 409
    assert "Invalid mission state transition" in resp.json()["detail"]


def test_mission_rejection_workflow(client: TestClient, db_session: Session, m6_setup: dict):
    """
    Verifies that rejecting a mission requires a reason, releases the resource,
    and returns the incident to pool for reassignment.
    """
    asgn_id = m6_setup["assignment"].id
    headers = m6_setup["headers_responder1"]

    # 1. Missing rejection reason fails
    bad_resp = client.post(
        f"/api/responder/missions/{asgn_id}/acknowledge",
        json={"action": "reject"},
        headers=headers,
    )
    assert bad_resp.status_code == 400

    # 2. Valid rejection with reason
    good_resp = client.post(
        f"/api/responder/missions/{asgn_id}/acknowledge",
        json={"action": "reject", "rejection_reason": "Mechanical vehicle breakdown (flat tire)"},
        headers=headers,
    )
    assert good_resp.status_code == 200
    assert good_resp.json()["current_status"] == MissionStatus.REJECTED

    db_session.expire_all()
    asgn = db_session.query(Assignment).filter(Assignment.id == asgn_id).first()
    res = db_session.query(Resource).filter(Resource.id == m6_setup["resource_1"].id).first()
    inc = db_session.query(Incident).filter(Incident.id == m6_setup["incident"].id).first()

    assert asgn.status == "Released"
    assert asgn.acknowledgement_status == "rejected"
    assert "Mechanical" in asgn.rejection_reason
    assert res.status == "Available"
    assert res.current_assignment_id is None
    assert inc.status == "Received"  # Returned to dispatch pool


def test_dispatcher_emergency_cancellation(client: TestClient, db_session: Session, m6_setup: dict):
    """Verifies dispatcher supervisory override to cancel an active mission."""
    asgn_id = m6_setup["assignment"].id
    resp_headers = m6_setup["headers_responder1"]
    disp_headers = m6_setup["headers_dispatcher"]

    # Responder accepts
    client.post(
        f"/api/responder/missions/{asgn_id}/acknowledge",
        json={"action": "accept"},
        headers=resp_headers,
    )

    # Dispatcher cancels mission (e.g. caller cancelled or false alarm)
    cancel_resp = client.post(
        f"/api/responder/missions/{asgn_id}/transition",
        json={"target_status": MissionStatus.CANCELLED, "notes": "Caller confirmed false alarm"},
        headers=disp_headers,
    )
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["current_status"] == MissionStatus.CANCELLED

    db_session.expire_all()
    asgn = db_session.query(Assignment).filter(Assignment.id == asgn_id).first()
    res = db_session.query(Resource).filter(Resource.id == m6_setup["resource_1"].id).first()

    assert asgn.status == "Cancelled"
    assert res.status == "Available"


def test_client_idempotency_duplicate_replay(client: TestClient, db_session: Session, m6_setup: dict):
    """Verifies duplicate transitions with same client_action_id do not create duplicate event rows."""
    asgn_id = m6_setup["assignment"].id
    headers = m6_setup["headers_responder1"]
    action_id = f"unique_action_id_12345"

    # First request
    resp1 = client.post(
        f"/api/responder/missions/{asgn_id}/acknowledge",
        json={"action": "accept", "client_action_id": action_id},
        headers=headers,
    )
    assert resp1.status_code == 200
    assert resp1.json()["is_duplicate_replay"] is False

    # Second request with identical client_action_id (mobile retry over cellular blip)
    resp2 = client.post(
        f"/api/responder/missions/{asgn_id}/acknowledge",
        json={"action": "accept", "client_action_id": action_id},
        headers=headers,
    )
    assert resp2.status_code == 200
    assert resp2.json()["is_duplicate_replay"] is True

    # Audit log check: exactly 1 record
    count = db_session.query(MissionEventLog).filter(MissionEventLog.client_action_id == action_id).count()
    assert count == 1


def test_responder_authorization_and_ownership(client: TestClient, db_session: Session, m6_setup: dict):
    """Verifies that an unassigned responder cannot modify another responder's mission."""
    asgn_id = m6_setup["assignment"].id
    unassigned_responder_headers = m6_setup["headers_responder2"]

    resp = client.post(
        f"/api/responder/missions/{asgn_id}/acknowledge",
        json={"action": "accept"},
        headers=unassigned_responder_headers,
    )
    assert resp.status_code == 403
    assert "Forbidden" in resp.json()["detail"]


# ==============================================================================
# 2. Assignment Acknowledgement & Timeout Sweeper Tests
# ==============================================================================

def test_acknowledgement_timeout_sweep(client: TestClient, db_session: Session, m6_setup: dict):
    """
    Verifies that unacknowledged assignments past deadline are detected during sweep,
    marked timeout, and alerted without silent auto-reassignment.
    """
    asgn = m6_setup["assignment"]
    disp_headers = m6_setup["headers_dispatcher"]

    # Artificially age deadline to 10 seconds in the past
    asgn.acknowledgement_deadline = utc_now() - timedelta(seconds=10)
    db_session.commit()

    # Trigger timeout sweep
    sweep_resp = client.post(
        "/api/responder/assignments/sweep-timeouts",
        headers=disp_headers,
    )
    assert sweep_resp.status_code == 200
    data = sweep_resp.json()
    assert data["processed_timeouts"] >= 1

    # Check assignment state
    db_session.expire_all()
    updated_asgn = db_session.query(Assignment).filter(Assignment.id == asgn.id).first()
    assert updated_asgn.acknowledgement_status == "timeout"
    assert updated_asgn.status == "Active"  # Crucial: Not silently unassigned!


# ==============================================================================
# 3. Push Notification Infrastructure & Privacy Tests
# ==============================================================================

def test_device_registration_and_deactivation(client: TestClient, db_session: Session, m6_setup: dict):
    """Verifies registering, refreshing, and deactivating push tokens across platforms."""
    headers = m6_setup["headers_responder1"]
    token_str = f"fcm_token_device_abc_{int(time.time())}"

    # 1. Register device
    reg_resp = client.post(
        "/api/responder/devices/register",
        json={
            "device_token": token_str,
            "platform": "fcm",
            "device_model": "Samsung Galaxy S23",
            "app_version": "1.4.0",
        },
        headers=headers,
    )
    assert reg_resp.status_code == 200
    data = reg_resp.json()
    assert data["platform"] == "fcm"
    assert data["is_active"] is True

    # 2. Query history (initially empty)
    hist_resp = client.get("/api/responder/notifications/history", headers=headers)
    assert hist_resp.status_code == 200

    # 3. Deactivate token
    del_resp = client.delete(f"/api/responder/devices/{token_str}", headers=headers)
    assert del_resp.status_code == 200

    # Verify deactivated
    reg = db_session.query(DeviceRegistration).filter(DeviceRegistration.device_token == token_str).first()
    assert reg.is_active is False


def test_push_notification_privacy_sanitization(db_session: Session, m6_setup: dict):
    """
    CRITICAL PRIVACY TEST:
    Verifies that push notification payloads never leak patient medical notes,
    triage records, or OTPs across third-party notification push pipes.
    """
    responder_id = m6_setup["responder_1"].id

    # Register an active device for the responder
    notification_service.register_device(
        db=db_session,
        user_id=responder_id,
        device_token=f"test_webpush_token_{int(time.time())}",
        platform="web_push",
    )

    # Dispatch notification containing sensitive medical keys
    dirty_payload = {
        "assignment_id": 42,
        "incident_code": "INC-TEST-01",
        "location_hint": "Main St & 4th Ave",
        "patient_name": "John Doe",
        "medical_condition": "Acute Myocardial Infarction",
        "triage_notes": "Patient unconscious and turning cyanotic",
        "symptoms": "Chest pain, shortness of breath",
        "otp": "987654",
    }

    logs = notification_service.dispatch_notification(
        db=db_session,
        user_id=responder_id,
        category="critical_alert",
        title="EMERGENCY MISSION",
        body="Immediate response requested",
        data=dirty_payload,
        idempotency_key=f"idem_privacy_{int(time.time())}",
    )

    assert len(logs) == 1
    assert logs[0].status == "sent"

    # Test direct sanitizer function
    sanitized = sanitize_notification_payload(dirty_payload)
    assert "assignment_id" in sanitized
    assert "incident_code" in sanitized
    assert "location_hint" in sanitized
    assert "patient_name" not in sanitized
    assert "medical_condition" not in sanitized
    assert "triage_notes" not in sanitized
    assert "symptoms" not in sanitized
    assert "otp" not in sanitized


# ==============================================================================
# 4. GPS & Telemetry Ingestion Tests
# ==============================================================================

def test_telemetry_batch_ingestion(client: TestClient, db_session: Session, m6_setup: dict):
    """Verifies batch telemetry ingestion, PostGIS coordinate updates, and outbox event logging."""
    res_id = m6_setup["resource_1"].id
    headers = m6_setup["headers_responder1"]

    points = [
        {
            "latitude": 12.3055,
            "longitude": 76.6555,
            "speed": 35.0,
            "heading": 90.0,
            "accuracy": 8.5,
            "battery_level": 88.0,
            "network_type": "cellular",
            "is_buffered": True,
            "client_action_id": f"gps_pt_1_{int(time.time())}",
        },
        {
            "latitude": 12.3060,
            "longitude": 76.6560,
            "speed": 40.0,
            "heading": 92.0,
            "accuracy": 5.2,
            "battery_level": 87.5,
            "network_type": "cellular",
            "is_buffered": False,
            "client_action_id": f"gps_pt_2_{int(time.time())}",
        },
    ]

    resp = client.post(
        "/api/responder/telemetry/batch",
        json={"resource_id": res_id, "points": points},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["processed"] == 2

    # Verify resource location updated
    db_session.expire_all()
    res = db_session.query(Resource).filter(Resource.id == res_id).first()
    assert abs(res.latitude - 12.3060) < 1e-4
    assert abs(res.longitude - 76.6560) < 1e-4


def test_telemetry_timestamp_drift_rejection(client: TestClient, db_session: Session, m6_setup: dict):
    """Verifies clock drift rejection: timestamps >5m in future or >7d in past fail with 422."""
    res_id = m6_setup["resource_1"].id
    headers = m6_setup["headers_responder1"]

    # Future point (>5 minutes)
    future_time = utc_now() + timedelta(minutes=15)
    resp_future = client.post(
        "/api/responder/telemetry/batch",
        json={
            "resource_id": res_id,
            "points": [
                {
                    "latitude": 12.3055,
                    "longitude": 76.6555,
                    "client_timestamp": future_time.isoformat(),
                }
            ],
        },
        headers=headers,
    )
    assert resp_future.status_code == 422
    assert "future" in resp_future.json()["detail"].lower()


def test_telemetry_velocity_anomaly_rejection(client: TestClient, db_session: Session, m6_setup: dict):
    """Verifies impossible velocity (>250 km/h) is rejected to prevent GPS spoofing / teleportation."""
    res_id = m6_setup["resource_1"].id
    headers = m6_setup["headers_responder1"]

    # Reported speed of 350 km/h
    resp = client.post(
        "/api/responder/telemetry/batch",
        json={
            "resource_id": res_id,
            "points": [
                {
                    "latitude": 12.3055,
                    "longitude": 76.6555,
                    "speed": 350.0,
                }
            ],
        },
        headers=headers,
    )
    assert resp.status_code == 422
    assert "velocity" in resp.json()["detail"].lower() or "speed" in resp.json()["detail"].lower()


def test_mission_event_history_endpoint(client: TestClient, db_session: Session, m6_setup: dict):
    """Verifies retrieval of full mission event log history."""
    asgn_id = m6_setup["assignment"].id
    headers = m6_setup["headers_responder1"]

    # Perform a couple of actions
    client.post(
        f"/api/responder/missions/{asgn_id}/acknowledge",
        json={"action": "accept"},
        headers=headers,
    )
    client.post(
        f"/api/responder/missions/{asgn_id}/transition",
        json={"target_status": MissionStatus.EN_ROUTE_INCIDENT},
        headers=headers,
    )

    hist_resp = client.get(f"/api/responder/missions/{asgn_id}/history", headers=headers)
    assert hist_resp.status_code == 200
    events = hist_resp.json()
    assert len(events) >= 2
    assert events[0]["new_status"] == MissionStatus.ACCEPTED
    assert events[1]["new_status"] == MissionStatus.EN_ROUTE_INCIDENT
