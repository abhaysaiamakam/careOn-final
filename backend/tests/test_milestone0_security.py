import os
import pytest
from concurrent.futures import ThreadPoolExecutor, as_completed
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError
from app.models import Incident, Resource, Assignment, User
from app.auth import validate_and_get_secret_key, INSECURE_DEFAULT_SECRET


# ==============================================================================
# PHASE 2: SEC-001 — Protect Database Reset
# ==============================================================================
def test_simulation_reset_unauthenticated_fails_401(client):
    """Unauthenticated request to reset endpoint must return HTTP 401."""
    res = client.post("/api/simulation/reset")
    assert res.status_code == 401
    assert "credentials" in res.json()["detail"].lower()


def test_simulation_reset_citizen_fails_403(client):
    """Citizen user request to reset endpoint must return HTTP 403."""
    user_login = client.post("/api/auth/login", json={
        "email": "aastha@example.com",
        "password": "user123",
    })
    token = user_login.json()["access_token"]
    res = client.post("/api/simulation/reset", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 403
    assert "administrative privileges" in res.json()["detail"].lower()


def test_simulation_reset_admin_in_dev_succeeds(client):
    """Authorized administrator in development environment can reset demo data."""
    admin_login = client.post("/api/auth/login", json={
        "email": "admin@careon.org",
        "password": "admin123",
    })
    token = admin_login.json()["access_token"]
    res = client.post("/api/simulation/reset", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json()["status"] == "success"


def test_simulation_reset_in_production_fails_403(client, monkeypatch):
    """Reset endpoint must be strictly blocked in production even for administrators."""
    monkeypatch.setenv("CAREON_ENV", "production")
    monkeypatch.setenv("CAREON_SECRET_KEY", "a_very_secure_random_production_secret_key_2026_xyz")
    admin_login = client.post("/api/auth/login", json={
        "email": "admin@careon.org",
        "password": "admin123",
    })
    token = admin_login.json()["access_token"]
    res = client.post("/api/simulation/reset", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 403
    assert "disabled in production" in res.json()["detail"].lower()


# ==============================================================================
# PHASE 3: SEC-002 — Fix Incident Data Access & Anonymous Tracking
# ==============================================================================
def test_incident_details_unauthenticated_fails_401(client):
    """Unauthenticated request to private incident endpoint must return HTTP 401."""
    res = client.get("/api/incidents/CARE-2026-101")
    assert res.status_code == 401
    assert "credentials" in res.json()["detail"].lower()


def test_incident_details_other_user_fails_403(client):
    """User B cannot access User A's private incident record."""
    # Register User A
    user_a = client.post("/api/auth/register", json={
        "name": "User Alpha Sec",
        "email": "alpha_sec@example.com",
        "phone": "+91 99999 11111",
        "password": "password123",
    }).json()

    # User A reports private emergency
    inc = client.post("/api/incidents", json={
        "category": "Medical",
        "description": "Sensitive condition reported.",
        "location_name": "Mysuru Palace East",
        "affected_people": 1,
        "help_required": "First Aid",
        "contact_name": "User Alpha",
        "contact_phone": "+91 99999 11111",
    }, headers={"Authorization": f"Bearer {user_a['access_token']}"}).json()

    # Register User B
    user_b = client.post("/api/auth/register", json={
        "name": "User Beta Sec",
        "email": "beta_sec@example.com",
        "phone": "+91 99999 22222",
        "password": "password123",
    }).json()

    # User B tries to view User A's incident -> HTTP 403
    res_b = client.get(
        f"/api/incidents/{inc['incident_code']}",
        headers={"Authorization": f"Bearer {user_b['access_token']}"},
    )
    assert res_b.status_code == 403
    assert "access denied" in res_b.json()["detail"].lower()

    # User A CAN access their own incident -> HTTP 200
    res_a = client.get(
        f"/api/incidents/{inc['incident_code']}",
        headers={"Authorization": f"Bearer {user_a['access_token']}"},
    )
    assert res_a.status_code == 200
    assert res_a.json()["incident_code"] == inc["incident_code"]

    # Admin CAN access User A's incident -> HTTP 200
    admin_login = client.post("/api/auth/login", json={"email": "admin@careon.org", "password": "admin123"}).json()
    res_admin = client.get(
        f"/api/incidents/{inc['incident_code']}",
        headers={"Authorization": f"Bearer {admin_login['access_token']}"},
    )
    assert res_admin.status_code == 200


def test_public_tracking_with_token_sanitizes_pii(client):
    """Anonymous tracking via tracking_token returns sanitized updates without PII or clinical notes."""
    # Report an incident
    inc = client.post("/api/incidents", json={
        "category": "Road accident",
        "description": "Confidential patient injuries and trauma details.",
        "location_name": "Sayyaji Rao Rd",
        "affected_people": 2,
        "help_required": "ALS Ambulance",
        "contact_name": "Private Contact Person",
        "contact_phone": "+91 98888 77777",
    }).json()

    tracking_token = inc.get("tracking_token")
    assert tracking_token is not None
    assert len(tracking_token) >= 32

    # Public tracking request (No Authorization header!)
    pub_res = client.get(f"/api/incidents/track/{tracking_token}")
    assert pub_res.status_code == 200
    pub_data = pub_res.json()

    # Non-sensitive tracking info is present
    assert pub_data["incident_code"] == inc["incident_code"]
    assert pub_data["category"] == "Road accident"
    assert pub_data["status"] == "Received"
    assert len(pub_data["updates"]) >= 1

    # SENSITIVE DATA MUST NOT BE EXPOSED:
    assert "contact_name" not in pub_data
    assert "contact_phone" not in pub_data
    assert "description" not in pub_data
    assert "verification_otp" not in pub_data
    assert "internal_admin_notes" not in pub_data
    assert "user_id" not in pub_data


def test_public_tracking_invalid_token_returns_404(client):
    """Non-existent tracking token returns HTTP 404."""
    res = client.get("/api/incidents/track/invalid-non-existent-token-xyz")
    assert res.status_code == 404


# ==============================================================================
# PHASE 4: SEC-003 — Fix Incident Cancellation
# ==============================================================================
def test_cancel_incident_unauthenticated_fails_401(client):
    """Unauthenticated cancellation attempt must return HTTP 401."""
    res = client.post("/api/incidents/1/cancel", json={"reason": "Emergency resolved"})
    assert res.status_code == 401


def test_cancel_incident_other_user_fails_403(client):
    """Citizen cannot cancel an incident owned by another citizen."""
    user_a = client.post("/api/auth/register", json={
        "name": "Owner User",
        "email": "owner@example.com",
        "phone": "+91 91111 22222",
        "password": "password123",
    }).json()

    inc = client.post("/api/incidents", json={
        "category": "Medical",
        "description": "Owner emergency",
        "location_name": "Base location",
        "affected_people": 1,
        "help_required": "First Aid",
        "contact_name": "Owner",
        "contact_phone": "+91 91111 22222",
    }, headers={"Authorization": f"Bearer {user_a['access_token']}"}).json()

    user_b = client.post("/api/auth/register", json={
        "name": "Attacker User",
        "email": "attacker@example.com",
        "phone": "+91 93333 44444",
        "password": "password123",
    }).json()

    # User B tries to cancel User A's incident -> HTTP 403
    cancel_res = client.post(
        f"/api/incidents/{inc['id']}/cancel",
        json={"reason": "Request submitted by mistake"},
        headers={"Authorization": f"Bearer {user_b['access_token']}"},
    )
    assert cancel_res.status_code == 403
    assert "access denied" in cancel_res.json()["detail"].lower()


def test_cancel_already_resolved_incident_fails_400(client):
    """Attempting to cancel an already Resolved incident must return HTTP 400."""
    admin_login = client.post("/api/auth/login", json={"email": "admin@careon.org", "password": "admin123"}).json()
    admin_headers = {"Authorization": f"Bearer {admin_login['access_token']}"}

    # CARE-2026-105 is pre-seeded with status 'Resolved'
    inc105 = client.get("/api/incidents/CARE-2026-105", headers=admin_headers).json()
    assert inc105["status"] == "Resolved"

    cancel_res = client.post(
        f"/api/incidents/{inc105['id']}/cancel",
        json={"reason": "Emergency resolved"},
        headers=admin_headers,
    )
    assert cancel_res.status_code == 400
    assert "already resolved" in cancel_res.json()["detail"].lower()


# ==============================================================================
# PHASE 5: SEC-004 — Eliminate Double Resource Assignment & Concurrency
# ==============================================================================
def test_partial_unique_index_blocks_double_active_assignment(db_session):
    """Direct database test verifying the partial unique index rejects concurrent active assignments."""
    # Find AMB-02 which is available
    res = db_session.query(Resource).filter(Resource.resource_code == "AMB-02").first()
    assert res is not None

    # Insert first active assignment
    a1 = Assignment(incident_id=1, resource_id=res.id, status="Active", assigned_by="Coord 1")
    db_session.add(a1)
    db_session.commit()

    # Second active assignment for the same resource MUST fail with IntegrityError
    a2 = Assignment(incident_id=2, resource_id=res.id, status="Active", assigned_by="Coord 2")
    db_session.add(a2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    # After releasing a1, a new active assignment MUST succeed
    a1.status = "Released"
    db_session.commit()

    a3 = Assignment(incident_id=3, resource_id=res.id, status="Active", assigned_by="Coord 3")
    db_session.add(a3)
    db_session.commit()
    assert a3.id is not None


def test_concurrency_50_simultaneous_assignment_attempts():
    """
    CRITICAL CONCURRENCY TEST:
    Simulate 50 simultaneous dispatch requests for the same single available ambulance.
    Uses an isolated file-backed database engine with connection pooling and timeouts.
    - Exactly ONE request must succeed (HTTP 200).
    - The remaining 49 requests must fail safely (HTTP 400 with conflict detail).
    - Database must have exactly 1 active assignment.
    - Closed assignments permit legitimate future reassignment.
    """
    import tempfile, shutil
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from fastapi.testclient import TestClient
    from app.database import Base, get_db
    from app.main import app
    from app import crud

    temp_dir = tempfile.mkdtemp()
    try:
        db_path = os.path.join(temp_dir, "concurrency.db")
        concurrent_engine = create_engine(
            f"sqlite:///{db_path}",
            connect_args={"check_same_thread": False, "timeout": 30},
        )
        ConcurrentSession = sessionmaker(autocommit=False, autoflush=False, bind=concurrent_engine)
        Base.metadata.create_all(bind=concurrent_engine)
        init_db = ConcurrentSession()
        crud.seed_demo_data(init_db)
        init_db.close()

        def override_concurrent_db():
            db = ConcurrentSession()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_concurrent_db
        with TestClient(app) as test_client:
            admin_login = test_client.post("/api/auth/login", json={"email": "admin@careon.org", "password": "admin123"}).json()
            admin_headers = {"Authorization": f"Bearer {admin_login['access_token']}"}

            # AMB-02 is Available in pre-seeded fleet
            resources = test_client.get("/api/resources?status=Available").json()
            amb2 = next(r for r in resources if r["resource_code"] == "AMB-02")
            res_id = amb2["id"]

            # Create 50 distinct test incidents
            inc_ids = []
            for i in range(50):
                inc = test_client.post("/api/incidents", json={
                    "category": "Medical",
                    "description": f"Concurrent test emergency #{i}",
                    "location_name": f"Location {i}",
                    "affected_people": 1,
                    "help_required": "Ambulance",
                    "contact_name": f"Caller {i}",
                    "contact_phone": "+91 98000 00000",
                }, headers=admin_headers).json()
                inc_ids.append(inc["id"])

            # Fire 50 concurrent allocation confirmation requests in a thread pool
            results = []
            def attempt_assignment(incident_id):
                return test_client.post(
                    "/api/allocations/confirm",
                    json={"incident_id": incident_id, "resource_id": res_id},
                    headers=admin_headers,
                )

            with ThreadPoolExecutor(max_workers=8) as executor:
                future_to_inc = {executor.submit(attempt_assignment, inc_id): inc_id for inc_id in inc_ids}
                for future in as_completed(future_to_inc):
                    res = future.result()
                    results.append((res.status_code, res.json()))

            success_responses = [r for r in results if r[0] == 200]
            conflict_responses = [r for r in results if r[0] == 400]

            # Exactly ONE dispatch succeeded
            assert len(success_responses) == 1, f"Expected exactly 1 success, got {len(success_responses)}"
            # Exactly 49 dispatches failed safely with conflict error
            assert len(conflict_responses) == 49, f"Expected 49 conflict failures, got {len(conflict_responses)}"

            for status_code, data in conflict_responses:
                detail_lower = data["detail"].lower()
                assert any(
                    phrase in detail_lower
                    for phrase in ["conflict", "no longer available", "already assigned", "cannot be assigned"]
                ), f"Unexpected error detail: {data['detail']}"

            # Verify resource is now Assigned
            res_check = test_client.get(f"/api/resources/{res_id}").json()
            assert res_check["status"] == "Assigned"

            # Verify that releasing this assignment permits legitimate future reassignment
            assigned_inc_id = success_responses[0][1]["assignment_id"]
            release_res = test_client.post(f"/api/allocations/{assigned_inc_id}/release", headers=admin_headers)
            assert release_res.status_code == 200

            # Resource is now Available again
            res_recheck = test_client.get(f"/api/resources/{res_id}").json()
            assert res_recheck["status"] == "Available"

            # Now assign to another pending incident -> must succeed!
            next_inc_id = [i for i in inc_ids if i != success_responses[0][1]["assignment_id"]][0]
            reassign_res = test_client.post(
                "/api/allocations/confirm",
                json={"incident_id": next_inc_id, "resource_id": res_id},
                headers=admin_headers,
            )
            assert reassign_res.status_code == 200
    finally:
        app.dependency_overrides.clear()
        shutil.rmtree(temp_dir, ignore_errors=True)


# ==============================================================================
# PHASE 6: SEC-005 — Remove Insecure Secret Fallback in Production
# ==============================================================================
def test_production_fails_when_secret_key_missing():
    """Server validation must fail in production if CAREON_SECRET_KEY is empty."""
    with pytest.raises(RuntimeError, match="CAREON_SECRET_KEY environment variable must be set in production"):
        validate_and_get_secret_key(environment="production", secret_override="")


def test_production_fails_when_secret_key_is_known_demo_default():
    """Server validation must fail in production if default demo secret is used."""
    with pytest.raises(RuntimeError, match="known default demo secret key is strictly forbidden"):
        validate_and_get_secret_key(environment="production", secret_override=INSECURE_DEFAULT_SECRET)


def test_production_fails_when_secret_key_too_short():
    """Server validation must fail in production if secret is shorter than 32 characters."""
    with pytest.raises(RuntimeError, match="must be at least 32 characters in production"):
        validate_and_get_secret_key(environment="production", secret_override="short-insecure-secret-key")


def test_production_succeeds_with_strong_secret():
    """Validation succeeds in production with a strong 32+ character secret."""
    strong_key = "a_very_secure_random_production_secret_key_2026_xyz"
    key = validate_and_get_secret_key(environment="production", secret_override=strong_key)
    assert key == strong_key


def test_development_uses_safe_fallback_when_secret_omitted():
    """In development/testing environments, missing secret returns the dev fallback cleanly."""
    key = validate_and_get_secret_key(environment="development", secret_override="")
    assert key is not None
    assert len(key) > 0


# ==============================================================================
# PHASE 7: SEC-008 — Protect Legacy Emergency Deletion
# ==============================================================================
def test_delete_legacy_emergency_citizen_fails_403(client):
    """Citizen user attempting to delete emergency record must receive HTTP 403."""
    # Create emergency
    item = client.post("/api/emergencies", json={
        "patient_name": "Test Patient",
        "room_number": "Ward-1",
        "emergency_type": "Medical",
        "priority": "Medium",
    }).json()

    user_login = client.post("/api/auth/login", json={"email": "aastha@example.com", "password": "user123"}).json()
    user_headers = {"Authorization": f"Bearer {user_login['access_token']}"}

    del_res = client.delete(f"/api/emergencies/{item['id']}", headers=user_headers)
    assert del_res.status_code == 403
    assert "administrative privileges required" in del_res.json()["detail"].lower()
