"""
CareOn Milestone 11 Test Suite — Multi-Agency Coordination & Unified Incident Command.

Covers:
1. Agency Classification and Mutual Aid Directory
2. Inter-Agency Collaboration Lifecycle (Invite -> Accept -> Suspend -> Revoke -> Complete)
3. Granular Scope-Based Information Governance (Deny-by-default, explicit grants)
4. M8 Clinical Privacy Isolation (Only tokens/reference exposed, zero raw clinical leakage)
5. Incident Command System (ICS) Structure:
   - Invariant: Exactly one active Incident Commander per command structure
   - Transactional Commander Transfer (atomic relief + appointment + history)
   - Emergency Command Succession
   - Subordinate Command Roles (Operations Chief, Safety Officer, Branch Directors)
6. Cross-Agency Operational Tasks (Lifecycle: REQUESTED -> ACKNOWLEDGED -> IN_PROGRESS -> COMPLETED/REJECTED)
7. Mutual Aid Resource Requests (Operational Sovereignty: Non-automatic dispatch, explicit accept/decline)
8. Geospatial Operational Zones (Perimeters, Hot/Warm/Cold zones, Hazards)
9. Scope-Filtered Common Operational Picture (COP)
10. Immutable Inter-Agency Audit Logging (Including denied access attempts)
11. Realtime M4 Outbox Integration
12. Background Maintenance Worker Sweep (Collaboration and Resource Request expiries)
"""

import json
import time
import uuid
import pytest
from datetime import datetime, timezone, timedelta
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
    EmergencyEncounter,
    Patient,
    DigitalHandoverRecord,
    AgencyClassification,
    IncidentAgencyCollaboration,
    IncidentInformationGrant,
    IncidentCommandStructure,
    IncidentCommandAssignment,
    IncidentCommandHistory,
    AgencyOperationalTask,
    AgencyResourceRequest,
    IncidentOperationalZone,
    InterAgencyAuditLog,
    OutboxEvent,
    utc_now,
)
from app.auth import hash_password, create_access_token
import app.coordination as coord_svc


