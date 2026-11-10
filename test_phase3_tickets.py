"""
Automated Integration and Backend Test Suite for Phase 3:
Real Issue Reporting in CampusConnect.

Tests:
1. POST /api/tickets with missing fields -> expects HTTP 400.
2. POST /api/tickets with invalid email -> expects HTTP 400.
3. POST /api/tickets with valid payload -> expects HTTP 201 and generated ticket number.
4. Verify database persistence in SQLite:
   - Queries SQLite directly to confirm ticket record exists with exact fields.
5. Safe Cleanup:
   - Removes test ticket from SQLite to keep database clean.
6. GET /api/tickets endpoint -> expects HTTP 200 and list of tickets.
7. Verification that /api/client-report diagnostic endpoint remains functional.
"""

import sys
import json
import urllib.request
import urllib.error
import sqlite3
import os

BASE_URL = "http://127.0.0.1:5000"
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'campus_connect.db')

def request_json(path, method="GET", payload=None):
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
    print("=" * 60)
    print(" Running Phase 3 Real Issue Reporting Test Suite")
    print("=" * 60)

    # 1. Test missing required fields
    print("\n[TEST 1] Missing required fields validation...")
    status, res = request_json("/api/tickets", method="POST", payload={
        "student_name": "Test Student",
        "student_id": "TEST-001"
        # missing email, category, subject, description
    })
    assert status == 400, f"Expected 400, got {status}: {res}"
    assert res.get('status') == 'error', f"Expected status error: {res}"
    print(f" PASS: Missing fields rejected with HTTP {status}: {res.get('message')}")

    # 2. Test invalid email format
    print("\n[TEST 2] Invalid email format validation...")
    status, res = request_json("/api/tickets", method="POST", payload={
        "student_name": "Test Student",
        "student_id": "TEST-001",
        "email": "invalid-email-string",
        "category": "Wi-Fi & IT",
        "subject": "Wi-Fi Issue in Lab",
        "description": "Connection drops constantly"
    })
    assert status == 400, f"Expected 400, got {status}: {res}"
    assert "email" in res.get('message', '').lower(), f"Expected email error message: {res}"
    print(f" PASS: Invalid email rejected with HTTP {status}: {res.get('message')}")

    # 3. Test valid ticket submission
    print("\n[TEST 3] Valid ticket submission...")
    test_payload = {
        "student_name": "Divya Krishnan",
        "student_id": "IT2024-055",
        "email": "divya.k@campus.edu",
        "category": "Wi-Fi & IT",
        "subject": "Frequent network timeout in Turing Lab",
        "description": "Ethernet switch port 8 experiences packet loss during coding practicals.",
        "location": "Turing Lab Room 302",
        "priority": "High"
    }
    status, res = request_json("/api/tickets", method="POST", payload=test_payload)
    assert status == 201, f"Expected 201, got {status}: {res}"
    assert res.get('status') == 'success', f"Expected success status: {res}"
    ticket_num = res.get('ticket_number')
    assert ticket_num and ticket_num.startswith("CC-TKT-"), f"Invalid ticket number generated: {ticket_num}"
    print(f" PASS: Valid ticket created with HTTP {status}. Generated Ticket: {ticket_num}")

    # 4. Verify database persistence in SQLite directly
    print("\n[TEST 4] Verifying direct SQLite database persistence...")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tickets WHERE ticket_number = ?", (ticket_num,))
    db_row = cursor.fetchone()
    assert db_row is not None, f"Ticket {ticket_num} was NOT found in SQLite database!"
    assert db_row['student_name'] == test_payload['student_name']
    assert db_row['student_id'] == test_payload['student_id']
    assert db_row['email'] == test_payload['email']
    assert db_row['category'] == test_payload['category']
    assert db_row['subject'] == test_payload['subject']
    assert db_row['priority'] == test_payload['priority']
    assert db_row['status'] == 'Pending'
    print(f" PASS: Ticket record verified in SQLite database.")
    print(f"       ID: {db_row['id']} | Ticket: {db_row['ticket_number']} | Student: {db_row['student_name']} | Status: {db_row['status']}")

    # 5. Clean up test record safely so no fake/test data is left in the DB
    print("\n[TEST 5] Safely cleaning up test record from database...")
    cursor.execute("DELETE FROM tickets WHERE ticket_number = ?", (ticket_num,))
    conn.commit()
    cursor.execute("SELECT 1 FROM tickets WHERE ticket_number = ?", (ticket_num,))
    assert cursor.fetchone() is None, "Failed to clean up test ticket record!"
    conn.close()
    print(f" PASS: Test ticket {ticket_num} safely cleaned up. Database is pristine.")

    # 6. Test GET /api/tickets
    print("\n[TEST 6] Testing GET /api/tickets endpoint...")
    status, res = request_json("/api/tickets", method="GET")
    assert status == 200, f"Expected 200, got {status}: {res}"
    assert 'tickets' in res and isinstance(res['tickets'], list)
    print(f" PASS: GET /api/tickets returned HTTP 200 with {res.get('count')} tickets.")

    # 7. Test /api/client-report preservation
    print("\n[TEST 7] Testing /api/client-report layout diagnostic endpoint...")
    status, res = request_json("/api/client-report", method="POST", payload={"test": True, "viewportWidth": 1280})
    assert status == 200, f"Expected 200, got {status}: {res}"
    assert res.get('status') == 'received'
    print(f" PASS: /api/client-report endpoint is intact and functional.")

    print("\n" + "=" * 60)
    print(" ALL 7 BACKEND & DATABASE TESTS PASSED SUCCESSFULLY! ")
    print("=" * 60)

if __name__ == '__main__':
    run_tests()
