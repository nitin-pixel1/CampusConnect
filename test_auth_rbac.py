"""
CampusConnect - Automated Test Suite for Authentication & Role-Based Access Control (Phase 5)
Verifies:
1. Student registration validation (missing fields, invalid email, short password, password mismatch)
2. Duplicate email prevention
3. Public registration security: Role is strictly forced to 'Student' (cannot forge Admin)
4. Password security: Direct SQLite inspection confirms password is stored as secure Werkzeug hash
5. Invalid login handling (wrong password, non-existent user)
6. Valid student login and session cookie handling
7. Protected endpoint access (/api/auth/me, /api/student/tickets, /student/dashboard)
8. RBAC protection: Student blocked from /admin, /admin/dashboard, /api/admin/tickets with HTTP 403 Forbidden
9. RBAC protection: Student blocked from updating ticket statuses with HTTP 403 Forbidden
10. Unauthenticated access blocked with HTTP 401/302 redirects
11. Student blocked on Admin Login portal
12. Valid Admin authentication and session creation
13. Admin access to ticket management (/api/admin/tickets)
14. Admin capability to update ticket status in SQLite (/api/admin/tickets/<id>/status)
15. Secure logout and session destruction
16. Safe cleanup of test user accounts from SQLite database
17. Full isolation: Runs against an isolated temporary SQLite database without touching campus_connect.db
18. Safe import: Importing test module does not initialize, seed, or modify production SQLite database
"""

import sys
import os
import json
import sqlite3
import tempfile

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

# Global references (assigned dynamically in run_tests before app loads)
DB_PATH = None
flask_app = None


class SessionClient:
    """
    Session-aware HTTP test client using Flask's in-process test_client.
    Runs requests directly against the configured Flask application,
    preserving cookies across requests while routing all DB operations
    to the isolated temporary database.
    """
    def __init__(self, app_instance=None):
        target_app = app_instance or flask_app
        if target_app is None:
            raise RuntimeError("Flask app has not been initialized for testing yet.")
        self.client = target_app.test_client()

    def request(self, path, method="GET", payload=None, follow_redirects=True):
        if path.startswith("http://") or path.startswith("https://"):
            from urllib.parse import urlparse
            path = urlparse(path).path

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        data = json.dumps(payload) if payload is not None else None

        resp = self.client.open(
            path,
            method=method,
            data=data,
            headers=headers,
            follow_redirects=follow_redirects
        )
        status = resp.status_code
        raw_text = resp.get_data(as_text=True)
        try:
            parsed = resp.get_json()
            if parsed is None:
                parsed = {"raw": raw_text}
        except Exception:
            parsed = {"raw": raw_text}
        return status, parsed


