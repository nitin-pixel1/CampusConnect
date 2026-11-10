import os
from functools import wraps
from datetime import date, timedelta
from flask import (
    Flask, render_template, jsonify, redirect, url_for,
    request, session, flash, abort
)
from database import (
    init_db,
    check_db_health,
    get_dashboard_data,
    seed_demo_data_if_empty,
    create_ticket,
    get_ticket_by_number,
    delete_ticket_by_number,
    create_lost_found_item,
    get_lost_found_items,
    get_lost_found_item_by_id,
    delete_lost_found_item,
    get_db_connection,
    DATABASE_PATH,
    # Auth & RBAC additions
    create_user,
    get_user_by_email,
    get_user_by_id,
    verify_user_credentials,
    init_admin_user,
    update_ticket_status,
    update_lost_found_status,
    get_tickets_by_student_email,
    delete_user_by_email,
    delete_user_by_id
)

import uuid
from werkzeug.utils import secure_filename

# Initialize Flask application
app = Flask(__name__)

# Session and cookie security configuration
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'campusconnect-secure-session-key-2026')
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)

# File upload configuration
app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 8 * 1024 * 1024  # 8MB max upload
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Predefined Lost & Found Categories (Form options, never sample records)
PREDEFINED_LF_CATEGORIES = [
    "ID Card",
    "Student Bus Pass",
    "Books & Notebooks",
    "Mobile Phone",
    "Laptop & Electronics",
    "Wallet & Purse",
    "Keys",
    "Bags",
    "Water Bottle & Lunch Box",
    "Earphones & Accessories",
    "Stationery",
    "Other"
]


# ============================================================================
# Authentication Context & Authorization Decorators
# ============================================================================

@app.context_processor
def inject_auth_user():
    """
    Injects current authenticated user context and predefined categories into all Jinja templates.
    """
    return {
        'current_user': {
            'is_authenticated': 'user_id' in session,
            'id': session.get('user_id'),
            'name': session.get('user_name'),
            'email': session.get('user_email'),
            'role': session.get('user_role'),
            'student_id': session.get('student_id'),
            'is_admin': session.get('user_role') == 'Admin',
            'is_student': session.get('user_role') == 'Student'
        },
        'predefined_categories': PREDEFINED_LF_CATEGORIES
    }


def login_required(f):
    """
    Ensures user is authenticated.
    Redirects unauthenticated browser requests to login or returns HTTP 401 for APIs.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            if request.path.startswith('/api/'):
                return jsonify({
                    'status': 'error',
                    'message': 'Authentication required. Please log in.'
                }), 401
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login', next=request.path))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """
    Role-Based Access Control decorator.
    Restricts access strictly to users with role == 'Admin'.
    Returns HTTP 403 Forbidden for students attempting to access administrative endpoints.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            if request.path.startswith('/api/'):
                return jsonify({
                    'status': 'error',
                    'message': 'Authentication required. Please log in as an administrator.'
                }), 401
            flash('Administrator authentication required to access this area.', 'warning')
            return redirect(url_for('admin_login', next=request.path))

        if session.get('user_role') != 'Admin':
            if request.path.startswith('/api/'):
                return jsonify({
                    'status': 'error',
                    'message': 'Access denied: Administrative privileges required.'
                }), 403
            return render_template('403.html'), 403

        return f(*args, **kwargs)
    return decorated_function


def setup_database_if_needed():
    """
    Safely initialize the SQLite database on startup if it does not exist,
    without overwriting existing data. Demo seeding is permanently disabled.
    """
    if not os.path.exists(DATABASE_PATH):
        print("[INFO] Database file not found. Initializing new SQLite database...")
        init_db()
    else:
        init_db()


# Ensure database is safely initialized upon application load
with app.app_context():
    setup_database_if_needed()



# ============================================================================
# Application Routes
# ============================================================================

@app.route('/')
def home():
    """
    Mandatory Login-First Entry Route.
    - If authenticated as Admin: redirects to /admin/dashboard
    - If authenticated as Student: redirects to /student/dashboard
    - If unauthenticated: displays the ULTRON Access Control entry page (entry.html)
      with prominent Student Access and Admin Access portals.
    """
    if 'user_id' in session:
        if session.get('user_role') == 'Admin':
            return redirect(url_for('admin_dashboard'))
        return redirect(url_for('student_dashboard'))

    return render_template(
        'entry.html',
        active_page='entry'
    )