@pytest.fixture
def m11_setup(client: TestClient, db_session: Session):
    """
    Sets up multi-agency test environment with:
    - Agency 1: City EMS (Ambulance Service)
    - Agency 2: Metro Fire & Rescue (Fire Department)
    - Agency 3: State Police (Law Enforcement)
    - Agency 4: General Hospital (Receiving Facility)
    - Super Admin user
    - Key personnel per agency
    - Active multi-casualty incident
    - Clinical encounter & digital handover record (M8)
    """
    t_id = int(time.time() * 1000) % 1000000

    # 1. Organizations
    org_ems = Organization(name=f"City EMS M11 {t_id}", org_type="ambulance_service", is_active=True)
    org_fire = Organization(name=f"Metro Fire M11 {t_id}", org_type="fire", is_active=True)
    org_police = Organization(name=f"State Police M11 {t_id}", org_type="police", is_active=True)
    org_hosp = Organization(name=f"City General Hospital M11 {t_id}", org_type="hospital", is_active=True)
    db_session.add_all([org_ems, org_fire, org_police, org_hosp])
    db_session.flush()

    # 2. Users
    user_ems_cmd = User(
        email=f"ems_cmd_{t_id}@careon.org",
        name="Chief EMS Officer",
        phone="+91 99999 60001",
        hashed_password=hash_password("Pass123!"),
        role="admin",
        is_active=True,
    )
    user_fire_cmd = User(
        email=f"fire_cmd_{t_id}@careon.org",
        name="Fire Battalion Chief",
        phone="+91 99999 60002",
        hashed_password=hash_password("Pass123!"),
        role="admin",
        is_active=True,
    )
    user_police_cmd = User(
        email=f"police_cmd_{t_id}@careon.org",
        name="Police Superintendent",
        phone="+91 99999 60003",
        hashed_password=hash_password("Pass123!"),
        role="admin",
        is_active=True,
    )
    user_superadmin = User(
        email=f"superadmin_{t_id}@careon.org",
        name="Global Ops SuperAdmin",
        phone="+91 99999 60000",
        hashed_password=hash_password("Pass123!"),
        role="super_admin",
        is_active=True,
    )
    db_session.add_all([user_ems_cmd, user_fire_cmd, user_police_cmd, user_superadmin])
    db_session.flush()

    # Memberships
    db_session.add_all([
        OrganizationMembership(user_id=user_ems_cmd.id, organization_id=org_ems.id, membership_role="admin", status="active"),
        OrganizationMembership(user_id=user_fire_cmd.id, organization_id=org_fire.id, membership_role="admin", status="active"),
        OrganizationMembership(user_id=user_police_cmd.id, organization_id=org_police.id, membership_role="admin", status="active"),
    ])

    # 3. Agency Classifications
    db_session.add_all([
        AgencyClassification(
            organization_id=org_ems.id,
            agency_type="EMS",
            jurisdiction="Metro City Central",
            dispatch_hotline="108",
            radio_channel="MED-NET-1",
            is_mutual_aid_signatory=True,
        ),
        AgencyClassification(
            organization_id=org_fire.id,
            agency_type="FIRE_RESCUE",
            jurisdiction="Metro City North & Central",
            dispatch_hotline="101",
            radio_channel="FIRE-TACTICAL-2",
            is_mutual_aid_signatory=True,
        ),
        AgencyClassification(
            organization_id=org_police.id,
            agency_type="POLICE",
            jurisdiction="Metro Police Commissionerate",
            dispatch_hotline="100",
            radio_channel="POLICE-DISPATCH-9",
            is_mutual_aid_signatory=True,
        ),
        AgencyClassification(
            organization_id=org_hosp.id,
            agency_type="HOSPITAL",
            jurisdiction="Metro City Health Zone",
            dispatch_hotline="080-22223333",
            is_mutual_aid_signatory=True,
        ),
    ])

    # 4. Multi-Casualty Incident
    incident = Incident(
        incident_code=f"INC-MCI-{t_id}",
        category="Disaster",
        title="Industrial Plant Chemical Explosion & Fire",
        description="Explosion at manufacturing facility. Multiple casualties, structural damage, active fire.",
        location_name="Industrial Area Phase 2",
        latitude=12.3300,
        longitude=76.6400,
        priority="Critical",
        status="In Progress",
        contact_name="Plant Safety Director",
        contact_phone="+91 98888 77777",
        help_required="Multi-Agency Response",
        is_disaster=True,
        disaster_details="Chemical explosion, structural collapse, HAZMAT risk",
        user_id=user_ems_cmd.id,
        created_at=utc_now(),
    )
    db_session.add(incident)
    db_session.flush()

    # 5. Clinical Data (M8 Handover)
    facility = HospitalFacility(
        organization_id=org_hosp.id,
        facility_code=f"FAC-GEN-{t_id}",
        name=f"General Hospital Trauma Center {t_id}",
        location_name="Trauma Center North",
        facility_type="General Hospital",
        latitude=12.3100,
        longitude=76.6500,
        emergency_phone="+91 99999 55555",
        is_active=True,
    )
    db_session.add(facility)
    db_session.flush()

    patient = Patient(
        patient_identifier=f"PAT-{t_id}",
        full_name="Confidential Patient A",
        date_of_birth=datetime(1985, 5, 20).date(),
        gender="male",
    )
    db_session.add(patient)
    db_session.flush()

    encounter = EmergencyEncounter(
        encounter_code=f"ENC-MCI-{t_id}",
        patient_id=patient.id,
        incident_id=incident.id,
        receiving_facility_id=facility.id,
        status="active",
        chief_complaint="Severe chemical inhalation and blast injury",
        initial_acuity="Critical",
        started_at=utc_now(),
    )
    db_session.add(encounter)
    db_session.flush()

    handover = DigitalHandoverRecord(
        handover_token=str(uuid.uuid4()),
        encounter_id=encounter.id,
        facility_id=facility.id,
        version=1,
        status="draft",
        clinical_summary_json=json.dumps({
            "vitals": {"bp": "90/60", "hr": 135, "spo2": 88},
            "injuries": "Tympanic membrane perforation, 2nd degree facial chemical burns",
            "medications_administered": ["Morphine 5mg IV", "Normal Saline 1000ml"],
        }),
        is_final=False,
    )
    db_session.add(handover)
    db_session.commit()

    # JWT Tokens
    token_ems = create_access_token({"sub": str(user_ems_cmd.id), "email": user_ems_cmd.email, "role": "admin"})
    token_fire = create_access_token({"sub": str(user_fire_cmd.id), "email": user_fire_cmd.email, "role": "admin"})
    token_police = create_access_token({"sub": str(user_police_cmd.id), "email": user_police_cmd.email, "role": "admin"})
    token_superadmin = create_access_token({"sub": str(user_superadmin.id), "email": user_superadmin.email, "role": "super_admin"})

    headers_ems = {"Authorization": f"Bearer {token_ems}"}
    headers_fire = {"Authorization": f"Bearer {token_fire}"}
    headers_police = {"Authorization": f"Bearer {token_police}"}
    headers_superadmin = {"Authorization": f"Bearer {token_superadmin}"}

    return {
        "org_ems": org_ems,
        "org_fire": org_fire,
        "org_police": org_police,
        "org_hosp": org_hosp,
        "user_ems_cmd": user_ems_cmd,
        "user_fire_cmd": user_fire_cmd,
        "user_police_cmd": user_police_cmd,
        "user_superadmin": user_superadmin,
        "incident": incident,
        "facility": facility,
        "handover": handover,
        "headers_ems": headers_ems,
        "headers_fire": headers_fire,
        "headers_police": headers_police,
        "headers_superadmin": headers_superadmin,
    }


# ==============================================================================
# 1. Agency Classification & Mutual Aid Registry Tests
# ==============================================================================

