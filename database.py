"""
Database management module for CampusConnect.
Provides safe SQLite connection helpers, schema initialization, and query utilities.
"""

import os
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

# Define database file path in the project root
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_PATH = os.path.join(BASE_DIR, 'campus_connect.db')
SCHEMA_PATH = os.path.join(BASE_DIR, 'schema.sql')


def get_db_connection():
    """
    Establish a connection to the SQLite database.
    Configures row_factory to sqlite3.Row so columns can be accessed by name.
    """
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    # Enable foreign key constraints
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db():
    """
    Initialize SQLite database safely using schema.sql.
    Uses CREATE TABLE IF NOT EXISTS to prevent duplicate tables or data loss.
    """
    if not os.path.exists(SCHEMA_PATH):
        raise FileNotFoundError(f"Schema file not found at: {SCHEMA_PATH}")

    with open(SCHEMA_PATH, 'r', encoding='utf-8') as f:
        schema_sql = f.read()

    conn = get_db_connection()
    try:
        # Execute schema creation script safely
        conn.executescript(schema_sql)

        # Seed initial system metadata safely if not already present
        conn.execute("""
            INSERT OR IGNORE INTO system_status (key_name, value_text)
            VALUES ('app_status', 'Operational')
        """)
        conn.execute("""
            INSERT OR REPLACE INTO system_status (key_name, value_text)
            VALUES ('project_phase', 'Phase 2 - Modern UI & Student Dashboard')
        """)
        conn.commit()
        print(f"[OK] Database initialized successfully at: {DATABASE_PATH}")

        # Check for environment-configured admin setup
        admin_email = os.environ.get('ADMIN_EMAIL')
        admin_password = os.environ.get('ADMIN_PASSWORD')
        admin_name = os.environ.get('ADMIN_NAME', 'Campus Administrator')
        if admin_email and admin_password:
            init_admin_user(admin_name, admin_email, admin_password)

    except sqlite3.Error as e:
        print(f"[ERROR] Database initialization failed: {e}")
        raise e
    finally:
        conn.close()


def seed_demo_data_if_empty():
    """
    Client-ready production mode:
    Automatic demo seeding is permanently disabled.
    Only genuine user-submitted reports and tickets are stored in the database.
    """
    pass


