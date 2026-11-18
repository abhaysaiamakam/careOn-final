import pytest


def test_root_endpoint(client):
    """Test the root endpoint returns service info."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "CareOn Emergency Dispatch API"
    assert data["status"] == "online"
    assert "version" in data


def test_health_check(client):
    """Test the healthcheck endpoint verifies healthy status and database connection."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database"] == "connected"
    assert "timestamp" in data
    assert "version" in data


def test_get_stats(client):
    """Test retrieving dashboard statistics."""
    response = client.get("/api/stats")
    assert response.status_code == 200
    data = response.json()
    assert "total" in data
    assert "pending" in data
    assert "responded" in data
    assert "resolved" in data
    assert "critical" in data
    assert data["total"] >= 3


def test_list_emergencies(client):
    """Test listing all emergencies."""
    response = client.get("/api/emergencies")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 3


def test_filter_emergencies_by_status(client):
    """Test filtering emergencies by status."""
    response = client.get("/api/emergencies?status=Pending")
    assert response.status_code == 200
    data = response.json()
    assert all(item["status"] == "Pending" for item in data)


def test_filter_emergencies_by_priority(client):
    """Test filtering emergencies by priority."""
    response = client.get("/api/emergencies?priority=Critical")
    assert response.status_code == 200
    data = response.json()
    assert all(item["priority"] == "Critical" for item in data)


def test_create_emergency_success(client):
    """Test creating a new emergency dispatch record."""
    payload = {
        "patient_name": "Sarah Connor",
        "room_number": "ICU-205",
        "emergency_type": "Cardiac",
        "priority": "Critical",
        "description": "Patient experiencing acute chest pain.",
    }
    response = client.post("/api/emergencies", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["patient_name"] == "Sarah Connor"
    assert data["room_number"] == "ICU-205"
    assert data["emergency_type"] == "Cardiac"
    assert data["priority"] == "Critical"
    assert data["status"] == "Pending"
    assert data["id"] is not None
    assert "created_at" in data


def test_create_emergency_validation_error(client):
    """Test that invalid payload triggers 422 Unprocessable Entity."""
    # Invalid: missing patient_name
    payload = {
        "room_number": "ER-01",
        "emergency_type": "Trauma",
        "priority": "Critical",
    }
    response = client.post("/api/emergencies", json=payload)
    assert response.status_code == 422

    # Invalid: priority not in allowed enum
    invalid_priority = {
        "patient_name": "John Doe",
        "room_number": "ER-01",
        "emergency_type": "Trauma",
        "priority": "SuperEmergency",
    }
    response = client.post("/api/emergencies", json=invalid_priority)
    assert response.status_code == 422


def test_get_emergency_by_id(client):
    """Test fetching a specific emergency by ID."""
    # First create an emergency
    payload = {
        "patient_name": "Bruce Wayne",
        "room_number": "Trauma-01",
        "emergency_type": "Trauma",
        "priority": "Critical",
        "description": "Multiple fractures.",
    }
    create_res = client.post("/api/emergencies", json=payload)
    item_id = create_res.json()["id"]

    response = client.get(f"/api/emergencies/{item_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == item_id
    assert data["patient_name"] == "Bruce Wayne"


def test_get_emergency_not_found(client):
    """Test fetching a non-existent emergency returns 404."""
    response = client.get("/api/emergencies/99999")
    assert response.status_code == 404


def test_update_emergency_status(client):
    """Test updating the status of an emergency (Pending -> Responded -> Resolved)."""
    # Create an emergency
    payload = {
        "patient_name": "Diana Prince",
        "room_number": "Ward-12",
        "emergency_type": "Neurological",
        "priority": "High",
    }
    create_res = client.post("/api/emergencies", json=payload)
    item_id = create_res.json()["id"]

    # Update to Responded
    patch_res = client.patch(
        f"/api/emergencies/{item_id}/status",
        json={"status": "Responded"},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["status"] == "Responded"

    # Update to Resolved
    patch_res2 = client.patch(
        f"/api/emergencies/{item_id}/status",
        json={"status": "Resolved"},
    )
    assert patch_res2.status_code == 200
    assert patch_res2.json()["status"] == "Resolved"


def test_update_status_not_found(client):
    """Test updating status of non-existent emergency returns 404."""
    response = client.patch("/api/emergencies/99999/status", json={"status": "Resolved"})
    assert response.status_code == 404


def test_delete_emergency(client):
    """Test deleting an emergency record requires admin authorization."""
    # Create an emergency
    payload = {
        "patient_name": "Clark Kent",
        "room_number": "Ward-1",
        "emergency_type": "General",
        "priority": "Low",
    }
    create_res = client.post("/api/emergencies", json=payload)
    item_id = create_res.json()["id"]

    # Unauthenticated deletion must fail with HTTP 401
    unauth_del = client.delete(f"/api/emergencies/{item_id}")
    assert unauth_del.status_code == 401

    # Authenticate as admin
    admin_login = client.post("/api/auth/login", json={
        "email": "admin@careon.org",
        "password": "admin123",
    })
    admin_token = admin_login.json()["access_token"]
    headers = {"Authorization": f"Bearer {admin_token}"}

    # Delete with admin authorization
    del_res = client.delete(f"/api/emergencies/{item_id}", headers=headers)
    assert del_res.status_code == 204

    # Verify it is deleted
    get_res = client.get(f"/api/emergencies/{item_id}")
    assert get_res.status_code == 404


def test_delete_emergency_not_found(client):
    """Test deleting non-existent emergency returns 404 for authorized admin, 401 for unauthenticated."""
    # Unauthenticated must fail with 401
    unauth_res = client.delete("/api/emergencies/99999")
    assert unauth_res.status_code == 401

    # Authenticated admin gets 404 Not Found
    admin_login = client.post("/api/auth/login", json={
        "email": "admin@careon.org",
        "password": "admin123",
    })
    admin_token = admin_login.json()["access_token"]
    headers = {"Authorization": f"Bearer {admin_token}"}

    response = client.delete("/api/emergencies/99999", headers=headers)
    assert response.status_code == 404
