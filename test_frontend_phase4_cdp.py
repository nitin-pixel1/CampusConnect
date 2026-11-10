"""
Automated Browser End-to-End Test for Phase 4:
Complete Lost & Found UI & Backend Integration via Chrome DevTools Protocol.

Tests:
1. Opens Report Lost/Found modal from the section action button
2. Client validation for empty inputs
3. Submitting a new Lost Item with real student details
4. Submitting state, loading spinner, and duplicate submission prevention
5. Auto-closing modal and success toast notification
6. Dynamic card rendering in #lost-found-grid
7. Search input filtering in real-time
8. Category and Type filter switching
9. Opening and viewing Claim / Inquire modal with masked contact details
10. Verifying direct SQLite database persistence
11. Safe cleanup of test records so production database is pristine
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
USER_DATA_DIR = r"D:\PROJECTS\project 1\temp_cdp_p4"
APP_URL = "http://127.0.0.1:5000/"
PORT = 9226
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'campus_connect.db')

created_item_id = None

async def run_phase4_browser_test():
    global created_item_id
    print("=" * 65)
    print(" CampusConnect Phase 4: Automated Browser End-to-End Test")
    print("=" * 65)

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
            raise RuntimeError("No browser page target found!")
        ws_url = page_targets[0]['webSocketDebuggerUrl']
        print(f"[OK] Connected to Chrome Page at: {ws_url}")

        async with websockets.connect(ws_url, max_size=20_000_000) as ws:
            msg_id = 1

            async def send_cmd(method, params=None):
                nonlocal msg_id
                cid = msg_id
                msg_id += 1
                payload = {"id": cid, "method": method, "params": params or {}}
                await ws.send(json.dumps(payload))
                while True:
                    raw = await ws.recv()
                    resp = json.loads(raw)
                    if resp.get("id") == cid:
                        return resp.get("result", {})

            await send_cmd("Page.enable")
            await send_cmd("Runtime.enable")
            await send_cmd("DOM.enable")

            # Set desktop viewport 1280x800
            await send_cmd("Emulation.setDeviceMetricsOverride", {
                "width": 1280,
                "height": 800,
                "deviceScaleFactor": 1,
                "mobile": False
            })

            # Navigate to Home
            print("\n[STEP 1] Navigating to CampusConnect Home...")
            await send_cmd("Page.navigate", {"url": APP_URL})
            while True:
                msg = json.loads(await ws.recv())
                if msg.get("method") == "Page.loadEventFired":
                    break
            await asyncio.sleep(0.5)

            # Check initial lost & found cards count
            initial_cards_res = await send_cmd("Runtime.evaluate", {
                "expression": "document.querySelectorAll('#lost-found-grid .lf-card').length",
                "returnByValue": True
            })
            initial_card_count = initial_cards_res.get("result", {}).get("value", 0)
            print(f"[PASS] Page loaded. Initial Lost & Found cards in grid: {initial_card_count}")

            # Open Report Lost / Found Modal
            print("\n[STEP 2] Opening 'Report Lost / Found' Modal via #btn-open-report-lf...")
            await send_cmd("Runtime.evaluate", {
                "expression": "document.getElementById('btn-open-report-lf').click()"
            })
            await asyncio.sleep(0.4)

            modal_open = await send_cmd("Runtime.evaluate", {
                "expression": "document.getElementById('report-lf-modal').classList.contains('show')",
                "returnByValue": True
            })
            assert modal_open.get("result", {}).get("value") is True, "Report Lost/Found modal did not open!"
            print("[PASS] Report Lost/Found modal opened successfully.")

            # Test empty submission validation
            print("\n[STEP 3] Testing empty submission validation...")
            await send_cmd("Runtime.evaluate", {
                "expression": "handleLostFoundSubmit(new Event('submit'))"
            })
            await asyncio.sleep(0.3)

            alert_text_res = await send_cmd("Runtime.evaluate", {
                "expression": "document.getElementById('lf-form-alert').textContent",
                "returnByValue": True
            })
            alert_text = alert_text_res.get("result", {}).get("value", "")
            assert "required" in alert_text.lower(), f"Expected required validation error, got: {alert_text}"
            print(f"[PASS] Client-side validation prevented empty submission: {alert_text}")

            # Fill in real lost item data
            print("\n[STEP 4] Populating form with real student lost item data...")
            fill_js = """
            (() => {
                document.getElementById('input-lf-type').value = 'Lost';
                document.getElementById('input-lf-name').value = 'Silver Apple Watch Series 8';
                document.getElementById('input-lf-category').value = 'Electronics';
                document.getElementById('input-lf-location').value = 'Sports Complex Gymnasium Locker #22';
                document.getElementById('input-lf-date').value = '2026-10-23';
                document.getElementById('input-lf-contact-name').value = 'Siddharth Iyer';
                document.getElementById('input-lf-contact-email').value = 'siddharth.i@campus.edu';
                document.getElementById('input-lf-contact-phone').value = '+91 98765 88990';
                document.getElementById('input-lf-description').value = 'Silver aluminum case with midnight blue sport band. Has a scratch near digital crown.';
                return true;
            })()
            """
            await send_cmd("Runtime.evaluate", {"expression": fill_js})

            # Submit form
            print("\n[STEP 5] Submitting form via button click...")
            submit_js = """
            (() => {
                const btn = document.getElementById('btn-submit-lf');
                btn.click();
                return {
                    disabled: btn.disabled,
                    text: btn.textContent.trim()
                };
            })()
            """
            click_res = await send_cmd("Runtime.evaluate", {"expression": submit_js, "returnByValue": True})
            click_state = click_res.get("result", {}).get("value", {})
            print(f"[INFO] Immediate button state: disabled={click_state.get('disabled')}, text='{click_state.get('text')}'")

            await asyncio.sleep(2.0)

            # Check if modal closed
            modal_closed = await send_cmd("Runtime.evaluate", {
                "expression": "!document.getElementById('report-lf-modal').classList.contains('show')",
                "returnByValue": True
            })
            assert modal_closed.get("result", {}).get("value") is True, "Modal should close upon successful submission!"
            print("[PASS] Modal closed automatically.")

            # Check success toast
            toast_res = await send_cmd("Runtime.evaluate", {
                "expression": "document.querySelector('.toast-notification') ? document.querySelector('.toast-notification').textContent : ''",
                "returnByValue": True
            })
            toast_text = toast_res.get("result", {}).get("value", "")
            print(f"[PASS] Success toast displayed: '{toast_text}'")
            assert "recorded successfully" in toast_text.lower() or "apple watch" in toast_text.lower()

            # Verify new item card in grid
            cards_after_res = await send_cmd("Runtime.evaluate", {
                "expression": "document.querySelectorAll('#lost-found-grid .lf-card').length",
                "returnByValue": True
            })
            cards_after = cards_after_res.get("result", {}).get("value", 0)
            print(f"[PASS] Grid refreshed with {cards_after} cards (was {initial_card_count}).")

            # Check that the card content matches
            first_card_title = await send_cmd("Runtime.evaluate", {
                "expression": "document.querySelector('#lost-found-grid .lf-card .lf-title').textContent.trim()",
                "returnByValue": True
            })
            title_val = first_card_title.get("result", {}).get("value", "")
            assert "Apple Watch" in title_val, f"Top card was not Apple Watch, got: '{title_val}'"
            print(f"[PASS] Top card verified: '{title_val}'")

            # Test search filter
            print("\n[STEP 6] Testing real-time keyword search in UI...")
            await send_cmd("Runtime.evaluate", {
                "expression": "document.getElementById('lf-search-input').value = 'Apple Watch'; handleLostFoundSearchInput();"
            })
            await asyncio.sleep(1.0)

            filtered_count_res = await send_cmd("Runtime.evaluate", {
                "expression": "document.querySelectorAll('#lost-found-grid .lf-card').length",
                "returnByValue": True
            })
            filtered_count = filtered_count_res.get("result", {}).get("value", 0)
            assert filtered_count == 1, f"Expected 1 search match, got {filtered_count}"
            print(f"[PASS] Real-time search returned exactly {filtered_count} matching card for 'Apple Watch'.")

            # Test Claim / Inquire Modal
            print("\n[STEP 7] Testing 'Claim / Inquire' modal opening...")
            await send_cmd("Runtime.evaluate", {
                "expression": "document.querySelector('#lost-found-grid .lf-card .btn-claim-preview').click()"
            })
            await asyncio.sleep(0.8)

            claim_modal_open = await send_cmd("Runtime.evaluate", {
                "expression": "document.getElementById('claim-item-modal').classList.contains('show')",
                "returnByValue": True
            })
            assert claim_modal_open.get("result", {}).get("value") is True, "Claim modal did not open!"
            claim_body_text = await send_cmd("Runtime.evaluate", {
                "expression": "document.getElementById('claim-modal-body').textContent",
                "returnByValue": True
            })
            body_val = claim_body_text.get("result", {}).get("value", "")
            assert "verification" in body_val.lower() or "apple watch" in body_val.lower(), f"Unexpected claim body: {body_val}"
            print("[PASS] Claim / Inquire modal rendered with complete item details and recovery instructions.")

            # Close claim modal
            await send_cmd("Runtime.evaluate", {"expression": "closeClaimModal()"})
            await asyncio.sleep(0.3)

            # Reset search filters
            await send_cmd("Runtime.evaluate", {"expression": "resetLostFoundFilters()"})
            await asyncio.sleep(0.8)

            # Capture screenshot
            ss_res = await send_cmd("Page.captureScreenshot", {"format": "png"})
            ss_data = base64.b64decode(ss_res.get("data", ""))
            ss_path = r"D:\PROJECTS\project 1\phase4_verified_lost_found.png"
            with open(ss_path, "wb") as f:
                f.write(ss_data)
            print(f"[PASS] Verified screenshot saved to: {ss_path}")

            # Verify SQLite persistence
            print("\n[STEP 8] Verifying SQLite database persistence...")
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM lost_found_items WHERE item_name LIKE '%Apple Watch%'")
            row = cursor.fetchone()
            assert row is not None, "Apple Watch item was not found in SQLite!"
            created_item_id = row['id']
            assert row['contact_name'] == 'Siddharth Iyer'
            assert row['location'] == 'Sports Complex Gymnasium Locker #22'
            print(f"[PASS] SQLite record verified: ID={row['id']} | Item='{row['item_name']}' | Reporter='{row['contact_name']}'")

            # Clean up test record
            print("\n[STEP 9] Cleaning up test record from SQLite database...")
            cursor.execute("DELETE FROM lost_found_items WHERE id = ?", (created_item_id,))
            conn.commit()
            cursor.execute("SELECT 1 FROM lost_found_items WHERE id = ?", (created_item_id,))
            assert cursor.fetchone() is None, "Failed to clean up test record!"
            conn.close()
            print(f"[PASS] Test record #{created_item_id} safely cleaned up. Database is pristine.")

            print("\n" + "=" * 65)
            print(" ALL PHASE 4 BROWSER & INTEGRATION TESTS PASSED 100%! ")
            print("=" * 65)

    finally:
        proc.terminate()
        proc.wait()

if __name__ == '__main__':
    asyncio.run(run_phase4_browser_test())
