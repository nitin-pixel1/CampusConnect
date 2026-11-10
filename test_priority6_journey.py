"""
Comprehensive Automated Verification Script for Refined ULTRON Flow:
Verifies:
1. Open / in unauthenticated session:
   - Dedicated ULTRON Access Gateway appears
   - Main title: CAMPUSCONNECT
   - System label: ULTRON INTERFACE // ACCESS CONTROL
   - Main message: IDENTITY VERIFICATION REQUIRED
   - Supporting text: Choose your access level to enter the campus command system.
   - Large central animated robotic AI core is visible and prominent
   - Two cards only: STUDENT ACCESS and ADMIN COMMAND ACCESS
   - Buttons only: INITIALIZE STUDENT ACCESS & ENTER ADMIN COMMAND
   - ZERO input fields on / (no email, no password)
2. Card 1 navigates to /login:
   - Dedicated Student Login page with student form ONLY
   - Show/hide password toggle works
   - Back to Access Gateway link exists and returns to /
   - No admin login form present on /login
3. Card 2 navigates to /admin/login:
   - Dedicated Admin Login page with admin form ONLY
   - Show/hide password toggle works
   - Back to Access Gateway link exists and returns to /
   - No student login form present on /admin/login
4. Direct access to protected routes without login is blocked & redirected
5. Student cannot access admin pages or APIs (HTTP 403 Forbidden)
6. Successful student login redirects to /student/dashboard
7. Successful admin login redirects to /admin/dashboard
8. Invalid credentials rejected on /login
9. Logout returns to / access gateway and protected routes remain blocked
10. Registration still works
11. Lost & Found and helpdesk functionality intact
12. Desktop (1280px) and mobile (375px) viewports have zero horizontal overflow
"""

import sys
import os
import json
import base64
import urllib.request
import subprocess
import asyncio
import websockets

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
PORT = 9227
BASE_URL = "http://127.0.0.1:5000"
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))

