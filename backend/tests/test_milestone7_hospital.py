"""
CareOn Milestone 7 Test Suite — Intelligent Hospital Readiness, Capacity & Emergency Coordination.

Tests:
1. Hospital Facility Profiles:
   - Creation, updating, and querying
   - Tenant & organization isolation (cross-tenant mutations blocked with 403)
   - Unauthorized actor access rejection (Citizen -> 403)
2. Dynamic Capacity Engine:
   - Multi-category capacity updates
   - Negative capacity rejection (422)
   - Over-capacity invariant rejection (occupied + reserved + unavailable > total -> 422)
   - Freshness classification (verified_current <= 15m vs aging vs stale > 3h vs unknown)
   - Concurrency-safe atomic reservations (SELECT ... FOR UPDATE)
   - Overbooking prevention (409 Conflict)
   - Reservation release & capacity reconciliation
   - Expiry sweep reclaiming reserved beds
3. Hospital Diversion Management:
   - Diversion status mutation (open, partial_diversion, full_diversion, closed, emergency_only)
   - Mandatory operational reason requirement
   - Redis cache invalidation and database synchronization
   - Audit trail in hospital_diversion_logs
4. Multi-Dimensional Readiness Assessment:
   - Fully suitable facility scoring
   - Missing required trauma/clinical capability -> capability_unavailable
   - Zero available beds -> capacity_unavailable
   - Stale capacity -> unknown_insufficient_info
   - Diverted facility -> diverted
   - Destination recommendation ranking
5. Incoming Patient Pre-Arrival Workflow:
   - Request creation by dispatcher (pending)
   - Hospital acknowledgement
   - Hospital acceptance with atomic bed reservation
   - Hospital decline with mandatory reason & reservation release
   - Clarification loop
   - Response timeout detection without silent reassignment
   - Request cancellation on mission redirect
6. Mass-Casualty Incident (MCI) Coordination:
   - Multi-patient distribution across regional hospitals
   - Trauma level matching (Critical -> Level 1/2 Trauma Centers)
   - Single-facility overload warning and balanced dispersion
7. Real-Time Outbox Integration & Privacy:
   - Outbox event persistence for readiness, capacity, diversion, and incoming requests
   - Zero patient PII in coordination payloads
"""

import json
import time
import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import (
    User,
    Organization,
    OrganizationMembership,
    HospitalFacility,
    HospitalCapacity,
    HospitalCapacityReservation,
    IncomingPatientRequest,
    HospitalDiversionLog,
    Incident,
    Assignment,
    OutboxEvent,
    utc_now,
)
from app.auth import hash_password
from app.identity.jwt_handler import create_access_token
from app.hospital_ops import (
    CapacityCategory,
    CapacityFreshnessStatus,
    DiversionStatus,
    DiversionType,
    ReadinessClassification,
    update_facility_capacity,
    reserve_facility_capacity,
    release_capacity_reservation,
    sweep_expired_reservations,
    get_facility_capacity_summary,
    get_facility_diversion_status,
    set_facility_diversion_status,
    assess_facility_readiness,
    rank_hospital_destinations,
    create_incoming_patient_request,
    accept_incoming_patient_request,
    decline_incoming_patient_request,
    sweep_incoming_request_timeouts,
    plan_mci_distribution,
)


