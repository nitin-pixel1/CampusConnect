
import sqlite3
from getpass import getpass
from werkzeug.security import generate_password_hash

email = "admin@campus.edu"

password = getpass("Enter NEW admin password: ")
confirm = getpass("Confirm NEW admin password: ")

if not password:
    print("Password cannot be empty.")
elif password != confirm:
    print("Passwords do not match.")
else:
    conn = sqlite3.connect("campus_connect.db")
    cur = conn.cursor()

    cur.execute(
        "UPDATE users SET password_hash = ? WHERE email = ? AND role = ?",
        (generate_password_hash(password), email, "Admin")
    )

    if cur.rowcount == 1:
        conn.commit()
        print("Admin password updated successfully!")
    else:
        conn.rollback()
        print("Admin account not found. No changes made.")

    conn.close()