@app.route('/report')
@login_required
def report_issue_page():
    """
    Navigation link route for 'Report an Issue'.
    Protected: Requires user authentication.
    Renders the student dashboard with the issue reporting preview modal active.
    """
    db_health = check_db_health()
    dashboard_data = get_dashboard_data()
    return render_template(
        'index.html',
        db_health=db_health,
        dashboard_data=dashboard_data,
        active_page='report',
        auto_open_report_modal=True
    )


@app.route('/lost-found')
@login_required
def lost_found_page():
    """
    Navigation link route for 'Lost & Found'.
    Protected: Requires user authentication.
    Renders the authenticated Lost & Found portal.
    """
    db_health = check_db_health()
    dashboard_data = get_dashboard_data()
    return render_template(
        'index.html',
        db_health=db_health,
        dashboard_data=dashboard_data,
        active_page='lost_found'
    )


@app.route('/report-lost')
@login_required
def report_lost_page():
    """
    Direct route for reporting a lost item.
    Protected: Requires user authentication.
    Opens the Report Lost Item form modal automatically.
    """
    db_health = check_db_health()
    dashboard_data = get_dashboard_data()
    return render_template(
        'index.html',
        db_health=db_health,
        dashboard_data=dashboard_data,
        active_page='report_lost',
        auto_open_lost_modal=True
    )


@app.route('/report-found')
@login_required
def report_found_page():
    """
    Direct route for reporting a found item.
    Protected: Requires user authentication.
    Opens the Report Found Item form modal automatically.
    """
    db_health = check_db_health()
    dashboard_data = get_dashboard_data()
    return render_template(
        'index.html',
        db_health=db_health,
        dashboard_data=dashboard_data,
        active_page='report_found',
        auto_open_found_modal=True
    )


@app.route('/my-reports')
@login_required
def my_reports_page():
    """
    Navigation link route for 'My Reports'.
    Protected: Requires user authentication.
    If logged in as a student, redirects directly to personal student dashboard.
    Otherwise renders the student dashboard positioned at the Recent Reports section.
    """
    if 'user_id' in session and session.get('user_role') == 'Student':
        return redirect(url_for('student_dashboard'))

    db_health = check_db_health()
    dashboard_data = get_dashboard_data()
    return render_template(
        'index.html',
        db_health=db_health,
        dashboard_data=dashboard_data,
        active_page='my_reports'
    )


# ============================================================================
# Authentication & Role-Based Access Control Routes (Phase 5)
# ============================================================================