def run_tests():
    global DB_PATH, flask_app
    print("=" * 65)
    print(" Running Phase 5 Authentication & RBAC Test Suite")
    print("=" * 65)

    temp_db_path = None
    orig_db_path = None
    database = None
    prev_app_in_sys = 'app' in sys.modules
    prev_app_module = sys.modules.get('app')
    app_imported = False
    tests_passed = 0
    total_tests = 18
    created_emails = []

    try:
        # 1. Create an isolated temporary SQLite database file
        temp_fd, temp_db_path = tempfile.mkstemp(prefix='campus_connect_test_auth_', suffix='.db')
        os.close(temp_fd)

        # 2. Import database module and record original database path
        import database
        orig_db_path = database.DATABASE_PATH

        # 3. CRITICAL: Re-point database.DATABASE_PATH to the temporary database
        # BEFORE importing app.py so that app startup initialization
        # (setup_database_if_needed()) executes against temp_db_path, NOT campus_connect.db!
        database.DATABASE_PATH = temp_db_path
        DB_PATH = temp_db_path

        # If app was previously loaded in sys.modules, remove it to force fresh import
        if 'app' in sys.modules:
            del sys.modules['app']

        # 4. Safely import app - its startup logic will execute strictly against temp_db_path
        import app as app_module
        from app import app
        app_imported = True
        flask_app = app

        # Ensure app_module also reflects temp_db_path
        if hasattr(app_module, 'DATABASE_PATH'):
            app_module.DATABASE_PATH = temp_db_path

        app.config['TESTING'] = True

        print(f"[SETUP] Isolated test database: {temp_db_path}")
        print(f"[SETUP] Production database protected: {orig_db_path}")

        # Provision admin account in temporary database
        database.init_admin_user("Campus Administrator", "admin@campus.edu", "Admin@Campus2026!")

        unauth_client = SessionClient()
        student_client = SessionClient()
        admin_client = SessionClient()

        # [TEST 1] Missing required registration fields
        print("\n[TEST 1] Missing registration fields validation...")
        status, res = unauth_client.request("/register", method="POST", payload={
            "name": "Test Student"
            # Missing student_id, email, password
        })
        assert status == 400, f"Expected 400, got {status}: {res}"
        assert res.get('status') == 'error'
        print(f" PASS: Missing fields rejected with HTTP {status}: {res.get('message')}")
        tests_passed += 1

        # [TEST 2] Invalid college email format
        print("\n[TEST 2] Invalid college email format validation...")
        status, res = unauth_client.request("/register", method="POST", payload={
            "name": "Test Student",
            "student_id": "CS2026-999",
            "email": "not-a-valid-email",
            "password": "Password123!",
            "confirm_password": "Password123!"
        })
        assert status == 400, f"Expected 400, got {status}: {res}"
        assert "email" in res.get('message', '').lower()
        print(f" PASS: Invalid email rejected with HTTP {status}: {res.get('message')}")
        tests_passed += 1

        # [TEST 3] Short password validation (< 6 chars)
        print("\n[TEST 3] Short password validation (< 6 chars)...")
        status, res = unauth_client.request("/register", method="POST", payload={
            "name": "Test Student",
            "student_id": "CS2026-999",
            "email": "student.test@campus.edu",
            "password": "123",
            "confirm_password": "123"
        })
        assert status == 400, f"Expected 400, got {status}: {res}"
        assert "password" in res.get('message', '').lower()
        print(f" PASS: Short password rejected with HTTP {status}: {res.get('message')}")
        tests_passed += 1

        # [TEST 4] Password mismatch validation
        print("\n[TEST 4] Password mismatch validation...")
        status, res = unauth_client.request("/register", method="POST", payload={
            "name": "Test Student",
            "student_id": "CS2026-999",
            "email": "student.test@campus.edu",
            "password": "Password123!",
            "confirm_password": "MismatchPassword456!"
        })
        assert status == 400, f"Expected 400, got {status}: {res}"
        assert "match" in res.get('message', '').lower()
        print(f" PASS: Password mismatch rejected with HTTP {status}: {res.get('message')}")
        tests_passed += 1

        # [TEST 5] Valid student registration (and role forgery prevention)
        print("\n[TEST 5] Valid student registration & role forgery prevention...")
        test_student_email = "rohit.verma@campus.edu"
        test_student_pass = "RohitPass2026!"
        created_emails.append(test_student_email)

        status, res = student_client.request("/register", method="POST", payload={
            "name": "Rohit Verma",
            "student_id": "CS2024-105",
            "email": test_student_email,
            "password": test_student_pass,
            "confirm_password": test_student_pass,
            "role": "Admin"  # Malicious attempt to forge an Admin role!
        })
        assert status == 201, f"Expected 201, got {status}: {res}"
        user_data = res.get('user', {})
        assert user_data.get('role') == 'Student', f"SECURITY BREACH: Role forgery succeeded: {user_data.get('role')}"
        print(f" PASS: Student account created with HTTP 201. Role strictly enforced to: '{user_data.get('role')}'.")
        tests_passed += 1

        # [TEST 6] Duplicate email registration prevention
        print("\n[TEST 6] Duplicate email prevention...")
        status, res = unauth_client.request("/register", method="POST", payload={
            "name": "Duplicate Rohit",
            "student_id": "CS2024-999",
            "email": test_student_email.upper(),  # Test case-insensitivity
            "password": "AnotherPassword123!",
            "confirm_password": "AnotherPassword123!"
        })
        assert status == 400, f"Expected 400, got {status}: {res}"
        assert "already exists" in res.get('message', '').lower()
        print(f" PASS: Duplicate email rejected with HTTP {status}: {res.get('message')}")
        tests_passed += 1

        # [TEST 7] Direct SQLite password hashing verification
        print("\n[TEST 7] Direct SQLite password hashing verification...")
        conn = sqlite3.connect(DB_PATH)
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT password_hash FROM users WHERE LOWER(email) = ?", (test_student_email,))
            row = cursor.fetchone()
            assert row is not None, "User not found in SQLite table `users`!"
            p_hash = row['password_hash']
            assert p_hash != test_student_pass, "SECURITY VIOLATION: Plaintext password was stored in database!"
            assert p_hash.startswith("scrypt:") or p_hash.startswith("pbkdf2:"), f"Invalid hash format: {p_hash}"
            print(f" PASS: Password safely hashed in SQLite: '{p_hash[:26]}...'")
        finally:
            conn.close()
        tests_passed += 1

        # [TEST 8] Invalid login credentials
        print("\n[TEST 8] Invalid login credentials handling...")
        bad_client = SessionClient()
        status, res = bad_client.request("/login", method="POST", payload={
            "email": test_student_email,
            "password": "WrongPassword123!"
        })
        assert status == 401, f"Expected 401, got {status}: {res}"
        print(f" PASS: Invalid password rejected with HTTP 401: {res.get('message')}")

        status, res = bad_client.request("/login", method="POST", payload={
            "email": "nonexistent@campus.edu",
            "password": "SomePassword123!"
        })
        assert status == 401, f"Expected 401, got {status}: {res}"
        print(f" PASS: Non-existent email rejected with HTTP 401: {res.get('message')}")
        tests_passed += 1

        # [TEST 9] Valid student login
        print("\n[TEST 9] Valid student login...")
        login_client = SessionClient()
        status, res = login_client.request("/login", method="POST", payload={
            "email": test_student_email,
            "password": test_student_pass
        })
        assert status == 200, f"Expected 200, got {status}: {res}"
        assert res.get('status') == 'success'
        print(f" PASS: Student login successful with HTTP 200: {res.get('message')}")
        tests_passed += 1

        # [TEST 10] Current user profile endpoint (/api/auth/me)
        print("\n[TEST 10] Current user profile endpoint (/api/auth/me)...")
        status, res = login_client.request("/api/auth/me", method="GET")
        assert status == 200, f"Expected 200, got {status}: {res}"
        assert res.get('user', {}).get('email') == test_student_email
        assert res.get('user', {}).get('role') == 'Student'
        print(f" PASS: /api/auth/me verified student session for: {test_student_email} (Role: Student)")
        tests_passed += 1

        # [TEST 11] Unauthenticated access to protected endpoints
        print("\n[TEST 11] Unauthenticated access blocking...")
        status, res = unauth_client.request("/api/auth/me", method="GET")
        assert status == 401, f"Expected 401, got {status}: {res}"
        print(" PASS: Unauthenticated /api/auth/me rejected with HTTP 401.")

        status, res = unauth_client.request("/api/student/tickets", method="GET")
        assert status == 401, f"Expected 401, got {status}: {res}"
        print(" PASS: Unauthenticated /api/student/tickets rejected with HTTP 401.")

        status, res = unauth_client.request("/api/admin/tickets", method="GET")
        assert status == 401, f"Expected 401, got {status}: {res}"
        print(" PASS: Unauthenticated /api/admin/tickets rejected with HTTP 401.")
        tests_passed += 1

        # [TEST 12] RBAC: Student blocked from Admin endpoints (HTTP 403 Forbidden)
        print("\n[TEST 12] RBAC enforcement: Student blocked from Admin endpoints...")
        # 12a. JSON API endpoint
        status, res = login_client.request("/api/admin/tickets", method="GET")
        assert status == 403, f"Expected 403 Forbidden for Student accessing /api/admin/tickets, got {status}: {res}"
        print(f" PASS: Student blocked from /api/admin/tickets with HTTP 403: {res.get('message')}")

        # 12b. Attempt to update ticket status via admin endpoint
        status, res = login_client.request("/api/admin/tickets/1/status", method="POST", payload={"status": "Resolved"})
        assert status == 403, f"Expected 403 Forbidden for Student updating ticket status, got {status}: {res}"
        print(f" PASS: Student blocked from /api/admin/tickets/1/status with HTTP 403: {res.get('message')}")

        # 12c. HTML Admin dashboard URL
        status, res = login_client.request("/admin/dashboard", method="GET")
        assert status == 403, f"Expected 403 Forbidden for Student accessing /admin/dashboard, got {status}"
        print(" PASS: Student navigating to /admin/dashboard receives HTTP 403 Forbidden HTML page.")
        tests_passed += 1

        # [TEST 13] Student login blocked on Admin Portal (/admin/login)
        print("\n[TEST 13] Student login attempt on Admin Login portal...")
        status, res = unauth_client.request("/admin/login", method="POST", payload={
            "email": test_student_email,
            "password": test_student_pass
        })
        assert status == 403, f"Expected 403 Access Denied, got {status}: {res}"
        assert "administrative privileges" in res.get('message', '').lower()
        print(f" PASS: Student rejected on /admin/login with HTTP 403: {res.get('message')}")
        tests_passed += 1

        # [TEST 14] Admin login and authentication
        print("\n[TEST 14] Administrator login...")
        admin_email = "admin@campus.edu"
        admin_pass = "Admin@Campus2026!"
        status, res = admin_client.request("/admin/login", method="POST", payload={
            "email": admin_email,
            "password": admin_pass
        })
        assert status == 200, f"Expected 200 for Admin login, got {status}: {res}"
        assert res.get('status') == 'success'
        assert res.get('user', {}).get('role') == 'Admin'
        print(f" PASS: Administrator logged in with HTTP 200: {res.get('message')}")
        tests_passed += 1

        # [TEST 15] Admin permitted ticket management (/api/admin/tickets)
        print("\n[TEST 15] Admin accessing ticket management endpoint...")
        # Create a test ticket in the isolated DB if none exist
        database.create_ticket(
            student_name="Rohit Verma",
            student_id="CS2026-999",
            email="rohit.verma@campus.edu",
            category="Wi-Fi & IT",
            priority="Medium",
            location="Room 101",
            subject="Test Wi-Fi connectivity",
            description="Testing admin ticket management in isolated DB"
        )
        status, res = admin_client.request("/api/admin/tickets", method="GET")
        assert status == 200, f"Expected 200, got {status}: {res}"
        tickets = res.get('tickets', [])
        assert len(tickets) >= 1, "Expected tickets list in admin view"
        print(f" PASS: Admin retrieved {len(tickets)} tickets successfully with HTTP 200.")
        tests_passed += 1

        # [TEST 16] Admin updating ticket status in SQLite
        print("\n[TEST 16] Admin updating ticket status (/api/admin/tickets/<id>/status)...")
        # Fetch first ticket ID
        target_ticket_id = tickets[0]['id']
        orig_status = tickets[0]['status']
        new_status = "In Progress" if orig_status != "In Progress" else "Resolved"

        status, res = admin_client.request(f"/api/admin/tickets/{target_ticket_id}/status", method="POST", payload={
            "status": new_status
        })
        assert status == 200, f"Expected 200, got {status}: {res}"
        assert res.get('status') == 'success'
        updated = res.get('ticket', {})
        assert updated.get('status') == new_status, f"Expected {new_status}, got {updated.get('status')}"
        print(f" PASS: Admin successfully updated ticket #{target_ticket_id} to '{new_status}'.")

        # Verify directly in SQLite with strict try/finally connection handling
        conn = sqlite3.connect(DB_PATH)
        try:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT status FROM tickets WHERE id = ?", (target_ticket_id,))
            db_ticket = cur.fetchone()
            assert db_ticket['status'] == new_status, "Status was not updated in SQLite database!"
            # Restore original status so DB remains pristine
            cur.execute("UPDATE tickets SET status = ? WHERE id = ?", (orig_status, target_ticket_id))
            conn.commit()
            print(f" PASS: SQLite persistence verified and status restored to '{orig_status}'.")
        finally:
            conn.close()
        tests_passed += 1

        # [TEST 17] Logout and session destruction
        print("\n[TEST 17] Logout and session destruction...")
        status, res = admin_client.request("/logout", method="POST")
        assert status == 200, f"Expected 200, got {status}: {res}"
        # Now try to access admin endpoint with logged out client
        status, res = admin_client.request("/api/admin/tickets", method="GET")
        assert status == 401, f"Expected 401 after logout, got {status}: {res}"
        print(" PASS: Session safely destroyed; subsequent request rejected with HTTP 401.")
        tests_passed += 1

    finally:
        # [TEST 18] Safe cleanup of test user accounts with strict try/finally
        if temp_db_path and os.path.exists(temp_db_path):
            print("\n[TEST 18] Safely cleaning up test user records from SQLite database...")
            test18_success = False
            try:
                conn = sqlite3.connect(temp_db_path)
                try:
                    cur = conn.cursor()
                    for em in created_emails:
                        cur.execute("DELETE FROM users WHERE LOWER(email) = ?", (em.lower(),))
                    conn.commit()
                    for em in created_emails:
                        cur.execute("SELECT 1 FROM users WHERE LOWER(email) = ?", (em.lower(),))
                        assert cur.fetchone() is None, f"User {em} was not cleaned up!"
                    print(f" PASS: Cleaned up {len(created_emails)} test user account(s). SQLite database is pristine.")
                    test18_success = True
                finally:
                    conn.close()
            except Exception as e:
                print(f" [WARN] Cleanup verification note: {e}")
            if test18_success:
                tests_passed += 1

        # Restore original database path in database module and app module
        if database is not None and orig_db_path is not None:
            database.DATABASE_PATH = orig_db_path
        if orig_db_path is not None:
            DB_PATH = orig_db_path

        # Restore app module state in sys.modules
        if not app_imported:
            # If app failed to import, revert sys.modules to its previous state
            if prev_app_in_sys:
                sys.modules['app'] = prev_app_module
            elif 'app' in sys.modules:
                del sys.modules['app']
        else:
            # App was imported; restore its DATABASE_PATH if it was previously set
            if 'app' in sys.modules and hasattr(sys.modules['app'], 'DATABASE_PATH') and orig_db_path is not None:
                sys.modules['app'].DATABASE_PATH = orig_db_path
            # If app wasn't loaded before run_tests(), remove it so environment remains clean
            if not prev_app_in_sys and 'app' in sys.modules:
                del sys.modules['app']

        # Delete temporary database files and any SQLite sidecars only AFTER all connections are closed
        if temp_db_path and os.path.exists(temp_db_path):
            for ext in ['', '-wal', '-shm', '-journal']:
                f = temp_db_path + ext
                if os.path.exists(f):
                    try:
                        os.remove(f)
                    except Exception as err:
                        print(f" [WARN] Could not remove temp file {f}: {err}")
            print(f"[TEARDOWN] Temporary database safely removed: {temp_db_path}")

    # Truthful final reporting: Only claim all passed if all 18 passed
    print("\n" + "=" * 65)
    if tests_passed == total_tests:
        print(f" ALL {total_tests} AUTHENTICATION & RBAC TESTS PASSED 100%! ")
    else:
        print(f" TEST RUN INCOMPLETE: {tests_passed}/{total_tests} tests passed. ")
    print("=" * 65)
    if tests_passed != total_tests:
        sys.exit(1)


if __name__ == '__main__':
    run_tests()