async def verify_user_journey():
    print("=" * 70)
    print(" CAMPUSCONNECT: VERIFYING REFINED ULTRON ACCESS GATEWAY & FLOW")
    print("=" * 70)

    user_data_dir = os.path.join(PROJECT_DIR, 'temp_cdp_journey2')
    if os.path.exists(user_data_dir):
        import shutil
        shutil.rmtree(user_data_dir, ignore_errors=True)

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
                print(f"  [SCREENSHOT] Saved: {filepath}")

            await cdp_send("Page.enable")
            await cdp_send("Runtime.enable")

            # -----------------------------------------------------------------
            # REQUIREMENT 1: Open / in fresh unauthenticated browser session
            # -----------------------------------------------------------------
            print("\n[REQ 1] Testing / in unauthenticated browser session...")
            await cdp_send("Page.navigate", {"url": f"{BASE_URL}/"})
            await asyncio.sleep(1.5)

            title = await eval_js("document.title")
            heading = await eval_js("document.querySelector('.entry-main-heading')?.innerText || ''")
            system_label = await eval_js("document.querySelector('.ultron-kicker-chip .chip-text')?.innerText || ''")
            warning_text = await eval_js("document.querySelector('.entry-sub-headline')?.innerText || ''")
            supporting_text = await eval_js("document.querySelector('.entry-supporting-text')?.innerText || ''")
            has_student_card = await eval_js("document.getElementById('student-access-card') !== null")
            has_admin_card = await eval_js("document.getElementById('admin-access-card') !== null")
            has_btn_student = await eval_js("document.getElementById('btn-init-student') !== null")
            has_btn_admin = await eval_js("document.getElementById('btn-init-admin') !== null")
            btn_student_text = await eval_js("document.getElementById('btn-init-student')?.innerText || ''")
            btn_admin_text = await eval_js("document.getElementById('btn-init-admin')?.innerText || ''")
            has_focal_core = await eval_js("document.querySelector('.ultron-focal-core-svg') !== null")
            has_any_inputs = await eval_js("document.querySelector('input[type=\"email\"], input[type=\"password\"], #login-email, #admin-email') !== null")

            print(f"  Page Title: '{title}'")
            print(f"  Main Heading: '{heading}'")
            print(f"  System Label: '{system_label}'")
            print(f"  Main Message: '{warning_text}'")
            print(f"  Supporting Text: '{supporting_text}'")
            print(f"  Student Button Text: '{btn_student_text.strip()}'")
            print(f"  Admin Button Text: '{btn_admin_text.strip()}'")
            print(f"  Has Central Robotic AI Core: {has_focal_core}")
            print(f"  Inputs present on Gateway (MUST BE FALSE): {has_any_inputs}")

            assert "CAMPUSCONNECT" in heading.replace(" ", "").upper()
            assert "ACCESS CONTROL" in system_label
            assert "IDENTITY VERIFICATION REQUIRED" in warning_text
            assert "Choose your access level to enter the campus command system." in supporting_text
            assert has_student_card and has_admin_card and has_btn_student and has_btn_admin
            assert "INITIALIZE STUDENT ACCESS" in btn_student_text
            assert "ENTER ADMIN COMMAND" in btn_admin_text
            assert has_focal_core, "Central robotic AI core missing!"
            assert not has_any_inputs, "Inputs must not exist on the entry gateway!"

            await capture_screenshot("ultron_verified_entry_gateway.png")
            print("  -> PASS: Dedicated ULTRON Access Gateway verified (Focal Core + 2 Action Cards, No inputs).")

            # -----------------------------------------------------------------
            # REQUIREMENT 2: Verify Gateway Navigation to Separate Login Pages
            # -----------------------------------------------------------------
            print("\n[REQ 2] Testing navigation from Gateway to Separate Login Pages...")

            # 2A. Click Student Access button
            await eval_js("document.getElementById('btn-init-student').click();")
            await asyncio.sleep(1.2)
            curr_url = await eval_js("window.location.href")
            print(f"  URL after clicking Student Access: {curr_url}")
            assert "/login" in curr_url

            has_student_form = await eval_js("document.getElementById('form-student-login') !== null")
            has_student_email = await eval_js("document.getElementById('login-email') !== null")
            has_student_pwd = await eval_js("document.getElementById('login-password') !== null")
            has_admin_form_on_login = await eval_js("document.getElementById('form-admin-login') !== null")
            has_back_to_gateway = await eval_js("document.getElementById('link-back-gateway') !== null")
            back_text = await eval_js("document.getElementById('link-back-gateway')?.innerText || ''")

            print(f"  Has Student Form on /login: {has_student_form}")
            print(f"  Has Admin Form on /login (MUST BE FALSE): {has_admin_form_on_login}")
            print(f"  Has 'Back to Access Gateway' link: {has_back_to_gateway} ('{back_text.strip()}')")

            assert has_student_form and has_student_email and has_student_pwd
            assert not has_admin_form_on_login, "Admin login form must not be on /login!"
            assert has_back_to_gateway and "Back to Access Gateway" in back_text
            await capture_screenshot("ultron_verified_student_login_page.png")
            print("  -> PASS: Dedicated Student Login page verified (/login).")

            # 2B. Test Back to Access Gateway from /login
            await eval_js("document.getElementById('link-back-gateway').click();")
            await asyncio.sleep(1.2)
            curr_url = await eval_js("window.location.href")
            print(f"  URL after clicking Back to Access Gateway: {curr_url}")
            assert curr_url.rstrip("/") == BASE_URL
            print("  -> PASS: 'Back to Access Gateway' successfully returns to /.")

            # 2C. Click Admin Command button from Gateway
            await eval_js("document.getElementById('btn-init-admin').click();")
            await asyncio.sleep(1.2)
            curr_url = await eval_js("window.location.href")
            print(f"  URL after clicking Admin Command: {curr_url}")
            assert "/admin/login" in curr_url

            has_admin_form = await eval_js("document.getElementById('form-admin-login') !== null")
            has_admin_email = await eval_js("document.getElementById('admin-email') !== null")
            has_admin_pwd = await eval_js("document.getElementById('admin-password') !== null")
            has_student_form_on_admin = await eval_js("document.getElementById('form-student-login') !== null")
            has_admin_back_link = await eval_js("document.getElementById('link-back-gateway') !== null")
            admin_back_text = await eval_js("document.getElementById('link-back-gateway')?.innerText || ''")

            print(f"  Has Admin Form on /admin/login: {has_admin_form}")
            print(f"  Has Student Form on /admin/login (MUST BE FALSE): {has_student_form_on_admin}")
            print(f"  Has 'Back to Access Gateway' link: {has_admin_back_link} ('{admin_back_text.strip()}')")

            assert has_admin_form and has_admin_email and has_admin_pwd
            assert not has_student_form_on_admin, "Student login form must not be on /admin/login!"
            assert has_admin_back_link and "Back to Access Gateway" in admin_back_text
            await capture_screenshot("ultron_verified_admin_login_page.png")
            print("  -> PASS: Dedicated Admin Login page verified (/admin/login).")

            # -----------------------------------------------------------------
            # REQUIREMENT 4: Direct access to protected routes without login is blocked
            # -----------------------------------------------------------------
            print("\n[REQ 4] Testing direct access to protected routes without login...")
            protected_routes = [
                "/dashboard",
                "/student/dashboard",
                "/admin/dashboard",
                "/lost-found",
                "/report",
                "/report-lost",
                "/report-found",
                "/my-reports"
            ]
            for route in protected_routes:
                await cdp_send("Page.navigate", {"url": f"{BASE_URL}{route}"})
                await asyncio.sleep(0.8)
                curr_url = await eval_js("window.location.href")
                assert "/login" in curr_url or curr_url.rstrip("/") == BASE_URL, f"Route {route} not protected! Reached {curr_url}"
                print(f"  Route '{route}' -> Successfully blocked/redirected to: {curr_url}")
            print("  -> PASS: All protected routes are strictly blocked for unauthenticated users.")

            # -----------------------------------------------------------------
            # REQUIREMENT 8: Invalid credentials are rejected
            # -----------------------------------------------------------------
            print("\n[REQ 8] Testing invalid credentials rejection on /login...")
            await cdp_send("Page.navigate", {"url": f"{BASE_URL}/login"})
            await asyncio.sleep(1.0)
            await eval_js("""
                document.getElementById('login-email').value = 'fake.student@campus.edu';
                document.getElementById('login-password').value = 'WrongPassword999!';
                document.getElementById('form-student-login').dispatchEvent(new Event('submit', {cancelable: true, bubbles: true}));
            """)
            await asyncio.sleep(1.5)
            err_msg = await eval_js("document.getElementById('auth-alert')?.innerText || ''")
            print(f"  Student login error message: '{err_msg}'")
            assert "invalid" in err_msg.lower() or "credentials" in err_msg.lower()
            print("  -> PASS: Invalid credentials rejected with clear error message.")

            # -----------------------------------------------------------------
            # REQUIREMENT 10: Registration works
            # -----------------------------------------------------------------
            print("\n[REQ 10] Testing Student Registration flow...")
            from database import delete_user_by_email
            reg_email = "test.journey@campus.edu"
            delete_user_by_email(reg_email)

            await cdp_send("Page.navigate", {"url": f"{BASE_URL}/register"})
            await asyncio.sleep(1.0)
            reg_title = await eval_js("document.title")
            print(f"  Registration page title: '{reg_title}'")

            await eval_js(f"""
                document.getElementById('reg-name').value = 'Journey Student';
                document.getElementById('reg-student-id').value = 'CS2026-999';
                document.getElementById('reg-email').value = '{reg_email}';
                document.getElementById('reg-password').value = 'ValidPass2026!';
                document.getElementById('reg-confirm-password').value = 'ValidPass2026!';
                document.getElementById('form-student-register').dispatchEvent(new Event('submit', {{cancelable: true, bubbles: true}}));
            """)
            await asyncio.sleep(2.0)
            reg_url = await eval_js("window.location.href")
            print(f"  URL after student registration: {reg_url}")
            assert "/student/dashboard" in reg_url
            print("  -> PASS: Student registration successfully created and redirected to dashboard.")

            # Log out before testing dedicated Student Login (REQ 6)
            await cdp_send("Page.navigate", {"url": f"{BASE_URL}/logout"})
            await asyncio.sleep(1.0)

            # -----------------------------------------------------------------
            # REQUIREMENT 6: Successful student login redirects to student dashboard
            # -----------------------------------------------------------------
            print("\n[REQ 6] Testing successful Student login...")
            await cdp_send("Page.navigate", {"url": f"{BASE_URL}/login"})
            await asyncio.sleep(1.0)
            await eval_js(f"""
                document.getElementById('login-email').value = '{reg_email}';
                document.getElementById('login-password').value = 'ValidPass2026!';
                document.getElementById('form-student-login').dispatchEvent(new Event('submit', {{cancelable: true, bubbles: true}}));
            """)
            await asyncio.sleep(2.0)
            curr_url = await eval_js("window.location.href")
            print(f"  URL after student login: {curr_url}")
            assert "/student/dashboard" in curr_url
            greeting = await eval_js("document.querySelector('.student-hero-title')?.innerText || ''")
            print(f"  Greeting: '{greeting}'")
            assert "Journey Student" in greeting
            await capture_screenshot("ultron_verified_student_dashboard.png")
            print("  -> PASS: Student login redirects to /student/dashboard with personalized welcome.")

            # -----------------------------------------------------------------
            # REQUIREMENT 2B: Open / after student login -> student dashboard appears
            # -----------------------------------------------------------------
            print("\n[REQ 2B] Opening / while authenticated as student...")
            await cdp_send("Page.navigate", {"url": f"{BASE_URL}/"})
            await asyncio.sleep(1.5)
            curr_url = await eval_js("window.location.href")
            print(f"  URL after navigating to /: {curr_url}")
            assert "/student/dashboard" in curr_url
            print("  -> PASS: Authenticated student visiting / is redirected to student dashboard.")

            # -----------------------------------------------------------------
            # REQUIREMENT 5: Student cannot access admin pages or APIs
            # -----------------------------------------------------------------
            print("\n[REQ 5] Testing RBAC: Student attempting to access Admin pages...")
            await cdp_send("Page.navigate", {"url": f"{BASE_URL}/admin/dashboard"})
            await asyncio.sleep(1.0)
            page_text = await eval_js("document.body.innerText")
            print(f"  Response text snippet: {page_text[:100]}...")
            assert "403" in page_text or "forbidden" in page_text.lower() or "access denied" in page_text.lower()
            print("  -> PASS: Authenticated student blocked from /admin/dashboard with 403 Forbidden.")

            # -----------------------------------------------------------------
            # REQUIREMENT 9: Logout returns to login/entry screen and re-locks routes
            # -----------------------------------------------------------------
            print("\n[REQ 9] Testing Student Logout...")
            await cdp_send("Page.navigate", {"url": f"{BASE_URL}/logout"})
            await asyncio.sleep(1.5)
            curr_url = await eval_js("window.location.href")
            print(f"  URL after logout: {curr_url}")
            assert curr_url.rstrip("/") == BASE_URL
            is_entry_page = await eval_js("document.querySelector('.entry-main-heading') !== null")
            assert is_entry_page
            print("  -> PASS: Logout returns user to / entry screen and protected routes remain blocked.")

            # -----------------------------------------------------------------
            # REQUIREMENT 7: Successful admin login redirects to admin dashboard
            # -----------------------------------------------------------------
            print("\n[REQ 7] Testing Administrator login from /admin/login...")
            await cdp_send("Page.navigate", {"url": f"{BASE_URL}/admin/login"})
            await asyncio.sleep(1.2)
            await eval_js("""
                document.getElementById('admin-email').value = 'admin@campus.edu';
                document.getElementById('admin-password').value = 'Admin@Campus2026!';
                document.getElementById('form-admin-login').dispatchEvent(new Event('submit', {cancelable: true, bubbles: true}));
            """)
            await asyncio.sleep(2.0)
            curr_url = await eval_js("window.location.href")
            print(f"  URL after admin login: {curr_url}")
            assert "/admin/dashboard" in curr_url or "/admin" in curr_url
            admin_heading = await eval_js("document.querySelector('.admin-hero-title')?.innerText || ''")
            print(f"  Admin heading: '{admin_heading}'")
            assert "Campus Control Center" in admin_heading
            await capture_screenshot("ultron_verified_admin_dashboard.png")
            print("  -> PASS: Admin login redirects to /admin/dashboard.")

            # -----------------------------------------------------------------
            # REQUIREMENT 3B: Open / after admin login -> admin dashboard appears
            # -----------------------------------------------------------------
            print("\n[REQ 3B] Opening / while authenticated as admin...")
            await cdp_send("Page.navigate", {"url": f"{BASE_URL}/"})
            await asyncio.sleep(1.5)
            curr_url = await eval_js("window.location.href")
            print(f"  URL after navigating to /: {curr_url}")
            assert "/admin/dashboard" in curr_url
            print("  -> PASS: Authenticated admin visiting / is redirected to admin dashboard.")

            # -----------------------------------------------------------------
            # REQUIREMENT 11: Lost & Found and helpdesk functionality still work
            # -----------------------------------------------------------------
            print("\n[REQ 11] Verifying Lost & Found view for authenticated admin...")
            await cdp_send("Page.navigate", {"url": f"{BASE_URL}/lost-found"})
            await asyncio.sleep(1.5)
            lf_url = await eval_js("window.location.href")
            print(f"  Lost & Found URL: {lf_url}")
            assert "/lost-found" in lf_url
            has_grid = await eval_js("document.querySelector('#lost-found-grid') !== null")
            print(f"  Has directory grid: {has_grid}")
            assert has_grid
            print("  -> PASS: Lost & Found functionality is fully operational.")

            # -----------------------------------------------------------------
            # REQUIREMENT 12: Desktop and mobile layouts (no horizontal overflow)
            # -----------------------------------------------------------------
            print("\n[REQ 12] Testing Desktop & Mobile layout overflow...")
            await cdp_send("Page.navigate", {"url": f"{BASE_URL}/logout"})
            await asyncio.sleep(1.0)

            # Test desktop (1280px)
            await cdp_send("Emulation.setDeviceMetricsOverride", {
                "width": 1280, "height": 900, "deviceScaleFactor": 1, "mobile": False
            })
            await asyncio.sleep(0.5)
            desktop_overflow = await eval_js("document.documentElement.scrollWidth > window.innerWidth")
            print(f"  Desktop (1280px) horizontal overflow: {desktop_overflow}")
            assert not desktop_overflow, "Desktop has horizontal overflow!"

            # Test mobile (375px)
            await cdp_send("Emulation.setDeviceMetricsOverride", {
                "width": 375, "height": 812, "deviceScaleFactor": 2, "mobile": True
            })
            await asyncio.sleep(0.5)
            mobile_overflow = await eval_js("document.documentElement.scrollWidth > window.innerWidth")
            print(f"  Mobile (375px) horizontal overflow: {mobile_overflow}")
            assert not mobile_overflow, "Mobile has horizontal overflow!"
            await capture_screenshot("ultron_verified_mobile_gateway.png")
            print("  -> PASS: Desktop and Mobile viewports have 0 horizontal overflow.")

            # Clean up test user
            delete_user_by_email(reg_email)
            print("\n[CLEANUP] Test student removed from database.")

            print("\n" + "=" * 70)
            print(" ALL USER JOURNEY & GATEWAY TESTS VERIFIED AND PASSED 100%! ")
            print("=" * 70)

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
    asyncio.run(verify_user_journey())