@app.route('/login', methods=['GET', 'POST'])
def login():
    """
    Student Login Page & Authentication Handler.
    Supports both traditional Form POST and AJAX/JSON requests.
    Redirects authenticated users to their corresponding dashboard.
    """
    if request.method == 'GET' and 'user_id' in session:
        if session.get('user_role') == 'Admin':
            return redirect(url_for('admin_dashboard'))
        return redirect(url_for('student_dashboard'))

    if request.method == 'POST':
        data = request.get_json(silent=True) or request.form
        email = str(data.get('email') or data.get('student_id') or data.get('identifier') or '').strip().lower()
        password = str(data.get('password', ''))
        remember_me = bool(data.get('remember_me')) if request.is_json else ('remember_me' in request.form)

        if not email or not password:
            msg = "Please provide both your college email and password."
            if request.is_json:
                return jsonify({'status': 'error', 'message': msg}), 400
            flash(msg, 'danger')
            return render_template('login.html', email=email), 400

        user = verify_user_credentials(email, password)
        if not user:
            msg = "Invalid email or password. Please verify your credentials."
            if request.is_json:
                return jsonify({'status': 'error', 'message': msg}), 401
            flash(msg, 'danger')
            return render_template('login.html', email=email), 401

        # Establish authenticated session
        session.clear()
        session['user_id'] = user['id']
        session['user_name'] = user['name']
        session['user_email'] = user['email']
        session['user_role'] = user['role']
        session['student_id'] = user.get('student_id')
        session.permanent = remember_me

        next_url = request.args.get('next') or data.get('next')
        if user['role'] == 'Admin':
            redirect_target = next_url if (next_url and next_url.startswith('/admin')) else url_for('admin_dashboard')
        else:
            redirect_target = next_url if (next_url and next_url.startswith('/') and not next_url.startswith('/admin')) else url_for('student_dashboard')

        if request.is_json:
            return jsonify({
                'status': 'success',
                'message': f"Welcome back, {user['name']}!",
                'user': user,
                'redirect_url': redirect_target
            }), 200

        flash(f"Welcome back, {user['name']}!", 'success')
        return redirect(redirect_target)

    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    """
    Student Registration Page & Handler.
    Allows students to register with Name, Student ID, Email, and Password.
    Public registration strictly creates Student accounts.
    """
    if request.method == 'GET' and 'user_id' in session:
        if session.get('user_role') == 'Admin':
            return redirect(url_for('admin_dashboard'))
        return redirect(url_for('student_dashboard'))

    if request.method == 'POST':
        data = request.get_json(silent=True) or request.form
        name = str(data.get('name', '')).strip()
        student_id = str(data.get('student_id', '')).strip()
        email = str(data.get('email', '')).strip().lower()
        password = str(data.get('password', ''))
        confirm_password = str(data.get('confirm_password', ''))

        # Validation checks
        if not name or not student_id or not email or not password:
            msg = "Please fill in all required fields: Name, Student ID, College Email, and Password."
            if request.is_json:
                return jsonify({'status': 'error', 'message': msg}), 400
            flash(msg, 'danger')
            return render_template('register.html', name=name, student_id=student_id, email=email), 400

        if '@' not in email or '.' not in email or len(email) < 5:
            msg = "Please enter a valid college email address."
            if request.is_json:
                return jsonify({'status': 'error', 'message': msg}), 400
            flash(msg, 'danger')
            return render_template('register.html', name=name, student_id=student_id, email=email), 400

        if len(password) < 6:
            msg = "Password must be at least 6 characters in length."
            if request.is_json:
                return jsonify({'status': 'error', 'message': msg}), 400
            flash(msg, 'danger')
            return render_template('register.html', name=name, student_id=student_id, email=email), 400

        if confirm_password and password != confirm_password:
            msg = "Passwords do not match. Please re-enter your password."
            if request.is_json:
                return jsonify({'status': 'error', 'message': msg}), 400
            flash(msg, 'danger')
            return render_template('register.html', name=name, student_id=student_id, email=email), 400

        try:
            # PUBLIC REGISTRATION ALWAYS CREATES STUDENT ACCOUNTS ONLY
            user = create_user(
                name=name,
                email=email,
                password=password,
                student_id=student_id,
                role='Student'
            )

            # Auto-login newly registered student
            session.clear()
            session['user_id'] = user['id']
            session['user_name'] = user['name']
            session['user_email'] = user['email']
            session['user_role'] = 'Student'
            session['student_id'] = user.get('student_id')
            session.permanent = True

            msg = f"Registration successful! Welcome to CampusConnect, {user['name']}."
            if request.is_json:
                return jsonify({
                    'status': 'success',
                    'message': msg,
                    'user': user,
                    'redirect_url': url_for('student_dashboard')
                }), 201

            flash(msg, 'success')
            return redirect(url_for('student_dashboard'))

        except ValueError as ve:
            if request.is_json:
                return jsonify({'status': 'error', 'message': str(ve)}), 400
            flash(str(ve), 'danger')
            return render_template('register.html', name=name, student_id=student_id, email=email), 400
        except Exception as e:
            print(f"[ERROR] Registration failed: {e}")
            msg = "A database error occurred during registration. Please try again."
            if request.is_json:
                return jsonify({'status': 'error', 'message': msg}), 500
            flash(msg, 'danger')
            return render_template('register.html', name=name, student_id=student_id, email=email), 500

    return render_template('register.html')


@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    """
    Dedicated Administrator Login Portal.
    Restricts access strictly to verified Admin accounts.
    """
    if request.method == 'GET' and 'user_id' in session:
        if session.get('user_role') == 'Admin':
            return redirect(url_for('admin_dashboard'))
        return redirect(url_for('student_dashboard'))

    if request.method == 'POST':
        data = request.get_json(silent=True) or request.form
        email = str(data.get('email', '')).strip().lower()
        password = str(data.get('password', ''))

        if not email or not password:
            msg = "Please provide your administrator email and password."
            if request.is_json:
                return jsonify({'status': 'error', 'message': msg}), 400
            flash(msg, 'danger')
            return render_template('admin_login.html', email=email), 400

        user = verify_user_credentials(email, password)
        if not user:
            msg = "Invalid administrator credentials. Please check your email and password."
            if request.is_json:
                return jsonify({'status': 'error', 'message': msg}), 401
            flash(msg, 'danger')
            return render_template('admin_login.html', email=email), 401

        # STRICT ROLE CHECK: Reject if user is not an Admin
        if user['role'] != 'Admin':
            msg = "Access denied: This account does not have administrative privileges."
            if request.is_json:
                return jsonify({'status': 'error', 'message': msg}), 403
            flash(msg, 'danger')
            return render_template('admin_login.html', email=email), 403

        # Establish admin session
        session.clear()
        session['user_id'] = user['id']
        session['user_name'] = user['name']
        session['user_email'] = user['email']
        session['user_role'] = 'Admin'
        session['student_id'] = None
        session.permanent = True

        next_url = request.args.get('next') or data.get('next')
        redirect_target = next_url if (next_url and next_url.startswith('/admin')) else url_for('admin_dashboard')

        if request.is_json:
            return jsonify({
                'status': 'success',
                'message': f"Welcome, Administrator {user['name']}!",
                'user': user,
                'redirect_url': redirect_target
            }), 200

        flash(f"Welcome to the Administrative Portal, {user['name']}!", 'success')
        return redirect(redirect_target)

    return render_template('admin_login.html')