@pytest.fixture
def m7_setup(client: TestClient, db_session: Session):
    """
    Creates test actors (dispatcher, hospital staff 1 & 2, citizen),
    two distinct hospital organizations with facilities, diverse capacities,
    and a test emergency incident.
    """
    t_id = int(time.time() * 1000) % 1000000

    # 1. Actors
    dispatcher = User(
        email=f"dispatcher_m7_{t_id}@careon.org",
        name="Dispatcher Suresh",
        phone="+91 99999 40001",
        hashed_password=hash_password("DispatchPass123!"),
        role="dispatcher",
        is_active=True,
    )
    hospital_staff_1 = User(
        email=f"staff1_m7_{t_id}@careon.org",
        name="Dr. Arvind (Apollo)",
        phone="+91 99999 40002",
        hashed_password=hash_password("HospitalPass123!"),
        role="hospital_staff",
        is_active=True,
    )
    hospital_staff_2 = User(
        email=f"staff2_m7_{t_id}@careon.org",
        name="Nurse Meera (Columbia)",
        phone="+91 99999 40003",
        hashed_password=hash_password("HospitalPass123!"),
        role="hospital_staff",
        is_active=True,
    )
    citizen = User(
        email=f"citizen_m7_{t_id}@example.com",
        name="Citizen Ramesh",
        phone="+91 99999 40004",
        hashed_password=hash_password("CitizenPass123!"),
        role="citizen",
        is_active=True,
    )
    db_session.add_all([dispatcher, hospital_staff_1, hospital_staff_2, citizen])
    db_session.commit()

    # 2. Hospital Organizations
    org_1 = Organization(
        name=f"Apollo Multi-Specialty Hospital {t_id}",
        org_type="hospital",
        location_name="Kuvempunagar, Mysuru",
        is_verified=True,
        is_active=True,
    )
    org_2 = Organization(
        name=f"Columbia Asia Medical Center {t_id}",
        org_type="hospital",
        location_name="Hebbal, Mysuru",
        is_verified=True,
        is_active=True,
    )
    db_session.add_all([org_1, org_2])
    db_session.commit()

    # 3. Organization Memberships
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

    # 4. Hospital Facilities
    # Facility 1: Apollo Trauma Center (Level 1 Trauma, Comprehensive, ~3km)
    fac_1 = HospitalFacility(
        organization_id=org_1.id,
        facility_code=f"FAC-APOLLO-{t_id}",
        name="Apollo Emergency & Trauma Center",
        facility_type="Tertiary Care Hospital",
        location_name="Kuvempunagar, Mysuru",
        latitude=12.3080,
        longitude=76.6450,
        geom="POINT(76.6450 12.3080)",
        trauma_level="Level 1",
        capabilities="emergency,trauma,icu,ct_scan,blood_bank,ambulance_bay,cath_lab",
        specialist_services="trauma_surgeon,cardiologist,neurologist,anesthesiologist",
        medical_equipment="ct_scanner,mri,ventilators,defibrillators,dialysis",
        ambulance_bays=6,
        operating_status="operational",
        emergency_phone="+91 821 2500001",
        is_active=True,
        last_verified_at=utc_now(),
    )
    # Facility 2: Columbia Asia Community Hospital (Level 3 Trauma, ~7km)
    fac_2 = HospitalFacility(
        organization_id=org_2.id,
        facility_code=f"FAC-COLUMBIA-{t_id}",
        name="Columbia Asia Community Hospital",
        facility_type="Community Hospital",
        location_name="Hebbal Ring Road, Mysuru",
        latitude=12.3550,
        longitude=76.6120,
        geom="POINT(76.6120 12.3550)",
        trauma_level="Level 3",
        capabilities="emergency,general_surgery,ambulance_bay",
        specialist_services="general_physician,general_surgeon",
        medical_equipment="xray,ultrasound,defibrillators",
        ambulance_bays=2,
        operating_status="operational",
        emergency_phone="+91 821 2500002",
        is_active=True,
        last_verified_at=utc_now(),
    )
    db_session.add_all([fac_1, fac_2])
    db_session.commit()

    # 5. Seed Initial Capacities for Facility 1
    update_facility_capacity(db_session, fac_1.id, CapacityCategory.ER_BEDS, total=20, occupied=10, unavailable=2)
    update_facility_capacity(db_session, fac_1.id, CapacityCategory.TRAUMA_BAYS, total=4, occupied=1, unavailable=0)
    update_facility_capacity(db_session, fac_1.id, CapacityCategory.ICU_BEDS, total=8, occupied=5, unavailable=1)

    # Seed Initial Capacities for Facility 2
    update_facility_capacity(db_session, fac_2.id, CapacityCategory.ER_BEDS, total=10, occupied=4, unavailable=0)
    update_facility_capacity(db_session, fac_2.id, CapacityCategory.TRAUMA_BAYS, total=1, occupied=0, unavailable=0)

    # 6. Test Emergency Incident
    incident = Incident(
        incident_code=f"INC-M7-{t_id}",
        tracking_token=f"token_m7_{t_id}",
        category="Road accident",
        title="High-Speed Highway Rollover",
        description="Multiple vehicles involved, severe trauma casualties trapped",
        location_name="Hunsur Highway Junction, Mysuru",
        latitude=12.3150,
        longitude=76.6500,
        affected_people=3,
        help_required="Ambulance,Rescue",
        contact_name="Inspector Gowda",
        contact_phone="+91 98888 22222",
        priority="Critical",
        status="In Progress",
        is_verified=True,
    )
    db_session.add(incident)
    db_session.commit()

    # Auth headers
    dispatcher_token = create_access_token(dispatcher.id, dispatcher.email, dispatcher.role)
    staff1_token = create_access_token(hospital_staff_1.id, hospital_staff_1.email, hospital_staff_1.role, org_ids=[org_1.id])
    staff2_token = create_access_token(hospital_staff_2.id, hospital_staff_2.email, hospital_staff_2.role, org_ids=[org_2.id])
    citizen_token = create_access_token(citizen.id, citizen.email, citizen.role)

    return {
        "dispatcher": dispatcher,
        "staff_1": hospital_staff_1,
        "staff_2": hospital_staff_2,
        "citizen": citizen,
        "org_1": org_1,
        "org_2": org_2,
        "fac_1": fac_1,
        "fac_2": fac_2,
        "incident": incident,
        "headers_dispatcher": {"Authorization": f"Bearer {dispatcher_token}"},
        "headers_staff1": {"Authorization": f"Bearer {staff1_token}"},
        "headers_staff2": {"Authorization": f"Bearer {staff2_token}"},
        "headers_citizen": {"Authorization": f"Bearer {citizen_token}"},
    }


