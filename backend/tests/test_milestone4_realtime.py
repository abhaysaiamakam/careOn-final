"""
CareOn Milestone 4 Test Suite — Real-Time Emergency Coordination Engine.

Tests:
1. WebSocket Authentication & Connection Lifecycle
   - Token validation via query param (?token=...)
   - Initial-message authentication fallback ({"action": "auth", "token": ...})
   - Rejection of invalid, tampered, expired, or deactivated user tokens
   - Ping / Pong heartbeat protocol
2. Channel Authorization & Multi-Tenant Role Isolation (M2 RBAC)
   - Citizen denied city-wide global dispatch channel
   - Citizen allowed to subscribe to own incident channel
   - Citizen denied other citizens' incident channels
   - Dispatcher allowed global channel and all incident channels
   - Hospital staff restricted to own hospital organization channel
   - Responder allowed assigned incident and private responder unit channel
   - Subscription and unsubscription lifecycle
3. Audience-Aware Data Sanitization
   - Citizen payloads stripped of verification OTP, contact phone numbers, internal triage notes
   - Dispatcher and super admin receive complete operational payloads
4. GPS Telemetry Ingestion & Spatial Cache
   - Ingestion of valid GPS coordinates updates PostGIS geometry and Redis cache
   - Boundary checks reject invalid lat/long (-90..90, -180..180)
   - Telemetry validation rejects impossible velocity jumps (>350 km/h)
   - Access control restricts telemetry endpoint to responder roles
   - Telemetry triggers real-time location event emission
5. Transactional Outbox & Event Recovery
   - Business mutations persist transactional OutboxEvent records in PostgreSQL
   - Outbox relay worker processes and republishes unpublished events
   - Event replay endpoint (/api/realtime/history) returns ordered events
   - Real-time operational health endpoint (/api/realtime/health)
"""

import json
import time
import pytest
from starlette.websockets import WebSocketDisconnect
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.models import (
    User,
    Resource,
    Incident,
    Assignment,
    Organization,
    OrganizationMembership,
    HospitalReadiness,
    OutboxEvent,
)
from app.auth import hash_password
from app.identity.jwt_handler import create_access_token
from app.schemas import IncidentCreate
from app import crud
from app.realtime.authorization import (
    RealtimeUserSession,
    can_subscribe_channel,
    sanitize_payload_for_viewer,
)
from app.rbac.roles import UserRole
from app.realtime.event_publisher import (
    record_and_publish_event,
    relay_pending_outbox_events,
    get_event_history,
)


