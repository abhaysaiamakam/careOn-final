import asyncio
import json
import urllib.request
import base64
import os
import websockets

SCREENSHOT_DIR = '/Users/abhaysaiam/.gemini/antigravity/brain/3fc1a273-9cf9-44d4-b97e-31d5c0949098/screenshots'
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

# 1. Fetch dispatcher auth token from backend
auth_req = urllib.request.Request(
    'http://localhost:8000/api/auth/login',
    data=json.dumps({'email': 'dispatcher@careon.org', 'password': 'Password123!'}).encode(),
    headers={'Content-Type': 'application/json'}
)
with urllib.request.urlopen(auth_req) as resp:
    auth_data = json.loads(resp.read().decode())
    ACCESS_TOKEN = auth_data['access_token']
    USER_PROFILE = auth_data['user']

print(f"Authenticated Dispatcher: {USER_PROFILE.get('name')} (Role: {USER_PROFILE.get('role')})")

VIEWPORTS = [
    ('desktop', 1440, 900, 1),
    ('tablet', 1024, 768, 1),
]

VIEWS = [
    ('command_overview', 'overview'),
    ('command_dispatch', 'overview'),
    ('command_map', 'map'),
    ('command_fleet', 'fleet'),
    ('command_hospitals', 'hospitals'),
    ('command_multiagency', 'multi-agency'),
    ('command_intelligence', 'intelligence'),
    ('command_analytics', 'analytics'),
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
    # 1. Create a new tab
    req = urllib.request.Request('http://localhost:9222/json/new?http://localhost:3003/', method='PUT')
    with urllib.request.urlopen(req) as resp:
        tab_info = json.loads(resp.read().decode())
    
    ws_url = tab_info['webSocketDebuggerUrl']
    req_counter = 1

    async with websockets.connect(ws_url) as ws:
        await cdp_call(ws, req_counter, 'Page.enable')
        req_counter += 1
        await cdp_call(ws, req_counter, 'Runtime.enable')
        req_counter += 1

        # First, capture unauthenticated login screen
        for vp_name, width, height, scale in VIEWPORTS:
            await cdp_call(ws, req_counter, 'Emulation.setDeviceMetricsOverride', {
                'width': width,
                'height': height,
                'deviceScaleFactor': scale,
                'mobile': vp_name == 'tablet',
            })
            req_counter += 1

            await cdp_call(ws, req_counter, 'Page.navigate', {'url': 'http://localhost:3003/'})
            req_counter += 1
            await asyncio.sleep(1.0)

            # Ensure localStorage is cleared for login view
            await cdp_call(ws, req_counter, 'Runtime.evaluate', {
                'expression': 'localStorage.clear();'
            })
            req_counter += 1
            await cdp_call(ws, req_counter, 'Page.navigate', {'url': 'http://localhost:3003/'})
            req_counter += 1
            await asyncio.sleep(1.0)

            shot = await cdp_call(ws, req_counter, 'Page.captureScreenshot', {'format': 'png'})
            req_counter += 1
            filename = f"{SCREENSHOT_DIR}/command_login_{vp_name}.png"
            with open(filename, 'wb') as f:
                f.write(base64.b64decode(shot['data']))
            print(f"Captured: {filename}")

        # Now authenticate dispatcher
        seed_script = f"""
        localStorage.setItem('careon_command_access_token', '{ACCESS_TOKEN}');
        localStorage.setItem('careon_command_user', JSON.stringify({json.dumps(USER_PROFILE)}));
        """
        await cdp_call(ws, req_counter, 'Runtime.evaluate', {'expression': seed_script})
        req_counter += 1

        for vp_name, width, height, scale in VIEWPORTS:
            print(f"\nCapturing authenticated views for {vp_name} ({width}x{height})...")
            await cdp_call(ws, req_counter, 'Emulation.setDeviceMetricsOverride', {
                'width': width,
                'height': height,
                'deviceScaleFactor': scale,
                'mobile': vp_name == 'tablet',
            })
            req_counter += 1

            for view_name, tab_id in VIEWS:
                await cdp_call(ws, req_counter, 'Page.navigate', {'url': 'http://localhost:3003/'})
                req_counter += 1
                await asyncio.sleep(1.0)

                # Switch active view in UI if needed
                switch_script = f"""
                (() => {{
                    const buttons = Array.from(document.querySelectorAll('header button'));
                    const target = buttons.find(b => b.innerText.toLowerCase().includes('{tab_id.split('-')[0]}'));
                    if (target) target.click();
                }})();
                """
                await cdp_call(ws, req_counter, 'Runtime.evaluate', {'expression': switch_script})
                req_counter += 1
                await asyncio.sleep(0.8)

                # If this is the command_dispatch view or overview, select the first incident in queue to open right command panel!
                if view_name == 'command_dispatch' or view_name == 'command_overview':
                    select_script = """
                    (() => {
                        const queueItems = Array.from(document.querySelectorAll('div')).filter(d => d.innerText && d.innerText.includes('CARE-2026') || d.innerText.includes('INC-'));
                        const clickable = document.querySelector('div[style*="cursor: pointer"]') || queueItems[0];
                        if (clickable) clickable.click();
                    })();
                    """
                    await cdp_call(ws, req_counter, 'Runtime.evaluate', {'expression': select_script})
                    req_counter += 1
                    await asyncio.sleep(0.8)

                shot = await cdp_call(ws, req_counter, 'Page.captureScreenshot', {'format': 'png'})
                req_counter += 1
                filename = f"{SCREENSHOT_DIR}/{view_name}_{vp_name}.png"
                with open(filename, 'wb') as f:
                    f.write(base64.b64decode(shot['data']))
                print(f"  Captured: {filename}")

    print("\nAll command centre screenshots successfully captured!")

asyncio.run(run())
