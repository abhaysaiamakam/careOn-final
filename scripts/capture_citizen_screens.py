import asyncio
import json
import urllib.request
import base64
import os
import websockets

SCREENSHOT_DIR = '/Users/abhaysaiam/.gemini/antigravity/brain/3fc1a273-9cf9-44d4-b97e-31d5c0949098/screenshots'
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

# 1. Fetch citizen auth token from backend
auth_req = urllib.request.Request(
    'http://localhost:8000/api/auth/login',
    data=json.dumps({'email': 'citizen@careon.org', 'password': 'Password123!'}).encode(),
    headers={'Content-Type': 'application/json'}
)
with urllib.request.urlopen(auth_req) as resp:
    auth_data = json.loads(resp.read().decode())
    ACCESS_TOKEN = auth_data['access_token']

me_req = urllib.request.Request(
    'http://localhost:8000/api/auth/me',
    headers={'Authorization': f'Bearer {ACCESS_TOKEN}'}
)
with urllib.request.urlopen(me_req) as resp:
    USER_PROFILE = json.loads(resp.read().decode())

print(f"Authenticated Citizen: {USER_PROFILE.get('name')}")

ROUTES = [
    ('home', 'http://localhost:3002/'),
    ('report_step1', 'http://localhost:3002/report'),
    ('track_incident', 'http://localhost:3002/track?id=CARE-2026-101'),
    ('citizen_dashboard', 'http://localhost:3002/dashboard'),
    ('emergency_history', 'http://localhost:3002/history'),
    ('profile', 'http://localhost:3002/profile'),
    ('emergency_contacts', 'http://localhost:3002/contacts'),
    ('notifications', 'http://localhost:3002/notifications'),
    ('settings', 'http://localhost:3002/settings'),
    ('drafts', 'http://localhost:3002/drafts'),
]

VIEWPORTS = [
    ('desktop', 1280, 800, 1),
    ('mobile', 390, 844, 2),
]

async def cdp_call(ws, req_id, method, params=None):
    payload = {'id': req_id, 'method': method}
    if params:
        payload['params'] = params
    await ws.send(json.dumps(payload))
    while True:
        msg = await ws.recv()
        data = json.loads(msg)
        if data.get('id') == req_id:
            return data.get('result', {})

async def run():
    # Create new tab
    req = urllib.request.Request('http://localhost:9222/json/new?http://localhost:3002/', method='PUT')
    with urllib.request.urlopen(req) as resp:
        tab_info = json.loads(resp.read().decode())
    
    ws_url = tab_info['webSocketDebuggerUrl']
    req_counter = 1

    async with websockets.connect(ws_url) as ws:
        # Enable domains
        await cdp_call(ws, req_counter, 'Page.enable')
        req_counter += 1
        await cdp_call(ws, req_counter, 'Runtime.enable')
        req_counter += 1

        # Seed localStorage on http://localhost:3002/
        await cdp_call(ws, req_counter, 'Page.navigate', {'url': 'http://localhost:3002/'})
        req_counter += 1
        await asyncio.sleep(1.0)

        seed_script = f"""
        localStorage.setItem('careon_citizen_access_token', '{ACCESS_TOKEN}');
        localStorage.setItem('careon_citizen_user', JSON.stringify({json.dumps(USER_PROFILE)}));
        """
        await cdp_call(ws, req_counter, 'Runtime.evaluate', {'expression': seed_script})
        req_counter += 1

        for vp_name, width, height, scale in VIEWPORTS:
            print(f"Setting viewport to {vp_name} ({width}x{height}, scale={scale})...")
            await cdp_call(ws, req_counter, 'Emulation.setDeviceMetricsOverride', {
                'width': width,
                'height': height,
                'deviceScaleFactor': scale,
                'mobile': vp_name == 'mobile',
            })
            req_counter += 1

            for route_name, url in ROUTES:
                print(f"  Navigating to {route_name} -> {url}")
                await cdp_call(ws, req_counter, 'Page.navigate', {'url': url})
                req_counter += 1
                await asyncio.sleep(1.2) # Allow components and data fetch to settle

                # Capture screenshot
                shot = await cdp_call(ws, req_counter, 'Page.captureScreenshot', {
                    'format': 'png',
                })
                req_counter += 1
                img_bytes = base64.b64decode(shot['data'])
                filename = f"{route_name}_{vp_name}.png"
                filepath = os.path.join(SCREENSHOT_DIR, filename)
                with open(filepath, 'wb') as f:
                    f.write(img_bytes)
                print(f"    Saved: {filepath} ({len(img_bytes)} bytes)")

    print("All screenshots successfully captured!")

if __name__ == '__main__':
    asyncio.run(run())