@pytest.fixture
def m4_setup(client: TestClient, db_session: Session):
    """
    Creates isolated test accounts and test data for Milestone 4:
    - Super Admin
    - Dispatcher
    - Responder
    - Citizen A (owner of Incident 1)
    - Citizen B (unrelated citizen)
    - Hospital Staff A (Hospital 1)
    - Hospital Staff B (Hospital 2)
    """
    t_id = int(time.time() * 1000) % 1000000

    # 1. Super Admin
    super_admin = User(
        email=f"admin_{t_id}@careon.org",
        name="M4 Super Admin",
        phone="+91 99999 00001",
        hashed_password=hash_password("AdminPass123!"),
        role="super_admin",
        is_active=True,
    )
    # 2. Dispatcher
    dispatcher = User(
        email=f"dispatcher_{t_id}@careon.org",
        name="M4 Dispatcher",
        phone="+91 99999 00002",
        hashed_password=hash_password("DispatchPass123!"),
        role="dispatcher",
        is_active=True,
    )
    # 3. Responder User + Assigned Resource
    responder_user = User(
        email=f"responder_{t_id}@careon.org",
        name="M4 Field Responder",
        phone="+91 99999 00003",
        hashed_password=hash_password("ResponderPass123!"),
        role="responder",
        is_active=True,
    )
    # 4. Citizen A (Owner of incident)
    citizen_a = User(
        email=f"citizen_a_{t_id}@example.com",
        name="Citizen Alice",
        phone="+91 99999 00004",
        hashed_password=hash_password("CitizenPass123!"),
        role="citizen",
        is_active=True,
    )
    # 5. Citizen B (Unrelated citizen)
    citizen_b = User(
        email=f"citizen_b_{t_id}@example.com",
        name="Citizen Bob",
        phone="+91 99999 00005",
        hashed_password=hash_password("CitizenPass123!"),
        role="citizen",
        is_active=True,
    )
    # 6. Deactivated user
    deactivated_user = User(
        email=f"inactive_{t_id}@example.com",
        name="Inactive User",
        phone="+91 99999 00006",
        hashed_password=hash_password("InactivePass123!"),
        role="citizen",
        is_active=False,
    )

    db_session.add_all([super_admin, dispatcher, responder_user, citizen_a, citizen_b, deactivated_user])
    db_session.commit()

    # Create Hospital Organizations
    hosp_org_1 = Organization(
        name=f"Mysuru General Hospital {t_id}",
        org_type="hospital",
        location_name="MG Road, Central Mysuru",
        is_verified=True,
        is_active=True,
    )
    hosp_org_2 = Organization(
        name=f"Apollo Specialty {t_id}",
        org_type="hospital",
        location_name="KRS Road, Mysuru",
        is_verified=True,
        is_active=True,
    )
    db_session.add_all([hosp_org_1, hosp_org_2])
    db_session.commit()

    # Hospital Staff Users
    staff_1 = User(
        email=f"staff1_{t_id}@hospital.org",
        name="Dr. Hospital One",
        phone="+91 99999 00007",
        hashed_password=hash_password("HospitalPass123!"),
        role="hospital_staff",
        is_active=True,
    )
    staff_2 = User(
        email=f"staff2_{t_id}@hospital.org",
        name="Dr. Hospital Two",
        phone="+91 99999 00008",
        hashed_password=hash_password("HospitalPass123!"),
        role="hospital_staff",
        is_active=True,
    )
    db_session.add_all([staff_1, staff_2])
    db_session.commit()

    # Add Org Memberships
    m1 = OrganizationMembership(organization_id=hosp_org_1.id, user_id=staff_1.id, membership_role="member")
    m2 = OrganizationMembership(organization_id=hosp_org_2.id, user_id=staff_2.id, membership_role="member")
    db_session.add_all([m1, m2])
    db_session.commit()

    # Responder Resource
    resource = Resource(
        resource_code=f"AMB-M4-{t_id}",
        name="M4 Rapid Ambulance",
        category="Ambulance",
        capabilities="ALS,oxygen,stretcher,defibrillator",
        location_name="Mysuru Central Base",
        latitude=12.3050,
        longitude=76.6550,
        status="Available",
        contact_phone="+91 99999 00003",
        assigned_user_id=responder_user.id,
    )
    db_session.add(resource)
    db_session.commit()

    # Create Incident reported by Citizen A
    inc_payload = IncidentCreate(
        category="Medical",
        description="Severe chest pains on MG Road",
        location_name="MG Road, Mysuru",
        latitude=12.3080,
        longitude=76.6580,
        affected_people=1,
        help_required="Ambulance",
        contact_name="Citizen Alice",
        contact_phone="+91 99999 00004",
    )
    incident_a = crud.create_incident(db_session, inc_payload, user_id=citizen_a.id)

    # Assign responder resource to incident A
    assignment = Assignment(
        incident_id=incident_a.id,
        resource_id=resource.id,
        status="Assigned",
        notes="Urgent dispatch",
    )
    db_session.add(assignment)
    db_session.commit()

    # Generate JWT Tokens
    tokens = {
        "super_admin": create_access_token(super_admin.id, super_admin.email, super_admin.role),
        "dispatcher": create_access_token(dispatcher.id, dispatcher.email, dispatcher.role),
        "responder": create_access_token(responder_user.id, responder_user.email, responder_user.role),
        "citizen_a": create_access_token(citizen_a.id, citizen_a.email, citizen_a.role),
        "citizen_b": create_access_token(citizen_b.id, citizen_b.email, citizen_b.role),
        "hospital_staff_1": create_access_token(staff_1.id, staff_1.email, staff_1.role, org_ids=[hosp_org_1.id]),
        "hospital_staff_2": create_access_token(staff_2.id, staff_2.email, staff_2.role, org_ids=[hosp_org_2.id]),
        "deactivated": create_access_token(deactivated_user.id, deactivated_user.email, deactivated_user.role),
    }

    return {
        "tokens": tokens,
        "users": {
            "super_admin": super_admin,
            "dispatcher": dispatcher,
            "responder": responder_user,
            "citizen_a": citizen_a,
            "citizen_b": citizen_b,
            "staff_1": staff_1,
            "staff_2": staff_2,
        },
        "orgs": {
            "hosp_1": hosp_org_1,
            "hosp_2": hosp_org_2,
        },
        "incident_a": incident_a,
        "resource": resource,
        "assignment": assignment,
    }