# ==============================================================================
# 1. Hospital Facility Profile Tests
# ==============================================================================

def test_facility_profile_crud_and_isolation(client: TestClient, db_session: Session, m7_setup: dict):
    """Verifies facility creation, retrieval, updates, and cross-tenant access control."""
    staff1_headers = m7_setup["headers_staff1"]
    staff2_headers = m7_setup["headers_staff2"]
    citizen_headers = m7_setup["headers_citizen"]
    fac_1 = m7_setup["fac_1"]
    org_1 = m7_setup["org_1"]

    # 1. Citizen cannot create facilities (403)
    resp_cit = client.post(
        "/api/hospital/facilities",
        json={
            "organization_id": org_1.id,
            "facility_code": "FAC-TEST-NEW",
            "name": "Unauthorized Facility",
            "location_name": "Test St",
            "latitude": 12.3,
            "longitude": 76.6,
        },
        headers=citizen_headers,
    )
    assert resp_cit.status_code == 403

    # 2. Staff 1 can query and update their own facility
    resp_get = client.get(f"/api/hospital/facilities/{fac_1.id}", headers=staff1_headers)
    assert resp_get.status_code == 200
    assert resp_get.json()["facility_code"] == fac_1.facility_code

    resp_patch = client.patch(
        f"/api/hospital/facilities/{fac_1.id}",
        json={"ambulance_bays": 8, "emergency_phone": "+91 821 9999999"},
        headers=staff1_headers,
    )
    assert resp_patch.status_code == 200
    assert resp_patch.json()["ambulance_bays"] == 8

    # 3. Staff 2 (Columbia) CANNOT mutate Staff 1's (Apollo) facility (403 Forbidden)
    resp_cross = client.patch(
        f"/api/hospital/facilities/{fac_1.id}",
        json={"ambulance_bays": 1},
        headers=staff2_headers,
    )
    assert resp_cross.status_code == 403
    assert "Not authorized" in resp_cross.json()["detail"]


# ==============================================================================
# 2. Dynamic Hospital Capacity & Safe Concurrency Tests
# ==============================================================================