@app.route('/logout', methods=['GET', 'POST'])
def logout():
    """
    Logs out the current user by destroying the session.
    """
    session.clear()
    flash("You have been successfully signed out.", 'info')
    if request.is_json:
        return jsonify({'status': 'success', 'message': 'Logged out successfully.'}), 200
    return redirect(url_for('home'))


@app.route('/dashboard')
@app.route('/student/dashboard')
@login_required
def student_dashboard():
    """
    Protected Student Portal.
    Displays personalized tickets, profile metrics, and quick reporting shortcuts.
    """
    student_email = session.get('user_email')
    student_tickets = get_tickets_by_student_email(student_email)

    total_tickets = len(student_tickets)
    pending_count = sum(1 for t in student_tickets if t['status'] in ['Pending', 'Open'])
    in_progress_count = sum(1 for t in student_tickets if t['status'] == 'In Progress')
    resolved_count = sum(1 for t in student_tickets if t['status'] in ['Resolved', 'Closed'])

    return render_template(
        'student_dashboard.html',
        tickets=student_tickets,
        total_tickets=total_tickets,
        pending_count=pending_count,
        in_progress_count=in_progress_count,
        resolved_count=resolved_count,
        active_page='my_reports'
    )


@app.route('/admin')
@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    """
    Protected Campus Administrator Dashboard.
    Provides complete ticket overview, status management, and statistics.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, ticket_number, student_name, student_id, email,
               category, subject, description, priority, status, created_at, updated_at
        FROM tickets
        ORDER BY id DESC
    """)
    all_tickets = [dict(row) for row in cursor.fetchall()]
    conn.close()

    total_tickets = len(all_tickets)
    open_tickets = sum(1 for t in all_tickets if t['status'] in ['Open', 'Pending'])
    in_progress_tickets = sum(1 for t in all_tickets if t['status'] == 'In Progress')
    resolved_tickets = sum(1 for t in all_tickets if t['status'] in ['Resolved', 'Closed'])

    # Fetch all Lost & Found items with unmasked contact details for administrative action
    all_lf_items = get_lost_found_items(include_contact=True)
    total_lf = len(all_lf_items)
    lost_count = sum(1 for item in all_lf_items if item.get('item_type') == 'Lost')
    found_count = sum(1 for item in all_lf_items if item.get('item_type') == 'Found')
    claimed_count = sum(1 for item in all_lf_items if item.get('status') in ['Claimed', 'Resolved', 'Returned'])

    return render_template(
        'admin_dashboard.html',
        tickets=all_tickets,
        total_tickets=total_tickets,
        open_tickets=open_tickets,
        in_progress_tickets=in_progress_tickets,
        resolved_tickets=resolved_tickets,
        lost_found_items=all_lf_items,
        total_lf=total_lf,
        lost_count=lost_count,
        found_count=found_count,
        claimed_count=claimed_count,
        active_page='admin'
    )


@app.errorhandler(403)
def forbidden_error(e):
    """
    Custom 403 Forbidden handler.
    """
    if request.path.startswith('/api/'):
        return jsonify({
            'status': 'error',
            'message': 'Access denied: You do not have permissions to access this resource.'
        }), 403
    return render_template('403.html'), 403



# ============================================================================
# API Diagnostics & Live Stats Routes
# ============================================================================

@app.route('/api/health')
def api_health():
    """
    Health check API endpoint.
    Preserved from Phase 1.
    """
    health_data = check_db_health()
    status_code = 200 if health_data.get('healthy') else 500
    return jsonify(health_data), status_code


@app.route('/api/stats')
def api_stats():
    """
    Live dashboard summary statistics API endpoint.
    Returns real-time report counts and status breakdowns from SQLite.
    """
    dashboard_data = get_dashboard_data()
    return jsonify(dashboard_data), 200


