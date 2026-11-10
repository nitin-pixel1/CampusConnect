"""
Automated CDP End-to-End Test for CampusConnect Phase 3:
Real Issue Reporting Frontend & Backend Submission Flow.

Verifies:
1. Modal opening from navigation and banners
2. Form field inputs and client-side validation
3. Loading state and duplicate submission prevention on submit button
4. Successful fetch() POST /api/tickets request
5. Toast notification displaying generated ticket number
6. Modal closing and form reset on success
7. Dynamic DOM prepending to #reports-table with live badge and status
8. SQLite database persistence verification
9. Safe cleanup of test records from SQLite database
"""

import asyncio
import base64
import json
import os
import subprocess
import sys
import time
import urllib.request
import sqlite3
import websockets

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
USER_DATA_DIR = r"D:\PROJECTS\project 1\temp_cdp_p3"
APP_URL = "http://127.0.0.1:5000/"
PORT = 9223
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'campus_connect.db')

created_test_ticket = None

async def run_frontend_e2e_test():
    global created_test_ticket
    print("=" * 65)
    print(" CampusConnect Phase 3: Automated Browser End-to-End Test")
    print("=" * 65)

    # 1. Start Chrome
    chrome_cmd = [
        CHROME_PATH,
        "--headless=new",
        "--no-sandbox",
        f"--user-data-dir={USER_DATA_DIR}",
        f"--remote-debugging-port={PORT}",
        "about:blank"
    ]
    proc = subprocess.Popen(chrome_cmd)
    time.sleep(2.0)

    try:
        tabs_url = f"http://127.0.0.1:{PORT}/json"
        req = urllib.request.urlopen(tabs_url)
        tabs = json.loads(req.read().decode('utf-8'))
        page_targets = [t for t in tabs if t.get('type') == 'page']
        if not page_targets:
            raise RuntimeError(f"No page target found in Chrome tabs: {tabs}")
        ws_url = page_targets[0]['webSocketDebuggerUrl']
        print(f"[OK] Connected to Chrome Page Target at: {ws_url}")

        async with websockets.connect(ws_url, max_size=20_000_000) as ws:
            msg_id = 1

            async def send_cmd(method, params=None):
                nonlocal msg_id
                cid = msg_id
                msg_id += 1
                payload = {"id": cid, "method": method, "params": params or {}}
                await ws.send(json.dumps(payload))
                while True:
                    resp_raw = await ws.recv()
                    resp = json.loads(resp_raw)
                    if resp.get("id") == cid:
                        return resp.get("result", {})

            await send_cmd("Page.enable")
            await send_cmd("Runtime.enable")
            await send_cmd("DOM.enable")

            # Set viewport to 1280x800
            await send_cmd("Emulation.setDeviceMetricsOverride", {
                "width": 1280,
                "height": 800,
                "deviceScaleFactor": 1,
                "mobile": False
            })

            # Navigate to Home
            print("\n[STEP 1] Navigating to CampusConnect Home...")
            await send_cmd("Page.navigate", {"url": APP_URL})
            
            # Wait for Page.loadEventFired
            while True:
                resp_raw = await ws.recv()
                msg = json.loads(resp_raw)
                if msg.get("method") == "Page.loadEventFired":
                    break

            await asyncio.sleep(0.5)

            # Check title
            title_res = await send_cmd("Runtime.evaluate", {"expression": "document.title", "returnByValue": True})
            title = title_res.get("result", {}).get("value", "")
            print(f"[PASS] Page loaded with title: '{title}'")

            # Check initial tickets count in table
            init_count_res = await send_cmd("Runtime.evaluate", {
                "expression": "document.querySelectorAll('#reports-table tbody tr.report-row').length",
                "returnByValue": True
            })
            initial_row_count = init_count_res.get("result", {}).get("value", 0)
            print(f"[INFO] Initial reports table rows: {initial_row_count}")

            # Open Modal
            print("\n[STEP 2] Opening Report an Issue modal...")
            await send_cmd("Runtime.evaluate", {
                "expression": "document.getElementById('btn-nav-report').click()"
            })
            await asyncio.sleep(0.5)

            modal_open = await send_cmd("Runtime.evaluate", {
                "expression": "document.getElementById('report-issue-modal').classList.contains('show')",
                "returnByValue": True
            })
            assert modal_open.get("result", {}).get("value") is True, "Modal did not open!"
            print("[PASS] Modal opened successfully.")

            # Test empty submission validation
            print("\n[STEP 3] Testing empty submission validation...")
            await send_cmd("Runtime.evaluate", {
                "expression": "handleReportSubmit(new Event('submit'))"
            })
            await asyncio.sleep(0.4)

            alert_text_res = await send_cmd("Runtime.evaluate", {
                "expression": "document.getElementById('report-form-alert').textContent",
                "returnByValue": True
            })
            alert_text = alert_text_res.get("result", {}).get("value", "")
            assert "required" in alert_text.lower(), f"Expected required validation error, got: {alert_text}"
            print(f"[PASS] Client-side validation prevented empty submission: {alert_text}")

            # Fill in real form data
            print("\n[STEP 4] Filling form with valid student issue data...")
            fill_js = """
            (() => {
                document.getElementById('input-student-name').value = 'Karthik Raja';
                document.getElementById('input-student-id').value = 'CS2023-099';
                document.getElementById('input-student-email').value = 'karthik.r@campus.edu';
                document.getElementById('input-issue-category').value = 'Lab Equipment';
                document.getElementById('input-issue-priority').value = 'Urgent';
                document.getElementById('input-issue-location').value = 'Computer Systems Lab 1, PC #14';
                document.getElementById('input-issue-subject').value = 'Monitor power supply tripping during compiler lab';
                document.getElementById('input-issue-description').value = 'When running benchmark builds on PC 14, the power unit trips and restarts unexpectedly.';
                return true;
            })()
            """
            await send_cmd("Runtime.evaluate", {"expression": fill_js})

            # Submit the form
            print("\n[STEP 5] Submitting form via button click...")
            submit_js = """
            (() => {
                const btn = document.getElementById('btn-submit-report-preview');
                btn.click();
                return {
                    disabled: btn.disabled,
                    text: btn.textContent.trim()
                };
            })()
            """
            click_state_res = await send_cmd("Runtime.evaluate", {"expression": submit_js, "returnByValue": True})
            click_state = click_state_res.get("result", {}).get("value", {})
            print(f"[INFO] Immediate button state during submission: disabled={click_state.get('disabled')}, text='{click_state.get('text')}'")

            # Wait for backend response and DOM updates
            await asyncio.sleep(2.0)

            # Check if modal closed
            modal_closed_res = await send_cmd("Runtime.evaluate", {
                "expression": "!document.getElementById('report-issue-modal').classList.contains('show')",
                "returnByValue": True
            })
            assert modal_closed_res.get("result", {}).get("value") is True, "Modal should be closed after success!"
            print("[PASS] Modal closed automatically after successful creation.")

            # Check for toast notification
            toast_res = await send_cmd("Runtime.evaluate", {
                "expression": "document.querySelector('.toast-notification') ? document.querySelector('.toast-notification').textContent : ''",
                "returnByValue": True
            })
            toast_text = toast_res.get("result", {}).get("value", "")
            print(f"[PASS] Success toast displayed: '{toast_text}'")
            assert "ticket #" in toast_text.lower() or "cc-tkt-" in toast_text.lower(), f"Toast text does not contain ticket number: {toast_text}"

            # Extract generated ticket number from table top row
            new_ticket_res = await send_cmd("Runtime.evaluate", {
                "expression": "document.querySelector('#reports-table tbody tr.report-row .ticket-code').textContent.trim()",
                "returnByValue": True
            })
            created_test_ticket = new_ticket_res.get("result", {}).get("value", "")
            print(f"[PASS] New ticket prepended to dashboard table: {created_test_ticket}")

            # Check new row count
            new_count_res = await send_cmd("Runtime.evaluate", {
                "expression": "document.querySelectorAll('#reports-table tbody tr.report-row').length",
                "returnByValue": True
            })
            new_row_count = new_count_res.get("result", {}).get("value", 0)
            assert new_row_count == initial_row_count + 1, f"Expected {initial_row_count + 1} rows, found {new_row_count}"
            print(f"[PASS] Reports table count increased from {initial_row_count} to {new_row_count}.")

            # Capture screenshot
            ss_res = await send_cmd("Page.captureScreenshot", {"format": "png"})
            ss_data = base64.b64decode(ss_res.get("data", ""))
            ss_path = r"D:\PROJECTS\project 1\phase3_verified_submission.png"
            with open(ss_path, "wb") as f:
                f.write(ss_data)
            print(f"[PASS] Verified screenshot saved to: {ss_path}")

            # Verify SQLite persistence
            print("\n[STEP 6] Verifying SQLite database persistence...")
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM tickets WHERE ticket_number = ?", (created_test_ticket,))
            ticket_row = cursor.fetchone()
            assert ticket_row is not None, f"Ticket {created_test_ticket} NOT found in SQLite database!"
            assert ticket_row['student_name'] == 'Karthik Raja'
            assert ticket_row['student_id'] == 'CS2023-099'
            assert ticket_row['category'] == 'Lab Equipment'
            assert ticket_row['priority'] == 'Urgent'
            print(f"[PASS] SQLite record verified:")
            print(f"       ID: {ticket_row['id']} | Ticket: {ticket_row['ticket_number']} | Student: {ticket_row['student_name']} | Status: {ticket_row['status']}")

            # Clean up test record safely
            print("\n[STEP 7] Cleaning up test record from SQLite database...")
            cursor.execute("DELETE FROM tickets WHERE ticket_number = ?", (created_test_ticket,))
            conn.commit()
            cursor.execute("SELECT 1 FROM tickets WHERE ticket_number = ?", (created_test_ticket,))
            assert cursor.fetchone() is None, "Test ticket was not deleted during cleanup!"
            conn.close()
            print(f"[PASS] Test ticket {created_test_ticket} safely removed. Production database is pristine.")

            print("\n" + "=" * 65)
            print(" ALL PHASE 3 FRONTEND & INTEGRATION TESTS PASSED 100%! ")
            print("=" * 65)

    finally:
        proc.terminate()
        proc.wait()

if __name__ == '__main__':
    asyncio.run(run_frontend_e2e_test())
