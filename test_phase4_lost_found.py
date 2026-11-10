"""
Automated Test Suite for Phase 4:
Complete Lost & Found Functionality in CampusConnect.

Verifies:
1. Valid 'Lost' item creation via POST /api/lost-found -> HTTP 201
2. Valid 'Found' item creation via POST /api/lost-found -> HTTP 201
3. Missing required fields validation -> HTTP 400
4. Invalid email format validation -> HTTP 400
5. Invalid item_type validation -> HTTP 400
6. Direct SQLite database persistence verification
7. Public listing endpoint GET /api/lost-found:
   - Verifies items are returned
   - Strict privacy check: contact_email and contact_phone are NOT exposed in public listing
8. Keyword search endpoint GET /api/lost-found?q=...
9. Filtering by item_type (Lost / Found)
10. Filtering by category
11. Single item view GET /api/lost-found/<id> -> HTTP 200 with masked contact details
12. Single item view 404 handling for non-existent IDs
13. Safe cleanup of test records from SQLite database
14. Isolated temporary database test
"""

import sys
import os
import json
import sqlite3
import urllib.request
import urllib.error
import tempfile
from typing import Any, Dict, List, Tuple

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

BASE_URL = "http://127.0.0.1:5000"
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'campus_connect.db')

def request_json(path: str, method: str = "GET", payload: Any = None) -> Tuple[int, Any]:
    url = f"{BASE_URL}{path}"
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    data = json.dumps(payload).encode('utf-8') if payload is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            body = resp.read().decode('utf-8')
            return resp.status, json.loads(body)
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8')
        try:
            parsed = json.loads(body)
        except Exception:
            parsed = {"raw": body}
        return e.code, parsed

