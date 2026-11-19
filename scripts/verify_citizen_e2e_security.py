import urllib.request
import json
import time

def request(url, method='GET', data=None, token=None):
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = f'Bearer {token}'
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode() if data else None,
        headers=headers,
        method=method
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        try:
            return e.code, json.loads(body)
        except Exception:
            return e.code, {'detail': body}

print("================================================================================")
print("CAREON CITIZEN — END-TO-END FUNCTIONAL, SECURITY & CROSS-APP TEST SUITE")
print("================================================================================")

# 1. Citizen Authentication
st, login_data = request('http://localhost:8000/api/auth/login', 'POST', {
    'email': 'citizen@careon.org',
    'password': 'Password123!'
})
assert st == 200, f"Citizen login failed: {login_data}"
citizen_token = login_data['access_token']
print(f"[PASS] 1. Citizen login successful (Token received).")

# 2. Citizen Submits Real Incident
inc_payload = {
    'category': 'Road accident',
    'description': 'Two-wheeler collision with pedestrian at KRS Road Junction. Leg fracture suspected.',
    'location_name': 'KRS Road Junction, Near Railway Overbridge',
    'latitude': 12.3080,
    'longitude': 76.6500,
    'affected_people': 2,
    'help_required': 'Ambulance & Traffic Police',
    'contact_name': 'Aastha Singh',
    'contact_phone': '9845012345',
    'additional_details': 'Patient conscious: Yes | Breathing: Yes | Clear access from South Gate',
    'is_disaster': False
}
st, inc = request('http://localhost:8000/api/incidents', 'POST', inc_payload, token=citizen_token)
assert st == 201, f"Incident creation failed: {inc}"
inc_id = inc['id']
inc_code = inc['incident_code']
tracking_token = inc['tracking_token']
print(f"[PASS] 2. Incident created: ID={inc_id}, Code={inc_code}, Status={inc['status']}")

# 3. Server-Confirmed Public Tracking (Without Data Leaks)
st, track_res = request(f'http://localhost:8000/api/incidents/track/{tracking_token}')
assert st == 200, f"Tracking failed: {track_res}"
assert track_res['incident_code'] == inc_code
assert track_res['status'] in ['Received', 'Verification Pending']
# Ensure private dispatch internal notes or full reporter phone are NOT in public tracking
assert 'internal_admin_notes' not in track_res or track_res.get('internal_admin_notes') is None
assert 'contact_phone' not in track_res
print(f"[PASS] 3. Public tracking verified. Privacy preserved: no contact phone or internal notes leaked.")

# 4. Dispatcher Cross-Application Retrieval
st, disp_auth = request('http://localhost:8000/api/auth/login', 'POST', {
    'email': 'dispatcher@careon.org',
    'password': 'Password123!'
})
assert st == 200, f"Dispatcher login failed: {disp_auth}"
dispatcher_token = disp_auth['access_token']

st, disp_inc = request(f'http://localhost:8000/api/incidents/{inc_id}', 'GET', token=dispatcher_token)
assert st == 200, f"Dispatcher failed to retrieve incident: {disp_inc}"
assert disp_inc['incident_code'] == inc_code
assert disp_inc['location_name'] == inc_payload['location_name']
print(f"[PASS] 4. Cross-Application Verified: Dispatcher successfully retrieved incident {inc_code} via unified API.")

# 5. Security Test: Invalid Tracking Token Handling
st, inv_track = request('http://localhost:8000/api/incidents/track/invalid-fake-token-XYZ123')
assert st == 404, f"Expected 404 for invalid tracking token, got {st}"
print(f"[PASS] 5. Security: Unguessable token security verified (Invalid token correctly rejected with 404).")

# 6. Security Test: Unauthorized Incident Cancellation by Another User
intruder_email = f'intruder_{int(time.time())}@careon.org'
st, intruder_reg = request('http://localhost:8000/api/auth/register', 'POST', {
    'name': 'Intruder User',
    'email': intruder_email,
    'phone': '9998887776',
    'password': 'Password123!',
    'role': 'user'
})
assert st == 200 or st == 201, f"Intruder register failed: {intruder_reg}"

st, intruder_login = request('http://localhost:8000/api/auth/login', 'POST', {
    'email': intruder_email,
    'password': 'Password123!'
})
assert st == 200, f"Intruder login failed: {intruder_login}"
intruder_token = intruder_login['access_token']

st, cancel_res = request(
    f'http://localhost:8000/api/incidents/{inc_id}/cancel',
    'POST',
    {'reason': 'Unauthorized cancel attempt'},
    token=intruder_token
)
assert st == 403, f"Expected 403 Forbidden for unauthorized cancel, got {st}: {cancel_res}"
print(f"[PASS] 6. Security: Unauthorized cancellation correctly blocked with 403 Forbidden.")

# 7. Citizen Cancels Their Own Incident with Reason
st, user_cancel = request(
    f'http://localhost:8000/api/incidents/{inc_id}/cancel',
    'POST',
    {'reason': 'Patient stabilized / family transport arranged'},
    token=citizen_token
)
assert st == 200, f"Expected 200 for authorized cancellation, got {st}: {user_cancel}"
assert user_cancel['status'] == 'Cancelled'
print(f"[PASS] 7. Lifecycle: Citizen successfully cancelled their incident with reason.")

# 8. Terminal Incident Re-Cancellation Protection
st, re_cancel = request(
    f'http://localhost:8000/api/incidents/{inc_id}/cancel',
    'POST',
    {'reason': 'Duplicate cancel'},
    token=citizen_token
)
assert st == 400, f"Expected 400 for cancelling terminal incident, got {st}"
print(f"[PASS] 8. Validation: Terminal incident cancellation protected against re-submission (400 Bad Request).")

print("================================================================================")
print("ALL FUNCTIONAL, CROSS-APPLICATION AND SECURITY TESTS PASSED SUCCESSFULLY!")
print("================================================================================")
