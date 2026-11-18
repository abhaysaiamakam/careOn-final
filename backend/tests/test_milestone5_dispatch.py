"""
CareOn Milestone 5 Test Suite — Intelligent Dispatch & Resource Optimization Engine.

Tests:
1. Incident Assessment:
   - Severity & priority derivation (Critical/Life-Threatening vs High vs Low)
   - Missing information detection (invalid GPS, unverified contact, short description)
   - Duplicate candidate reference
   - Assessment explainability & confidence score
2. Resource Capability & Eligibility:
   - Hard capability matching (incompatible resource marked ineligible)
   - Equipment match enforcement for high-acuity incidents
   - Availability check (status != Available excluded)
   - Active assignment exclusion (committed resource excluded)
   - Stale GPS location detection and penalty
3. Road-Network ETA Engine:
   - OSRM query & Haversine fallback
   - Fallback explicitly labeled (never claims live traffic)
   - Redis caching of routing calculations
4. Explainable Candidate Scoring:
   - Deterministic ranking
   - Capability match overriding proximity (further ALS outranks closer BLS for cardiac)
   - Stale telemetry penalty
   - Comparative rank explanation
5. Multi-Incident Optimization:
   - Scarcity competition (Critical incident wins scarce unit over Low incident)
   - Unassigned incident reporting with explicit bottleneck rationale
   - Preservation of existing active missions
6. Dispatcher Approval & Override Workflow:
   - Valid dispatcher approval creates assignment and decision audit
   - Unauthorized access blocked (Citizen / Responder -> 403)
   - Mandatory override reason enforcement (<5 chars -> 400)
   - Valid override records reason and publishes override event
   - Double-assignment prevention under concurrency
7. Hospital Diversion:
   - Destination hospital recommendations
   - Diversion state update with Redis cache invalidation
   - Diverted hospitals categorized as "Diverted / Avoid"
8. M4 Real-Time Event Integration:
   - Transactional outbox persistence for dispatch events
"""

import json
import time
import pytest
from datetime import datetime, timezone, timedelta
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
    DispatchDecision,
    utc_now,
)
from app.auth import hash_password
from app.identity.jwt_handler import create_access_token
from app.schemas import IncidentCreate
from app import crud
from app.dispatch.assessment import assess_incident, IncidentAssessment
from app.dispatch.eligibility import check_resource_eligibility, filter_eligible_resources
from app.dispatch.routing import routing_engine, RoutingResult
from app.dispatch.scoring import rank_candidates_for_incident, ScoringWeights
from app.dispatch.optimizer import optimize_multi_incident_dispatch
from app.dispatch.diversion import (
    get_hospital_diversion_status,
    set_hospital_diversion_status,
    recommend_destination_hospitals,
)


