# CampusConnect – Smart Campus Helpdesk & Lost-and-Found Portal

**CampusConnect** is a full-stack college web application designed to provide an automated, centralized platform for university campus administration, student grievance redressal, community asset recovery, and role-based access management.

---

## 🔐 Phase 5: Authentication & Role-Based Access Control (RBAC)

Phase 5 implements a complete, production-grade security architecture:
- **Student Registration & Login:** Dedicated registration (`/register`) and login (`/login`) workflows with client-side & server-side validation.
- **Role Enforcement:** Public registration strictly provisions `Student` accounts. Server-side role assignment ensures no privilege escalation or role forgery.
- **Cryptographic Password Hashing:** All credentials are hashed securely using **Werkzeug scrypt hashing** (`generate_password_hash` & `check_password_hash`). Plaintext passwords are never stored in the database.
- **Separate Administrator Portal:** Distinct Admin login portal (`/admin/login`) with customized administrative theming and strict server-side role validation.
- **Role-Based Access Control (RBAC):**
  - `@login_required`: Restricts protected user endpoints and views to authenticated sessions.
  - `@admin_required`: Strictly verifies that `session['user_role'] == 'Admin'`. Unauthorized student attempts to access admin endpoints are blocked with HTTP `403 Forbidden`.
- **Administrative Ticket Management Center (`/admin/dashboard`):** Allows campus staff and facilities coordinators to review all campus tickets, filter by status or category, and dynamically update ticket resolution statuses (`Pending`, `In Progress`, `Resolved`) directly in SQLite with real-time toast feedback.
- **Personalized Student Dashboard (`/student/dashboard`):** Displays tickets submitted under the student's account with status breakdowns and immediate shortcuts.
- **Secure Flask Sessions:** Configured with `SECRET_KEY`, `SESSION_COOKIE_HTTPONLY=True`, and `SESSION_COOKIE_SAMESITE='Lax'`.

---

## 🛠️ Technology Stack

- **Backend:** Python (Flask 3.1)
- **Security & Hashing:** Werkzeug Security (`scrypt`)
- **Database:** SQLite3 (`campus_connect.db`) with parameterized queries
- **Frontend:** Semantic HTML5, Vanilla CSS3 (Design Tokens, Grid & Flexbox), Vanilla JavaScript (ES6+)
- **Server:** Flask Local Development Server

---

## 📂 Project Directory Structure

```text
project 1/
│
├── app.py                     # Flask backend with routes, RBAC decorators & JSON APIs
├── database.py                # SQLite connection, CRUD helpers, user & password hashing functions
├── create_admin.py            # Secure CLI script for provisioning administrators
├── schema.sql                 # Database schema with safe CREATE TABLE IF NOT EXISTS
├── requirements.txt           # Python dependency specifications
├── README.md                  # Comprehensive project documentation & run instructions
│
├── templates/                 # Jinja2 HTML templates
│   ├── base.html              # Shared base layout, responsive navbar, auth badges & modals
│   ├── index.html             # Campus portal home page & live metrics overview
│   ├── login.html             # Student login page with show/hide password toggle
│   ├── register.html          # Student registration page with full validation
│   ├── admin_login.html       # Separate administrative portal login
│   ├── admin_dashboard.html   # Admin ticket control center & status management
│   ├── student_dashboard.html # Personalized student dashboard & ticket tracker
│   ├── lost_found.html        # Complete Lost & Found directory & search
│   ├── my_reports.html        # Public recent reports feed
│   └── 403.html               # Custom 403 Forbidden security error page
│
├── static/                    # Static web assets
│   ├── css/
│   │   └── style.css          # Modern blue/white theme, auth cards & responsive styles
│   └── js/
│       └── main.js            # Frontend logic: auth, tickets, Lost & Found, modals
│
└── tests/                     # Automated Test Suites
    ├── test_auth_rbac.py      # 18 automated tests for Auth, Registration, Login & RBAC
    ├── test_phase3_tickets.py # 7 automated tests for Issue Reporting backend
    ├── test_phase4_lost_found.py # 14 automated tests for Lost & Found backend
    └── test_frontend_auth_cdp.py # End-to-end browser tests via Chrome DevTools Protocol
```

---

## 🚀 How to Set Up and Run Locally

### Prerequisites
- Python 3.8 or higher installed on your computer (`py --version`).
- Standard terminal (PowerShell, Command Prompt, or Bash).

