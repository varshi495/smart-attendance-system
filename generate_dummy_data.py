"""
generate_dummy_data.py - Generate sample attendance data for testing
Smart Attendance System

Run this AFTER installing dependencies and AFTER registering at least one user.
Or use it standalone to populate the DB with fake records for demo purposes.

Usage:
    python generate_dummy_data.py
"""

import sqlite3
import random
from datetime import date, timedelta
from config import DB_PATH
from database import init_db, get_connection

# ── Sample Users ─────────────────────────────────────────────────────────────
SAMPLE_USERS = [
    {"user_id": "CS001", "name": "Arjun Sharma",   "department": "Computer Science"},
    {"user_id": "CS002", "name": "Priya Patel",    "department": "Computer Science"},
    {"user_id": "EC001", "name": "Rahul Verma",    "department": "Electronics"},
    {"user_id": "ME001", "name": "Anjali Singh",   "department": "Mechanical"},
    {"user_id": "CS003", "name": "Vikram Nair",    "department": "Computer Science"},
    {"user_id": "EC002", "name": "Divya Menon",    "department": "Electronics"},
    {"user_id": "CS004", "name": "Rohan Gupta",    "department": "Computer Science"},
    {"user_id": "ME002", "name": "Sneha Reddy",    "department": "Mechanical"},
]

ATTENDANCE_TIMES = ["09:01:32", "09:14:05", "09:22:41", "09:35:17", "09:42:58",
                    "09:55:03", "10:02:29", "10:11:47"]


def create_dummy_users():
    """Insert sample users WITHOUT face encodings (for demo/testing only)."""
    conn = get_connection()
    inserted = 0

    for u in SAMPLE_USERS:
        try:
            conn.execute("""
                INSERT OR IGNORE INTO users (user_id, name, department, encoding)
                VALUES (?, ?, ?, NULL)
            """, (u["user_id"], u["name"], u["department"]))
            inserted += 1
        except Exception as e:
            print(f"  Skipped {u['user_id']}: {e}")

    conn.commit()
    conn.close()
    print(f"✅ Inserted {inserted} sample users")


def create_dummy_attendance():
    """Generate attendance records for the past 10 days."""
    conn  = get_connection()
    today = date.today()
    count = 0

    for days_back in range(10, 0, -1):
        day = (today - timedelta(days=days_back)).isoformat()

        # Randomly pick 5–8 users to mark present for each day
        daily_attendees = random.sample(SAMPLE_USERS, k=random.randint(5, len(SAMPLE_USERS)))

        for i, user in enumerate(daily_attendees):
            time_str = ATTENDANCE_TIMES[i % len(ATTENDANCE_TIMES)]
            try:
                conn.execute("""
                    INSERT OR IGNORE INTO attendance (user_id, name, date, time, status)
                    VALUES (?, ?, ?, ?, 'Present')
                """, (user["user_id"], user["name"], day, time_str))
                count += 1
            except Exception:
                pass

    conn.commit()
    conn.close()
    print(f"✅ Inserted {count} sample attendance records (past 10 days)")


if __name__ == "__main__":
    print("\n🔧 Generating dummy data for Smart Attendance System...\n")

    # Initialize DB first
    init_db()

    create_dummy_users()
    create_dummy_attendance()

    print("\n✨ Done! Launch the app with:  python app.py")
    print("   Then open: http://localhost:5000\n")
    print("⚠  Note: Dummy users have NO face encodings.")
    print("   They appear in the Report and Dashboard, but")
    print("   facial recognition only works for users registered via the UI.\n")