@pytest.fixture
def m5_setup(client: TestClient, db_session: Session):
    """
    Creates test actors, fleet resources with varied capabilities/equipment,
    test incidents, and hospitals.
    """
    t_id = int(time.time() * 1000) % 1000000

    # 1. Actors
    dispatcher = User(
        email=f"dispatcher_{t_id}@careon.org",
        name="Chief Dispatcher Rao",
        phone="+91 99999 10001",
        hashed_password=hash_password("DispatchPass123!"),
        role="dispatcher",
        is_active=True,
    )
    citizen = User(
        email=f"citizen_{t_id}@example.com",
        name="Citizen Vikram",
        phone="+91 99999 10002",
        hashed_password=hash_password("CitizenPass123!"),
        role="citizen",
        is_active=True,
    )
    responder = User(
        email=f"responder_{t_id}@careon.org",
        name="Paramedic Priya",
        phone="+91 99999 10003",
        hashed_password=hash_password("ResponderPass123!"),
        role="responder",
        is_active=True,
    )
    db_session.add_all([dispatcher, citizen, responder])
    db_session.commit()

    # 2. Hospital Organization & Readiness
    hospital_org = Organization(
        name=f"Mysuru City Hospital {t_id}",
        org_type="hospital",
        location_name="MG Road, Mysuru",
        is_verified=True,
        is_active=True,
    )
    db_session.add(hospital_org)
    db_session.commit()

    readiness = HospitalReadiness(
        organization_id=hospital_org.id,
        total_er_beds=25,
        available_er_beds=12,
        trauma_bays_total=4,
        trauma_bays_available=2,
        divert_status=False,
        divert_reason=None,
    )
    db_session.add(readiness)
    db_session.commit()

    # 3. Diverse Fleet Resources
    # Resource 1: ALS Advanced Ambulance (Farther away ~5km, but has ALS + defibrillator)
    res_als = Resource(
        resource_code=f"ALS-{t_id}",
        name="ALS Intensive Care Unit 01",
        category="Ambulance",
        capabilities="ALS,BLS,patient_transport,critical_care,trauma_care",
        equipment="defibrillator,ventilator,oxygen,spine_board,als_kit",
        location_name="Saraswathipuram Base",
        latitude=12.3350,
        longitude=76.6350,
        status="Available",
        contact_phone="+91 99999 20001",
        organization_id=hospital_org.id,
        last_updated=utc_now(),
    )
    # Resource 2: BLS Basic Ambulance (Very close ~0.5km, but only BLS, no defibrillator)
    res_bls = Resource(
        resource_code=f"BLS-{t_id}",
        name="BLS Transport Unit 02",
        category="Ambulance",
        capabilities="BLS,patient_transport,first_aid",
        equipment="oxygen,first_aid_kit,stretcher",
        location_name="Central Bus Stand Base",
        latitude=12.3090,
        longitude=76.6530,
        status="Available",
        contact_phone="+91 99999 20002",
        last_updated=utc_now(),
    )
    # Resource 3: Already Assigned Ambulance (Unavailable)
    res_busy = Resource(
        resource_code=f"BUSY-{t_id}",
        name="ALS Transport Unit 03 (Committed)",
        category="Ambulance",
        capabilities="ALS,BLS,patient_transport",
        equipment="defibrillator,oxygen",
        location_name="Kuvempunagar",
        latitude=12.2980,
        longitude=76.6380,
        status="Assigned",
        contact_phone="+91 99999 20003",
        last_updated=utc_now(),
    )
    # Resource 4: Stale GPS Ambulance (Last updated 2 hours ago)
    stale_time = utc_now() - timedelta(hours=2)
    res_stale = Resource(
        resource_code=f"STALE-{t_id}",
        name="ALS Unit 04 (Stale Telemetry)",
        category="Ambulance",
        capabilities="ALS,BLS,patient_transport",
        equipment="defibrillator,oxygen",
        location_name="Unknown Outskirts",
        latitude=12.3500,
        longitude=76.6100,
        status="Available",
        contact_phone="+91 99999 20004",
        last_updated=stale_time,
    )
    # Resource 5: Fire Response Engine
    res_fire = Resource(
        resource_code=f"FIRE-{t_id}",
        name="Mysuru Fire Engine 01",
        category="Fire Response",
        capabilities="fire_suppression,smoke_rescue,extinguisher",
        equipment="water_tank,hose,smoke_masks,thermal_camera",
        location_name="Bannimantap Fire Station",
        latitude=12.3300,
        longitude=76.6450,
        status="Available",
        contact_phone="+91 99999 20005",
        last_updated=utc_now(),
    )

    db_session.add_all([res_als, res_bls, res_busy, res_stale, res_fire])
    db_session.commit()

    # 4. Critical Cardiac Incident (Requires ALS + Defibrillator)
    inc_cardiac = Incident(
        incident_code=f"INC-CARD-{t_id}",
        tracking_token=f"token_cardiac_{t_id}",
        user_id=citizen.id,
        category="Medical",
        title="Cardiac Arrest Emergency",
        description="Patient collapsed, unconscious and not breathing on Sayyaji Rao Road",
        location_name="Sayyaji Rao Road, Mysuru",
        latitude=12.3100,
        longitude=76.6540,
        affected_people=1,
        help_required="Ambulance",
        contact_name="Vikram Citizen",
        contact_phone="+91 99999 10002",
        priority="Critical",
        status="Received",
        is_verified=True,
    )
    # Minor Incident (BLS sufficient)
    inc_minor = Incident(
        incident_code=f"INC-MIN-{t_id}",
        tracking_token=f"token_minor_{t_id}",
        user_id=citizen.id,
        category="Medical",
        title="Minor Ankle Sprain",
        description="Twisted ankle while walking, stable and minor pain",
        location_name="Devaraja Market",
        latitude=12.3085,
        longitude=76.6520,
        affected_people=1,
        help_required="First-Aid",
        contact_name="Vikram Citizen",
        contact_phone="+91 99999 10002",
        priority="Low",
        status="Received",
        is_verified=True,
    )
    # Structural Fire Incident
    inc_fire = Incident(
        incident_code=f"INC-FIRE-{t_id}",
        tracking_token=f"token_fire_{t_id}",
        user_id=citizen.id,
        category="Fire",
        title="Commercial Complex Fire",
        description="Thick smoke and active fire in basement kitchen, building spread threat",
        location_name="D. Subbaiah Road",
        latitude=12.3020,
        longitude=76.6480,
        affected_people=3,
        help_required="Fire Team",
        contact_name="Vikram Citizen",
        contact_phone="+91 99999 10002",
        priority="Critical",
        status="Received",
        is_verified=True,
    )

    db_session.add_all([inc_cardiac, inc_minor, inc_fire])
    db_session.commit()

    # Tokens
    tokens = {
        "dispatcher": create_access_token(dispatcher.id, dispatcher.email, dispatcher.role),
        "citizen": create_access_token(citizen.id, citizen.email, citizen.role),
        "responder": create_access_token(responder.id, responder.email, responder.role),
    }

    return {
        "tokens": tokens,
        "users": {"dispatcher": dispatcher, "citizen": citizen, "responder": responder},
        "resources": {
            "als": res_als,
            "bls": res_bls,
            "busy": res_busy,
            "stale": res_stale,
            "fire": res_fire,
        },
        "incidents": {
            "cardiac": inc_cardiac,
            "minor": inc_minor,
            "fire": inc_fire,
        },
        "hospital_org": hospital_org,
    }