### Step 1: Open the Project Directory
```powershell
cd "d:\PROJECTS\project 1"
```

### Step 2: Install Required Dependencies
```powershell
py -m pip install -r requirements.txt
```

### Step 3: Securely Provision the First Administrator
Admins cannot be created through the public registration form. Use `create_admin.py` to provision an admin safely:

```powershell
# Option A: Create a pre-configured demo administrator
py create_admin.py --demo

# Option B: Interactive prompt (masks password input)
py create_admin.py --email admin@university.edu --name "Campus Registrar"

# Option C: Command-line arguments
py create_admin.py --email admin@campus.edu --password "Admin@Campus2026!" --name "Campus Administrator"

# Option D: Using environment variables
$env:ADMIN_EMAIL="admin@campus.edu"
$env:ADMIN_PASSWORD="YourSecurePassword123!"
py create_admin.py
```

*Demo Admin Credentials:*
- **Email:** `admin@campus.edu`
- **Password:** `Admin@Campus2026!`

### Step 4: Run the Flask Application
```powershell
py app.py
```

### Step 5: Open in Your Web Browser
Visit:
👉 **[http://127.0.0.1:5000](http://127.0.0.1:5000)**

---

## 🌐 Application URLs & Workflows

| Page / Endpoint | URL | Description | Access Level |
|---|---|---|---|
| **Home Portal** | `http://127.0.0.1:5000/` | Public overview, live campus stats & reports | Public |
| **Student Sign In** | `http://127.0.0.1:5000/login` | Student login page with show/hide password | Public |
| **Student Registration** | `http://127.0.0.1:5000/register` | Student account registration | Public |
| **Admin Sign In** | `http://127.0.0.1:5000/admin/login` | Separate administrator login portal | Public |
| **Student Dashboard** | `http://127.0.0.1:5000/student/dashboard` | Student ticket history & quick actions | Student / Admin |
| **Admin Control Center** | `http://127.0.0.1:5000/admin/dashboard` | Ticket management & live status updates | **Admin Only** |
| **Lost & Found Hub** | `http://127.0.0.1:5000/lost-found` | Item directory, search & reporting | Public |
| **Sign Out** | `http://127.0.0.1:5000/logout` | Destroys session and redirects to login | Authenticated |

---

## 🧪 Running the Automated Test Suites

CampusConnect includes comprehensive automated test suites covering all system layers:

### 1. Authentication & Role-Based Access Control Tests
```powershell
py test_auth_rbac.py
```
*Validates:* Missing registration fields, invalid email format, short password, password mismatch, role forgery rejection, duplicate email prevention, Werkzeug password hashing in SQLite, invalid credentials, student login, `/api/auth/me`, unauthenticated access blocking, student blocked from admin endpoints (HTTP 403), student login on admin portal (HTTP 403), administrator login, ticket status modification, logout, and test cleanup.

### 2. Phase 3 Issue Reporting Backend Tests
```powershell
py test_phase3_tickets.py
```
*Validates:* Field validation, parameterized insertion, unique ticket generation (`CC-TKT-XXXX`), SQLite persistence, and test record cleanup.

### 3. Phase 4 Lost & Found Backend Tests
```powershell
py test_phase4_lost_found.py
```
*Validates:* Lost & Found item creation, search, type and category filters, privacy redaction of contact details, and database persistence.

### 4. End-to-End Browser Tests (Chrome DevTools Protocol)
```powershell
py test_frontend_auth_cdp.py
```
*Validates:* Browser rendering, password show/hide DOM toggling, live student registration and login, session redirection, admin login, and ticket status changes in the live UI.

---

## 🔒 Security Architecture Highlights

1. **Password Hashing:** `werkzeug.security.generate_password_hash(..., method='scrypt')` ensures industry-standard resistance against brute-force and rainbow table attacks.
2. **SQL Injection Prevention:** 100% of database interactions use parameterized queries (`?` placeholders).
3. **Session Hardening:** Flask sessions utilize HttpOnly cookies, SameSite protection, and cryptographic signing.
4. **Privilege Separation:** Public registration assigns `role = 'Student'` directly in backend code; user-submitted role parameters are strictly ignored.
5. **Route Protection:** Decorators check `session.get('user_role')` on every protected request. Attempting to bypass the UI by typing `/admin/dashboard` or calling `/api/admin/*` yields an explicit `403 Forbidden`.
6. **Data Privacy:** Lost & Found item listings automatically omit reporter email and phone numbers from public JSON and templates.