def test_agency_classification_crud(client: TestClient, m11_setup: dict):
    headers = m11_setup["headers_ems"]
    org_id = m11_setup["org_ems"].id

    # Get classification
    res = client.get(f"/api/coordination/v1/agencies/{org_id}/classification", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["agency_type"] == "EMS"
    assert data["radio_channel"] == "MED-NET-1"
    assert data["is_mutual_aid_signatory"] is True

    # Update classification
    update_payload = {
        "agency_type": "EMS",
        "jurisdiction": "Expanded Metro Region",
        "dispatch_hotline": "108-EXT",
        "radio_channel": "MED-TACTICAL-4",
        "capabilities_json": json.dumps(["ALS", "MASS_CASUALTY_RESPONSE", "HAZMAT_TRIAGE"]),
        "is_mutual_aid_signatory": True,
    }
    update_res = client.post(f"/api/coordination/v1/agencies/{org_id}/classification", json=update_payload, headers=headers)
    assert update_res.status_code == 200
    assert update_res.json()["radio_channel"] == "MED-TACTICAL-4"
    assert update_res.json()["jurisdiction"] == "Expanded Metro Region"


def test_mutual_aid_partners_directory(client: TestClient, m11_setup: dict):
    headers = m11_setup["headers_ems"]
    res = client.get("/api/coordination/v1/mutual-aid-partners", headers=headers)
    assert res.status_code == 200
    partners = res.json()
    assert len(partners) >= 3
    # Ensure current agency (EMS) is excluded from partner directory
    assert all(p["organization_id"] != m11_setup["org_ems"].id for p in partners)

    # Filter by agency type
    res_fire = client.get("/api/coordination/v1/mutual-aid-partners?agency_type=FIRE_RESCUE", headers=headers)
    assert res_fire.status_code == 200
    fire_partners = res_fire.json()
    assert len(fire_partners) >= 1
    assert all(p["agency_type"] == "FIRE_RESCUE" for p in fire_partners)


# ==============================================================================
# 2. Inter-Agency Collaboration Lifecycle Tests
# ==============================================================================

def test_collaboration_lifecycle_and_grants(client: TestClient, m11_setup: dict):
    incident_id = m11_setup["incident"].id
    fire_org_id = m11_setup["org_fire"].id
    ems_headers = m11_setup["headers_ems"]
    fire_headers = m11_setup["headers_fire"]

    # 1. EMS invites Fire to incident
    invite_payload = {
        "target_organization_id": fire_org_id,
        "collaboration_purpose": "Fire suppression and HAZMAT containment at industrial plant",
        "initial_scopes": ["INCIDENT_SUMMARY", "OPERATIONAL_LOCATION", "HAZARD_INFORMATION"],
        "expires_hours": 12,
    }
    res_invite = client.post(
        f"/api/coordination/v1/incidents/{incident_id}/collaborations/invite",
        json=invite_payload,
        headers=ems_headers,
    )
    assert res_invite.status_code == 200
    invite_data = res_invite.json()
    collab_id = invite_data["id"]
    assert invite_data["collaboration_status"] == "INVITED"
    assert set(invite_data["active_scopes"]) == {"INCIDENT_SUMMARY", "OPERATIONAL_LOCATION", "HAZARD_INFORMATION"}

    # 2. Prevent self-invite
    self_invite = client.post(
        f"/api/coordination/v1/incidents/{incident_id}/collaborations/invite",
        json={"target_organization_id": m11_setup["org_ems"].id, "collaboration_purpose": "Self"},
        headers=ems_headers,
    )
    assert self_invite.status_code == 400

    # 3. Fire accepts collaboration
    res_accept = client.post(
        f"/api/coordination/v1/collaborations/{collab_id}/action",
        json={"status": "ACCEPTED"},
        headers=fire_headers,
    )
    assert res_accept.status_code == 200
    assert res_accept.json()["collaboration_status"] == "ACCEPTED"
    assert res_accept.json()["accepted_at"] is not None

    # 4. Updating granular information grants (Grant AGENCY_TASKS, revoke HAZARD_INFORMATION)
    grants_payload = {
        "scopes_to_grant": ["AGENCY_TASKS", "COMMAND_INFORMATION"],
        "scopes_to_revoke": ["HAZARD_INFORMATION"],
    }
    res_grants = client.put(
        f"/api/coordination/v1/collaborations/{collab_id}/grants",
        json=grants_payload,
        headers=ems_headers,
    )
    assert res_grants.status_code == 200
    grants_list = res_grants.json()
    granted_scopes = {g["scope"] for g in grants_list if g["is_granted"]}
    assert "AGENCY_TASKS" in granted_scopes
    assert "COMMAND_INFORMATION" in granted_scopes
    assert "HAZARD_INFORMATION" not in granted_scopes

    # 5. List collaborations
    res_list = client.get(f"/api/coordination/v1/incidents/{incident_id}/collaborations", headers=ems_headers)
    assert res_list.status_code == 200
    collabs = res_list.json()
    assert len(collabs) >= 1
    assert any(c["organization_id"] == fire_org_id for c in collabs)


# ==============================================================================
# 3. Strict Multi-Tenant Isolation & Deny-by-Default
# ==============================================================================

def test_deny_by_default_and_scope_filtering(client: TestClient, m11_setup: dict):
    incident_id = m11_setup["incident"].id
    police_headers = m11_setup["headers_police"]

    # Police has NO active collaboration on this incident yet -> Denied with 403
    res_unauth = client.get(
        f"/api/coordination/v1/incidents/{incident_id}/operational-picture",
        headers=police_headers,
    )
    assert res_unauth.status_code == 403
    assert "no active collaboration" in res_unauth.json()["detail"].lower()

    # Verify audit log captures this denied access attempt
    super_headers = m11_setup["headers_superadmin"]
    audit_res = client.get(f"/api/coordination/v1/incidents/{incident_id}/audit-logs", headers=super_headers)
    assert audit_res.status_code == 200
    logs = audit_res.json()
    assert any(l["action_type"] == "ACCESS_DENIED_NO_ACTIVE_COLLABORATION" for l in logs)


# ==============================================================================
# 4. Privacy Preservation: M8 Clinical Isolation
# ==============================================================================

def test_m8_clinical_privacy_isolation(client: TestClient, m11_setup: dict):
    incident_id = m11_setup["incident"].id
    police_org_id = m11_setup["org_police"].id
    ems_headers = m11_setup["headers_ems"]
    police_headers = m11_setup["headers_police"]

    # Invite Police and grant CLINICAL_HANDOVER_REFERENCE
    invite_payload = {
        "target_organization_id": police_org_id,
        "collaboration_purpose": "Perimeter traffic control and casualty evacuation corridor",
        "initial_scopes": ["INCIDENT_SUMMARY", "OPERATIONAL_LOCATION", "CLINICAL_HANDOVER_REFERENCE"],
    }
    invite_res = client.post(
        f"/api/coordination/v1/incidents/{incident_id}/collaborations/invite",
        json=invite_payload,
        headers=ems_headers,
    )
    collab_id = invite_res.json()["id"]

    # Police accepts
    client.post(
        f"/api/coordination/v1/collaborations/{collab_id}/action",
        json={"status": "ACCEPTED"},
        headers=police_headers,
    )

    # Police retrieves Common Operational Picture
    cop_res = client.get(
        f"/api/coordination/v1/incidents/{incident_id}/operational-picture",
        headers=police_headers,
    )
    assert cop_res.status_code == 200
    cop = cop_res.json()

    # Verify Summary and Location are present
    assert cop["summary"] is not None
    assert cop["location"] is not None

    # CRITICAL PRIVACY VERIFICATION:
    # CLINICAL_HANDOVER_REFERENCE must ONLY expose token / reference status,
    # NEVER vitals, meds, notes, or patient clinical history!
    handover_ref = cop["clinical_handover_reference"]
    assert handover_ref is not None
    assert "handover_token" in handover_ref
    assert handover_ref["is_reference_only"] is True

    # Ensure no raw clinical data leaked into COP
    cop_str = json.dumps(cop)
    assert "chemical inhalation" not in cop_str
    assert "Morphine" not in cop_str
    assert "Confidential Patient A" not in cop_str


# ==============================================================================
# 5. Incident Command System (ICS) Invariants & Transfers
# ==============================================================================

def test_incident_command_system_and_invariant(client: TestClient, m11_setup: dict):
    incident_id = m11_setup["incident"].id
    ems_headers = m11_setup["headers_ems"]
    ems_user_id = m11_setup["user_ems_cmd"].id
    fire_user_id = m11_setup["user_fire_cmd"].id
    ems_org_id = m11_setup["org_ems"].id
    fire_org_id = m11_setup["org_fire"].id

    # 1. Establish Command Structure
    est_payload = {
        "structure_type": "UNIFIED_COMMAND",
        "lead_agency_id": ems_org_id,
        "initial_commander_user_id": ems_user_id,
        "activation_notes": "Unified command established due to chemical explosion severity.",
        "radio_callsign": "COMMAND-1",
        "contact_number": "+91 99999 60001",
    }
    res_cmd = client.post(
        f"/api/coordination/v1/incidents/{incident_id}/command/establish",
        json=est_payload,
        headers=ems_headers,
    )
    assert res_cmd.status_code == 200
    cmd_data = res_cmd.json()
    cmd_id = cmd_data["command_uuid"]
    assert cmd_data["is_active"] is True
    assert cmd_data["active_commander"]["command_role"] == "INCIDENT_COMMANDER"
    assert cmd_data["active_commander"]["assigned_user_id"] == ems_user_id

    # 2. Attempting to establish a second command structure fails with 409
    res_dup = client.post(
        f"/api/coordination/v1/incidents/{incident_id}/command/establish",
        json=est_payload,
        headers=ems_headers,
    )
    assert res_dup.status_code == 409

    # Retrieve structure database ID
    get_res = client.get(f"/api/coordination/v1/incidents/{incident_id}/command", headers=ems_headers)
    struct_id = get_res.json()["active_commander"]["command_structure_id"]

    # 3. Assign subordinate command roles
    sub_payload = {
        "command_role": "OPERATIONS_CHIEF",
        "assigned_user_id": fire_user_id,
        "assigned_org_id": fire_org_id,
        "radio_callsign": "OPS-CHIEF-1",
    }
    res_sub = client.post(
        f"/api/coordination/v1/command/{struct_id}/assign-role",
        json=sub_payload,
        headers=ems_headers,
    )
    assert res_sub.status_code == 200
    assert res_sub.json()["command_role"] == "OPERATIONS_CHIEF"

    # 4. Transactional Commander Transfer (EMS Commander -> Fire Battalion Chief)
    transfer_payload = {
        "new_commander_user_id": fire_user_id,
        "new_commander_org_id": fire_org_id,
        "briefing_summary": "Incident briefing: chemical leak isolated, shifting focus to structure ventilation.",
        "radio_callsign": "COMMAND-2",
        "contact_number": "+91 99999 60002",
    }
    res_trans = client.post(
        f"/api/coordination/v1/command/{struct_id}/transfer",
        json=transfer_payload,
        headers=ems_headers,
    )
    assert res_trans.status_code == 200
    trans_data = res_trans.json()
    assert trans_data["command_role"] == "INCIDENT_COMMANDER"
    assert trans_data["assigned_user_id"] == fire_user_id
    assert trans_data["is_active"] is True

    # 5. Verify Invariant: Exactly one active commander
    get_res_after = client.get(f"/api/coordination/v1/incidents/{incident_id}/command", headers=ems_headers)
    assignments = get_res_after.json()["assignments"]
    active_commanders = [a for a in assignments if a["command_role"] == "INCIDENT_COMMANDER" and a["is_active"]]
    assert len(active_commanders) == 1
    assert active_commanders[0]["assigned_user_id"] == fire_user_id

    # 6. Verify Command Audit History
    res_hist = client.get(f"/api/coordination/v1/command/{struct_id}/history", headers=ems_headers)
    assert res_hist.status_code == 200
    hist = res_hist.json()
    assert len(hist) >= 3  # ESTABLISHED, ROLE_ASSIGNED, COMMANDER_TRANSFERRED
    events = [h["event_type"] for h in hist]
    assert "ESTABLISHED" in events
    assert "COMMANDER_TRANSFERRED" in events


def test_emergency_command_succession(client: TestClient, m11_setup: dict, db_session: Session):
    # Establish command structure directly
    incident_id = m11_setup["incident"].id
    fire_user_id = m11_setup["user_fire_cmd"].id
    police_user_id = m11_setup["user_police_cmd"].id
    fire_org_id = m11_setup["org_fire"].id
    police_org_id = m11_setup["org_police"].id

    struct = coord_svc.get_active_command_structure(db_session, incident_id)
    if not struct:
        struct = coord_svc.establish_command_structure(
            db=db_session,
            incident_id=incident_id,
            structure_type="UNIFIED_COMMAND",
            lead_agency_id=fire_org_id,
            initial_commander_user_id=fire_user_id,
            authorizing_user_id=fire_user_id,
        )

    headers = m11_setup["headers_superadmin"]
    succ_payload = {
        "new_commander_user_id": police_user_id,
        "new_commander_org_id": police_org_id,
        "reason": "Fire Commander communications lost inside collapsed structure sector B.",
        "briefing_summary": "Emergency succession to Police Commander to maintain active operational command.",
    }
    res_succ = client.post(
        f"/api/coordination/v1/command/{struct.id}/succession",
        json=succ_payload,
        headers=headers,
    )
    assert res_succ.status_code == 200
    assert res_succ.json()["assigned_user_id"] == police_user_id
    assert res_succ.json()["is_active"] is True

    # Verify history
    res_hist = client.get(f"/api/coordination/v1/command/{struct.id}/history", headers=headers)
    events = [h["event_type"] for h in res_hist.json()]
    assert "EMERGENCY_SUCCESSION" in events


# ==============================================================================
# 6. Cross-Agency Operational Tasks
# ==============================================================================

def test_operational_task_lifecycle(client: TestClient, m11_setup: dict):
    incident_id = m11_setup["incident"].id
    ems_headers = m11_setup["headers_ems"]
    police_headers = m11_setup["headers_police"]
    police_org_id = m11_setup["org_police"].id

    # 1. Create task: Request police to establish perimeter
    task_payload = {
        "assigned_organization_id": police_org_id,
        "title": "Establish 500m Hazard Exclusion Perimeter",
        "description": "Block all civilian traffic along Ring Road South and East Access Gate.",
        "priority": "HIGH",
        "deadline": (utc_now() + timedelta(hours=2)).isoformat(),
    }
    res_task = client.post(
        f"/api/coordination/v1/incidents/{incident_id}/tasks",
        json=task_payload,
        headers=ems_headers,
    )
    assert res_task.status_code == 200
    task_data = res_task.json()
    task_id = task_data["id"]
    task_uuid = task_data["task_uuid"]
    assert task_data["status"] == "REQUESTED"
    assert task_data["priority"] == "HIGH"

    # 2. Get task DB ID
    res_list = client.get(f"/api/coordination/v1/incidents/{incident_id}/tasks", headers=police_headers)
    task_item = [t for t in res_list.json() if t["task_uuid"] == task_uuid][0]

    # 3. Police acknowledges task and assigns unit
    ack_res = client.put(
        f"/api/coordination/v1/tasks/{task_id}",
        json={"status": "ACKNOWLEDGED", "assigned_unit_name": "Traffic Patrol 4"},
        headers=police_headers,
    )
    assert ack_res.status_code == 200
    assert ack_res.json()["status"] == "ACKNOWLEDGED"
    assert ack_res.json()["assigned_unit_name"] == "Traffic Patrol 4"

    # 4. Progress to IN_PROGRESS and then COMPLETED
    prog_res = client.put(
        f"/api/coordination/v1/tasks/{task_id}",
        json={"status": "IN_PROGRESS", "status_notes": "Perimeter tape established; barriers deployed."},
        headers=police_headers,
    )
    assert prog_res.status_code == 200
    assert prog_res.json()["status"] == "IN_PROGRESS"

    comp_res = client.put(
        f"/api/coordination/v1/tasks/{task_id}",
        json={"status": "COMPLETED", "status_notes": "All access routes secured."},
        headers=police_headers,
    )
    assert comp_res.status_code == 200
    assert comp_res.json()["status"] == "COMPLETED"


# ==============================================================================
# 7. Mutual Aid Resource Requests (Operational Sovereignty)
# ==============================================================================

def test_mutual_aid_resource_requests_sovereignty(client: TestClient, m11_setup: dict):
    incident_id = m11_setup["incident"].id
    ems_headers = m11_setup["headers_ems"]
    fire_headers = m11_setup["headers_fire"]
    fire_org_id = m11_setup["org_fire"].id

    # 1. EMS requests 2 Hazmat Decontamination Units from Fire
    req_payload = {
        "requested_organization_id": fire_org_id,
        "resource_type": "HAZMAT_UNIT",
        "quantity": 2,
        "urgency": "EMERGENCY",
        "operational_justification": "Triage sector overwhelmed with contaminated chemical burn patients.",
        "staging_location_name": "Sector 4 North Gate Staging",
        "staging_latitude": 12.3320,
        "staging_longitude": 76.6420,
        "expires_hours": 4,
    }
    res_req = client.post(
        f"/api/coordination/v1/incidents/{incident_id}/resource-requests",
        json=req_payload,
        headers=ems_headers,
    )
    assert res_req.status_code == 200
    req_data = res_req.json()
    req_id = req_data["id"]
    assert req_data["status"] == "REQUESTED"
    assert req_data["quantity"] == 2
    assert req_data["urgency"] == "EMERGENCY"

    # 2. Operating Principle: Request is NOT an automatic dispatch order!
    # Fire agency exercises operational sovereignty to review and accept
    act_payload = {
        "action": "ACCEPT",
        "decision_notes": "Deploying HAZMAT-Unit-1 and HAZMAT-Unit-2 from Station 3.",
        "assigned_resource_ids": ["HZ-01", "HZ-02"],
    }
    res_act = client.post(
        f"/api/coordination/v1/resource-requests/{req_id}/action",
        json=act_payload,
        headers=fire_headers,
    )
    assert res_act.status_code == 200
    assert res_act.json()["status"] == "ACCEPTED"
    assert res_act.json()["assigned_resource_ids"] == ["HZ-01", "HZ-02"]

    # 3. Fulfill request once on scene
    fulfill_res = client.post(
        f"/api/coordination/v1/resource-requests/{req_id}/action",
        json={"action": "FULFILL", "decision_notes": "Both decontamination units arrived at Sector 4."},
        headers=fire_headers,
    )
    assert fulfill_res.status_code == 200
    assert fulfill_res.json()["status"] == "FULFILLED"


# ==============================================================================
# 8. Geospatial Operational Zones
# ==============================================================================

def test_operational_zones_management(client: TestClient, m11_setup: dict):
    incident_id = m11_setup["incident"].id
    fire_headers = m11_setup["headers_fire"]

    # 1. Create Hot Zone
    hot_zone_payload = {
        "zone_type": "HOT_ZONE",
        "name": "Chemical Storage Tank Perimeter",
        "description": "Immediate toxic hazard area. Full SCBA and Level A hazmat suit mandatory.",
        "center_latitude": 12.3305,
        "center_longitude": 76.6405,
        "radius_meters": 150.0,
        "hazard_type": "CHEMICAL_TOXIC_VAPOR",
        "access_restrictions": "Authorized Hazmat Entry Team only",
    }
    res_zone = client.post(
        f"/api/coordination/v1/incidents/{incident_id}/zones",
        json=hot_zone_payload,
        headers=fire_headers,
    )
    assert res_zone.status_code == 200
    zone_data = res_zone.json()
    assert zone_data["zone_type"] == "HOT_ZONE"
    assert zone_data["hazard_type"] == "CHEMICAL_TOXIC_VAPOR"

    # 2. List zones
    res_list = client.get(f"/api/coordination/v1/incidents/{incident_id}/zones", headers=fire_headers)
    assert res_list.status_code == 200
    zones = res_list.json()
    assert len(zones) >= 1
    assert any(z["zone_type"] == "HOT_ZONE" for z in zones)


# ==============================================================================
# 9. Background Maintenance Worker Sweep
# ==============================================================================

def test_coordination_worker_sweep(client: TestClient, m11_setup: dict, db_session: Session):
    incident_id = m11_setup["incident"].id
    ems_headers = m11_setup["headers_ems"]

    # Create expired collaboration
    expired_collab = IncidentAgencyCollaboration(
        collaboration_uuid=str(uuid.uuid4()),
        incident_id=incident_id,
        organization_id=m11_setup["org_hosp"].id,
        collaboration_status="INVITED",
        inviting_organization_id=m11_setup["org_ems"].id,
        collaboration_purpose="Expired test invite",
        expires_at=utc_now() - timedelta(hours=2),
        created_at=utc_now() - timedelta(hours=5),
        updated_at=utc_now() - timedelta(hours=5),
    )
    # Create expired resource request
    expired_req = AgencyResourceRequest(
        request_uuid=str(uuid.uuid4()),
        incident_id=incident_id,
        requesting_organization_id=m11_setup["org_ems"].id,
        requested_organization_id=m11_setup["org_police"].id,
        requested_by_user_id=m11_setup["user_ems_cmd"].id,
        resource_type="POLICE_PATROL",
        quantity=1,
        urgency="ROUTINE",
        status="REQUESTED",
        operational_justification="Expired patrol request",
        expires_at=utc_now() - timedelta(hours=1),
        created_at=utc_now() - timedelta(hours=4),
        updated_at=utc_now() - timedelta(hours=4),
    )
    db_session.add_all([expired_collab, expired_req])
    db_session.commit()

    # Trigger maintenance worker sweep
    sweep_res = client.post("/api/coordination/v1/worker/sweep-expiries", headers=ems_headers)
    assert sweep_res.status_code == 200
    stats = sweep_res.json()
    assert stats["expired_collaborations"] >= 1
    assert stats["expired_resource_requests"] >= 1


# ==============================================================================
# 10. M4 Outbox & Realtime Integration
# ==============================================================================

def test_m4_outbox_integration(client: TestClient, m11_setup: dict, db_session: Session):
    incident_id = m11_setup["incident"].id
    fire_org_id = m11_setup["org_fire"].id
    ems_headers = m11_setup["headers_ems"]

    # Trigger action that emits outbox event
    invite_payload = {
        "target_organization_id": fire_org_id,
        "collaboration_purpose": "M4 Outbox test invite",
        "initial_scopes": ["INCIDENT_SUMMARY", "OPERATIONAL_LOCATION"],
    }
    client.post(
        f"/api/coordination/v1/incidents/{incident_id}/collaborations/invite",
        json=invite_payload,
        headers=ems_headers,
    )

    # Verify events were written to OutboxEvent table
    events = (
        db_session.query(OutboxEvent)
        .filter(OutboxEvent.event_type.like("inter_agency.%"))
        .all()
    )
    assert len(events) >= 1
    event_types = [e.event_type for e in events]
    assert "inter_agency.collaboration.invited" in event_types


# ==============================================================================
# 11. Additional Security, Edge Case & Boundary Invariant Tests
# ==============================================================================

def test_invalid_scope_rejection(client: TestClient, m11_setup: dict):
    incident_id = m11_setup["incident"].id
    fire_org_id = m11_setup["org_fire"].id
    ems_headers = m11_setup["headers_ems"]

    invalid_invite = {
        "target_organization_id": fire_org_id,
        "collaboration_purpose": "Test invalid scopes",
        "initial_scopes": ["INCIDENT_SUMMARY", "INVALID_SUPER_SECRET_SCOPE"],
    }
    res = client.post(
        f"/api/coordination/v1/incidents/{incident_id}/collaborations/invite",
        json=invalid_invite,
        headers=ems_headers,
    )
    assert res.status_code == 400
    assert "invalid scopes" in res.json()["detail"].lower()


def test_expired_collaboration_denies_access(client: TestClient, m11_setup: dict, db_session: Session):
    incident_id = m11_setup["incident"].id
    hosp_org_id = m11_setup["org_hosp"].id
    user_hosp = User(
        email="hosp_medic@careon.org",
        name="Hospital Physician",
        phone="+91 99999 55551",
        hashed_password=hash_password("Pass123!"),
        role="admin",
        is_active=True,
    )
    db_session.add(user_hosp)
    db_session.flush()
    db_session.add(OrganizationMembership(user_id=user_hosp.id, organization_id=hosp_org_id, membership_role="admin", status="active"))

    # Create expired accepted collaboration
    expired_collab = IncidentAgencyCollaboration(
        collaboration_uuid=str(uuid.uuid4()),
        incident_id=incident_id,
        organization_id=hosp_org_id,
        collaboration_status="ACCEPTED",
        collaboration_purpose="Past casualty reception",
        expires_at=utc_now() - timedelta(minutes=10),
        created_at=utc_now() - timedelta(hours=2),
        updated_at=utc_now() - timedelta(hours=2),
    )
    db_session.add(expired_collab)
    db_session.commit()

    token_hosp = create_access_token({"sub": str(user_hosp.id), "email": user_hosp.email, "role": "admin"})
    headers_hosp = {"Authorization": f"Bearer {token_hosp}"}

    res = client.get(f"/api/coordination/v1/incidents/{incident_id}/operational-picture", headers=headers_hosp)
    assert res.status_code == 403


def test_subordinate_endpoint_cannot_assign_incident_commander(client: TestClient, m11_setup: dict, db_session: Session):
    incident_id = m11_setup["incident"].id
    ems_headers = m11_setup["headers_ems"]
    ems_user_id = m11_setup["user_ems_cmd"].id
    fire_user_id = m11_setup["user_fire_cmd"].id
    ems_org_id = m11_setup["org_ems"].id

    struct = coord_svc.get_active_command_structure(db_session, incident_id)
    if not struct:
        struct = coord_svc.establish_command_structure(
            db=db_session,
            incident_id=incident_id,
            structure_type="SINGLE_COMMAND",
            lead_agency_id=ems_org_id,
            initial_commander_user_id=ems_user_id,
            authorizing_user_id=ems_user_id,
        )

    # Attempting to assign INCIDENT_COMMANDER via assign-role endpoint must fail with 400
    res = client.post(
        f"/api/coordination/v1/command/{struct.id}/assign-role",
        json={
            "command_role": "INCIDENT_COMMANDER",
            "assigned_user_id": fire_user_id,
            "assigned_org_id": ems_org_id,
        },
        headers=ems_headers,
    )
    assert res.status_code == 400
    assert "transfer_incident_commander" in res.json()["detail"]


def test_transfer_to_self_rejected(client: TestClient, m11_setup: dict, db_session: Session):
    incident_id = m11_setup["incident"].id
    ems_headers = m11_setup["headers_ems"]
    ems_user_id = m11_setup["user_ems_cmd"].id
    ems_org_id = m11_setup["org_ems"].id

    struct = coord_svc.get_active_command_structure(db_session, incident_id)
    if not struct:
        struct = coord_svc.establish_command_structure(
            db=db_session,
            incident_id=incident_id,
            structure_type="SINGLE_COMMAND",
            lead_agency_id=ems_org_id,
            initial_commander_user_id=ems_user_id,
            authorizing_user_id=ems_user_id,
        )

    # Transferring command to current commander returns 400
    res = client.post(
        f"/api/coordination/v1/command/{struct.id}/transfer",
        json={
            "new_commander_user_id": ems_user_id,
            "new_commander_org_id": ems_org_id,
            "briefing_summary": "Self transfer attempt",
        },
        headers=ems_headers,
    )
    assert res.status_code == 400
    assert "already the active incident commander" in res.json()["detail"].lower()


def test_task_rejection_flow(client: TestClient, m11_setup: dict):
    incident_id = m11_setup["incident"].id
    ems_headers = m11_setup["headers_ems"]
    fire_headers = m11_setup["headers_fire"]
    fire_org_id = m11_setup["org_fire"].id

    create_res = client.post(
        f"/api/coordination/v1/incidents/{incident_id}/tasks",
        json={
            "assigned_organization_id": fire_org_id,
            "title": "Enter collapsing warehouse floor 2",
            "description": "Attempt interior structural search.",
            "priority": "CRITICAL",
        },
        headers=ems_headers,
    )
    assert create_res.status_code == 200
    task_id = create_res.json()["id"]

    # Fire department rejects task on safety grounds
    rej_res = client.put(
        f"/api/coordination/v1/tasks/{task_id}",
        json={"status": "REJECTED", "rejection_reason": "Floor structural collapse imminent; safety officer ordered defensive posture."},
        headers=fire_headers,
    )
    assert rej_res.status_code == 200
    assert rej_res.json()["status"] == "REJECTED"
    assert "structural collapse" in rej_res.json()["rejection_reason"]


def test_mutual_aid_declined_and_cancelled_flow(client: TestClient, m11_setup: dict):
    incident_id = m11_setup["incident"].id
    ems_headers = m11_setup["headers_ems"]
    police_headers = m11_setup["headers_police"]
    police_org_id = m11_setup["org_police"].id

    # Request 1: Declined by receiving agency
    req1 = client.post(
        f"/api/coordination/v1/incidents/{incident_id}/resource-requests",
        json={
            "requested_organization_id": police_org_id,
            "resource_type": "HELICOPTER",
            "quantity": 1,
            "urgency": "ROUTINE",
            "operational_justification": "Aerial survey of plant",
        },
        headers=ems_headers,
    )
    assert req1.status_code == 200
    req1_id = req1.json()["id"]

    dec_res = client.post(
        f"/api/coordination/v1/resource-requests/{req1_id}/action",
        json={"action": "DECLINE", "decision_notes": "All aviation units grounded due to low ceiling storm."},
        headers=police_headers,
    )
    assert dec_res.status_code == 200
    assert dec_res.json()["status"] == "DECLINED"

    # Request 2: Cancelled by requesting agency
    req2 = client.post(
        f"/api/coordination/v1/incidents/{incident_id}/resource-requests",
        json={
            "requested_organization_id": police_org_id,
            "resource_type": "POLICE_PATROL",
            "quantity": 3,
            "urgency": "ROUTINE",
            "operational_justification": "Traffic reroute",
        },
        headers=ems_headers,
    )
    req2_id = req2.json()["id"]

    canc_res = client.post(
        f"/api/coordination/v1/resource-requests/{req2_id}/action",
        json={"action": "CANCEL", "decision_notes": "Private security redirected traffic; patrols not required."},
        headers=ems_headers,
    )
    assert canc_res.status_code == 200
    assert canc_res.json()["status"] == "CANCELLED"


def test_superadmin_full_cop_access(client: TestClient, m11_setup: dict):
    incident_id = m11_setup["incident"].id
    super_headers = m11_setup["headers_superadmin"]

    res = client.get(f"/api/coordination/v1/incidents/{incident_id}/operational-picture", headers=super_headers)
    assert res.status_code == 200
    cop = res.json()
    assert cop["summary"] is not None
    assert cop["location"] is not None
    assert cop["participating_agencies"] is not None
    assert len(cop["granted_scopes"]) == 10  # All 10 valid scopes granted to superadmin


def test_operational_zones_geojson_polygon(client: TestClient, m11_setup: dict):
    incident_id = m11_setup["incident"].id
    fire_headers = m11_setup["headers_fire"]

    polygon_data = {
        "type": "Polygon",
        "coordinates": [
            [
                [76.6380, 12.3290],
                [76.6420, 12.3290],
                [76.6420, 12.3320],
                [76.6380, 12.3320],
                [76.6380, 12.3290],
            ]
        ],
    }

    zone_payload = {
        "zone_type": "EVACUATION_ZONE",
        "name": "Residential Downwind Sector 1",
        "description": "Downwind plume dispersion sector. Mandatory evacuation order issued.",
        "polygon_geojson": json.dumps(polygon_data),
        "hazard_type": "TOXIC_SMOKE_PLUME",
        "access_restrictions": "Full evacuation; ingress restricted to emergency services.",
    }
    res = client.post(f"/api/coordination/v1/incidents/{incident_id}/zones", json=zone_payload, headers=fire_headers)
    assert res.status_code == 200
    assert res.json()["zone_type"] == "EVACUATION_ZONE"
    assert "Polygon" in res.json()["polygon_geojson"]

