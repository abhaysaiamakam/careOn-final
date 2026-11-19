#!/usr/bin/env python3
"""
Captures high-fidelity desktop, tablet, and mobile screenshots of the CareOn Responder Web application (port 3004).
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

# 1. Fetch responder auth token from backend
auth_req = urllib.request.Request(
    'http://localhost:8000/api/auth/login',
    data=json.dumps({'email': 'm2_responder@careon.org', 'password': 'responder123'}).encode(),
    headers={'Content-Type': 'application/json'}
)
with urllib.request.urlopen(auth_req) as resp:
    auth_data = json.loads(resp.read().decode())
    ACCESS_TOKEN = auth_data['access_token']
    USER_PROFILE = auth_data['user']

print(f"Authenticated Responder: {USER_PROFILE.get('name')} (Role: {USER_PROFILE.get('role')})")

VIEWPORTS = [
    ('desktop', 1440, 900, 1, False),
    ('tablet', 768, 1024, 1, True),
    ('mobile', 390, 844, 2, True),
]

VIEWS = [
    ('responder_dashboard', 'dashboard'),
    ('responder_inbox', 'inbox'),
    ('responder_workspace_active', 'active'),
    ('responder_history', 'history'),
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
    # 1. Create a new tab for Responder Web
    req = urllib.request.Request('http://localhost:9222/json/new?http://localhost:3004/', method='PUT')
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
            print(f"\nCapturing login screen for {vp_name} ({width}x{height})...")
            await cdp_call(ws, req_counter, 'Emulation.setDeviceMetricsOverride', {
                'width': width,
                'height': height,
                'deviceScaleFactor': scale,
                'mobile': is_mobile,
            })
            req_counter += 1

            await cdp_call(ws, req_counter, 'Page.navigate', {'url': 'http://localhost:3004/'})
            req_counter += 1
            await asyncio.sleep(1.0)

            # Clear session
            await cdp_call(ws, req_counter, 'Runtime.evaluate', {
                'expression': 'localStorage.clear();'
            })
            req_counter += 1
            await cdp_call(ws, req_counter, 'Page.navigate', {'url': 'http://localhost:3004/'})
            req_counter += 1
            await asyncio.sleep(1.2)

            shot = await cdp_call(ws, req_counter, 'Page.captureScreenshot', {'format': 'png'})
            req_counter += 1
            filename = f"{SCREENSHOT_DIR}/responder_login_{vp_name}.png"
            with open(filename, 'wb') as f:
                f.write(base64.b64decode(shot['data']))
            print(f"  Captured: {filename}")

        # B. Seed Authenticated Responder Session
        seed_script = f"""
        localStorage.setItem('careon_responder_access_token', '{ACCESS_TOKEN}');
        localStorage.setItem('careon_responder_user', JSON.stringify({json.dumps(USER_PROFILE)}));
        """
        await cdp_call(ws, req_counter, 'Runtime.evaluate', {'expression': seed_script})
        req_counter += 1

        # C. Capture Authenticated Views across Desktop, Tablet, Mobile
        for vp_name, width, height, scale, is_mobile in VIEWPORTS:
            print(f"\nCapturing authenticated views for {vp_name} ({width}x{height})...")
            await cdp_call(ws, req_counter, 'Emulation.setDeviceMetricsOverride', {
                'width': width,
                'height': height,
                'deviceScaleFactor': scale,
                'mobile': is_mobile,
            })
            req_counter += 1

            for view_name, nav_target in VIEWS:
                await cdp_call(ws, req_counter, 'Page.navigate', {'url': 'http://localhost:3004/'})
                req_counter += 1
                await asyncio.sleep(1.2)

                # Switch active view in header/nav
                switch_script = f"""
                (() => {{
                    const buttons = Array.from(document.querySelectorAll('header button, nav button'));
                    const target = buttons.find(b => {{
                        const text = (b.innerText || '').toLowerCase();
                        if ('{nav_target}' === 'dashboard') return text.includes('dashboard');
                        if ('{nav_target}' === 'inbox') return text.includes('inbox');
                        if ('{nav_target}' === 'active') return text.includes('active') || text.includes('mission');
                        if ('{nav_target}' === 'history') return text.includes('history');
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

    print("\nAll Responder Web screenshots successfully captured!")

if __name__ == '__main__':
    asyncio.run(run())