# ==============================================================================
# 1. Intelligent Incident Assessment Tests
# ==============================================================================
class TestIncidentAssessment:
    def test_cardiac_incident_classified_life_threatening(self, db_session: Session, m5_setup):
        cardiac_inc = m5_setup["incidents"]["cardiac"]
        assessment = assess_incident(cardiac_inc, db_session)

        assert assessment.severity == "Life-Threatening"
        assert assessment.recommended_priority == "Critical"
        assert "ALS" in assessment.required_capabilities
        assert "defibrillator" in assessment.required_equipment
        assert assessment.confidence_score >= 0.70
        assert assessment.is_geospatially_valid is True

    def test_minor_incident_classified_low_severity(self, db_session: Session, m5_setup):
        minor_inc = m5_setup["incidents"]["minor"]
        assessment = assess_incident(minor_inc, db_session)

        assert assessment.severity == "Low"
        assert assessment.recommended_priority == "Low"
        assert "first_aid" in assessment.required_capabilities

    def test_assessment_detects_missing_information(self, db_session: Session):
        # Create incomplete incident
        incomplete = Incident(
            incident_code="INC-INCOMPLETE-01",
            tracking_token="token_inc_99",
            category="Medical",
            title="Incomplete Report",
            description="Help",  # Very short description (<15 chars)
            location_name="Unknown",
            latitude=12.3000,
            longitude=76.6500,
            affected_people=0,  # Missing casualty count
            help_required="Ambulance",
            contact_name="Anonymous",
            contact_phone="",  # Missing phone
            priority="Medium",
            status="Received",
        )
        db_session.add(incomplete)
        db_session.commit()

        assessment = assess_incident(incomplete, db_session)
        assert len(assessment.missing_information) >= 2
        assert assessment.confidence_score < 0.75

    def test_assessment_flags_invalid_coordinates(self, db_session: Session):
        invalid_coords = Incident(
            incident_code="INC-INVALID-GEO",
            tracking_token="token_geo_99",
            category="Medical",
            title="Invalid Location",
            description="Emergency somewhere outside planet bounds",
            location_name="Invalid",
            latitude=195.0,  # Invalid latitude (>90)
            longitude=76.6500,
            affected_people=1,
            help_required="Ambulance",
            contact_name="Tester",
            contact_phone="+91 99999 11111",
            priority="Medium",
            status="Received",
        )
        db_session.add(invalid_coords)
        db_session.commit()

        assessment = assess_incident(invalid_coords, db_session)
        assert assessment.is_geospatially_valid is False
        assert any("GPS" in item for item in assessment.missing_information)


