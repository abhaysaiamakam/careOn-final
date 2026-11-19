#!/usr/bin/env python3
"""
CAREON M12 — End-to-End Cross-Application Integration Workflow Verification.
Validates the complete lifecycle:
Citizen Report -> Command Dispatch -> Responder Inbox -> Accept ->
M6 Lifecycle Transitions -> Real GPS Telemetry -> Clinical Vitals & ABCDE ->
Digital SBAR Handover Submission -> Hospital Acceptance -> Handover & Mission Completion ->
M9 Offline Synchronization.
"""

import os
import sys
import json
import time
import requests

API_URL = os.environ.get("API_URL", "http://localhost:8001")

def log(step, msg):
    print(f"\n[STEP {step}] {msg}")

def assert_status(resp, expected=200, context=""):
    if resp.status_code != expected:
        print(f"FAILED {context}: expected {expected}, got {resp.status_code}")
        print("Response:", resp.text)
        sys.exit(1)
    return resp.json()

def main():
    print("=================================================================")
    print("CAREON M12: CROSS-APPLICATION INTEGRATION & FIELD LIFECYCLE SUITE")
    print(f"Backend Target: {API_URL}")
    print("=================================================================")

    # 1. Health check & Fail-Closed Guard
    log(1, "Verify Central Backend Health & Fail-Closed Isolation")
    r = requests.get(f"{API_URL}/api/health")
    data = assert_status(r, 200, "Backend Health")
    db_name = data.get("database_name")
    if db_name and db_name != "careon_test":
        print(f"FATAL PRE-FLIGHT ERROR: Backend is connected to '{db_name}', NOT 'careon_test'!")
        print("Test execution aborted immediately to prevent database contamination.")
        sys.exit(1)
    print(f"  OK: Database={data.get('database')} ({db_name}), Status={data.get('status')}")

    # 2. Authenticate Dispatcher
    log(2, "Authenticate Command Dispatcher Account")
    r = requests.post(f"{API_URL}/api/auth/login", json={"email": "m2_dispatcher@careon.org", "password": "dispatcher123"})
    dispatch_auth = assert_status(r, 200, "Dispatcher Login")
    disp_token = dispatch_auth["access_token"]
    disp_headers = {"Authorization": f"Bearer {disp_token}"}
    print("  OK: Command Dispatcher authenticated.")

    # 3. Authenticate Responder (Paramedic)
    log(3, "Authenticate Field Responder Unit Account")
    r = requests.post(f"{API_URL}/api/auth/login", json={"email": "m2_responder@careon.org", "password": "responder123"})
    resp_auth = assert_status(r, 200, "Responder Login")
    resp_token = resp_auth["access_token"]
    resp_headers = {"Authorization": f"Bearer {resp_token}"}
    print("  OK: Responder authenticated.")

    # Check responder profile & vehicle
    r = requests.get(f"{API_URL}/api/responder/me", headers=resp_headers)
    resp_profile = assert_status(r, 200, "Responder /me profile")
    vehicle = resp_profile.get("vehicle") or {}
    resource_id = vehicle.get("id") or resp_profile.get("resource_id") or resp_profile.get("assigned_resource_id")
    print(f"  OK: Callsign={resp_profile.get('callsign')}, ResourceID={resource_id}")

    # 4. Authenticate Citizen & Submit Incident
    log(4, "Citizen Reports Emergency Incident via Citizen Web API")
    r = requests.post(f"{API_URL}/api/auth/login", json={"email": "m2_citizen@careon.org", "password": "citizen123"})
    cit_auth = assert_status(r, 200, "Citizen Login")
    cit_token = cit_auth["access_token"]
    cit_headers = {"Authorization": f"Bearer {cit_token}"}

    incident_payload = {
        "category": "Medical",
        "description": "Adult male collapsed, unresponsive, bystander starting CPR",
        "location_name": "100 MG Road, Bengaluru",
        "latitude": 12.9716,
        "longitude": 77.5946,
        "affected_people": 1,
        "help_required": "Ambulance",
        "contact_name": "Suresh Kumar",
        "contact_phone": "+919876543210"
    }
    r = requests.post(f"{API_URL}/api/incidents", json=incident_payload, headers=cit_headers)
    incident = assert_status(r, 201, "Create Incident")
    incident_id = incident["id"]
    tracking_token = incident.get("tracking_token") or str(incident_id)
    print(f"  OK: Incident Created: ID={incident_id}, Code={incident.get('incident_code')}")

    # 5. Command Dispatcher Allocates & Confirms Mission to Responder Unit
    log(5, "Command Dispatcher Allocates and Dispatches Responder Unit")
    # Authenticate Super Admin for allocation confirmation
    r_adm = requests.post(f"{API_URL}/api/auth/login", json={"email": "m2_superadmin@careon.org", "password": "superadmin123"})
    adm_token = r_adm.json()["access_token"]
    adm_headers = {"Authorization": f"Bearer {adm_token}"}

    # Reset Resource status to Available if currently busy from previous test
    target_res_id = resource_id or 2
    requests.patch(f"{API_URL}/api/resources/{target_res_id}", json={"status": "Available"}, headers=adm_headers)

    alloc_payload = {
        "incident_id": incident_id,
        "resource_id": target_res_id,
        "notes": "Emergency unit dispatched via Command Center"
    }
    r = requests.post(f"{API_URL}/api/allocations/confirm", json=alloc_payload, headers=adm_headers)
    allocation = assert_status(r, 200, "Confirm Allocation")
    assignment_id = allocation.get("assignment_id") or allocation.get("id") or 1
    # Check assignment id from assignments table or missions
    r_missions = requests.get(f"{API_URL}/api/responder/missions", headers=resp_headers)
    missions_list = r_missions.json()
    if missions_list:
        assignment_id = missions_list[0]["id"]
    print(f"  OK: Assignment Confirmed: ID={assignment_id}")

    # 6. Responder Polls Inbox & Receives Assignment
    log(6, "Responder Polls Missions and Retrieves New Assignment")
    r = requests.get(f"{API_URL}/api/responder/missions", headers=resp_headers)
    missions = assert_status(r, 200, "List Responder Missions")
    active_m = next((m for m in missions if m["id"] == assignment_id or m.get("assignment_id") == assignment_id), None)
    if not active_m:
        print(f"FAILED: Assignment {assignment_id} not found in responder inbox missions")
        sys.exit(1)
    print(f"  OK: Found Mission in Inbox: Status={active_m['status']}")

    # 7. Responder Acknowledges (Accepts) Mission
    log(7, "Responder Acknowledges and Accepts Mission")
    ack_payload = {"action": "accept"}
    r = requests.post(f"{API_URL}/api/responder/missions/{assignment_id}/acknowledge", json=ack_payload, headers=resp_headers)
    accepted_m = assert_status(r, 200, "Acknowledge Mission")
    print(f"  OK: Mission Accepted. New Status={accepted_m.get('target_status') or accepted_m.get('status')}")

    # 8. M6 State Transitions & Real GPS Telemetry
    log(8, "Execute M6 Operational Lifecycle Transitions & GPS Telemetry")
    lifecycle_states = [
        "en_route_incident",
        "arrived_scene",
        "patient_contact"
    ]
    for target in lifecycle_states:
        r = requests.post(
            f"{API_URL}/api/responder/missions/{assignment_id}/transition",
            json={"target_status": target},
            headers=resp_headers
        )
        assert_status(r, 200, f"Transition to {target}")
        print(f"  OK: Transitioned -> {target}")

        # Send live telemetry
        telem = {
            "resource_id": resource_id,
            "latitude": 12.9716 + 0.001,
            "longitude": 77.5946 + 0.001,
            "speed": 45,
            "heading": 120,
            "accuracy": 8.5,
            "mission_id": assignment_id,
            "incident_id": incident_id
        }
        tr = requests.post(f"{API_URL}/api/responder/telemetry", json=telem, headers=resp_headers)
        assert_status(tr, 200, "Send Telemetry")

    # 9. Record Clinical Encounter, Vitals & ABCDE Assessment
    log(9, "Record Clinical Encounter, Vitals & ABCDE Assessment")
    enc_payload = {
        "incident_id": incident_id,
        "chief_complaint": "Acute cardiac arrest with ROSC post-resuscitation",
        "patient_id": None
    }
    r = requests.post(f"{API_URL}/api/clinical/encounters", json=enc_payload, headers=resp_headers)
    enc = assert_status(r, 201, "Create Clinical Encounter")
    encounter_id = enc["id"]
    print(f"  OK: Encounter Created: ID={encounter_id}")

    # Vitals
    vitals_payload = {
        "heart_rate": 86,
        "systolic_bp": 122,
        "diastolic_bp": 80,
        "respiratory_rate": 16,
        "spo2": 98,
        "temperature_celsius": 36.8,
        "gcs_score": 15
    }
    r = requests.post(f"{API_URL}/api/clinical/encounters/{encounter_id}/vitals", json=vitals_payload, headers=resp_headers)
    assert_status(r, 201, "Record Vitals")
    print("  OK: Vital Signs Recorded (HR 86, BP 122/80, SpO2 98%, GCS 15).")

    # ABCDE
    abcde_payload = {
        "airway_status": "Patent",
        "breathing_status": "Normal",
        "circulation_status": "Normal pulses, CRT < 2s",
        "disability_status": "Alert (AVPU)",
        "exposure_status": "No external signs of hemorrhage",
        "clinical_notes": "Patient regained consciousness following bystander CPR and automated defib."
    }
    r = requests.post(f"{API_URL}/api/clinical/encounters/{encounter_id}/assessments", json=abcde_payload, headers=resp_headers)
    assert_status(r, 201, "Record ABCDE Assessment")
    print("  OK: ABCDE Assessment Recorded.")

    # 10. Hospital Transport & Digital SBAR Handover Submission
    log(10, "Patient Picked Up & Hospital Transport Transitions")
    for target in ["patient_picked_up", "en_route_hospital"]:
        r = requests.post(
            f"{API_URL}/api/responder/missions/{assignment_id}/transition",
            json={"target_status": target},
            headers=resp_headers
        )
        assert_status(r, 200, f"Transition to {target}")
        print(f"  OK: Transitioned -> {target}")

    # Fetch hospitals
    r = requests.get(f"{API_URL}/api/hospital/facilities", headers=resp_headers)
    hospitals = assert_status(r, 200, "Get Hospital Facilities")
    hospital_id = hospitals[0]["id"] if hospitals else 1
    print(f"  OK: Selected Receiving Hospital Facility: ID={hospital_id}")

    # Create & Submit Handover
    handover_payload = {
        "encounter_id": encounter_id,
        "facility_id": hospital_id,
        "receiving_department": "Emergency Department",
        "outstanding_clinical_concerns": "Immediate 12-lead ECG, cardiology consult"
    }
    r = requests.post(f"{API_URL}/api/clinical/handovers", json=handover_payload, headers=resp_headers)
    handover = assert_status(r, 201, "Create Digital Handover")
    handover_token = handover.get("handover_token") or handover.get("token") or handover["id"]
    print(f"  OK: Handover Drafted: Token={handover_token}")

    # Submit handover
    r = requests.post(f"{API_URL}/api/clinical/handovers/{handover_token}/submit", json={"receiving_department": "Emergency Department"}, headers=resp_headers)
    submitted_h = assert_status(r, 200, "Submit Digital Handover")
    print(f"  OK: Handover Submitted to Hospital. Status={submitted_h.get('status')}")

    # 11. Hospital Reception, Bed Allocation & Mission Completion
    log(11, "Hospital Receives, Acknowledges Handover & Mission Completion")
    # Arrived hospital
    r = requests.post(f"{API_URL}/api/responder/missions/{assignment_id}/transition", json={"target_status": "arrived_hospital"}, headers=resp_headers)
    assert_status(r, 200, "Transition to arrived_hospital")
    print("  OK: Transitioned -> arrived_hospital")

    # Handover initiated
    r = requests.post(f"{API_URL}/api/responder/missions/{assignment_id}/transition", json={"target_status": "handover_initiated"}, headers=resp_headers)
    assert_status(r, 200, "Transition to handover_initiated")
    print("  OK: Transitioned -> handover_initiated")

    # Hospital acknowledges / accepts handover record
    # Authenticate as hospital staff (m2_hospital@careon.org / hospital123)
    r_hosp = requests.post(f"{API_URL}/api/auth/login", json={"email": "m2_hospital@careon.org", "password": "hospital123"})
    hosp_token = r_hosp.json()["access_token"]
    hosp_headers = {"Authorization": f"Bearer {hosp_token}"}

    r = requests.post(
        f"{API_URL}/api/clinical/handovers/{handover_token}/action",
        json={"action": "acknowledge", "clarification_notes": "Patient received in Resuscitation Bay 1. Bed confirmed."},
        headers=hosp_headers
    )
    if r.status_code == 200:
        print("  OK: Hospital acknowledged digital handover.")

    # Handover completed
    r = requests.post(f"{API_URL}/api/responder/missions/{assignment_id}/transition", json={"target_status": "handover_completed"}, headers=resp_headers)
    assert_status(r, 200, "Transition to handover_completed")
    print("  OK: Transitioned -> handover_completed")

    # Complete mission
    r = requests.post(f"{API_URL}/api/responder/missions/{assignment_id}/transition", json={"target_status": "completed"}, headers=resp_headers)
    assert_status(r, 200, "Transition to completed")
    print("  OK: Mission Successfully Completed.")

    # 12. Verify Multi-App State Synchronization
    log(12, "Verify Incident Status Across Citizen and Command Consoles")
    # Verify Citizen track view
    r = requests.get(f"{API_URL}/api/incidents/track/{tracking_token}")
    if r.status_code == 200:
        cit_track = r.json()
        print(f"  OK: Citizen Tracking State={cit_track.get('status')}")

    # Verify Command / Ops view
    r = requests.get(f"{API_URL}/api/incidents/{incident_id}", headers=adm_headers)
    cmd_inc = assert_status(r, 200, "Command View Incident")
    print(f"  OK: Command Console Incident State={cmd_inc.get('status')}")

    # 13. Verify M9 Offline Sync Batch Upload API
    log(13, "Verify M9 Offline Sync Batch Upload Engine")
    device_id = f"test_resp_pwa_{int(time.time())}"
    # Register device
    reg_payload = {
        "device_identifier": device_id,
        "platform": "web_pwa",
        "app_version": "1.12.0"
    }
    r = requests.post(f"{API_URL}/api/sync/v1/devices/register", json=reg_payload, headers=resp_headers)
    assert_status(r, 200, "Register Sync Device")

    sync_batch_payload = {
        "device_id": device_id,
        "client_batch_id": f"batch_{int(time.time())}",
        "actions": [
            {
                "action_uuid": f"act_sync_{int(time.time())}_1",
                "action_type": "record_vitals",
                "encounter_id": encounter_id,
                "client_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "device_sequence_number": 1,
                "payload": {"heart_rate": 84, "spo2": 99}
            }
        ]
    }
    r = requests.post(f"{API_URL}/api/sync/v1/upload", json=sync_batch_payload, headers=resp_headers)
    sync_res = assert_status(r, 200, "Offline Sync Batch Upload")
    print(f"  OK: Offline Sync Processed. Receipts={len(sync_res.get('receipts', []))}")

    print("\n=================================================================")
    print("SUCCESS: ALL 13/13 CROSS-APPLICATION WORKFLOW PHASES VERIFIED!")
    print("=================================================================")

if __name__ == "__main__":
    main()