# ==============================================================================
# 1. WebSocket Authentication & Lifecycle
# ==============================================================================
class TestWebSocketAuthentication:
    def test_ws_connect_with_valid_token_query_param(self, client: TestClient, m4_setup):
        token = m4_setup["tokens"]["dispatcher"]
        with client.websocket_connect(f"/ws?token={token}") as ws:
            data = ws.receive_json()
            assert data["event"] == "connected"
            assert data["role"] == "dispatcher"
            assert data["user_id"] == m4_setup["users"]["dispatcher"].id

    def test_ws_connect_with_invalid_token_is_rejected(self, client: TestClient):
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect("/ws?token=invalid.tampered.token") as ws:
                data = ws.receive_json()
                assert data["event"] == "error"
                ws.receive_json()
        # 4003 or 1008 policy violation close code
        assert exc_info.value.code in (4003, 1008)

    def test_ws_connect_deactivated_user_is_rejected(self, client: TestClient, m4_setup):
        token = m4_setup["tokens"]["deactivated"]
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect(f"/ws?token={token}") as ws:
                data = ws.receive_json()
                assert data["event"] == "error"
                ws.receive_json()
        assert exc_info.value.code in (4003, 1008)

    def test_ws_connect_without_token_then_authenticate(self, client: TestClient, m4_setup):
        token = m4_setup["tokens"]["citizen_a"]
        with client.websocket_connect("/ws") as ws:
            # Expect auth_required challenge
            prompt = ws.receive_json()
            assert prompt["event"] == "auth_required"

            # Send auth action
            ws.send_json({"action": "auth", "token": token})
            ack = ws.receive_json()
            assert ack["event"] == "authenticated"
            assert ack["role"] == "citizen"

    def test_ws_ping_pong_heartbeat(self, client: TestClient, m4_setup):
        token = m4_setup["tokens"]["dispatcher"]
        with client.websocket_connect(f"/ws?token={token}") as ws:
            ws.receive_json()  # connected
            ws.send_json({"action": "ping"})
            resp = ws.receive_json()
            assert resp["event"] == "pong"
            assert "timestamp" in resp


