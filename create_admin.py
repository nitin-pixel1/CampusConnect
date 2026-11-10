"""
CampusConnect - Secure Administrator Provisioning Utility
Allows initializing or updating campus administrator accounts safely
using command-line flags, environment variables, or interactive input.
Passwords are encrypted using Werkzeug scrypt/pbkdf2 hashing before storage.
"""

import sys
import os
import argparse
import getpass

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import init_admin_user, init_db

def main():
    parser = argparse.ArgumentParser(
        description="Provision a CampusConnect Administrator account with secure password hashing."
    )
    parser.add_argument("--name", type=str, default=None, help="Administrator Full Name (e.g. 'Campus Admin')")
    parser.add_argument("--email", type=str, default=None, help="Administrator College Email (e.g. admin@campus.edu)")
    parser.add_argument("--password", type=str, default=None, help="Administrator Password (min 6 characters)")
    parser.add_argument("--demo", action="store_true", help="Quick setup with standard demonstration administrator credentials")

    args = parser.parse_args()

    # Ensure DB schema is ready
    init_db()

    name = args.name
    email = args.email
    password = args.password

    # Check for demo flag
    if args.demo:
        name = name or "Campus Administrator"
        email = email or "admin@campus.edu"
        password = password or "Admin@Campus2026!"
        print("[SETUP] Using demo administrator configuration.")

    # Check environment variables fallback
    if not email:
        email = os.environ.get("ADMIN_EMAIL")
    if not password:
        password = os.environ.get("ADMIN_PASSWORD")
    if not name:
        name = os.environ.get("ADMIN_NAME", "Campus Administrator")

    # If still not provided, ask interactively
    if not email:
        try:
            print("\n--- CampusConnect Secure Admin Account Setup ---")
            name = input("Administrator Name [Campus Administrator]: ").strip() or "Campus Administrator"
            email = input("Administrator College Email: ").strip()
            if not email:
                print("[ERROR] Email is required.")
                sys.exit(1)
            password = getpass.getpass("Administrator Password (min 6 characters): ")
            confirm = getpass.getpass("Confirm Password: ")
            if password != confirm:
                print("[ERROR] Passwords do not match.")
                sys.exit(1)
        except (KeyboardInterrupt, EOFError):
            print("\nSetup cancelled.")
            sys.exit(1)

    if not password or len(password) < 6:
        print("[ERROR] Password must be at least 6 characters in length.")
        sys.exit(1)

    try:
        admin = init_admin_user(name=name, email=email, password=password)
        if admin:
            print("=" * 60)
            print(" [SUCCESS] Campus Administrator Account Configured!")
            print(f" Name:  {admin['name']}")
            print(f" Email: {admin['email']}")
            print(f" Role:  {admin['role']}")
            print(" Password safely encrypted with Werkzeug hashing.")
            print("=" * 60)
        else:
            print("[ERROR] Failed to provision administrator account.")
            sys.exit(1)
    except Exception as e:
        print(f"[ERROR] Administrator provisioning failed: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