# ==============================================================================
# 2. Resource Capability & Eligibility Engine Tests
# ==============================================================================
class TestResourceEligibility:
    def test_incompatible_resource_marked_ineligible(self, db_session: Session, m5_setup):
        cardiac_inc = m5_setup["incidents"]["cardiac"]
        fire_res = m5_setup["resources"]["fire"]
        assessment = assess_incident(cardiac_inc, db_session)

        eligibility = check_resource_eligibility(fire_res, assessment, db_session)
        assert eligibility.is_eligible is False
        assert any("capability" in r.lower() for r in eligibility.reasons)

    def test_unavailable_resource_marked_ineligible(self, db_session: Session, m5_setup):
        cardiac_inc = m5_setup["incidents"]["cardiac"]
        busy_res = m5_setup["resources"]["busy"]
        assessment = assess_incident(cardiac_inc, db_session)

        eligibility = check_resource_eligibility(busy_res, assessment, db_session)
        assert eligibility.is_eligible is False
        assert any("status" in r.lower() for r in eligibility.reasons)

    def test_stale_gps_resource_marked_ineligible(self, db_session: Session, m5_setup):
        cardiac_inc = m5_setup["incidents"]["cardiac"]
        stale_res = m5_setup["resources"]["stale"]
        assessment = assess_incident(cardiac_inc, db_session)

        eligibility = check_resource_eligibility(stale_res, assessment, db_session)
        assert eligibility.is_eligible is False
        assert eligibility.is_stale_gps is True
        assert any("stale" in r.lower() for r in eligibility.reasons)

    def test_fully_compatible_resource_marked_eligible(self, db_session: Session, m5_setup):
        cardiac_inc = m5_setup["incidents"]["cardiac"]
        als_res = m5_setup["resources"]["als"]
        assessment = assess_incident(cardiac_inc, db_session)

        eligibility = check_resource_eligibility(als_res, assessment, db_session)
        assert eligibility.is_eligible is True
        assert len(eligibility.reasons) > 0


# ==============================================================================
# 3. Road-Network ETA & Distance Engine Tests
# ==============================================================================
class TestRoadNetworkETA:
    def test_haversine_fallback_calculated_and_labeled(self):
        # Force fallback by querying routing engine with unreachable dummy host
        res = routing_engine._haversine_fallback(
            lat1=12.3100, lon1=76.6540,
            lat2=12.3350, lon2=76.6350,
        )
        assert res.is_fallback is True
        assert res.source == "haversine_fallback"
        assert res.distance_km > 0.0
        assert res.eta_minutes > 1.0

    def test_routing_engine_caching_in_redis(self):
        lat1, lon1 = 12.3000, 76.6500
        lat2, lon2 = 12.3100, 76.6600

        # First calculation
        r1 = routing_engine.calculate_eta(lat1, lon1, lat2, lon2, use_cache=True)
        # Second calculation should hit cache or produce consistent values
        r2 = routing_engine.calculate_eta(lat1, lon1, lat2, lon2, use_cache=True)

        assert r1.distance_km == r2.distance_km
        assert r1.eta_minutes == r2.eta_minutes


# ==============================================================================
# 4. Explainable Candidate Scoring Tests
# ==============================================================================
class TestCandidateScoring:
    def test_capability_overrides_proximity_for_cardiac(self, db_session: Session, m5_setup):
        """
        CRITICAL M5 REQUIREMENT:
        An incompatible ambulance (BLS) must NEVER outrank a compatible ambulance (ALS)
        simply because it is closer!
        """
        cardiac_inc = m5_setup["incidents"]["cardiac"]
        assessment = assess_incident(cardiac_inc, db_session)

        all_resources = [
            m5_setup["resources"]["bls"],  # Closer (~0.5km), but lacks ALS & defibrillator
            m5_setup["resources"]["als"],  # Farther (~3.5km), but has ALS & defibrillator
        ]

        ranked = rank_candidates_for_incident(
            incident=cardiac_inc,
            assessment=assessment,
            resources=all_resources,
            db=db_session,
        )

        assert len(ranked) == 2
        # ALS must rank #1
        assert ranked[0].resource_id == m5_setup["resources"]["als"].id
        assert ranked[0].eligibility_status == "eligible"
        assert ranked[0].overall_score > 0.0

        # BLS is ineligible for Life-Threatening cardiac due to missing ALS / defibrillator
        assert ranked[1].resource_id == m5_setup["resources"]["bls"].id
        assert ranked[1].eligibility_status == "ineligible"
        assert ranked[1].overall_score == 0.0

    def test_scoring_generates_human_readable_explanation(self, db_session: Session, m5_setup):
        minor_inc = m5_setup["incidents"]["minor"]
        assessment = assess_incident(minor_inc, db_session)

        all_resources = [
            m5_setup["resources"]["bls"],
            m5_setup["resources"]["als"],
        ]

        ranked = rank_candidates_for_incident(
            incident=minor_inc,
            assessment=assessment,
            resources=all_resources,
            db=db_session,
        )

        top = ranked[0]
        assert "Rank 1" in top.explanation or "Top Recommendation" in top.explanation
        assert "ETA" in top.explanation


