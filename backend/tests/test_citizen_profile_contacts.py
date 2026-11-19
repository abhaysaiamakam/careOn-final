"""
Unit tests for Citizen Profile, Emergency Contacts, and Onboarding Flow.
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_citizen_profile_and_contacts_full_lifecycle():
    # 1. Register a test citizen
    import time
    unique_suffix = int(time.time() * 1000)
    email = f"citizen_{unique_suffix}@careon.org"
    password = "TestPassword123!"

    reg_res = client.post(
        "/api/auth/register",
        json={
            "name": f"Citizen User {unique_suffix}",
            "email": email,
            "phone": "+919876543210",
            "password": password,
            "confirm_password": password,
            "role": "user",
        },
    )
    assert reg_res.status_code == 201, reg_res.text
    token = reg_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Retrieve initial profile - should auto-create if missing
    prof_res = client.get("/api/citizen/profile", headers=headers)
    assert prof_res.status_code == 200, prof_res.text
    profile = prof_res.json()
    assert profile["onboarding_completed"] is False
    assert profile["preferred_language"] == "en"

    # 3. Update profile with address, medical notes, and emergency consent
    up_res = client.put(
        "/api/citizen/profile",
        headers=headers,
        json={
            "residential_address": "Flat 402, Sunshine Heights, Koramangala",
            "residential_city": "Bengaluru",
            "residential_state": "Karnataka",
            "residential_postal_code": "560034",
            "address_landmark": "Near Koramangala Police Station",
            "access_instructions": "Gate code 1234, 4th floor",
            "preferred_language": "kn",
            "blood_group": "O+",
            "allergies": "Penicillin, Peanuts",
            "medical_conditions": "Mild Asthma",
            "current_medications": "Inhaler PRN",
            "emergency_notes": "Speaks Kannada and English",
            "is_organ_donor": True,
            "consent_data_sharing_emergency": True,
        },
    )
    assert up_res.status_code == 200, up_res.text
    updated = up_res.json()
    assert updated["residential_city"] == "Bengaluru"
    assert updated["blood_group"] == "O+"
    assert updated["readiness_score"] > 50

    # 4. Add Primary ICE contact
    c1_res = client.post(
        "/api/citizen/contacts",
        headers=headers,
        json={
            "full_name": "Anita Kumar",
            "relationship_type": "Spouse",
            "phone": "+919845011111",
            "secondary_phone": "+919845022222",
            "email": "anita@example.com",
            "is_primary": True,
            "can_authorize_medical_treatment": True,
        },
    )
    assert c1_res.status_code == 201, c1_res.text
    contact1 = c1_res.json()
    assert contact1["full_name"] == "Anita Kumar"
    assert contact1["is_primary"] is True

    # 5. Add Secondary ICE contact
    c2_res = client.post(
        "/api/citizen/contacts",
        headers=headers,
        json={
            "full_name": "Dr. Rajesh Rao",
            "relationship_type": "Doctor",
            "phone": "+919845033333",
            "is_primary": False,
            "can_authorize_medical_treatment": True,
        },
    )
    assert c2_res.status_code == 201, c2_res.text

    # 6. List contacts
    list_res = client.get("/api/citizen/contacts", headers=headers)
    assert list_res.status_code == 200, list_res.text
    contacts = list_res.json()
    assert len(contacts) == 2

    # 7. Complete Onboarding
    onb_res = client.post("/api/citizen/onboarding/complete", headers=headers)
    assert onb_res.status_code == 200, onb_res.text
    assert onb_res.json()["onboarding_completed"] is True

    # 8. Get Dashboard Summary
    dash_res = client.get("/api/citizen/dashboard-summary", headers=headers)
    assert dash_res.status_code == 200, dash_res.text
    dash_data = dash_res.json()
    assert dash_data["profile"]["onboarding_completed"] is True
    assert len(dash_data["contacts"]) == 2
    assert "active_incidents" in dash_data
    assert "recent_incidents" in dash_data

    # 9. Delete secondary contact
    del_res = client.delete(f"/api/citizen/contacts/{c2_res.json()['id']}", headers=headers)
    assert del_res.status_code == 200, del_res.text

    # Verify contacts count decremented to 1
    list_res2 = client.get("/api/citizen/contacts", headers=headers)
    assert len(list_res2.json()) == 1