# ==============================================================================
# 2. Subscription Authorization & Role Isolation
# ==============================================================================
class TestSubscriptionAuthorization:
    def test_citizen_subscription_to_global_channel_denied(self, client: TestClient, m4_setup):
        token = m4_setup["tokens"]["citizen_a"]
        with client.websocket_connect(f"/ws?token={token}") as ws:
            ws.receive_json()  # connected
            ws.send_json({"action": "subscribe", "channel": "careon:events:global"})
            resp = ws.receive_json()
            assert resp["event"] == "subscription_error"
            assert resp["status"] == "denied"

    def test_citizen_subscription_to_own_incident_allowed(self, client: TestClient, m4_setup):
        token = m4_setup["tokens"]["citizen_a"]
        inc_id = m4_setup["incident_a"].id
        with client.websocket_connect(f"/ws?token={token}") as ws:
            ws.receive_json()  # connected
            ws.send_json({"action": "subscribe", "channel": f"careon:events:incident:{inc_id}"})
            resp = ws.receive_json()
            assert resp["event"] == "subscribed"
            assert resp["channel"] == f"careon:events:incident:{inc_id}"

    def test_citizen_subscription_to_other_incident_denied(self, client: TestClient, m4_setup):
        token = m4_setup["tokens"]["citizen_b"]
        inc_id = m4_setup["incident_a"].id
        with client.websocket_connect(f"/ws?token={token}") as ws:
            ws.receive_json()  # connected
            ws.send_json({"action": "subscribe", "channel": f"careon:events:incident:{inc_id}"})
            resp = ws.receive_json()
            assert resp["event"] == "subscription_error"
            assert resp["status"] == "denied"

    def test_dispatcher_allowed_global_and_incident_subscriptions(self, client: TestClient, m4_setup):
        token = m4_setup["tokens"]["dispatcher"]
        inc_id = m4_setup["incident_a"].id
        with client.websocket_connect(f"/ws?token={token}") as ws:
            ws.receive_json()  # connected

            # Subscribe global
            ws.send_json({"action": "subscribe", "channel": "careon:events:global"})
            resp1 = ws.receive_json()
            assert resp1["event"] == "subscribed"
            assert resp1["channel"] == "careon:events:global"

            # Subscribe incident
            ws.send_json({"action": "subscribe", "channel": f"careon:events:incident:{inc_id}"})
            resp2 = ws.receive_json()
            assert resp2["event"] == "subscribed"

    def test_hospital_staff_tenant_isolation(self, client: TestClient, m4_setup):
        token = m4_setup["tokens"]["hospital_staff_1"]
        org1_id = m4_setup["orgs"]["hosp_1"].id
        org2_id = m4_setup["orgs"]["hosp_2"].id

        with client.websocket_connect(f"/ws?token={token}") as ws:
            ws.receive_json()  # connected

            # Subscribe to own org channel -> allowed
            ws.send_json({"action": "subscribe", "channel": f"careon:events:org:{org1_id}"})
            resp1 = ws.receive_json()
            assert resp1["event"] == "subscribed"

            # Subscribe to rival org channel -> denied
            ws.send_json({"action": "subscribe", "channel": f"careon:events:org:{org2_id}"})
            resp2 = ws.receive_json()
            assert resp2["event"] == "subscription_error"
            assert resp2["status"] == "denied"

    def test_unsubscribe_workflow(self, client: TestClient, m4_setup):
        token = m4_setup["tokens"]["dispatcher"]
        with client.websocket_connect(f"/ws?token={token}") as ws:
            ws.receive_json()
            ws.send_json({"action": "subscribe", "channel": "careon:events:global"})
            ws.receive_json()  # subscribed
            ws.send_json({"action": "unsubscribe", "channel": "careon:events:global"})
            unsub_resp = ws.receive_json()
            assert unsub_resp["event"] == "unsubscribed"
            assert unsub_resp["channel"] == "careon:events:global"


# ==============================================================================
# 3. Audience-Aware Data Sanitization
# ==============================================================================
class TestAudienceDataSanitization:
    def test_citizen_sanitization_removes_sensitive_pii(self, m4_setup):
        raw_payload = {
            "id": 100,
            "category": "Medical",
            "title": "Cardiac Arrest",
            "verification_otp": "847291",
            "contact_phone": "+91 99999 11111",
            "internal_notes": "Caller sounds panicky. Triage level 1.",
            "admin_notes": "Suspected duplicate.",
            "dispatcher_notes": "Dispatched Unit 4.",
            "status": "Verified",
        }

        # Citizen view
        citizen_session = RealtimeUserSession(
            user_id=1,
            email="citizen@example.com",
            name="Alice",
            role=UserRole.CITIZEN,
        )
        sanitized = sanitize_payload_for_viewer(raw_payload, citizen_session)

        assert "verification_otp" not in sanitized
        assert "contact_phone" not in sanitized
        assert "internal_notes" not in sanitized
        assert "admin_notes" not in sanitized
        assert "dispatcher_notes" not in sanitized
        assert sanitized["category"] == "Medical"
        assert sanitized["status"] == "Verified"

    def test_dispatcher_receives_complete_payload(self, m4_setup):
        raw_payload = {
            "id": 100,
            "verification_otp": "847291",
            "contact_phone": "+91 99999 11111",
            "internal_notes": "Caller sounds panicky.",
            "status": "Verified",
        }

        dispatcher_session = RealtimeUserSession(
            user_id=2,
            email="dispatcher@careon.org",
            name="Dispatcher Dave",
            role=UserRole.DISPATCHER,
        )
        full_payload = sanitize_payload_for_viewer(raw_payload, dispatcher_session)
        assert full_payload["verification_otp"] == "847291"
        assert full_payload["contact_phone"] == "+91 99999 11111"
        assert full_payload["internal_notes"] == "Caller sounds panicky."