@app.route('/api/tickets', methods=['GET', 'POST'])
def api_tickets():
    """
    Dedicated endpoint for student helpdesk tickets.
    - POST: Validates required fields, generates a unique ticket number,
      and inserts a new ticket into SQLite using parameterized SQL. Returns HTTP 201.
    - GET: Returns all tickets in descending order of ID. Returns HTTP 200.
    """
    if request.method == 'POST':
        try:
            data = request.get_json(silent=True)
            if not data or not isinstance(data, dict):
                return jsonify({
                    'status': 'error',
                    'message': 'Invalid request format. Expected JSON body.'
                }), 400

            # Validate required fields
            required_fields = {
                'student_name': 'Student Full Name',
                'student_id': 'Student / Roll ID',
                'email': 'College Email ID',
                'category': 'Issue Category',
                'subject': 'Issue Subject',
                'description': 'Detailed Description'
            }

            missing = []
            for field, label in required_fields.items():
                val = data.get(field)
                if val is None or not str(val).strip():
                    missing.append(label)

            if missing:
                return jsonify({
                    'status': 'error',
                    'message': f"Please complete all required fields: {', '.join(missing)}.",
                    'missing_fields': missing
                }), 400

            # Validate email address
            email = str(data.get('email', '')).strip()
            if '@' not in email or '.' not in email or len(email) < 5:
                return jsonify({
                    'status': 'error',
                    'message': 'Please provide a valid college email address.',
                    'field': 'email'
                }), 400

            # Validate priority
            priority = str(data.get('priority', 'Medium')).strip()
            if priority not in ['Low', 'Medium', 'High', 'Urgent']:
                priority = 'Medium'

            student_name = str(data.get('student_name', '')).strip()
            student_id = str(data.get('student_id', '')).strip()
            category = str(data.get('category', '')).strip()
            subject = str(data.get('subject', '')).strip()
            description = str(data.get('description', '')).strip()
            location = str(data.get('location', '')).strip() if data.get('location') else None

            # Insert ticket into SQLite safely with parameterized queries
            ticket = create_ticket(
                student_name=student_name,
                student_id=student_id,
                email=email,
                category=category,
                subject=subject,
                description=description,
                priority=priority,
                location=location,
                status='Pending'
            )

            if not ticket:
                return jsonify({
                    'status': 'error',
                    'message': 'Failed to save ticket into the database.'
                }), 500

            return jsonify({
                'status': 'success',
                'message': f"Ticket {ticket['ticket_number']} logged successfully.",
                'ticket_number': ticket['ticket_number'],
                'ticket': ticket
            }), 201

        except Exception as e:
            print(f"[ERROR] API /api/tickets POST failure: {e}")
            return jsonify({
                'status': 'error',
                'message': 'A database or server error occurred while processing your ticket. Please try again.'
            }), 500

    # GET method: return all tickets
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, ticket_number, student_name, student_id, email,
                   category, subject, description, priority, status, created_at
            FROM tickets
            ORDER BY id DESC
        """)
        tickets = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return jsonify({
            'status': 'success',
            'count': len(tickets),
            'tickets': tickets
        }), 200
    except Exception as e:
        print(f"[ERROR] API /api/tickets GET failure: {e}")
        return jsonify({
            'status': 'error',
            'message': 'Could not fetch tickets from database.'
        }), 500


# ============================================================================
# Lost & Found API Endpoints (Phase 4)
# ============================================================================

@app.route('/api/lost-found', methods=['GET', 'POST'])
def api_lost_found():
    """
    Dedicated endpoint to list and report Lost & Found items.
    Supports JSON and multipart/form-data for optional photo uploads.
    - GET: Query and filter items by type, category, status, or keyword search.
      Never exposes private contact email/phone in public catalog listings.
    - POST: Validates required fields, secure file upload (optional photo), and inserts into SQLite.
    """
    if request.method == 'POST':
        try:
            if request.content_type and 'multipart/form-data' in request.content_type:
                data = request.form.to_dict()
            else:
                data = request.get_json(silent=True) or request.form.to_dict()

            if not data or not isinstance(data, dict):
                return jsonify({
                    'status': 'error',
                    'message': 'Invalid request format.'
                }), 400

            # Required fields validation
            required_fields = {
                'item_type': 'Item Type (Lost or Found)',
                'item_name': 'Item Name',
                'category': 'Category',
                'location': 'Location',
                'description': 'Description',
                'contact_name': 'Contact Name',
                'contact_email': 'Contact Email'
            }

            missing = []
            for field, label in required_fields.items():
                val = data.get(field)
                if val is None or not str(val).strip():
                    missing.append(label)

            if missing:
                return jsonify({
                    'status': 'error',
                    'message': f"Please complete all required fields: {', '.join(missing)}.",
                    'missing_fields': missing
                }), 400

            # Validate item_type
            raw_type = str(data.get('item_type', '')).strip().capitalize()
            if raw_type not in ['Lost', 'Found']:
                return jsonify({
                    'status': 'error',
                    'message': "Item type must be either 'Lost' or 'Found'."
                }), 400

            # Validate contact_email
            email = str(data.get('contact_email', '')).strip()
            if '@' not in email or '.' not in email or len(email) < 5:
                return jsonify({
                    'status': 'error',
                    'message': 'Please provide a valid contact email address.'
                }), 400

            # Handle optional photo upload securely
            image_path = None
            if 'photo' in request.files:
                file = request.files['photo']
                if file and file.filename:
                    orig_filename = secure_filename(file.filename)
                    ext = os.path.splitext(orig_filename)[1].lower()
                    if ext in ['.png', '.jpg', '.jpeg', '.webp']:
                        unique_filename = f"lf_{uuid.uuid4().hex[:12]}{ext}"
                        upload_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                        file.save(upload_path)
                        image_path = f"/static/uploads/{unique_filename}"
                    else:
                        return jsonify({
                            'status': 'error',
                            'message': 'Invalid photo format. Only JPG, PNG, and WebP images are allowed.'
                        }), 400
            elif data.get('image_path'):
                image_path = str(data.get('image_path')).strip()

            # Date reported (default to current date if missing or empty)
            date_reported = str(data.get('date_reported', '')).strip()
            if not date_reported:
                date_reported = date.today().strftime('%Y-%m-%d')

            item_name = str(data.get('item_name', '')).strip()
            category = str(data.get('category', '')).strip()
            location = str(data.get('location', '')).strip()
            description = str(data.get('description', '')).strip()
            contact_name = str(data.get('contact_name', '')).strip()
            contact_phone = str(data.get('contact_phone', '')).strip() if data.get('contact_phone') else ''
            status = str(data.get('status', 'Active')).strip().capitalize()
            if status not in ['Active', 'Open', 'Claimed', 'Resolved', 'Returned', 'Matched', 'Closed']:
                status = 'Active'

            # Insert into SQLite safely with parameterized queries
            item = create_lost_found_item(
                item_type=raw_type,
                item_name=item_name,
                category=category,
                location=location,
                date_reported=date_reported,
                description=description,
                contact_name=contact_name,
                contact_email=email,
                contact_phone=contact_phone,
                status=status,
                image_path=image_path
            )

            if not item:
                return jsonify({
                    'status': 'error',
                    'message': 'Failed to save item to the database.'
                }), 500

            # Mask contact details in response for privacy
            safe_item = dict(item)
            if 'contact_email' in safe_item and safe_item['contact_email']:
                em = safe_item['contact_email']
                u, d = em.split('@', 1)
                safe_item['contact_email'] = f"{u[0]}***{u[-1]}@{d}" if len(u) > 2 else f"{u[0]}*@{d}"
            if 'contact_phone' in safe_item and safe_item['contact_phone']:
                ph = safe_item['contact_phone']
                safe_item['contact_phone'] = ph[:3] + ' *** ' + ph[-2:] if len(ph) >= 6 else '***'

            return jsonify({
                'status': 'success',
                'message': f"Item '{item['item_name']}' reported successfully in the campus directory.",
                'item': safe_item
            }), 201

        except ValueError as ve:
            return jsonify({'status': 'error', 'message': str(ve)}), 400
        except Exception as e:
            print(f"[ERROR] API /api/lost-found POST failure: {e}")
            return jsonify({
                'status': 'error',
                'message': 'A database error occurred while recording the lost and found item.'
            }), 500

    # GET: List items with search and filtering
    try:
        item_type = request.args.get('type') or request.args.get('item_type')
        category = request.args.get('category')
        status = request.args.get('status')
        search = request.args.get('q') or request.args.get('search')

        # Privacy: include_contact is False to prevent exposing student contact details
        items = get_lost_found_items(
            item_type=item_type,
            category=category,
            status=status,
            search=search,
            include_contact=False
        )

        return jsonify({
            'status': 'success',
            'count': len(items),
            'items': items
        }), 200

    except Exception as e:
        print(f"[ERROR] API /api/lost-found GET failure: {e}")
        return jsonify({
            'status': 'error',
            'message': 'Could not fetch lost and found items.'
        }), 500


@app.route('/api/lost-found/<int:item_id>', methods=['GET'])
def api_get_lost_found_item(item_id):
    """
    View a single lost and found item by ID.
    Returns masked contact details for privacy and inquiry guidance.
    """
    try:
        item = get_lost_found_item_by_id(item_id, mask_contact=True)
        if not item:
            return jsonify({
                'status': 'error',
                'message': f'Lost & Found item with ID {item_id} not found.'
            }), 404

        return jsonify({
            'status': 'success',
            'item': item
        }), 200

    except Exception as e:
        print(f"[ERROR] API /api/lost-found/{item_id} GET failure: {e}")
        return jsonify({
            'status': 'error',
            'message': 'A server error occurred while retrieving item details.'
        }), 500


@app.route('/api/dashboard/stats', methods=['GET'])
def api_dashboard_stats():
    """
    JSON API returning genuine real-time database telemetry for the futuristic dashboard.
    Zero fabricated statistics.
    """
    try:
        data = get_dashboard_data()
        return jsonify({
            'status': 'success',
            'stats': {
                'total_lost_items': data.get('total_lost_items', 0),
                'total_found_items': data.get('total_found_items', 0),
                'active_reports': data.get('active_reports', 0),
                'matched_returned_items': data.get('matched_returned_items', 0),
                'total_reports': data.get('total_reports', 0),
                'resolved_reports': data.get('resolved_reports', 0),
                'categories_count': 12
            },
            'system_status': 'ONLINE',
            'security_level': 'OPTIMAL'
        }), 200
    except Exception as e:
        print(f"[ERROR] API /api/dashboard/stats failure: {e}")
        return jsonify({'status': 'error', 'message': 'Could not fetch telemetry stats.'}), 500


# ============================================================================
# Authentication & Role-Based Access Control API Endpoints
# ============================================================================

@app.route('/api/auth/register', methods=['POST'])
def api_auth_register():
    """JSON API endpoint for student account registration."""
    return register()


@app.route('/api/auth/login', methods=['POST'])
def api_auth_login():
    """JSON API endpoint for student login."""
    return login()


@app.route('/api/auth/admin-login', methods=['POST'])
def api_auth_admin_login():
    """JSON API endpoint for administrator login."""
    return admin_login()


@app.route('/api/auth/logout', methods=['POST'])
def api_auth_logout():
    """JSON API endpoint for session termination."""
    session.clear()
    return jsonify({
        'status': 'success',
        'message': 'Logged out successfully.'
    }), 200


@app.route('/api/auth/me', methods=['GET'])
def api_auth_me():
    """
    Returns current authenticated user information.
    Protected: returns HTTP 401 if unauthenticated.
    """
    if 'user_id' not in session:
        return jsonify({
            'status': 'error',
            'message': 'Not authenticated.'
        }), 401

    return jsonify({
        'status': 'success',
        'user': {
            'id': session.get('user_id'),
            'name': session.get('user_name'),
            'email': session.get('user_email'),
            'role': session.get('user_role'),
            'student_id': session.get('student_id')
        }
    }), 200


@app.route('/api/student/tickets', methods=['GET'])
@login_required
def api_student_tickets():
    """
    Returns tickets submitted by the logged-in student.
    Protected: Requires user authentication.
    """
    email = session.get('user_email')
    tickets = get_tickets_by_student_email(email)
    return jsonify({
        'status': 'success',
        'count': len(tickets),
        'tickets': tickets
    }), 200


@app.route('/api/admin/tickets', methods=['GET'])
@admin_required
def api_admin_tickets():
    """
    Returns all tickets for administrative management with filtering and search.
    Protected: Strictly restricted to Admin role (returns 403 for students).
    """
    status_filter = request.args.get('status')
    category_filter = request.args.get('category')
    search = request.args.get('q')

    conn = get_db_connection()
    cursor = conn.cursor()
    query = """
        SELECT id, ticket_number, student_name, student_id, email,
               category, subject, description, priority, status, created_at, updated_at
        FROM tickets WHERE 1=1
    """
    params = []
    if status_filter and status_filter.lower() != 'all':
        norm_s = 'In Progress' if status_filter.lower() == 'in progress' else status_filter.capitalize()
        query += " AND status = ?"
        params.append(norm_s)
    if category_filter and category_filter.lower() != 'all':
        query += " AND category = ?"
        params.append(category_filter)
    if search:
        kw = f"%{search.strip()}%"
        query += " AND (ticket_number LIKE ? OR student_name LIKE ? OR student_id LIKE ? OR subject LIKE ? OR description LIKE ?)"
        params.extend([kw, kw, kw, kw, kw])

    query += " ORDER BY id DESC"
    cursor.execute(query, tuple(params))
    tickets = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return jsonify({
        'status': 'success',
        'count': len(tickets),
        'tickets': tickets
    }), 200


@app.route('/api/admin/tickets/<int:ticket_id>/status', methods=['POST', 'PATCH'])
@admin_required
def api_admin_update_ticket_status(ticket_id):
    """
    Updates the status of a specific ticket in SQLite.
    Protected: Strictly restricted to Admin role (returns 403 for students).
    """
    data = request.get_json(silent=True) or request.form
    new_status = data.get('status') if isinstance(data, dict) else None
    if not new_status:
        return jsonify({
            'status': 'error',
            'message': 'New status is required in request body.'
        }), 400

    try:
        updated_ticket = update_ticket_status(ticket_id, new_status)
        if not updated_ticket:
            return jsonify({
                'status': 'error',
                'message': f"Ticket with ID {ticket_id} was not found."
            }), 404

        return jsonify({
            'status': 'success',
            'message': f"Ticket #{updated_ticket['ticket_number']} status updated to {updated_ticket['status']}.",
            'ticket': updated_ticket
        }), 200
    except ValueError as ve:
        return jsonify({'status': 'error', 'message': str(ve)}), 400
    except Exception as e:
        print(f"[ERROR] Failed to update ticket #{ticket_id} status: {e}")
        return jsonify({
            'status': 'error',
            'message': 'Failed to update ticket status in database.'
        }), 500


@app.route('/api/admin/lost-found', methods=['GET'])
@admin_required
def api_admin_get_lost_found():
    """
    Retrieves all Lost & Found records for administrators, including full student contact details.
    Protected: Strictly restricted to Admin role.
    """
    item_type = request.args.get('type') or request.args.get('item_type')
    category = request.args.get('category')
    status = request.args.get('status')
    search = request.args.get('q') or request.args.get('search')

    items = get_lost_found_items(
        item_type=item_type,
        category=category,
        status=status,
        search=search,
        include_contact=True
    )
    return jsonify({
        'status': 'success',
        'count': len(items),
        'items': items
    }), 200


@app.route('/api/admin/lost-found/<int:item_id>/status', methods=['POST', 'PATCH'])
@admin_required
def api_admin_update_lost_found_status(item_id):
    """
    Updates the status of a specific Lost & Found item in SQLite (e.g. Active -> Claimed).
    Protected: Strictly restricted to Admin role.
    """
    data = request.get_json(silent=True) or request.form
    new_status = data.get('status') if isinstance(data, dict) else None
    if not new_status:
        return jsonify({
            'status': 'error',
            'message': 'New status is required in request body.'
        }), 400

    try:
        updated_item = update_lost_found_status(item_id, new_status)
        if not updated_item:
            return jsonify({
                'status': 'error',
                'message': f"Lost & Found item with ID {item_id} was not found."
            }), 404

        return jsonify({
            'status': 'success',
            'message': f"Item '{updated_item['item_name']}' status updated to {updated_item['status']}.",
            'item': updated_item
        }), 200
    except ValueError as ve:
        return jsonify({'status': 'error', 'message': str(ve)}), 400
    except Exception as e:
        print(f"[ERROR] Failed to update Lost & Found item #{item_id} status: {e}")
        return jsonify({
            'status': 'error',
            'message': 'Failed to update item status in database.'
        }), 500


@app.route('/api/client-report', methods=['POST'])

def client_report():
    """
    Receives viewport layout telemetry and overflow diagnostics from automated browser checks.
    """
    import json
    from flask import request
    data = request.get_json(silent=True) or {}
    report_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'overflow_report.json')
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
    return jsonify({'status': 'received', 'data': data}), 200


# ============================================================================
# Development Server Runner
# ============================================================================

if __name__ == '__main__':
    print("=" * 65)
    print(" CampusConnect – Smart Campus Helpdesk & Lost-and-Found Portal")
    print(" College Mini Project: Phase 2 (Modern UI & Student Dashboard)")
    print(" Server running locally at: http://127.0.0.1:5000/")
    print("=" * 65)

    # Run the local Flask development server
    app.run(host='127.0.0.1', port=5000, debug=True)