def run_tests():
    print("=" * 65)
    print(" Running Phase 4 Lost & Found Backend & Database Test Suite")
    print("=" * 65)

    created_ids = []

    try:
        # [TEST 1] Missing required fields validation
        print("\n[TEST 1] Missing required fields validation...")
        status, res = request_json("/api/lost-found", method="POST", payload={
            "item_name": "Lost Wallet"
            # Missing item_type, category, location, contact_name, contact_email, description
        })
        assert status == 400, f"Expected 400, got {status}: {res}"
        assert res.get('status') == 'error'
        print(f" PASS: Rejected with HTTP {status}: {res.get('message')}")

        # [TEST 2] Invalid email format validation
        print("\n[TEST 2] Invalid email format validation...")
        status, res = request_json("/api/lost-found", method="POST", payload={
            "item_type": "Lost",
            "item_name": "Casio Calculator",
            "category": "Electronics",
            "location": "Library Floor 1",
            "contact_name": "Test Student",
            "contact_email": "not-an-email",
            "description": "Black calculator with silver buttons"
        })
        assert status == 400, f"Expected 400, got {status}: {res}"
        assert "email" in res.get('message', '').lower()
        print(f" PASS: Invalid email rejected with HTTP {status}: {res.get('message')}")

        # [TEST 3] Invalid item_type validation
        print("\n[TEST 3] Invalid item_type validation...")
        status, res = request_json("/api/lost-found", method="POST", payload={
            "item_type": "Misplaced", # Invalid, must be Lost or Found
            "item_name": "USB Flash Drive",
            "category": "Electronics",
            "location": "Lab 3",
            "contact_name": "Test Student",
            "contact_email": "test@campus.edu",
            "description": "32GB SanDisk drive"
        })
        assert status == 400, f"Expected 400, got {status}: {res}"
        assert "lost" in res.get('message', '').lower() or "found" in res.get('message', '').lower()
        print(f" PASS: Invalid item_type rejected with HTTP {status}: {res.get('message')}")

        # [TEST 4] Valid 'Lost' item submission
        print("\n[TEST 4] Valid 'Lost' item creation via POST /api/lost-found...")
        lost_payload = {
            "item_type": "Lost",
            "item_name": "Grey HP Laptop Charger 65W",
            "category": "Electronics",
            "location": "Mechanical Seminar Hall",
            "date_reported": "2026-10-23",
            "contact_name": "Pooja Hegde",
            "contact_email": "pooja.h@campus.edu",
            "contact_phone": "+91 98765 22334",
            "description": "Type-C connector with red cable tie attached near the adapter."
        }
        status, res = request_json("/api/lost-found", method="POST", payload=lost_payload)
        assert status == 201, f"Expected 201, got {status}: {res}"
        assert res.get('status') == 'success'
        lost_item = res.get('item', {})
        lost_id = lost_item.get('id')
        assert lost_id is not None, "Missing item ID in response!"
        created_ids.append(lost_id)
        print(f" PASS: Created Lost item #{lost_id}: '{lost_item.get('item_name')}'")

        # [TEST 5] Valid 'Found' item submission
        print("\n[TEST 5] Valid 'Found' item creation via POST /api/lost-found...")
        found_payload = {
            "item_type": "Found",
            "item_name": "Parker Matte Black Ballpoint Pen",
            "category": "General",
            "location": "Classroom 108, Row 3",
            "date_reported": "2026-10-23",
            "contact_name": "Campus Security Officer",
            "contact_email": "security@campus.edu",
            "contact_phone": "Ext: 104",
            "description": "Metal pen with silver clip found on desk after mathematics lecture."
        }
        status, res = request_json("/api/lost-found", method="POST", payload=found_payload)
        assert status == 201, f"Expected 201, got {status}: {res}"
        assert res.get('status') == 'success'
        found_item = res.get('item', {})
        found_id = found_item.get('id')
        assert found_id is not None, "Missing item ID in response!"
        created_ids.append(found_id)
        print(f" PASS: Created Found item #{found_id}: '{found_item.get('item_name')}'")

        # [TEST 6] Verify direct SQLite database persistence
        print("\n[TEST 6] Verifying SQLite database persistence...")
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM lost_found_items WHERE id = ?", (lost_id,))
        row = cursor.fetchone()
        assert row is not None, f"Item #{lost_id} not found in database!"
        assert row['item_name'] == lost_payload['item_name']
        assert row['item_type'] == 'Lost'
        assert row['category'] == 'Electronics'
        assert row['contact_name'] == lost_payload['contact_name']
        print(f" PASS: Item #{lost_id} successfully verified in SQLite table `lost_found_items`.")
        conn.close()

        # [TEST 7] Public listing privacy check (Requirement 7)
        print("\n[TEST 7] Public listing privacy verification (contact email/phone NEVER exposed)...")
        status, res = request_json("/api/lost-found", method="GET")
        assert status == 200, f"Expected 200, got {status}: {res}"
        items: List[Dict[str, Any]] = res.get('items', [])
        assert len(items) >= 2, "Expected at least 2 items in listing"
        for it in items:
            assert 'contact_email' not in it, f"PRIVACY VIOLATION: contact_email was exposed in public listing for item #{it.get('id')}!"
            assert 'contact_phone' not in it, f"PRIVACY VIOLATION: contact_phone was exposed in public listing for item #{it.get('id')}!"
        print(f" PASS: All {len(items)} items in public listing strictly omit private contact details.")

        # [TEST 8] Search keyword filtering
        print("\n[TEST 8] Testing keyword search (q=Charger)...")
        status, res = request_json("/api/lost-found?q=Charger", method="GET")
        assert status == 200, f"Expected 200, got {status}: {res}"
        search_items: List[Dict[str, Any]] = res.get('items', [])
        assert any(it['id'] == lost_id for it in search_items), "Search for 'Charger' did not return the created lost item!"
        print(f" PASS: Search for 'Charger' returned {len(search_items)} item(s) including #{lost_id}.")

        # [TEST 9] Filter by item_type ('Lost' vs 'Found')
        print("\n[TEST 9] Testing filter by item_type (type=Lost)...")
        status, res = request_json("/api/lost-found?type=Lost", method="GET")
        assert status == 200, f"Expected 200, got {status}: {res}"
        lost_only: List[Dict[str, Any]] = res.get('items', [])
        assert all(it['item_type'] == 'Lost' for it in lost_only), "Non-Lost item found in type=Lost results!"
        assert any(it['id'] == lost_id for it in lost_only), f"Item #{lost_id} missing from type=Lost results!"
        print(f" PASS: Filter type=Lost returned {len(lost_only)} Lost items exclusively.")

        # [TEST 10] Filter by category ('Electronics')
        print("\n[TEST 10] Testing filter by category (category=Electronics)...")
        status, res = request_json("/api/lost-found?category=Electronics", method="GET")
        assert status == 200, f"Expected 200, got {status}: {res}"
        elec_items: List[Dict[str, Any]] = res.get('items', [])
        assert all(it['category'] == 'Electronics' for it in elec_items), "Non-Electronics item found in category=Electronics results!"
        print(f" PASS: Filter category=Electronics returned {len(elec_items)} matching items.")

        # [TEST 11] Single item view with masked contact details
        print(f"\n[TEST 11] Testing single item view GET /api/lost-found/{lost_id}...")
        status, res = request_json(f"/api/lost-found/{lost_id}", method="GET")
        assert status == 200, f"Expected 200, got {status}: {res}"
        item_view: Dict[str, Any] = res.get('item', {})
        assert item_view.get('id') == lost_id
        # Check that contact details are present but masked
        masked_email = item_view.get('contact_email', '')
        assert '*' in masked_email, f"Email was not masked for privacy: {masked_email}"
        print(f" PASS: Single item view returned HTTP 200 with masked email: '{masked_email}'")

        # [TEST 12] Single item 404 test for non-existent item
        print("\n[TEST 12] Testing single item view for non-existent ID (99999)...")
        status, res = request_json("/api/lost-found/99999", method="GET")
        assert status == 404, f"Expected 404, got {status}: {res}"
        print(f" PASS: Non-existent item returned HTTP {status}: {res.get('message')}")

    finally:
        # [TEST 13] Safe cleanup of test records
        print("\n[TEST 13] Safely cleaning up test records from SQLite database...")
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        for cid in created_ids:
            cursor.execute("DELETE FROM lost_found_items WHERE id = ?", (cid,))
        conn.commit()
        for cid in created_ids:
            cursor.execute("SELECT 1 FROM lost_found_items WHERE id = ?", (cid,))
            assert cursor.fetchone() is None, f"Item #{cid} was not cleaned up!"
        conn.close()
        print(f" PASS: Cleaned up {len(created_ids)} test records. SQLite database is pristine.")

    # [TEST 14] Isolated temporary database test
    print("\n[TEST 14] Running isolated temporary database test...")
    import database
    tmp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False).name
    orig_path = database.DATABASE_PATH
    try:
        database.DATABASE_PATH = tmp_db
        database.init_db()
        item = database.create_lost_found_item(
            item_type='Lost',
            item_name='Test Temp Item',
            category='Keys',
            location='Main Gate',
            date_reported='2026-10-23',
            description='Room 12 key with red tag',
            contact_name='Temp User',
            contact_email='temp@campus.edu'
        )
        assert item is not None and item['id'] == 1
        fetched = database.get_lost_found_items(item_type='Lost')
        assert len(fetched) == 1 and fetched[0]['item_name'] == 'Test Temp Item'
        print(" PASS: Isolated temporary database operations verified successfully.")
    finally:
        database.DATABASE_PATH = orig_path
        if os.path.exists(tmp_db):
            os.remove(tmp_db)

    print("\n" + "=" * 65)
    print(" ALL 14 PHASE 4 BACKEND & DATABASE TESTS PASSED 100%! ")
    print("=" * 65)

if __name__ == '__main__':
    run_tests()