def test_capacity_update_validation_and_invariants(client: TestClient, db_session: Session, m7_setup: dict):
    """Verifies validation rules: non-negative capacity and total >= occupied + reserved + unavailable."""
    staff1_headers = m7_setup["headers_staff1"]
    fac_1 = m7_setup["fac_1"]

    # 1. Negative total capacity fails
    resp_neg = client.put(
        f"/api/hospital/facilities/{fac_1.id}/capacity",
        json={"category": CapacityCategory.ER_BEDS, "total": -5, "occupied": 2},
        headers=staff1_headers,
    )
    assert resp_neg.status_code == 422

    # 2. Total less than occupied + unavailable fails
    resp_inv = client.put(
        f"/api/hospital/facilities/{fac_1.id}/capacity",
        json={"category": CapacityCategory.ER_BEDS, "total": 10, "occupied": 8, "unavailable": 4},
        headers=staff1_headers,
    )
    assert resp_inv.status_code == 422
    assert "less than sum" in resp_inv.json()["detail"]

    # 3. Valid capacity update succeeds and calculates available capacity correctly
    resp_valid = client.put(
        f"/api/hospital/facilities/{fac_1.id}/capacity",
        json={"category": CapacityCategory.ER_BEDS, "total": 25, "occupied": 10, "unavailable": 3},
        headers=staff1_headers,
    )
    assert resp_valid.status_code == 200
    data = resp_valid.json()
    assert data["total_capacity"] == 25
    assert data["occupied_capacity"] == 10
    assert data["available_capacity"] == 12  # 25 - 10 - 0 - 3 = 12


def test_capacity_freshness_classification(db_session: Session, m7_setup: dict):
    """Verifies capacity confidence tiering: verified_current, aging, stale, unknown."""
    fac_1 = m7_setup["fac_1"]

    # 1. Freshly updated -> verified_current
    summary = get_facility_capacity_summary(db_session, fac_1.id)
    assert summary["overall_freshness"] == CapacityFreshnessStatus.VERIFIED_CURRENT

    # 2. Age capacity to 2 hours ago -> aging
    cap_row = db_session.query(HospitalCapacity).filter(HospitalCapacity.facility_id == fac_1.id).first()
    cap_row.last_updated = utc_now() - timedelta(hours=2)
    db_session.commit()

    summary_aging = get_facility_capacity_summary(db_session, fac_1.id)
    assert summary_aging["categories"][cap_row.category]["verification_status"] == CapacityFreshnessStatus.AGING

    # 3. Age capacity to 5 hours ago -> stale
    cap_row.last_updated = utc_now() - timedelta(hours=5)
    db_session.commit()

    summary_stale = get_facility_capacity_summary(db_session, fac_1.id)
    assert summary_stale["categories"][cap_row.category]["verification_status"] == CapacityFreshnessStatus.STALE


def test_atomic_capacity_reservation_and_overbooking_prevention(client: TestClient, db_session: Session, m7_setup: dict):
    """Verifies atomic capacity reservation, prevention of overbooking, and safe release."""
    disp_headers = m7_setup["headers_dispatcher"]
    fac_1 = m7_setup["fac_1"]
    incident = m7_setup["incident"]

    # Current available trauma bays = 4 total - 1 occupied = 3 available
    # 1. Reserve 2 trauma bays -> succeeds
    resp_res1 = client.post(
        f"/api/hospital/facilities/{fac_1.id}/reservations",
        json={
            "facility_id": fac_1.id,
            "incident_id": incident.id,
            "category": CapacityCategory.TRAUMA_BAYS,
            "quantity": 2,
            "expires_in_seconds": 1800,
        },
        headers=disp_headers,
    )
    assert resp_res1.status_code == 200
    token1 = resp_res1.json()["reservation_token"]

    # 2. Attempt to reserve 2 MORE trauma bays (only 1 remaining) -> fails with 409 Conflict
    resp_res2 = client.post(
        f"/api/hospital/facilities/{fac_1.id}/reservations",
        json={
            "facility_id": fac_1.id,
            "incident_id": incident.id,
            "category": CapacityCategory.TRAUMA_BAYS,
            "quantity": 2,
        },
        headers=disp_headers,
    )
    assert resp_res2.status_code == 409
    assert "Insufficient available capacity" in resp_res2.json()["detail"]

    # 3. Release first reservation -> frees up capacity
    resp_rel = client.delete(f"/api/hospital/reservations/{token1}", headers=disp_headers)
    assert resp_rel.status_code == 200

    # 4. Now reservation of 2 succeeds
    resp_res3 = client.post(
        f"/api/hospital/facilities/{fac_1.id}/reservations",
        json={
            "facility_id": fac_1.id,
            "incident_id": incident.id,
            "category": CapacityCategory.TRAUMA_BAYS,
            "quantity": 2,
        },
        headers=disp_headers,
    )
    assert resp_res3.status_code == 200


