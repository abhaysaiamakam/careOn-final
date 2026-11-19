#!/usr/bin/env python3
"""
Captures high-fidelity desktop, tablet, and mobile screenshots of the CareOn Clinical Web application (port 3005).
Connects to headless Chrome CDP on port 9222.
"""

import asyncio
import json
import urllib.request
import base64
import os
import websockets

SCREENSHOT_DIR = '/Users/abhaysaiam/.gemini/antigravity/brain/3fc1a273-9cf9-44d4-b97e-31d5c0949098/screenshots'
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

# 1. Fetch hospital staff auth token from backend
auth_req = urllib.request.Request(
    'http://localhost:8000/api/auth/login',
    data=json.dumps({'email': 'm2_hospital@careon.org', 'password': 'hospital123'}).encode(),
    headers={'Content-Type': 'application/json'}
)
with urllib.request.urlopen(auth_req) as resp:
    auth_data = json.loads(resp.read().decode())
    ACCESS_TOKEN = auth_data['access_token']
    USER_PROFILE = auth_data['user']

print(f"Authenticated Clinical Staff: {USER_PROFILE.get('name')} (Role: {USER_PROFILE.get('role')})")

VIEWPORTS = [
    ('desktop', 1440, 900, 1, False),
    ('tablet', 768, 1024, 1, True),
    ('mobile', 390, 844, 2, True),
]

VIEWS = [
    ('clinical_dashboard', 'dashboard'),
    ('clinical_incoming', 'incoming'),
    ('clinical_capacity', 'capacity'),
    ('clinical_handover', 'handover'),
    ('clinical_mci', 'mci'),
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
    # 1. Create a new tab for Clinical Web
    req = urllib.request.Request('http://localhost:9222/json/new?http://localhost:3005/', method='PUT')
    with urllib.request.urlopen(req) as resp:
        tab_info = json.loads(resp.read().decode())
    
    ws_url = tab_info['webSocketDebuggerUrl']
    req_counter = 1

    async with websockets.connect(ws_url) as ws:
        await cdp_call(ws, req_counter, 'Page.enable')
        req_counter += 1
        await cdp_call(ws, req_counter, 'Runtime.enable')
        req_counter += 1

        # A. Capture Login Screens (unauthenticated)
        for vp_name, width, height, scale, is_mobile in VIEWPORTS:
            print(f"\nCapturing clinical login screen for {vp_name} ({width}x{height})...")
            await cdp_call(ws, req_counter, 'Emulation.setDeviceMetricsOverride', {
                'width': width,
                'height': height,
                'deviceScaleFactor': scale,
                'mobile': is_mobile,
            })
            req_counter += 1

            await cdp_call(ws, req_counter, 'Page.navigate', {'url': 'http://localhost:3005/'})
            req_counter += 1
            await asyncio.sleep(1.0)

            # Clear session
            await cdp_call(ws, req_counter, 'Runtime.evaluate', {
                'expression': 'localStorage.clear();'
            })
            req_counter += 1
            await cdp_call(ws, req_counter, 'Page.navigate', {'url': 'http://localhost:3005/'})
            req_counter += 1
            await asyncio.sleep(1.2)

            shot = await cdp_call(ws, req_counter, 'Page.captureScreenshot', {'format': 'png'})
            req_counter += 1
            filename = f"{SCREENSHOT_DIR}/clinical_login_{vp_name}.png"
            with open(filename, 'wb') as f:
                f.write(base64.b64decode(shot['data']))
            print(f"  Captured: {filename}")

        # B. Seed Authenticated Clinical Session
        seed_script = f"""
        localStorage.setItem('careon_clinical_access_token', '{ACCESS_TOKEN}');
        localStorage.setItem('careon_clinical_user', JSON.stringify({json.dumps(USER_PROFILE)}));
        """
        await cdp_call(ws, req_counter, 'Runtime.evaluate', {'expression': seed_script})
        req_counter += 1

        # C. Capture Authenticated Views across Desktop, Tablet, Mobile
        for vp_name, width, height, scale, is_mobile in VIEWPORTS:
            print(f"\nCapturing authenticated clinical views for {vp_name} ({width}x{height})...")
            await cdp_call(ws, req_counter, 'Emulation.setDeviceMetricsOverride', {
                'width': width,
                'height': height,
                'deviceScaleFactor': scale,
                'mobile': is_mobile,
            })
            req_counter += 1

            for view_name, nav_target in VIEWS:
                await cdp_call(ws, req_counter, 'Page.navigate', {'url': 'http://localhost:3005/'})
                req_counter += 1
                await asyncio.sleep(1.2)

                # Switch active view in header/nav
                switch_script = f"""
                (() => {{
                    const buttons = Array.from(document.querySelectorAll('header button, nav button'));
                    const target = buttons.find(b => {{
                        const text = (b.innerText || '').toLowerCase();
                        if ('{nav_target}' === 'dashboard') return text.includes('dashboard');
                        if ('{nav_target}' === 'incoming') return text.includes('incoming');
                        if ('{nav_target}' === 'capacity') return text.includes('capacity');
                        if ('{nav_target}' === 'handover') return text.includes('handover');
                        if ('{nav_target}' === 'mci') return text.includes('mci');
                        return false;
                    }});
                    if (target) target.click();
                }})();
                """
                await cdp_call(ws, req_counter, 'Runtime.evaluate', {'expression': switch_script})
                req_counter += 1
                await asyncio.sleep(1.2)

                shot = await cdp_call(ws, req_counter, 'Page.captureScreenshot', {'format': 'png'})
                req_counter += 1
                filename = f"{SCREENSHOT_DIR}/{view_name}_{vp_name}.png"
                with open(filename, 'wb') as f:
                    f.write(base64.b64decode(shot['data']))
                print(f"  Captured: {filename}")

    print("\nAll Clinical Web screenshots successfully captured!")

if __name__ == '__main__':
    asyncio.run(run())
