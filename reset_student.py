
import sqlite3
from getpass import getpass
from werkzeug.security import generate_password_hash

email = "nitin.nagarajanapn@gmail.com"
student_id = "25it1130"

password = getpass("Enter NEW student password: ")
confirm = getpass("Confirm NEW student password: ")

if not password:
    print("Password cannot be empty.")
elif password != confirm:
    print("Passwords do not match.")
else:
    conn = sqlite3.connect("campus_connect.db")
    cur = conn.cursor()

    cur.execute(
        """UPDATE users SET password_hash = ?
           WHERE email = ? AND student_id = ? AND role = ?""",
        (generate_password_hash(password), email, student_id, "Student")
    )

    if cur.rowcount == 1:
        conn.commit()
        print("Student password updated successfully!")
    else:
        conn.rollback()
        print("Student account not found. No changes made.")

    conn.close()