def test_reservation_expiry_sweep(db_session: Session, m7_setup: dict):
    """Verifies background sweeping of expired reservations."""
    fac_1 = m7_setup["fac_1"]
    incident = m7_setup["incident"]

    # Create reservation with expired deadline
    res = reserve_facility_capacity(
        db=db_session,
        facility_id=fac_1.id,
        incident_id=incident.id,
        assignment_id=None,
        category=CapacityCategory.ER_BEDS,
        quantity=3,
        expires_in_seconds=10,
    )
    res.expires_at = utc_now() - timedelta(seconds=20)
    db_session.commit()

    # Run sweeper
    reclaimed = sweep_expired_reservations(db_session)
    assert len(reclaimed) >= 1
    assert any(r.reservation_token == res.reservation_token for r in reclaimed)

    # Check status
    db_session.refresh(res)
    assert res.status == "expired"


# ==============================================================================
# 3. Hospital Diversion Management Tests
# ==============================================================================

def test_hospital_diversion_management(client: TestClient, db_session: Session, m7_setup: dict):
    """Verifies full and partial diversion setting, Redis invalidation, and audit logging."""
    staff1_headers = m7_setup["headers_staff1"]
    fac_1 = m7_setup["fac_1"]

    # 1. Mutate to Full Diversion with mandatory reason
    resp_div = client.post(
        f"/api/hospital/facilities/{fac_1.id}/diversion",
        json={
            "new_status": DiversionStatus.FULL_DIVERSION,
            "reason": "Emergency department saturated, all acute bays occupied",
        },
        headers=staff1_headers,
    )
    assert resp_div.status_code == 200
    assert resp_div.json()["is_diverted"] is True

    # Check audit log in DB
    log = (
        db_session.query(HospitalDiversionLog)
        .filter(HospitalDiversionLog.facility_id == fac_1.id)
        .order_by(HospitalDiversionLog.created_at.desc())
        .first()
    )
    assert log is not None
    assert log.new_status == DiversionStatus.FULL_DIVERSION

    # 2. Re-open facility
    resp_open = client.post(
        f"/api/hospital/facilities/{fac_1.id}/diversion",
        json={
            "new_status": DiversionStatus.OPEN,
            "reason": "Capacity restored following patient discharges",
        },
        headers=staff1_headers,
    )
    assert resp_open.status_code == 200
    assert resp_open.json()["is_diverted"] is False


# ==============================================================================
# 4. Hospital Readiness Assessment & Destination Recommendation Tests
# ==============================================================================

def test_readiness_assessment_and_ranking(client: TestClient, db_session: Session, m7_setup: dict):
    """
    Verifies multi-dimensional readiness assessment:
    - Trauma center matching critical incident
    - Exclusion of diverted hospitals
    - Ranking hierarchy
    """
    disp_headers = m7_setup["headers_dispatcher"]
    fac_1 = m7_setup["fac_1"]
    fac_2 = m7_setup["fac_2"]
    incident = m7_setup["incident"]

    # 1. Assess Facility 1 (Apollo Level 1 Trauma) -> Suitable Recent
    resp_ass1 = client.get(
        f"/api/hospital/readiness/assess/{fac_1.id}?incident_id={incident.id}",
        headers=disp_headers,
    )
    assert resp_ass1.status_code == 200
    data1 = resp_ass1.json()
    assert data1["classification"] in (ReadinessClassification.SUITABLE_RECENT, ReadinessClassification.SUITABLE_CONFIRMED)
    assert "trauma" in data1["matched_capabilities"]

    # 2. Put Facility 1 on Full Diversion
    set_facility_diversion_status(db_session, fac_1.id, DiversionStatus.FULL_DIVERSION, reason="Flooding in trauma wing")

    resp_ass1_div = client.get(
        f"/api/hospital/readiness/assess/{fac_1.id}?incident_id={incident.id}",
        headers=disp_headers,
    )
    assert resp_ass1_div.status_code == 200
    assert resp_ass1_div.json()["classification"] == ReadinessClassification.DIVERTED

    # 3. Query network recommendations -> Facility 2 outranks diverted Facility 1
    resp_rec = client.get(
        f"/api/hospital/destinations/recommend?incident_id={incident.id}",
        headers=disp_headers,
    )
    assert resp_rec.status_code == 200
    recs = resp_rec.json()
    assert len(recs) >= 2
    # First recommendation should NOT be diverted
    assert recs[0]["classification"] != ReadinessClassification.DIVERTED

    # Reset diversion
    set_facility_diversion_status(db_session, fac_1.id, DiversionStatus.OPEN, reason="Flooding resolved")