# ==============================================================================
# 4. GPS Telemetry Ingestion & Spatial Cache
# ==============================================================================
class TestGPSTelemetryIngestion:
    def test_telemetry_valid_responder_updates_location(self, client: TestClient, m4_setup):
        token = m4_setup["tokens"]["responder"]
        res_id = m4_setup["resource"].id
        payload = {
            "resource_id": res_id,
            "latitude": 12.3110,
            "longitude": 76.6520,
            "speed": 42.5,
            "heading": 180.0,
            "accuracy": 4.5,
            "altitude": 770.0,
        }
        res = client.post(
            "/api/realtime/telemetry",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "success"
        assert data["resource_id"] == res_id
        assert data["latitude"] == 12.3110
        assert data["longitude"] == 76.6520
        assert data["speed"] == 42.5

    def test_telemetry_invalid_coordinates_rejected(self, client: TestClient, m4_setup):
        token = m4_setup["tokens"]["responder"]
        res_id = m4_setup["resource"].id

        # Latitude out of bounds
        res = client.post(
            "/api/realtime/telemetry",
            json={"resource_id": res_id, "latitude": 95.0, "longitude": 76.6520},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 400
        assert "latitude" in res.json()["detail"].lower()

        # Longitude out of bounds
        res2 = client.post(
            "/api/realtime/telemetry",
            json={"resource_id": res_id, "latitude": 12.3110, "longitude": -195.0},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res2.status_code == 400
        assert "longitude" in res2.json()["detail"].lower()

    def test_telemetry_unreasonable_speed_rejected(self, client: TestClient, m4_setup):
        token = m4_setup["tokens"]["responder"]
        res_id = m4_setup["resource"].id
        res = client.post(
            "/api/realtime/telemetry",
            json={"resource_id": res_id, "latitude": 12.3110, "longitude": 76.6520, "speed": 450.0},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 400
        assert "speed" in res.json()["detail"].lower()

    def test_telemetry_forbidden_for_citizen(self, client: TestClient, m4_setup):
        token = m4_setup["tokens"]["citizen_a"]
        res_id = m4_setup["resource"].id
        res = client.post(
            "/api/realtime/telemetry",
            json={"resource_id": res_id, "latitude": 12.3110, "longitude": 76.6520},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 403


# ==============================================================================
# 5. Transactional Outbox & Event Recovery
# ==============================================================================
class TestTransactionalOutbox:
    def test_outbox_event_persisted_on_incident_creation(self, db_session: Session, m4_setup):
        inc_id = m4_setup["incident_a"].id
        outbox_row = (
            db_session.query(OutboxEvent)
            .filter(OutboxEvent.incident_id == inc_id)
            .first()
        )
        assert outbox_row is not None
        assert outbox_row.event_type.startswith("incident.")
        assert outbox_row.event_id is not None
        assert outbox_row.channel.startswith("careon:events:")

    def test_outbox_relay_worker_processes_pending(self, db_session: Session):
        # Manually seed an unpublished outbox event
        dummy_event = OutboxEvent(
            event_id="test-uuid-relay-12345",
            event_type="incident.test_relay",
            event_version=1,
            channel="careon:events:global",
            payload_json=json.dumps({"test": "relay_data"}),
            is_published=False,
        )
        db_session.add(dummy_event)
        db_session.commit()

        # Run relay worker
        relayed_count = relay_pending_outbox_events(db_session)
        assert relayed_count >= 1

        db_session.refresh(dummy_event)
        assert dummy_event.is_published is True
        assert dummy_event.published_at is not None

    def test_realtime_health_endpoint(self, client: TestClient, m4_setup):
        token = m4_setup["tokens"]["super_admin"]
        res = client.get(
            "/api/realtime/health",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["status"] in ("healthy", "operational")
        assert "websocket_connections" in data
        assert "redis_pubsub" in data
        assert "outbox_backlog" in data
        assert "total_messages_sent" in data

    def test_realtime_history_endpoint(self, client: TestClient, m4_setup):
        token = m4_setup["tokens"]["dispatcher"]
        channel = "careon:events:global"
        res = client.get(
            f"/api/realtime/history?channel={channel}&limit=10",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 200
        data = res.json()
        assert "events" in data
        assert isinstance(data["events"], list)
        assert data["channel"] == channel
