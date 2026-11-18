import pytest
from app.algorithms.classification import classify_incident
from app.algorithms.allocation import calculate_haversine_distance, calculate_eta_minutes


# ==============================================================================
# Auth & Access Control Tests
# ==============================================================================
def test_user_registration_and_login(client):
    # Register new user
    reg_payload = {
        "name": "Priya Sharma",
        "email": "priya.test@example.com",
        "phone": "+91 99887 76655",
        "password": "securepassword123",
        "role": "user",
    }
    res = client.post("/api/auth/register", json=reg_payload)
    assert res.status_code == 201
    data = res.json()
    assert "access_token" in data
    assert data["user"]["email"] == "priya.test@example.com"
    assert data["user"]["role"] == "user"

    # Login
    login_res = client.post("/api/auth/login", json={
        "email": "priya.test@example.com",
        "password": "securepassword123",
    })
    assert login_res.status_code == 200
    login_data = login_res.json()
    assert "access_token" in login_data
    token = login_data["access_token"]

    # Access /api/auth/me
    me_res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    assert me_res.json()["name"] == "Priya Sharma"


def test_admin_route_protection(client):
    # Register normal user
    res = client.post("/api/auth/register", json={
        "name": "Normal Citizen",
        "email": "citizen@example.com",
        "phone": "+91 91234 56789",
        "password": "userpass123",
    })
    token = res.json()["access_token"]

    # Attempt to call admin endpoint without token -> 401
    res_no_auth = client.get("/api/admin/analytics")
    assert res_no_auth.status_code == 401

    # Attempt to call admin endpoint with normal user token -> 403 Forbidden
    res_forbidden = client.get(
        "/api/admin/analytics",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_forbidden.status_code == 403

    # Login as seeded admin -> 200 OK
    admin_login = client.post("/api/auth/login", json={
        "email": "admin@careon.org",
        "password": "admin123",
    })
    assert admin_login.status_code == 200
    admin_token = admin_login.json()["access_token"]

    admin_res = client.get(
        "/api/admin/analytics",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert admin_res.status_code == 200
    assert "active_incidents" in admin_res.json()


# ==============================================================================
# Incident Reporting, Classification & Duplicate Detection
# ==============================================================================
def test_incident_reporting_and_classification(client):
    payload = {
        "category": "Medical",
        "description": "Patient is having severe cardiac arrest and unconsciousness.",
        "location_name": "MG Road Cross",
        "latitude": 12.9750,
        "longitude": 77.6060,
        "affected_people": 1,
        "help_required": "ALS Ambulance & Defibrillator",
        "contact_name": "Test Reporter",
        "contact_phone": "+91 98765 00000",
    }
    res = client.post("/api/incidents", json=payload)
    assert res.status_code == 201
    data = res.json()
    assert data["incident_code"].startswith("CARE-2026-")
    assert data["priority"] == "Critical"  # Cardiac keyword rule
    assert data["status"] == "Received"
    assert data["is_verified"] is False
    assert data["verification_otp"] == "123456"


def test_duplicate_incident_detection(client):
    # First report
    p1 = {
        "category": "Road accident",
        "description": "Two car collision at junction.",
        "location_name": "Koramangala 5th Block",
        "latitude": 12.9350,
        "longitude": 77.6250,
        "affected_people": 2,
        "help_required": "Ambulance",
        "contact_name": "Reporter One",
        "contact_phone": "+91 98888 11111",
    }
    res1 = client.post("/api/incidents", json=p1)
    assert res1.status_code == 201
    code1 = res1.json()["incident_code"]

    # Duplicate report: same category, location < 800m
    p2 = {
        "category": "Road accident",
        "description": "Accident between two cars blocking lane.",
        "location_name": "Koramangala 5th Block Signal",
        "latitude": 12.9352,
        "longitude": 77.6251,
        "affected_people": 2,
        "help_required": "Ambulance",
        "contact_name": "Reporter Two",
        "contact_phone": "+91 98888 22222",
    }
    res2 = client.post("/api/incidents", json=p2)
    assert res2.status_code == 201
    data2 = res2.json()
    assert data2["is_duplicate"] is True


def test_phone_verification_via_otp(client):
    # Create incident
    res = client.post("/api/incidents", json={
        "category": "Medical",
        "description": "Patient breathing difficulty.",
        "location_name": "Jayanagar 4th T Block",
        "affected_people": 1,
        "help_required": "Oxygen",
        "contact_name": "Pooja",
        "contact_phone": "+91 97777 66666",
    })
    inc_id = res.json()["id"]

    # Verify with correct demo OTP
    v_res = client.post(f"/api/incidents/{inc_id}/verify", json={"otp": "123456"})
    assert v_res.status_code == 200
    assert v_res.json()["is_verified"] is True
    assert v_res.json()["status"] == "Verified"

    # Verify with invalid OTP fails
    bad_res = client.post(f"/api/incidents/{inc_id}/verify", json={"otp": "999999"})
    assert bad_res.status_code == 400


# ==============================================================================
# Smart Allocation & Conflict Prevention Tests
# ==============================================================================
def test_allocation_recommendation_and_conflict_prevention(client):
    admin_login = client.post("/api/auth/login", json={
        "email": "admin@careon.org",
        "password": "admin123",
    })
    admin_token = admin_login.json()["access_token"]
    headers = {"Authorization": f"Bearer {admin_token}"}

    # Create test incident
    inc_res = client.post("/api/incidents", json={
        "category": "Fire",
        "description": "Fire outbreak in shop.",
        "location_name": "South Fire Area",
        "latitude": 12.9300,
        "longitude": 77.5850,
        "affected_people": 1,
        "help_required": "Fire Response",
        "contact_name": "Fire Caller",
        "contact_phone": "+91 96666 55555",
    })
    inc_id = inc_res.json()["id"]

    # Recommend allocation
    rec_res = client.post("/api/allocations/recommend", json={"incident_id": inc_id})
    assert rec_res.status_code == 200
    rec_data = rec_res.json()
    assert rec_data["has_allocation"] is True
    assert rec_data["resource_category"] == "Fire Response"
    res_id = rec_data["resource_id"]

    # Confirm assignment
    conf_res = client.post(
        "/api/allocations/confirm",
        json={"incident_id": inc_id, "resource_id": res_id},
        headers=headers,
    )
    assert conf_res.status_code == 200

    # Verify incident status is updated to Team Dispatched
    updated_inc = client.get(f"/api/incidents/{inc_id}", headers=headers).json()
    assert updated_inc["status"] == "Team Dispatched"

    # CONFLICT PREVENTION CHECK:
    # Try assigning the SAME resource to another incident -> must be blocked
    inc_res2 = client.post("/api/incidents", json={
        "category": "Fire",
        "description": "Second fire outbreak.",
        "location_name": "Jayanagar",
        "affected_people": 1,
        "help_required": "Fire Response",
        "contact_name": "Fire Caller 2",
        "contact_phone": "+91 96666 44444",
    })
    inc_id2 = inc_res2.json()["id"]

    conflict_res = client.post(
        "/api/allocations/confirm",
        json={"incident_id": inc_id2, "resource_id": res_id},
        headers=headers,
    )
    assert conflict_res.status_code == 400
    assert "conflict" in conflict_res.json()["detail"].lower() or "cannot be assigned" in conflict_res.json()["detail"].lower()


# ==============================================================================
# Shortage & External Provider Coordination Tests
# ==============================================================================
def test_shortage_detection_and_external_provider_flow(client):
    admin_login = client.post("/api/auth/login", json={
        "email": "admin@careon.org",
        "password": "admin123",
    })
    admin_token = admin_login.json()["access_token"]
    headers = {"Authorization": f"Bearer {admin_token}"}

    # Get shortages
    shortage_res = client.get("/api/allocations/shortages")
    assert shortage_res.status_code == 200
    assert "shortages" in shortage_res.json()

    # List registered providers
    prov_res = client.get("/api/providers")
    assert prov_res.status_code == 200
    providers = prov_res.json()
    assert len(providers) >= 3

    # Pick St. Mary's or CityCare
    provider = providers[1]

    # Create enquiry for CARE-2026-103
    inc_103 = client.get("/api/incidents/CARE-2026-103", headers=headers).json()
    enquiry_res = client.post(
        "/api/providers/enquiries",
        json={
            "incident_id": inc_103["id"],
            "provider_id": provider["id"],
            "charge_quote": 1500.0,
            "user_consent": "Pending",
            "response_time_minutes": 12,
            "notes": "Simulated partner enquiry - provider confirmed vehicle standby.",
        },
        headers=headers,
    )
    assert enquiry_res.status_code == 201
    enquiry_id = enquiry_res.json()["id"]

    # Update provider status to Available & check consent
    patch_res = client.patch(
        f"/api/providers/enquiries/{enquiry_id}",
        json={"status": "Available", "charge_quote": 1500.0, "user_consent": "Accepted"},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["user_consent"] == "Accepted"


# ==============================================================================
# Cancellation, Resolution & Feedback Tests
# ==============================================================================
def test_cancellation_and_safe_resource_release(client):
    admin_login = client.post("/api/auth/login", json={
        "email": "admin@careon.org",
        "password": "admin123",
    })
    admin_token = admin_login.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    user_login = client.post("/api/auth/login", json={
        "email": "aastha@example.com",
        "password": "user123",
    })
    user_token = user_login.json()["access_token"]
    user_headers = {"Authorization": f"Bearer {user_token}"}

    # Create incident as authenticated user
    inc = client.post("/api/incidents", json={
        "category": "Medical",
        "description": "Patient dizzy, recovering.",
        "location_name": "MG Road Plaza",
        "affected_people": 1,
        "help_required": "First Aid",
        "contact_name": "Deepak",
        "contact_phone": "+91 95555 44444",
    }, headers=user_headers).json()

    # User cancels their own incident with reason
    cancel_res = client.post(
        f"/api/incidents/{inc['id']}/cancel",
        json={"reason": "Help arranged independently", "details": "Family took patient to nearby clinic."},
        headers=user_headers,
    )
    assert cancel_res.status_code == 200
    assert cancel_res.json()["status"] == "Cancelled"

    # Admin acknowledges cancellation and releases resources
    ack_res = client.post(
        f"/api/incidents/{inc['id']}/acknowledge-cancellation",
        headers=admin_headers,
    )
    assert ack_res.status_code == 200


def test_incident_resolution_and_feedback(client):
    admin_login = client.post("/api/auth/login", json={
        "email": "admin@careon.org",
        "password": "admin123",
    })
    admin_token = admin_login.json()["access_token"]
    headers = {"Authorization": f"Bearer {admin_token}"}

    # Create incident
    inc = client.post("/api/incidents", json={
        "category": "Safety / Other",
        "description": "Minor sports event sprain.",
        "location_name": "Stadium",
        "affected_people": 1,
        "help_required": "First Aid Kit",
        "contact_name": "Coach",
        "contact_phone": "+91 94444 33333",
    }).json()

    # Feedback before resolution must fail
    fb_early = client.post("/api/feedback", json={
        "incident_id": inc["id"],
        "rating": 5,
        "tags": "Great support",
    })
    assert fb_early.status_code == 400

    # Resolve incident
    res_res = client.post(
        f"/api/incidents/{inc['id']}/resolve",
        params={"notes": "Bandage applied and cleared safely."},
        headers=headers,
    )
    assert res_res.status_code == 200
    assert res_res.json()["status"] == "Resolved"

    # Feedback after resolution succeeds
    fb_res = client.post("/api/feedback", json={
        "incident_id": inc["id"],
        "rating": 5,
        "tags": "Clear updates, Helpful coordination",
        "comments": "Extremely fast and professional coordinator support.",
    })
    assert fb_res.status_code == 201
    assert fb_res.json()["rating"] == 5


# ==============================================================================
# Sahara Chatbot Intent Tests
# ==============================================================================
def test_sahara_chatbot_intent_matching(client):
    # Greeting
    res1 = client.post("/api/chatbot/message", json={"message": "Hello Sahara!"})
    assert res1.status_code == 200
    assert "Sahara" in res1.json()["reply"]

    # Medical triage safety disclaimer
    res2 = client.post("/api/chatbot/message", json={"message": "Can you diagnose severe chest pain?"})
    assert res2.status_code == 200
    reply = res2.json()["reply"]
    assert "cannot provide medical diagnoses" in reply or "112" in reply

    # Cost transparency explanation
    res3 = client.post("/api/chatbot/message", json={"message": "Does CareOn charge any fee?"})
    assert res3.status_code == 200
    assert "₹0" in res3.json()["reply"]

    # Track by incident code
    res4 = client.post("/api/chatbot/message", json={"message": "What is status of CARE-2026-101?"})
    assert res4.status_code == 200
    assert "CARE-2026-101" in res4.json()["reply"]


# ==============================================================================
# Security, Role Enforcement & Privacy Tests
# ==============================================================================
def test_public_registration_cannot_create_admin(client):
    # Attacker tries to register with role="admin"
    res = client.post("/api/auth/register", json={
        "name": "Malicious User",
        "email": "hacker@example.com",
        "phone": "+91 99999 88888",
        "password": "attackpassword123",
        "role": "admin",
    })
    assert res.status_code == 201
    data = res.json()
    # Backend security must force role to 'user'
    assert data["user"]["role"] == "user"

    # Verify they cannot access admin endpoints
    token = data["access_token"]
    admin_probe = client.get("/api/admin/analytics", headers={"Authorization": f"Bearer {token}"})
    assert admin_probe.status_code == 403


def test_password_mismatch_registration_fails(client):
    res = client.post("/api/auth/register", json={
        "name": "Mismatch User",
        "email": "mismatch@example.com",
        "phone": "+91 98888 77777",
        "password": "passwordA123",
        "confirm_password": "passwordB999",
    })
    assert res.status_code == 400
    assert "Passwords do not match" in res.json()["detail"]


def test_demo_account_names_verification(client):
    # Verify Admin account is Aastha Singh
    admin_login = client.post("/api/auth/login", json={
        "email": "admin@careon.org",
        "password": "admin123",
    })
    assert admin_login.status_code == 200
    assert admin_login.json()["user"]["name"] == "Aastha Singh"
    assert admin_login.json()["user"]["role"] == "admin"

    # Verify Demo User account is Demo User
    user_login = client.post("/api/auth/login", json={
        "email": "aastha@example.com",
        "password": "user123",
    })
    assert user_login.status_code == 200
    assert user_login.json()["user"]["name"] == "Demo User"
    assert user_login.json()["user"]["role"] == "user"


def test_private_user_incident_access_restriction(client):
    # User A reports an incident
    user_a = client.post("/api/auth/register", json={
        "name": "User Alpha",
        "email": "alpha@example.com",
        "phone": "+91 98765 11111",
        "password": "alphapassword123",
    }).json()
    token_a = user_a["access_token"]

    inc = client.post(
        "/api/incidents",
        json={
            "category": "Medical",
            "description": "Confidential patient condition.",
            "location_name": "Mysuru Palace West Gate",
            "affected_people": 1,
            "help_required": "First Aid",
            "contact_name": "User Alpha",
            "contact_phone": "+91 98765 11111",
        },
        headers={"Authorization": f"Bearer {token_a}"},
    ).json()
    inc_code = inc["incident_code"]

    # User B registers
    user_b = client.post("/api/auth/register", json={
        "name": "User Beta",
        "email": "beta@example.com",
        "phone": "+91 98765 22222",
        "password": "betapassword123",
    }).json()
    token_b = user_b["access_token"]

    # User B attempts to access User A's private incident -> HTTP 403 Forbidden
    res_b = client.get(
        f"/api/incidents/{inc_code}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert res_b.status_code == 403
    assert "Access denied" in res_b.json()["detail"]

    # Admin CAN access User A's incident -> HTTP 200 OK
    admin_login = client.post("/api/auth/login", json={"email": "admin@careon.org", "password": "admin123"}).json()
    res_admin = client.get(
        f"/api/incidents/{inc_code}",
        headers={"Authorization": f"Bearer {admin_login['access_token']}"},
    )
    assert res_admin.status_code == 200
    assert res_admin.json()["incident_code"] == inc_code