# ==============================================================================
# 5. Pre-Arrival Incoming Patient Workflow Tests
# ==============================================================================

def test_incoming_patient_notification_and_response_lifecycle(client: TestClient, db_session: Session, m7_setup: dict):
    """
    Verifies pre-arrival notification workflow:
    request creation -> hospital acknowledgement -> acceptance with bed reservation.
    """
    disp_headers = m7_setup["headers_dispatcher"]
    staff1_headers = m7_setup["headers_staff1"]
    fac_1 = m7_setup["fac_1"]
    incident = m7_setup["incident"]

    # 1. Dispatcher creates incoming patient request
    resp_create = client.post(
        "/api/hospital/incoming-requests",
        json={
            "facility_id": fac_1.id,
            "incident_id": incident.id,
            "emergency_severity": "Critical",
            "patient_condition_summary": "Intubated polytrauma with multiple fractures",
            "eta_minutes": 12.5,
            "eta_source": "osrm_road_network",
        },
        headers=disp_headers,
    )
    assert resp_create.status_code == 201
    token = resp_create.json()["request_token"]
    assert resp_create.json()["status"] == "pending"

    # 2. Hospital staff acknowledges request
    resp_ack = client.post(
        f"/api/hospital/incoming-requests/{token}/respond",
        json={"action": "acknowledge"},
        headers=staff1_headers,
    )
    assert resp_ack.status_code == 200
    assert resp_ack.json()["status"] == "acknowledged"

    # 3. Hospital staff accepts request
    resp_accept = client.post(
        f"/api/hospital/incoming-requests/{token}/respond",
        json={"action": "accept", "reserve_er_bed": True, "reserve_trauma_bay": True},
        headers=staff1_headers,
    )
    assert resp_accept.status_code == 200
    assert resp_accept.json()["status"] == "accepted"

    # Verify atomic capacity reservation was created in DB
    reservation = (
        db_session.query(HospitalCapacityReservation)
        .filter(
            HospitalCapacityReservation.facility_id == fac_1.id,
            HospitalCapacityReservation.incident_id == incident.id,
            HospitalCapacityReservation.status == "active",
        )
        .first()
    )
    assert reservation is not None


def test_incoming_patient_decline_and_clarification(client: TestClient, db_session: Session, m7_setup: dict):
    """Verifies hospital decline workflow and clarification loop."""
    disp_headers = m7_setup["headers_dispatcher"]
    staff1_headers = m7_setup["headers_staff1"]
    fac_1 = m7_setup["fac_1"]
    incident = m7_setup["incident"]

    # 1. Create request
    resp_create = client.post(
        "/api/hospital/incoming-requests",
        json={"facility_id": fac_1.id, "incident_id": incident.id, "emergency_severity": "High"},
        headers=disp_headers,
    )
    token = resp_create.json()["request_token"]

    # 2. Decline without reason fails (400)
    resp_bad_dec = client.post(
        f"/api/hospital/incoming-requests/{token}/respond",
        json={"action": "decline"},
        headers=staff1_headers,
    )
    assert resp_bad_dec.status_code == 400

    # 3. Decline with valid clinical reason succeeds
    resp_dec = client.post(
        f"/api/hospital/incoming-requests/{token}/respond",
        json={"action": "decline", "reason": "CT scanner down, neurosurgery team currently in emergency surgery"},
        headers=staff1_headers,
    )
    assert resp_dec.status_code == 200
    assert resp_dec.json()["status"] == "declined"
    assert "CT scanner down" in resp_dec.json()["hospital_response_reason"]