def get_dashboard_data():
    """
    Retrieves comprehensive summary statistics and recent records from SQLite.
    Returns:
        dict: Counts, lists of recent tickets and lost & found items.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Total tickets
        cursor.execute("SELECT COUNT(*) AS count FROM tickets")
        total_reports = cursor.fetchone()['count']

        # Pending / active reports (Open, Pending, or In Progress)
        cursor.execute("SELECT COUNT(*) AS count FROM tickets WHERE status IN ('Pending', 'Open', 'In Progress')")
        pending_reports = cursor.fetchone()['count']

        # In-Progress breakdown
        cursor.execute("SELECT COUNT(*) AS count FROM tickets WHERE status = 'In Progress'")
        in_progress_reports = cursor.fetchone()['count']

        # Resolved reports
        cursor.execute("SELECT COUNT(*) AS count FROM tickets WHERE status IN ('Resolved', 'Closed')")
        resolved_reports = cursor.fetchone()['count']

        # Total Lost & Found items
        cursor.execute("SELECT COUNT(*) AS count FROM lost_found_items")
        lost_found_count = cursor.fetchone()['count']

        # Total Lost Items count (real database count)
        cursor.execute("SELECT COUNT(*) AS count FROM lost_found_items WHERE item_type = 'Lost'")
        total_lost_items = cursor.fetchone()['count']

        # Total Found Items count (real database count)
        cursor.execute("SELECT COUNT(*) AS count FROM lost_found_items WHERE item_type = 'Found'")
        total_found_items = cursor.fetchone()['count']

        # Active Reports count (Lost/Found items currently Active or Open)
        cursor.execute("SELECT COUNT(*) AS count FROM lost_found_items WHERE status IN ('Active', 'Open')")
        active_reports = cursor.fetchone()['count']

        # Matched or Returned Items count
        cursor.execute("SELECT COUNT(*) AS count FROM lost_found_items WHERE status IN ('Matched', 'Returned', 'Claimed', 'Resolved')")
        matched_returned_items = cursor.fetchone()['count']

        # Active Lost & Found items (legacy compatibility)
        cursor.execute("SELECT COUNT(*) AS count FROM lost_found_items WHERE status = 'Active'")
        active_lost_found = cursor.fetchone()['count']

        # Recent 5 tickets
        cursor.execute("""
            SELECT id, ticket_number, student_name, student_id, category,
                   subject, description, priority, status, created_at
            FROM tickets
            ORDER BY id DESC
            LIMIT 5
        """)
        recent_tickets = [dict(row) for row in cursor.fetchall()]

        # Recent lost & found items with image_path support
        cursor.execute("""
            SELECT id, item_type, item_name, category, location,
                   date_reported, description, contact_name, status, image_path
            FROM lost_found_items
            ORDER BY id DESC
            LIMIT 12
        """)
        recent_lost_found = [dict(row) for row in cursor.fetchall()]

        return {
            'total_reports': total_reports,
            'pending_reports': pending_reports,
            'in_progress_reports': in_progress_reports,
            'resolved_reports': resolved_reports,
            'lost_found_count': lost_found_count,
            'total_lost_items': total_lost_items,
            'total_found_items': total_found_items,
            'active_reports': active_reports,
            'matched_returned_items': matched_returned_items,
            'active_lost_found': active_lost_found,
            'recent_tickets': recent_tickets,
            'recent_lost_found': recent_lost_found,
            'db_connected': True
        }
    except sqlite3.Error as e:
        print(f"[ERROR] Failed to fetch dashboard data: {e}")
        return {
            'total_reports': 0,
            'pending_reports': 0,
            'in_progress_reports': 0,
            'resolved_reports': 0,
            'lost_found_count': 0,
            'total_lost_items': 0,
            'total_found_items': 0,
            'active_reports': 0,
            'matched_returned_items': 0,
            'active_lost_found': 0,
            'recent_tickets': [],
            'recent_lost_found': [],
            'db_connected': False,
            'error': str(e)
        }
    finally:
        conn.close()


def generate_ticket_number(cursor):
    """
    Generates a unique sequential ticket number in the format 'CC-TKT-XXXX'.
    Ensures absolute uniqueness against existing records in SQLite.
    """
    cursor.execute("""
        SELECT ticket_number FROM tickets 
        WHERE ticket_number LIKE 'CC-TKT-%' 
        ORDER BY id DESC LIMIT 50
    """)
    rows = cursor.fetchall()
    max_num = 1000
    for row in rows:
        t_num = row['ticket_number'] if isinstance(row, sqlite3.Row) else row[0]
        if t_num and t_num.startswith('CC-TKT-'):
            try:
                val = int(t_num.split('-')[-1])
                if val > max_num:
                    max_num = val
            except (ValueError, IndexError):
                pass

    next_num = max_num + 1
    while True:
        candidate = f"CC-TKT-{next_num:04d}"
        cursor.execute("SELECT 1 FROM tickets WHERE ticket_number = ?", (candidate,))
        if not cursor.fetchone():
            return candidate
        next_num += 1


def create_ticket(student_name, student_id, email, category, subject, description, priority='Medium', location=None, status='Pending'):
    """
    Inserts a new ticket record into SQLite using parameterized SQL.
    Generates a unique ticket number.
    Returns:
        dict: The inserted ticket record as a dictionary.
    Raises:
        sqlite3.Error: If database insert fails.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        ticket_number = generate_ticket_number(cursor)

        # Handle location by appending to description if provided
        if location and str(location).strip() and "Location:" not in description:
            final_description = f"{str(description).strip()} (Location: {str(location).strip()})"
        else:
            final_description = str(description).strip()

        cursor.execute("""
            INSERT INTO tickets (
                ticket_number, student_name, student_id, email,
                category, subject, description, priority, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            ticket_number,
            str(student_name).strip(),
            str(student_id).strip(),
            str(email).strip(),
            str(category).strip(),
            str(subject).strip(),
            final_description,
            str(priority).strip() if priority else 'Medium',
            str(status).strip() if status else 'Pending'
        ))

        ticket_id = cursor.lastrowid
        conn.commit()

        cursor.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def get_ticket_by_number(ticket_number):
    """
    Fetch a single ticket by its ticket number using parameterized SQL.
    Returns dict or None.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM tickets WHERE ticket_number = ?", (ticket_number,))
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def delete_ticket_by_number(ticket_number):
    """
    Safely delete a ticket by its ticket number using parameterized SQL.
    Used for automated test cleanup to avoid leaving test records in database.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM tickets WHERE ticket_number = ?", (ticket_number,))
        deleted_count = cursor.rowcount
        conn.commit()
        return deleted_count > 0
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def create_lost_found_item(item_type, item_name, category, location, date_reported, description, contact_name, contact_email, contact_phone='', status='Active', image_path=None):
    """
    Inserts a new lost-and-found record into SQLite using parameterized SQL.
    Validates item_type ('Lost' or 'Found').
    Returns:
        dict: The inserted record as a dictionary.
    Raises:
        ValueError: If item_type is invalid.
        sqlite3.Error: If database insert fails.
    """
    norm_type = str(item_type).strip().capitalize()
    if norm_type not in ['Lost', 'Found']:
        raise ValueError(f"Invalid item_type '{item_type}'. Must be 'Lost' or 'Found'.")

    norm_status = str(status).strip().capitalize() if status else 'Active'
    valid_statuses = ['Active', 'Open', 'Claimed', 'Resolved', 'Returned', 'Matched', 'Closed']
    if norm_status not in valid_statuses:
        norm_status = 'Active'

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO lost_found_items (
                item_type, item_name, category, location, date_reported,
                description, contact_name, contact_email, contact_phone, status, image_path
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            norm_type,
            str(item_name).strip(),
            str(category).strip(),
            str(location).strip(),
            str(date_reported).strip(),
            str(description).strip() if description else '',
            str(contact_name).strip(),
            str(contact_email).strip(),
            str(contact_phone).strip() if contact_phone else '',
            norm_status,
            str(image_path).strip() if image_path else None
        ))
        item_id = cursor.lastrowid
        conn.commit()

        cursor.execute("SELECT * FROM lost_found_items WHERE id = ?", (item_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def get_lost_found_items(item_type=None, category=None, status=None, search=None, include_contact=False):
    """
    Retrieves lost and found items with dynamic filtering and search.
    Uses parameterized SQL queries.
    Privacy constraint: If include_contact is False (default for public listings),
    contact_email and contact_phone are excluded from query results.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        if include_contact:
            columns = """
                id, item_type, item_name, category, location, date_reported,
                description, contact_name, contact_email, contact_phone, status, image_path, created_at
            """
        else:
            columns = """
                id, item_type, item_name, category, location, date_reported,
                description, contact_name, status, image_path, created_at
            """

        query = f"SELECT {columns} FROM lost_found_items WHERE 1=1"
        params = []

        if item_type and str(item_type).strip().lower() not in ['all', '']:
            norm_type = str(item_type).strip().capitalize()
            query += " AND item_type = ?"
            params.append(norm_type)

        if category and str(category).strip().lower() not in ['all', '']:
            query += " AND category = ?"
            params.append(str(category).strip())

        if status and str(status).strip().lower() not in ['all', '']:
            norm_status = str(status).strip().capitalize()
            query += " AND status = ?"
            params.append(norm_status)

        if search and str(search).strip():
            kw = f"%{str(search).strip()}%"
            query += " AND (item_name LIKE ? OR description LIKE ? OR location LIKE ? OR category LIKE ?)"
            params.extend([kw, kw, kw, kw])

        query += " ORDER BY id DESC"
        cursor.execute(query, tuple(params))
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def get_lost_found_item_by_id(item_id, mask_contact=True):
    """
    Retrieves a single lost-and-found item by ID using parameterized SQL.
    If mask_contact is True, partially masks contact_email and contact_phone to protect student privacy.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM lost_found_items WHERE id = ?", (item_id,))
        row = cursor.fetchone()
        if not row:
            return None
        data = dict(row)
        if mask_contact:
            email = data.get('contact_email') or ''
            if '@' in email:
                user_part, domain_part = email.split('@', 1)
                if len(user_part) > 2:
                    masked_user = user_part[0] + ('*' * (len(user_part) - 2)) + user_part[-1]
                else:
                    masked_user = user_part[0] + '*'
                data['contact_email'] = f"{masked_user}@{domain_part}"

            phone = data.get('contact_phone') or ''
            if len(phone) >= 6:
                data['contact_phone'] = phone[:3] + ' *** *** ' + phone[-2:]
        return data
    finally:
        conn.close()


def delete_lost_found_item(item_id):
    """
    Safely deletes a lost-and-found record by ID using parameterized SQL.
    Used for automated test cleanup to avoid leaving test records in database.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM lost_found_items WHERE id = ?", (item_id,))
        deleted = cursor.rowcount > 0
        conn.commit()
        return deleted
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def update_lost_found_status(item_id, new_status):
    """
    Updates the status of a lost-and-found item in SQLite using parameterized SQL.
    Validates status against accepted values: ['Active', 'Claimed', 'Resolved', 'Returned'].
    Returns:
        dict: The updated item record, or None if item not found.
    """
    valid_statuses = ['Active', 'Open', 'Claimed', 'Resolved', 'Returned', 'Matched', 'Closed']
    raw_status = str(new_status).strip().capitalize()
    if raw_status not in valid_statuses:
        raise ValueError(f"Invalid Lost & Found status '{new_status}'. Must be one of: {', '.join(valid_statuses)}")

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE lost_found_items
            SET status = ?
            WHERE id = ?
        """, (raw_status, item_id))
        if cursor.rowcount == 0:
            return None
        conn.commit()

        cursor.execute("SELECT * FROM lost_found_items WHERE id = ?", (item_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def check_db_health():
    """
    Verifies database health and returns a dictionary of stats.
    Preserves backwards compatibility with Phase 1 endpoints.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) AS count FROM tickets")
        tickets_count = cursor.fetchone()['count']

        cursor.execute("SELECT COUNT(*) AS count FROM lost_found_items")
        items_count = cursor.fetchone()['count']

        cursor.execute("SELECT value_text FROM system_status WHERE key_name = 'app_status'")
        status_row = cursor.fetchone()
        app_status = status_row['value_text'] if status_row else 'Operational'

        conn.close()
        return {
            'healthy': True,
            'status': app_status,
            'tickets_count': tickets_count,
            'items_count': items_count,
            'database_path': DATABASE_PATH
        }
    except Exception as e:
        return {
            'healthy': False,
            'status': 'Error',
            'error_message': str(e),
            'tickets_count': 0,
            'items_count': 0,
            'users_count': 0,
            'database_path': DATABASE_PATH
        }


