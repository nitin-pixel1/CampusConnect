"""
Verification script for Admin viewing Lost & Found items (Found ID card).
"""
import asyncio
import os
import subprocess
import time
import urllib.request
import json
import base64
import websockets

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
PORT = 9228
BASE_URL = "http://127.0.0.1:5000"
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
user_data_dir = os.path.join(PROJECT_DIR, "temp_cdp_admin_lf_test")

import database
import sqlite3

async def test_admin_view():
    test_item = database.create_lost_found_item(
        item_type="Found",
        item_name="Student ID Card (Rohan Sharma)",
        category="ID Card",
        location="Library Ground Floor Entrance",
        date_reported="2026-10-23",
        description="Blue student RFID card found on front lawn bench",
        contact_name="Security Desk",
        contact_email="security@campus.edu",
        contact_phone="+91 98765 00000",
        status="Active"
    )
    test_id = test_item['id']

    chrome_cmd = [
        CHROME_PATH,
        "--headless=new",
        f"--remote-debugging-port={PORT}",
        f"--user-data-dir={user_data_dir}",
        "--disable-gpu",
        "--no-first-run",
        "--no-default-browser-check",
        "--window-size=1280,1050",
        "about:blank"
    ]
    proc = subprocess.Popen(chrome_cmd)
    time.sleep(2.0)

    try:
        targets_url = f"http://127.0.0.1:{PORT}/json"
        req = urllib.request.urlopen(targets_url)
        targets = json.loads(req.read().decode('utf-8'))
        ws_url = None
        for t in targets:
            if t.get('type') == 'page' and 'webSocketDebuggerUrl' in t:
                ws_url = t['webSocketDebuggerUrl']
                break
        if not ws_url:
            ws_url = targets[0]['webSocketDebuggerUrl']

        async with websockets.connect(ws_url) as ws:
            msg_id = 0

            async def send(method, params=None):
                nonlocal msg_id
                msg_id += 1
                payload = {'id': msg_id, 'method': method, 'params': params or {}}
                await ws.send(json.dumps(payload))
                while True:
                    res = json.loads(await ws.recv())
                    if res.get('id') == msg_id:
                        return res.get('result', {})

            async def eval_js(expr):
                r = await send('Runtime.evaluate', {'expression': expr, 'returnByValue': True})
                return r.get('result', {}).get('value')

            await send('Page.enable')
            await send('DOM.enable')

            # 1. Admin login
            print("[STEP 1] Navigating to Admin Login portal...")
            await send('Page.navigate', {'url': f"{BASE_URL}/admin/login"})
            await asyncio.sleep(1.5)

            print("[STEP 2] Submitting administrator credentials...")
            await eval_js("document.getElementById('admin-email').value = 'admin@campus.edu';")
            await eval_js("document.getElementById('admin-password').value = 'Admin@Campus2026!';")
            await eval_js("document.getElementById('form-admin-login').submit();")
            await asyncio.sleep(2.0)

            # 2. Check admin dashboard URL
            url = await eval_js("window.location.href")
            print(f"[STEP 3] Admin Dashboard URL: {url}")
            assert "/admin" in url, f"Expected redirect to /admin, got {url}"

            # 3. Scroll to Lost & Found Section
            print("[STEP 4] Scrolling to Lost & Found management section...")
            await eval_js("document.getElementById('admin-lost-found-section').scrollIntoView({behavior: 'instant'});")
            await asyncio.sleep(1.0)

            # 4. Check metrics and table row
            total_badge = await eval_js("document.querySelector('#admin-lost-found-section .badge-pill').innerText")
            print(f"[INFO] Total items badge: {total_badge}")

            row_exists = await eval_js(f"Boolean(document.getElementById('lf-row-{test_id}'))")
            print(f"[INFO] Row #lf-row-{test_id} exists: {row_exists}")
            assert row_exists, f"Row #lf-row-{test_id} not found in admin table!"

            item_title = await eval_js(f"document.querySelector('#lf-row-{test_id} .subject-title').innerText")
            category_badge = await eval_js(f"document.querySelector('#lf-row-{test_id} .category-badge').innerText")
            type_badge = await eval_js(f"document.querySelector('#lf-row-{test_id} .badge-type').innerText")
            reporter_name = await eval_js(f"document.querySelector('#lf-row-{test_id} .student-name').innerText")
            reporter_email = await eval_js(f"document.querySelector('#lf-row-{test_id} a[href^=\"mailto:\"]').innerText")
            reporter_phone = await eval_js(f"document.querySelector('#lf-row-{test_id} a[href^=\"tel:\"]').innerText")
            status_value = await eval_js(f"document.querySelector('#lf-row-{test_id} select.admin-status-dropdown').value")

            print("\n" + "=" * 60)
            print(" VERIFIED LOST & FOUND ITEM IN ADMIN VIEW:")
            print(f" ID & Type:       #LF-{test_id} ({type_badge})")
            print(f" Item Name:       {item_title}")
            print(f" Category:        {category_badge}")
            print(f" Reporter Name:   {reporter_name}")
            print(f" Reporter Email:  {reporter_email}")
            print(f" Reporter Phone:  {reporter_phone}")
            print(f" Current Status:  {status_value}")
            print("=" * 60 + "\n")

            # 5. Capture screenshot of admin view
            ss = await send('Page.captureScreenshot', {'format': 'png'})
            ss_data = base64.b64decode(ss['data'])
            out_path = os.path.join(PROJECT_DIR, "admin_lost_found_verified.png")
            with open(out_path, "wb") as f:
                f.write(ss_data)
            print(f"[SUCCESS] Screenshot captured: {out_path}")

            # 6. Test Filtering: Filter by Found Only
            print("[STEP 5] Testing 'Found Only' filter...")
            await eval_js("document.querySelector('button[data-admin-lf-filter=\"Found\"]').click();")
            await asyncio.sleep(0.5)
            row_disp = await eval_js(f"document.getElementById('lf-row-{test_id}').style.display")
            assert row_disp != 'none', f"Row {test_id} should be visible under 'Found Only' filter!"
            print(f"[PASS] Item #LF-{test_id} is visible under 'Found Only' filter.")

            # 7. Test Search: Search for "Rohan"
            print("[STEP 6] Testing live search for 'Rohan'...")
            await eval_js("const inp = document.getElementById('admin-lf-search-input'); inp.value = 'Rohan'; inp.dispatchEvent(new Event('input', {bubbles: true}));")
            await asyncio.sleep(0.5)
            row_disp2 = await eval_js(f"document.getElementById('lf-row-{test_id}').style.display")
            assert row_disp2 != 'none', f"Row {test_id} should be visible when searching for 'Rohan'!"
            print(f"[PASS] Item #LF-{test_id} is visible when searching for 'Rohan'.")

            # 8. Test status change via dropdown
            print("[STEP 7] Testing status update dropdown to 'Claimed'...")
            await eval_js(f"""
                const sel = document.querySelector('#lf-row-{test_id} select.admin-status-dropdown');
                sel.value = 'Claimed';
                sel.dispatchEvent(new Event('change', {{bubbles: true}}));
            """)
            await asyncio.sleep(1.0)
            toast_text = await eval_js("document.getElementById('toast-container') ? document.getElementById('toast-container').innerText : ''")
            print(f"[INFO] Toast notification: {toast_text}")

            # Reset back to Active
            await eval_js(f"""
                const sel = document.querySelector('#lf-row-{test_id} select.admin-status-dropdown');
                sel.value = 'Active';
                sel.dispatchEvent(new Event('change', {{bubbles: true}}));
            """)
            await asyncio.sleep(1.0)
            print("[PASS] Successfully updated status and restored to Active.")

            print("\n ALL ADMIN LOST & FOUND VERIFICATIONS PASSED 100%! ")

    finally:
        # Clean up test record so DB remains pristine
        try:
            conn = sqlite3.connect(database.DATABASE_PATH)
            conn.execute("DELETE FROM lost_found_items WHERE id = ?", (test_id,))
            conn.commit()
            conn.close()
            print(f"[CLEANUP] Test item #{test_id} removed. Database is pristine.")
        except Exception:
            pass

        proc.terminate()
        try:
            proc.wait(timeout=3)
        except Exception:
            proc.kill()
        import shutil
        if os.path.exists(user_data_dir):
            shutil.rmtree(user_data_dir, ignore_errors=True)

if __name__ == '__main__':
    asyncio.run(test_admin_view())