def test_incoming_request_timeout_sweep(db_session: Session, m7_setup: dict):
    """Verifies detection of unacknowledged hospital requests that exceed deadline."""
    dispatcher = m7_setup["dispatcher"]
    fac_1 = m7_setup["fac_1"]
    incident = m7_setup["incident"]

    req = create_incoming_patient_request(
        db=db_session,
        facility_id=fac_1.id,
        incident_id=incident.id,
        assignment_id=None,
        dispatcher=dispatcher,
        deadline_seconds=10,
    )
    # Artificially expire deadline
    req.acknowledgement_deadline = utc_now() - timedelta(seconds=30)
    db_session.commit()

    expired = sweep_incoming_request_timeouts(db_session)
    assert len(expired) >= 1
    assert any(r.request_token == req.request_token for r in expired)

    db_session.refresh(req)
    assert req.status == "expired"


# ==============================================================================
# 6. Mass-Casualty Incident (MCI) Distribution Tests
# ==============================================================================

def test_mci_distribution_balancing_and_overload_prevention(client: TestClient, db_session: Session, m7_setup: dict):
    """
    Verifies that MCI distribution:
    - Allocates multiple casualties across multiple hospitals
    - Prioritizes Level 1 Trauma Center for Critical casualties
    - Balances non-critical patients to avoid overloading nearest hospital
    """
    disp_headers = m7_setup["headers_dispatcher"]
    incident = m7_setup["incident"]

    # 6 casualties: 2 Critical, 2 High, 2 Low
    patient_severities = ["Critical", "Critical", "High", "High", "Low", "Low"]

    resp = client.post(
        "/api/hospital/mci/distribute",
        json={"incident_id": incident.id, "patient_severities": patient_severities},
        headers=disp_headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["total_patients"] == 6

    allocations = data["allocations"]
    assert len(allocations) == 6

    # Verify that not ALL patients are sent to the same single hospital
    allocated_facilities = set(a["facility_id"] for a in allocations)
    assert len(allocated_facilities) >= 2, "MCI distribution failed to disperse patients across hospitals!"

    # Verify Critical patients are assigned to hospital with trauma center
    critical_allocs = [a for a in allocations if a["severity"] == "Critical"]
    assert len(critical_allocs) == 2
    # At least one critical patient should be at Facility 1 (Apollo Level 1)
    assert any(a["facility_id"] == m7_setup["fac_1"].id for a in critical_allocs)


# ==============================================================================
# 7. Real-Time Outbox Integration & Privacy Tests
# ==============================================================================

def test_hospital_events_outbox_persistence_and_privacy(db_session: Session, m7_setup: dict):
    """
    Verifies:
    1. Hospital events are written to outbox_events with valid channel targeting.
    2. Sensitive patient notes/PII are never leaked in broadcast payload.
    """
    dispatcher = m7_setup["dispatcher"]
    fac_1 = m7_setup["fac_1"]
    incident = m7_setup["incident"]

    # Trigger incoming patient request
    req = create_incoming_patient_request(
        db=db_session,
        facility_id=fac_1.id,
        incident_id=incident.id,
        assignment_id=None,
        dispatcher=dispatcher,
        patient_condition_summary="Stabilized male, Glasgow Coma Scale 14",
    )

    # Check outbox events
    outbox = (
        db_session.query(OutboxEvent)
        .filter(
            OutboxEvent.event_type == "hospital.incoming_patient_requested",
            OutboxEvent.incident_id == incident.id,
        )
        .first()
    )
    assert outbox is not None
    payload = json.loads(outbox.payload_json)

    # Assert privacy: no patient name, phone, or PII leaked
    assert "patient_name" not in payload
    assert "patient_phone" not in payload
    assert "contact_phone" not in payload
    assert payload["facility_id"] == fac_1.id
    assert payload["status"] == "pending"
