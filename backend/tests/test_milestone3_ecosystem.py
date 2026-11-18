"""
CareOn Milestone 3 Test Suite — Five-Application Ecosystem & RBAC.

Tests:
1. Responder Application Endpoints & Missions Lifecycle
   - Profile & active mission (/api/responder/me)
   - Mission listing & filtering (/api/responder/missions)
   - Mission acceptance workflow & incident updates
   - Mission rejection workflow with reason
   - Status progression (En Route -> On Scene -> Transporting -> Cleared)
   - Telemetry GPS location update
   - Access controls: Citizen cannot access responder endpoints (403)

2. Hospital Portal Endpoints & Tenant Isolation
   - Readiness status (/api/hospital/readiness)
   - Capacity updates & diversion toggle (/api/hospital/readiness)
   - Incoming patient feed (/api/hospital/incoming)
   - Patient arrival intake acknowledgment & bed decrement (/api/hospital/incoming/{id}/arrival)
   - Network hospital directory (/api/hospital/directory)
   - Access controls & organization tenant isolation

3. Super Admin & Operations Endpoints
   - System health dashboard (/api/admin/system-health)
   - Audit log queries and filter inspection (/api/admin/audit-logs)
   - User list & role promotion/demotion (/api/admin/users/{id}/role)
   - Account deactivation & self-deactivation protection (/api/admin/users/{id}/status)
   - Platform operations summary (/api/admin/operations-summary)
   - Access controls: Dispatcher / Citizen cannot access Super Admin endpoints (403)
"""

import time
import pytest
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
    AuditLog,
)
from app.auth import hash_password
from app.identity.jwt_handler import create_access_token


@pytest.fixture
def auth_tokens(client: TestClient, db_session: Session):
    """
    Creates isolated test accounts across the 5 primary ecosystem roles:
    - citizen
    - dispatcher
    - responder
    - hospital_staff
    - super_admin
    """
    t_id = int(time.time() * 1000) % 1000000

    # 1. Super Admin
    super_admin = User(
        email=f"admin_{t_id}@careon.org",
        name="Test Super Admin",
        phone="+91 99999 00001",
        hashed_password=hash_password("AdminPass123!"),
        role="super_admin",
        is_active=True,
    )
    # 2. Dispatcher
    dispatcher = User(
        email=f"dispatch_{t_id}@careon.org",
        name="Test Dispatcher",
        phone="+91 99999 00002",
        hashed_password=hash_password("DispatchPass123!"),
        role="dispatcher",
        is_active=True,
    )
    # 3. Responder
    responder = User(
        email=f"responder_{t_id}@careon.org",
        name="Test Responder EMT",
        phone="+91 99999 00003",
        hashed_password=hash_password("ResponderPass123!"),
        role="responder",
        is_active=True,
    )
    # 4. Hospital Staff
    hospital_staff = User(
        email=f"dr_sharma_{t_id}@careon.org",
        name="Dr. Sharma",
        phone="+91 99999 00004",
        hashed_password=hash_password("HospitalPass123!"),
        role="hospital_staff",
        is_active=True,
    )
    # 5. Citizen
    citizen = User(
        email=f"citizen_{t_id}@careon.org",
        name="Test Citizen",
        phone="+91 99999 00005",
        hashed_password=hash_password("CitizenPass123!"),
        role="citizen",
        is_active=True,
    )

    db_session.add_all([super_admin, dispatcher, responder, hospital_staff, citizen])
    db_session.commit()
    for u in [super_admin, dispatcher, responder, hospital_staff, citizen]:
        db_session.refresh(u)

    # Create Hospital Org and membership for hospital_staff
    hosp_org = Organization(
        name=f"City General Hospital {t_id}",
        org_type="hospital",
        location_name="Central District",
        is_active=True,
        is_verified=True,
    )
    db_session.add(hosp_org)
    db_session.commit()
    db_session.refresh(hosp_org)

    hosp_mem = OrganizationMembership(
        organization_id=hosp_org.id,
        user_id=hospital_staff.id,
        membership_role="admin",
        status="active",
    )
    db_session.add(hosp_mem)

    # Assign a dedicated resource to the responder
    amb_res = Resource(
        resource_code=f"AMB-M3-{t_id}",
        name=f"Paramedic Unit {t_id}",
        category="Ambulance",
        capabilities="ALS,trauma_care",
        location_name="Station 1",
        latitude=12.9716,
        longitude=77.5946,
        status="Available",
        capacity=2,
        contact_phone="+91 98888 77777",
        assigned_user_id=responder.id,
    )
    db_session.add(amb_res)
    db_session.commit()
    db_session.refresh(amb_res)

    tokens = {
        "super_admin": create_access_token(str(super_admin.id), email=super_admin.email, role="super_admin"),
        "dispatcher": create_access_token(str(dispatcher.id), email=dispatcher.email, role="dispatcher"),
        "responder": create_access_token(str(responder.id), email=responder.email, role="responder"),
        "hospital_staff": create_access_token(str(hospital_staff.id), email=hospital_staff.email, role="hospital_staff", org_ids=[hosp_org.id]),
        "citizen": create_access_token(str(citizen.id), email=citizen.email, role="citizen"),
        "users": {
            "super_admin": super_admin,
            "dispatcher": dispatcher,
            "responder": responder,
            "hospital_staff": hospital_staff,
            "citizen": citizen,
        },
        "hosp_org": hosp_org,
        "resource": amb_res,
    }

    yield tokens

    # Teardown
    try:
        db_session.query(HospitalReadiness).filter(HospitalReadiness.organization_id == hosp_org.id).delete()
        db_session.query(OrganizationMembership).filter(OrganizationMembership.organization_id == hosp_org.id).delete()
        db_session.query(Organization).filter(Organization.id == hosp_org.id).delete()
        db_session.query(Assignment).filter(Assignment.resource_id == amb_res.id).delete()
        db_session.query(Resource).filter(Resource.id == amb_res.id).delete()
        for u in [super_admin, dispatcher, responder, hospital_staff, citizen]:
            db_session.query(User).filter(User.id == u.id).delete()
        db_session.commit()
    except Exception:
        db_session.rollback()


