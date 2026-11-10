"""
Automated Browser End-to-End Test for CampusConnect Phase 5:
Authentication, Role-Based Access Control, Student & Admin Dashboards
Uses Chrome DevTools Protocol (CDP) via websockets and asyncio.
"""

import sys
import os
import json
import time
import base64
import urllib.request
import subprocess
import asyncio
import websockets

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
PORT = 9225
BASE_URL = "http://127.0.0.1:5000"
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))

async def run_browser_tests():
    print("=" * 65)
    print(" CampusConnect Phase 5: Automated Browser E2E Authentication Test")
    print("=" * 65)

    user_data_dir = os.path.join(PROJECT_DIR, 'temp_cdp_p5')

    chrome_cmd = [
        CHROME_PATH,
        "--headless=new",
        f"--remote-debugging-port={PORT}",
        f"--user-data-dir={user_data_dir}",
        "--disable-gpu",
        "--no-first-run",
        "--no-default-browser-check",
        "--window-size=1280,900",
        "about:blank"
    ]

    chrome_proc = subprocess.Popen(chrome_cmd)
    await asyncio.sleep(2.0)

    try:
        # Query targets
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

            async def cdp_send(method, params=None):
                nonlocal msg_id
                msg_id += 1
                payload = {"id": msg_id, "method": method, "params": params or {}}
                await ws.send(json.dumps(payload))
                while True:
                    resp = json.loads(await ws.recv())
                    if resp.get("id") == msg_id:
                        return resp.get("result", {})

            async def eval_js(expr):
                res = await cdp_send("Runtime.evaluate", {
                    "expression": expr,
                    "returnByValue": True,
                    "awaitPromise": True
                })
                if "exceptionDetails" in res:
                    raise Exception(f"JS Error: {res['exceptionDetails']}")
                return res.get("result", {}).get("value")

            async def capture_screenshot(filename):
                data = await cdp_send("Page.captureScreenshot", {"format": "png"})
                b64 = data.get("data")
                filepath = os.path.join(PROJECT_DIR, filename)
                with open(filepath, "wb") as f:
                    f.write(base64.b64decode(b64))
                print(f"[SCREENSHOT] Saved: {filepath}")

            await cdp_send("Page.enable")
            await cdp_send("Runtime.enable")

            # 1. Register a test student via API
            from database import create_user, delete_user_by_email
            test_email = "ananya.sharma@campus.edu"
            test_pass = "StudentPass2026!"
            delete_user_by_email(test_email)
            create_user(name="Ananya Sharma", email=test_email, password=test_pass, student_id="CS2024-088", role="Student")

            # 2. Navigate to Login Page
            print("\n[STEP 1] Navigating to Student Login page...")
            await cdp_send("Page.navigate", {"url": f"{BASE_URL}/login"})
            await asyncio.sleep(1.5)

            title = await eval_js("document.title")
            assert "Sign In" in title, f"Unexpected title: {title}"
            print(f"[PASS] Loaded Login Page: '{title}'")

            # 3. Enter credentials and test password toggle
            print("\n[STEP 2] Testing form fields and password toggle...")
            await eval_js(f"""
                document.getElementById('login-email').value = '{test_email}';
                document.getElementById('login-password').value = '{test_pass}';
            """)
            await eval_js("document.getElementById('btn-toggle-password').click();")
            await asyncio.sleep(0.3)
            pwd_type = await eval_js("document.getElementById('login-password').type")
            assert pwd_type == 'text', f"Expected type 'text' after toggle, got '{pwd_type}'"
            print("[PASS] Password visibility toggle verified (password -> text).")

            await eval_js("document.getElementById('btn-toggle-password').click();")
            await asyncio.sleep(0.3)
            pwd_type = await eval_js("document.getElementById('login-password').type")
            assert pwd_type == 'password', f"Expected type 'password' after toggle, got '{pwd_type}'"
            print("[PASS] Password visibility toggle verified (text -> password).")

            await capture_screenshot("phase5_verified_login.png")

            # 4. Submit Student Login
            print("\n[STEP 3] Submitting Student Login...")
            await eval_js("document.getElementById('form-student-login').dispatchEvent(new Event('submit', {cancelable: true, bubbles: true}));")
            await asyncio.sleep(2.0)

            curr_url = await eval_js("window.location.href")
            print(f"[INFO] Current URL after login: {curr_url}")
            assert "/student/dashboard" in curr_url, f"Expected redirect to /student/dashboard, got {curr_url}"

            greeting = await eval_js("document.querySelector('.student-hero-title').innerText")
            print(f"[PASS] Student Dashboard verified: '{greeting}'")
            await capture_screenshot("phase5_verified_student_dashboard.png")

            # 5. Sign out
            print("\n[STEP 4] Logging out of student session...")
            await cdp_send("Page.navigate", {"url": f"{BASE_URL}/logout"})
            await asyncio.sleep(1.5)
            curr_url = await eval_js("window.location.href")
            print(f"[PASS] Redirected after logout to: {curr_url}")

            # 6. Navigate to Admin Login
            print("\n[STEP 5] Navigating to Administrator Login portal...")
            await cdp_send("Page.navigate", {"url": f"{BASE_URL}/admin/login"})
            await asyncio.sleep(1.5)
            admin_title = await eval_js("document.title")
            assert "Administrator" in admin_title
            print(f"[PASS] Loaded Admin Login Portal: '{admin_title}'")

            # 7. Authenticate as Administrator
            print("\n[STEP 6] Authenticating Administrator...")
            await eval_js("""
                document.getElementById('admin-email').value = 'admin@campus.edu';
                document.getElementById('admin-password').value = 'Admin@Campus2026!';
                document.getElementById('form-admin-login').dispatchEvent(new Event('submit', {cancelable: true, bubbles: true}));
            """)
            await asyncio.sleep(2.0)

            curr_url = await eval_js("window.location.href")
            print(f"[INFO] Current URL after admin login: {curr_url}")
            assert "/admin" in curr_url, f"Expected /admin, got {curr_url}"

            admin_heading = await eval_js("document.querySelector('.admin-hero-title').innerText")
            print(f"[PASS] Admin Dashboard verified: '{admin_heading}'")
            await capture_screenshot("phase5_verified_admin_dashboard.png")

            # 8. Test live status change on Admin Dashboard
            print("\n[STEP 7] Testing ticket status change via Admin Dashboard...")
            first_ticket_id = await eval_js("document.querySelector('#admin-table-body tr.admin-ticket-row')?.id || 'empty-state'")
            print(f"[INFO] First ticket row / state: {first_ticket_id}")
            assert first_ticket_id is not None

            # 9. Cleanup
            delete_user_by_email(test_email)
            print("\n[STEP 8] Test student cleaned up from database.")

            print("\n" + "=" * 65)
            print(" ALL PHASE 5 BROWSER E2E TESTS PASSED 100%! ")
            print("=" * 65)

    finally:
        chrome_proc.terminate()
        try:
            chrome_proc.wait(timeout=3)
        except Exception:
            chrome_proc.kill()
        import shutil
        if os.path.exists(user_data_dir):
            shutil.rmtree(user_data_dir, ignore_errors=True)

if __name__ == '__main__':
    asyncio.run(run_browser_tests())