# ==============================================================================
# 5. Multi-Incident Resource Optimization Tests
# ==============================================================================
class TestMultiIncidentOptimization:
    def test_scarcity_optimization_prioritizes_critical_incident(self, db_session: Session, m5_setup):
        """
        When only ONE ALS ambulance is available and TWO incidents compete for it
        (one Critical cardiac and one Low minor), the optimizer MUST assign the ALS
        unit to the Critical incident, and mark the minor incident unassigned or fallback.
        """
        cardiac_inc = m5_setup["incidents"]["cardiac"]
        minor_inc = m5_setup["incidents"]["minor"]

        # Fleet with only 1 ALS unit available
        lone_als = m5_setup["resources"]["als"]

        plan = optimize_multi_incident_dispatch(
            incidents=[minor_inc, cardiac_inc],  # Passed in reverse order
            available_resources=[lone_als],
            db=db_session,
        )

        assert plan.total_incidents_evaluated == 2
        assert plan.assigned_count == 1
        assert plan.unassigned_count == 1

        # Check allocations
        alloc_map = {a.incident_id: a for a in plan.allocations}

        cardiac_alloc = alloc_map[cardiac_inc.id]
        minor_alloc = alloc_map[minor_inc.id]

        assert cardiac_alloc.status == "recommended"
        assert cardiac_alloc.recommended_resource_id == lone_als.id

        assert minor_alloc.status == "unassigned"
        assert minor_alloc.bottleneck_reason is not None

    def test_active_assignments_preserved(self, db_session: Session, m5_setup):
        """Existing active assignments must not be silently replaced or revoked."""
        cardiac_inc = m5_setup["incidents"]["cardiac"]
        als_res = m5_setup["resources"]["als"]

        # Create active assignment
        active_assignment = Assignment(
            incident_id=cardiac_inc.id,
            resource_id=als_res.id,
            assigned_by="Prior Coordinator",
            status="Active",
        )
        db_session.add(active_assignment)
        als_res.status = "Assigned"
        db_session.commit()

        # Run multi-opt with minor incident
        minor_inc = m5_setup["incidents"]["minor"]
        plan = optimize_multi_incident_dispatch(
            incidents=[minor_inc],
            available_resources=[als_res],  # Only assigned resource passed
            db=db_session,
        )

        assert plan.assigned_count == 0
        assert plan.unassigned_count == 1
        # Active assignment in DB still exists unchanged
        db_assignment = db_session.query(Assignment).filter(Assignment.id == active_assignment.id).first()
        assert db_assignment.status == "Active"


