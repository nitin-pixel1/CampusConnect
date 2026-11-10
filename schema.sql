-- CampusConnect Database Schema
-- Safe initialization: Uses CREATE TABLE IF NOT EXISTS to prevent data loss or duplicate tables

-- Table 1: Student Helpdesk Tickets (Supports Phase 2 & beyond)
CREATE TABLE IF NOT EXISTS tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_number TEXT UNIQUE NOT NULL,
    student_name TEXT NOT NULL,
    student_id TEXT NOT NULL,
    email TEXT NOT NULL,
    category TEXT NOT NULL,
    subject TEXT NOT NULL,
    description TEXT NOT NULL,
    priority TEXT DEFAULT 'Medium',
    status TEXT DEFAULT 'Open',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table 2: Lost & Found Items (Supports Phase 3 & beyond)
CREATE TABLE IF NOT EXISTS lost_found_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_type TEXT NOT NULL,          -- 'Lost' or 'Found'
    item_name TEXT NOT NULL,
    category TEXT NOT NULL,
    location TEXT NOT NULL,
    date_reported TEXT NOT NULL,
    description TEXT,
    contact_name TEXT NOT NULL,
    contact_email TEXT NOT NULL,
    contact_phone TEXT,
    status TEXT DEFAULT 'Active',      -- 'Active', 'Open', 'Claimed', 'Resolved', 'Returned', 'Matched', 'Closed'
    image_path TEXT DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table 3: System Status & Metadata (Confirms DB initialization in Phase 1)
CREATE TABLE IF NOT EXISTS system_status (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key_name TEXT UNIQUE NOT NULL,
    value_text TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table 4: Users (Authentication & RBAC - Students & Admins)
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    student_id TEXT,                    -- Required for students, optional/null for admins
    email TEXT UNIQUE NOT NULL,          -- Unique constraint on college email
    password_hash TEXT NOT NULL,         -- Secure Werkzeug scrypt/pbkdf2 password hash
    role TEXT NOT NULL DEFAULT 'Student',-- 'Student' or 'Admin'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