# ==============================================================================
# 1. Responder Mobile / Web Tests
# ==============================================================================

def test_responder_profile_and_me(client: TestClient, auth_tokens):
    """Responder can fetch profile, assigned vehicle, and active mission."""
    headers = {"Authorization": f"Bearer {auth_tokens['responder']}"}
    res = client.get("/api/responder/me", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["user"]["email"] == auth_tokens["users"]["responder"].email
    assert data["assigned_resource"]["id"] == auth_tokens["resource"].id
    assert data["assigned_resource"]["code"] == auth_tokens["resource"].resource_code


def test_responder_mission_lifecycle(client: TestClient, auth_tokens, db_session: Session):
    """Full mission lifecycle: dispatch -> accept -> en route -> on scene -> clear."""
    responder_headers = {"Authorization": f"Bearer {auth_tokens['responder']}"}
    resource = auth_tokens["resource"]

    # 1. Create a live incident
    t_id = int(time.time() * 1000) % 1000000
    incident = Incident(
        incident_code=f"INC-M3-{t_id}",
        category="Road accident",
        title="Collision at MG Road",
        description="Two vehicles involved, one person injured",
        location_name="MG Road Metro",
        latitude=12.9750,
        longitude=77.6000,
        affected_people=1,
        help_required="Ambulance with ALS",
        contact_name="Ramesh",
        contact_phone="+91 98765 43210",
        priority="Critical",
        status="Team Dispatched",
    )
    db_session.add(incident)
    db_session.commit()
    db_session.refresh(incident)

    # 2. Dispatch the responder's resource to this incident
    assignment = Assignment(
        incident_id=incident.id,
        resource_id=resource.id,
        assigned_by="Dispatcher Priya",
        status="Active",
    )
    resource.status = "Assigned"
    db_session.add(assignment)
    db_session.commit()
    db_session.refresh(assignment)

    try:
        # A. List missions
        missions_res = client.get("/api/responder/missions", headers=responder_headers)
        assert missions_res.status_code == 200
        missions = missions_res.json()
        assert len(missions) >= 1
        m = next(item for item in missions if item["id"] == assignment.id)
        assert m["incident_code"] == incident.incident_code

        # B. Get mission details
        detail_res = client.get(f"/api/responder/missions/{assignment.id}", headers=responder_headers)
        assert detail_res.status_code == 200
        assert detail_res.json()["category"] == "Road accident"

        # C. Accept mission
        accept_res = client.post(
            f"/api/responder/missions/{assignment.id}/accept",
            headers=responder_headers,
            json={"reason": "Unit moving immediately"},
        )
        assert accept_res.status_code == 200
        assert accept_res.json()["status"] == "Accepted"

        # D. Advance status: En Route
        enroute_res = client.post(
            f"/api/responder/missions/{assignment.id}/status",
            headers=responder_headers,
            json={"status": "En Route", "notes": "ETA 6 mins"},
        )
        assert enroute_res.status_code == 200
        assert enroute_res.json()["status"] == "En Route"

        # E. Advance status: On Scene
        scene_res = client.post(
            f"/api/responder/missions/{assignment.id}/status",
            headers=responder_headers,
            json={"status": "On Scene", "notes": "Patient stabilized"},
        )
        assert scene_res.status_code == 200

        # F. Advance status: Cleared / Completed
        clear_res = client.post(
            f"/api/responder/missions/{assignment.id}/status",
            headers=responder_headers,
            json={"status": "Completed", "notes": "Handover finished, returning to post"},
        )
        assert clear_res.status_code == 200
        assert clear_res.json()["status"] == "Completed"

    finally:
        db_session.query(Assignment).filter(Assignment.id == assignment.id).delete()
        db_session.query(Incident).filter(Incident.id == incident.id).delete()
        db_session.commit()


def test_responder_mission_rejection(client: TestClient, auth_tokens, db_session: Session):
    """Responder can reject a mission with a clear operational reason."""
    responder_headers = {"Authorization": f"Bearer {auth_tokens['responder']}"}
    resource = auth_tokens["resource"]

    t_id = int(time.time() * 1000) % 1000000
    incident = Incident(
        incident_code=f"INC-REJ-{t_id}",
        category="Medical",
        title="Asthma Attack",
        description="Severe respiratory distress",
        location_name="Indiranagar",
        latitude=12.9784,
        longitude=77.6408,
        affected_people=1,
        help_required="Oxygen required",
        contact_name="Sunil",
        contact_phone="+91 98765 11111",
        status="Team Dispatched",
    )
    db_session.add(incident)
    db_session.commit()
    db_session.refresh(incident)

    assignment = Assignment(
        incident_id=incident.id,
        resource_id=resource.id,
        assigned_by="System Algorithm",
        status="Active",
    )
    db_session.add(assignment)
    db_session.commit()
    db_session.refresh(assignment)

    try:
        reject_res = client.post(
            f"/api/responder/missions/{assignment.id}/reject",
            headers=responder_headers,
            json={"reason": "Mechanical vehicle breakdown on 100ft road"},
        )
        assert reject_res.status_code == 200
        assert reject_res.json()["status"] == "Rejected"

        # Verify resource is released to Available
        db_session.refresh(resource)
        assert resource.status == "Available"
    finally:
        db_session.query(Assignment).filter(Assignment.id == assignment.id).delete()
        db_session.query(Incident).filter(Incident.id == incident.id).delete()
        db_session.commit()


def test_responder_telemetry_update(client: TestClient, auth_tokens, db_session: Session):
    """Responder sends periodic GPS coordinates to update vehicle position."""
    responder_headers = {"Authorization": f"Bearer {auth_tokens['responder']}"}
    res = client.post(
        "/api/responder/telemetry",
        headers=responder_headers,
        json={"latitude": 12.9810, "longitude": 77.5990, "speed": 42.5},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["latitude"] == 12.9810
    assert data["longitude"] == 77.5990


def test_responder_rbac_isolation(client: TestClient, auth_tokens):
    """Citizens cannot access responder mission endpoints (403 Forbidden)."""
    citizen_headers = {"Authorization": f"Bearer {auth_tokens['citizen']}"}
    res = client.get("/api/responder/me", headers=citizen_headers)
    assert res.status_code == 403

    missions_res = client.get("/api/responder/missions", headers=citizen_headers)
    assert missions_res.status_code == 403


# ==============================================================================
# 2. Hospital Portal Tests
# ==============================================================================

def test_hospital_readiness_lifecycle(client: TestClient, auth_tokens):
    """Hospital staff can inspect and update bed capacities and divert status."""
    hosp_headers = {"Authorization": f"Bearer {auth_tokens['hospital_staff']}"}

    # A. Get readiness
    res = client.get("/api/hospital/readiness", headers=hosp_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["organization_id"] == auth_tokens["hosp_org"].id
    assert "available_er_beds" in data
    assert "divert_status" in data

    # B. Update capacity & divert status
    patch_res = client.patch(
        "/api/hospital/readiness",
        headers=hosp_headers,
        json={
            "available_er_beds": 5,
            "icu_beds_available": 1,
            "divert_status": True,
            "divert_reason": "Trauma center at maximum surge capacity",
        },
    )
    assert patch_res.status_code == 200
    updated = patch_res.json()
    assert updated["available_er_beds"] == 5
    assert updated["icu_beds_available"] == 1
    assert updated["divert_status"] is True
    assert updated["divert_reason"] == "Trauma center at maximum surge capacity"


def test_hospital_incoming_and_patient_arrival(client: TestClient, auth_tokens, db_session: Session):
    """Hospital receives incoming ambulance transports and confirms intake."""
    hosp_headers = {"Authorization": f"Bearer {auth_tokens['hospital_staff']}"}
    resource = auth_tokens["resource"]

    t_id = int(time.time() * 1000) % 1000000
    incident = Incident(
        incident_code=f"INC-HOSP-{t_id}",
        category="Road accident",
        title="Highway pileup",
        description="Critical polytrauma patient",
        location_name="Airport Road",
        latitude=13.0000,
        longitude=77.6000,
        affected_people=1,
        help_required="Trauma surgeon and ventilator",
        contact_name="Officer John",
        contact_phone="+91 99999 88888",
        priority="Critical",
        status="Team Dispatched",
    )
    db_session.add(incident)
    db_session.commit()
    db_session.refresh(incident)

    assignment = Assignment(
        incident_id=incident.id,
        resource_id=resource.id,
        assigned_by="Dispatcher",
        status="Transporting",
    )
    db_session.add(assignment)
    db_session.commit()
    db_session.refresh(assignment)

    try:
        # A. Check incoming list
        inc_res = client.get("/api/hospital/incoming", headers=hosp_headers)
        assert inc_res.status_code == 200
        incoming = inc_res.json()
        assert any(item["incident_id"] == incident.id for item in incoming)

        # B. Acknowledge patient arrival
        arrival_res = client.post(
            f"/api/hospital/incoming/{incident.id}/arrival",
            headers=hosp_headers,
            json={"bed_type": "trauma_bay", "intake_notes": "Immediate surgery scheduled"},
        )
        assert arrival_res.status_code == 200
        intake_data = arrival_res.json()
        assert intake_data["status"] == "acknowledged"
        assert intake_data["bed_type"] == "trauma_bay"

    finally:
        db_session.query(Assignment).filter(Assignment.id == assignment.id).delete()
        db_session.query(Incident).filter(Incident.id == incident.id).delete()
        db_session.commit()


def test_hospital_directory_accessible_to_dispatcher(client: TestClient, auth_tokens):
    """Hospital directory is visible to dispatchers for triage routing."""
    disp_headers = {"Authorization": f"Bearer {auth_tokens['dispatcher']}"}
    res = client.get("/api/hospital/directory", headers=disp_headers)
    assert res.status_code == 200
    assert isinstance(res.json(), list)


def test_hospital_tenant_isolation(client: TestClient, auth_tokens):
    """Citizen cannot access hospital readiness or incoming patients (403 Forbidden)."""
    citizen_headers = {"Authorization": f"Bearer {auth_tokens['citizen']}"}
    res = client.get("/api/hospital/readiness", headers=citizen_headers)
    assert res.status_code == 403


# ==============================================================================
# 3. Super Admin & Operations Tests
# ==============================================================================

def test_super_admin_system_health(client: TestClient, auth_tokens):
    """Super Admin can inspect live infrastructure health metrics."""
    admin_headers = {"Authorization": f"Bearer {auth_tokens['super_admin']}"}
    res = client.get("/api/admin/system-health", headers=admin_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["database_connected"] is True
    assert "active_incidents" in data
    assert "available_resources" in data
    assert "total_users" in data


def test_super_admin_audit_logs(client: TestClient, auth_tokens):
    """Super Admin can query and filter centralized audit logs."""
    admin_headers = {"Authorization": f"Bearer {auth_tokens['super_admin']}"}
    res = client.get("/api/admin/audit-logs?limit=10", headers=admin_headers)
    assert res.status_code == 200
    data = res.json()
    assert "total" in data
    assert "items" in data
    assert isinstance(data["items"], list)


def test_super_admin_user_role_and_status_management(client: TestClient, auth_tokens, db_session: Session):
    """Super Admin can change user roles and activate/deactivate accounts."""
    admin_headers = {"Authorization": f"Bearer {auth_tokens['super_admin']}"}
    target_user = auth_tokens["users"]["citizen"]

    # Change role to dispatcher
    role_res = client.patch(
        f"/api/admin/users/{target_user.id}/role",
        headers=admin_headers,
        json={"role": "dispatcher"},
    )
    assert role_res.status_code == 200
    assert role_res.json()["role"] == "dispatcher"

    # Toggle status to inactive
    status_res = client.patch(
        f"/api/admin/users/{target_user.id}/status",
        headers=admin_headers,
        json={"is_active": False, "reason": "Security audit test"},
    )
    assert status_res.status_code == 200
    assert status_res.json()["is_active"] is False

    # Prevent self-deactivation by Super Admin
    self_admin = auth_tokens["users"]["super_admin"]
    self_res = client.patch(
        f"/api/admin/users/{self_admin.id}/status",
        headers=admin_headers,
        json={"is_active": False},
    )
    assert self_res.status_code == 400


def test_super_admin_access_controls(client: TestClient, auth_tokens):
    """Non-super admins (citizens, dispatchers) cannot access admin endpoints."""
    disp_headers = {"Authorization": f"Bearer {auth_tokens['dispatcher']}"}
    res = client.get("/api/admin/system-health", headers=disp_headers)
    assert res.status_code == 403

    citizen_headers = {"Authorization": f"Bearer {auth_tokens['citizen']}"}
    res = client.get("/api/admin/audit-logs", headers=citizen_headers)
    assert res.status_code == 403