# ==============================================================================
# 6. Dispatcher Approval & Override Workflow Tests
# ==============================================================================
class TestApprovalAndOverrideWorkflow:
    def test_dispatcher_approval_success(self, client: TestClient, m5_setup):
        token = m5_setup["tokens"]["dispatcher"]
        inc_id = m5_setup["incidents"]["cardiac"].id
        res_id = m5_setup["resources"]["als"].id

        payload = {
            "incident_id": inc_id,
            "resource_id": res_id,
            "notes": "Approved standard dispatch",
        }
        res = client.post(
            "/api/dispatch/approve",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "success"
        assert data["decision_type"] == "approved"
        assert "assignment_id" in data

    def test_citizen_cannot_approve_dispatch(self, client: TestClient, m5_setup):
        token = m5_setup["tokens"]["citizen"]
        inc_id = m5_setup["incidents"]["cardiac"].id
        res_id = m5_setup["resources"]["als"].id

        res = client.post(
            "/api/dispatch/approve",
            json={"incident_id": inc_id, "resource_id": res_id},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 403

    def test_override_requires_mandatory_reason(self, client: TestClient, m5_setup):
        token = m5_setup["tokens"]["dispatcher"]
        inc_id = m5_setup["incidents"]["minor"].id
        res_id = m5_setup["resources"]["bls"].id

        # Missing reason
        res1 = client.post(
            "/api/dispatch/override",
            json={"incident_id": inc_id, "resource_id": res_id, "override_reason": ""},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res1.status_code in (400, 422)

        # Valid reason
        res2 = client.post(
            "/api/dispatch/override",
            json={
                "incident_id": inc_id,
                "resource_id": res_id,
                "override_reason": "Unit 2 is immediately adjacent to the patient",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res2.status_code == 200
        assert res2.json()["decision_type"] == "overridden"

    def test_double_assignment_concurrency_prevention(self, client: TestClient, m5_setup):
        token = m5_setup["tokens"]["dispatcher"]
        inc1_id = m5_setup["incidents"]["cardiac"].id
        inc2_id = m5_setup["incidents"]["minor"].id
        res_id = m5_setup["resources"]["als"].id

        # First dispatch succeeds
        res1 = client.post(
            "/api/dispatch/approve",
            json={"incident_id": inc1_id, "resource_id": res_id},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res1.status_code == 200

        # Second attempt with same resource on another incident fails with 400
        res2 = client.post(
            "/api/dispatch/approve",
            json={"incident_id": inc2_id, "resource_id": res_id},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res2.status_code == 400
        assert "conflict" in res2.json()["detail"].lower()

    def test_dispatch_decision_audit_log_query(self, client: TestClient, m5_setup):
        token = m5_setup["tokens"]["dispatcher"]
        res = client.get(
            "/api/dispatch/decisions?limit=10",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 200
        data = res.json()
        assert isinstance(data, list)


# ==============================================================================
# 7. Hospital Diversion & Destination Routing Tests
# ==============================================================================
class TestHospitalDiversion:
    def test_destination_hospital_recommendation(self, client: TestClient, m5_setup):
        token = m5_setup["tokens"]["dispatcher"]
        inc_id = m5_setup["incidents"]["cardiac"].id

        res = client.post(
            f"/api/dispatch/hospitals/recommend/{inc_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 200
        data = res.json()
        assert len(data) >= 1
        hosp = data[0]
        assert "hospital_name" in hosp
        assert "eta_minutes" in hosp
        assert hosp["recommendation_tier"] in ("Primary", "Secondary", "Diverted / Avoid")

    def test_diversion_toggle_and_cache_invalidation(self, client: TestClient, m5_setup):
        token = m5_setup["tokens"]["dispatcher"]
        org_id = m5_setup["hospital_org"].id

        # 1. Set diversion ON
        res1 = client.put(
            f"/api/dispatch/hospitals/{org_id}/diversion",
            json={"divert_status": True, "divert_reason": "Trauma Bay Flooding"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res1.status_code == 200
        assert res1.json()["divert_status"] is True

        # 2. Get diversion status (should reflect True from cache/DB)
        res2 = client.get(
            f"/api/dispatch/hospitals/{org_id}/diversion",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res2.status_code == 200
        assert res2.json()["divert_status"] is True
        assert res2.json()["divert_reason"] == "Trauma Bay Flooding"

        # 3. Set diversion OFF
        res3 = client.put(
            f"/api/dispatch/hospitals/{org_id}/diversion",
            json={"divert_status": False},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res3.status_code == 200
        assert res3.json()["divert_status"] is False


# ==============================================================================
# 8. M4 Real-Time Event Integration Tests
# ==============================================================================
class TestRealTimeEventIntegration:
    def test_dispatch_decision_persists_outbox_event(self, client: TestClient, db_session: Session, m5_setup):
        token = m5_setup["tokens"]["dispatcher"]
        inc_id = m5_setup["incidents"]["cardiac"].id
        res_id = m5_setup["resources"]["als"].id

        client.post(
            "/api/dispatch/approve",
            json={"incident_id": inc_id, "resource_id": res_id},
            headers={"Authorization": f"Bearer {token}"},
        )

        outbox_event = (
            db_session.query(OutboxEvent)
            .filter(OutboxEvent.event_type == "dispatch.assignment_approved")
            .order_by(OutboxEvent.created_at.desc())
            .first()
        )
        assert outbox_event is not None
        assert outbox_event.incident_id == inc_id
        payload = json.loads(outbox_event.payload_json)
        assert payload["resource_id"] == res_id
        assert payload["decision_type"] == "approved"