# ============================================================================
# User Authentication & Role-Based Access Control Functions (Phase 5)
# ============================================================================

def create_user(name, email, password, student_id=None, role='Student'):
    """
    Creates a new user record in SQLite with a secure Werkzeug password hash.
    Enforces uniqueness of email (case-insensitive) and validates input.
    Returns:
        dict: The created user record (excluding password_hash).
    Raises:
        ValueError: If input is invalid or email already exists.
        sqlite3.Error: If database insert fails.
    """
    clean_name = str(name).strip() if name else ''
    clean_email = str(email).strip().lower() if email else ''
    clean_password = str(password) if password else ''
    clean_student_id = str(student_id).strip() if student_id else None
    clean_role = str(role).strip().capitalize() if role else 'Student'

    if not clean_name:
        raise ValueError("Full Name is required.")
    if not clean_email or '@' not in clean_email or '.' not in clean_email:
        raise ValueError("A valid college email address is required.")
    if not clean_password or len(clean_password) < 6:
        raise ValueError("Password must be at least 6 characters in length.")
    if clean_role not in ['Student', 'Admin']:
        clean_role = 'Student'
    if clean_role == 'Student' and not clean_student_id:
        raise ValueError("Student / Roll ID is required for student accounts.")

    # Check for existing email (case-insensitive)
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id FROM users WHERE LOWER(email) = ?", (clean_email,))
        if cursor.fetchone():
            raise ValueError(f"An account with email '{clean_email}' already exists.")

        password_hash = generate_password_hash(clean_password)

        cursor.execute("""
            INSERT INTO users (name, student_id, email, password_hash, role)
            VALUES (?, ?, ?, ?, ?)
        """, (clean_name, clean_student_id, clean_email, password_hash, clean_role))
        user_id = cursor.lastrowid
        conn.commit()

        cursor.execute("""
            SELECT id, name, student_id, email, role, created_at
            FROM users WHERE id = ?
        """, (user_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def get_user_by_email(email, include_password_hash=False):
    """
    Retrieve user record by email (case-insensitive).
    """
    if not email:
        return None
    clean_email = str(email).strip().lower()
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        if include_password_hash:
            cursor.execute("SELECT * FROM users WHERE LOWER(email) = ?", (clean_email,))
        else:
            cursor.execute("""
                SELECT id, name, student_id, email, role, created_at, updated_at
                FROM users WHERE LOWER(email) = ?
            """, (clean_email,))
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_user_by_id(user_id, include_password_hash=False):
    """
    Retrieve user record by primary key ID.
    """
    if not user_id:
        return None
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        if include_password_hash:
            cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        else:
            cursor.execute("""
                SELECT id, name, student_id, email, role, created_at, updated_at
                FROM users WHERE id = ?
            """, (user_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_user_by_identifier(identifier, include_password_hash=False):
    """
    Retrieve user record by email OR student_id (case-insensitive).
    Allows students to log in using either their College Email or Student Roll ID.
    """
    if not identifier:
        return None
    clean_id = str(identifier).strip().lower()
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        if include_password_hash:
            cursor.execute("""
                SELECT * FROM users 
                WHERE LOWER(email) = ? OR (student_id IS NOT NULL AND LOWER(student_id) = ?)
            """, (clean_id, clean_id))
        else:
            cursor.execute("""
                SELECT id, name, student_id, email, role, created_at, updated_at
                FROM users 
                WHERE LOWER(email) = ? OR (student_id IS NOT NULL AND LOWER(student_id) = ?)
            """, (clean_id, clean_id))
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def verify_user_credentials(identifier, password):
    """
    Verifies user login credentials using Werkzeug check_password_hash.
    Supports authentication via college email OR student roll ID.
    Returns safe user dict if valid, None otherwise.
    """
    if not identifier or not password:
        return None
    user = get_user_by_identifier(identifier, include_password_hash=True)
    if not user:
        return None
    if check_password_hash(user['password_hash'], str(password)):
        safe_user = {k: v for k, v in user.items() if k != 'password_hash'}
        return safe_user
    return None


def init_admin_user(name, email, password):
    """
    Safe administrative account provisioning helper.
    Creates an Admin user if not existing, or updates credentials if already present.
    Ensures passwords are encrypted with Werkzeug hashing.
    """
    clean_name = str(name).strip() if name else 'Campus Administrator'
    clean_email = str(email).strip().lower() if email else ''
    clean_password = str(password) if password else ''

    if not clean_email or '@' not in clean_email or '.' not in clean_email:
        raise ValueError("Valid administrative email is required.")
    if not clean_password or len(clean_password) < 6:
        raise ValueError("Admin password must be at least 6 characters in length.")

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        password_hash = generate_password_hash(clean_password)
        cursor.execute("SELECT id FROM users WHERE LOWER(email) = ?", (clean_email,))
        existing = cursor.fetchone()

        if existing:
            cursor.execute("""
                UPDATE users
                SET name = ?, password_hash = ?, role = 'Admin', updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (clean_name, password_hash, existing['id']))
            user_id = existing['id']
            print(f"[INFO] Updated existing Admin account: {clean_email}")
        else:
            cursor.execute("""
                INSERT INTO users (name, student_id, email, password_hash, role)
                VALUES (?, NULL, ?, ?, 'Admin')
            """, (clean_name, clean_email, password_hash))
            user_id = cursor.lastrowid
            print(f"[INFO] Provisioned new Admin account: {clean_email}")

        conn.commit()
        cursor.execute("SELECT id, name, email, role, created_at FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def update_ticket_status(ticket_id, new_status):
    """
    Updates the status of a ticket in SQLite with parameterized SQL.
    Validates status against accepted values.
    Returns:
        dict: The updated ticket record, or None if ticket not found.
    """
    valid_statuses = ['Open', 'Pending', 'In Progress', 'Resolved', 'Closed']
    raw_status = str(new_status).strip()
    norm_status = 'In Progress' if raw_status.lower() == 'in progress' else raw_status.title()

    if norm_status not in valid_statuses:
        raise ValueError(f"Invalid ticket status '{new_status}'. Must be one of: {', '.join(valid_statuses)}")

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE tickets
            SET status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (norm_status, ticket_id))
        if cursor.rowcount == 0:
            return None
        conn.commit()

        cursor.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def get_tickets_by_student_email(email):
    """
    Fetches all tickets logged by a specific student using parameterized SQL.
    Used for Student Dashboard / My Reports.
    """
    if not email:
        return []
    clean_email = str(email).strip().lower()
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT id, ticket_number, student_name, student_id, email,
                   category, subject, description, priority, status, created_at, updated_at
            FROM tickets
            WHERE LOWER(email) = ?
            ORDER BY id DESC
        """, (clean_email,))
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def delete_user_by_email(email):
    """
    Safely deletes a user by email for test cleanup.
    """
    if not email:
        return False
    clean_email = str(email).strip().lower()
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM users WHERE LOWER(email) = ?", (clean_email,))
        deleted = cursor.rowcount > 0
        conn.commit()
        return deleted
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def delete_user_by_id(user_id):
    """
    Safely deletes a user by primary key ID for test cleanup.
    """
    if not user_id:
        return False
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
        deleted = cursor.rowcount > 0
        conn.commit()
        return deleted
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


if __name__ == '__main__':
    print("Running standalone database initialization and seeding...")
    init_db()
    seed_demo_data_if_empty()
    data = get_dashboard_data()
    print("Dashboard Data Summary:")
    print(f"Total Reports: {data['total_reports']}")
    print(f"Pending Reports: {data['pending_reports']}")
    print(f"Resolved Reports: {data['resolved_reports']}")
    print(f"Lost & Found Items: {data['lost_found_count']}")
