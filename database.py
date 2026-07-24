"""
database.py - SQLite database operations
Smart Attendance System with Facial Recognition

Tables:
  users                 - Stores registered users and their face encodings
  attendance            - Stores attendance records with timestamps
  notification_settings - Stores email/SMS notification credentials
"""

import sqlite3
import numpy as np
import pickle
import logging
from typing import Optional
from datetime import date, datetime
from config import DB_PATH

logger = logging.getLogger(__name__)


# ── Schema Initialization ────────────────────────────────────────────────────

def init_db():
    """Create database tables if they do not already exist."""
    conn = get_connection()
    cursor = conn.cursor()

    # Users table: stores name, unique ID, and serialized face encoding
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     TEXT    NOT NULL UNIQUE,
            name        TEXT    NOT NULL,
            department  TEXT    DEFAULT '',
            photo_path  TEXT    DEFAULT '',
            encoding    BLOB,                        -- Pickled NumPy array
            created_at  TEXT    DEFAULT (datetime('now','localtime'))
        )
    """)

    # Attendance table: one row per check-in event
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS attendance (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     TEXT    NOT NULL,
            name        TEXT    NOT NULL,
            date        TEXT    NOT NULL,
            time        TEXT    NOT NULL,
            status      TEXT    DEFAULT 'Present',
            marked_at   TEXT    DEFAULT (datetime('now','localtime')),
            lat         REAL,
            lng         REAL,
            verified    BOOLEAN
        )
    """)

    # Try adding columns if table already existed without them
    try:
        cursor.execute("ALTER TABLE attendance ADD COLUMN lat REAL")
        cursor.execute("ALTER TABLE attendance ADD COLUMN lng REAL")
        cursor.execute("ALTER TABLE attendance ADD COLUMN verified BOOLEAN")
    except sqlite3.OperationalError:
        pass  # Columns likely already exist


    # Notification settings table: one row per key-value config entry
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS notification_settings (
            key    TEXT PRIMARY KEY,
            value  TEXT DEFAULT ''
        )
    """)

    # Insert default keys if they don't exist yet
    default_keys = [
        "email_enabled", "smtp_host", "smtp_port", "sender_email",
        "sender_pass", "recipient_email",
        "sms_enabled", "twilio_sid", "twilio_token", "twilio_from", "twilio_to",
    ]
    defaults = {
        "email_enabled": "0", "smtp_host": "smtp.gmail.com",
        "smtp_port": "587", "sms_enabled": "0",
    }
    for key in default_keys:
        cursor.execute(
            "INSERT OR IGNORE INTO notification_settings (key, value) VALUES (?, ?)",
            (key, defaults.get(key, ""))
        )

    conn.commit()
    conn.close()
    logger.info("Database initialized at: %s", DB_PATH)


# ── Connection Helper ────────────────────────────────────────────────────────

def get_connection():
    """Return a new SQLite connection with row_factory for dict-like access."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row   # Allows column access by name
    return conn


# ── User Operations ──────────────────────────────────────────────────────────

def register_user(user_id: str, name: str, department: str,
                  photo_path: str, encoding: np.ndarray) -> bool:
    """
    Register a new user with their face encoding.

    Args:
        user_id:    Unique student/employee ID (e.g. "EMP001")
        name:       Full name
        department: Department or class
        photo_path: Path to saved face photo
        encoding:   128-d NumPy face encoding from face_recognition

    Returns:
        True on success, False if user_id already exists
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Serialize NumPy array to bytes for BLOB storage
        encoding_blob = pickle.dumps(encoding)

        cursor.execute("""
            INSERT INTO users (user_id, name, department, photo_path, encoding)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, name, department, photo_path, encoding_blob))

        conn.commit()
        conn.close()
        logger.info("Registered user: %s (%s)", name, user_id)
        return True

    except sqlite3.IntegrityError:
        logger.warning("User already exists: %s", user_id)
        return False
    except Exception as e:
        logger.error("Error registering user: %s", e)
        return False


def update_user_encoding(user_id: str, encoding: np.ndarray) -> bool:
    """Update face encoding for an existing user (re-registration)."""
    try:
        conn = get_connection()
        encoding_blob = pickle.dumps(encoding)
        conn.execute(
            "UPDATE users SET encoding = ? WHERE user_id = ?",
            (encoding_blob, user_id)
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error("Error updating encoding: %s", e)
        return False


def get_all_users() -> list:
    """
    Fetch all registered users with their decoded face encodings.

    Returns:
        List of dicts: {user_id, name, department, photo_path, encoding}
    """
    conn = get_connection()
    rows = conn.execute(
        "SELECT user_id, name, department, photo_path, encoding FROM users"
    ).fetchall()
    conn.close()

    users = []
    for row in rows:
        enc = pickle.loads(row["encoding"]) if row["encoding"] else None
        users.append({
            "user_id":    row["user_id"],
            "name":       row["name"],
            "department": row["department"],
            "photo_path": row["photo_path"],
            "encoding":   enc,
        })
    return users


def get_user_count() -> int:
    """Return total number of registered users."""
    conn = get_connection()
    count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    conn.close()
    return count


def get_user_by_id(user_id: str) -> Optional[dict]:
    """Fetch a single user record (without encoding) by user_id."""
    conn = get_connection()
    row = conn.execute(
        "SELECT user_id, name, department, photo_path FROM users WHERE user_id = ?",
        (user_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def delete_user(user_id: str) -> bool:
    """Delete a user and all their attendance records."""
    try:
        conn = get_connection()
        conn.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM attendance WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error("Error deleting user: %s", e)
        return False


# ── Attendance Operations ────────────────────────────────────────────────────

def is_already_marked(user_id: str, today: str = None) -> bool:
    """
    Check if a user has already been marked Present today.

    Args:
        user_id: User's unique ID
        today:   Date string YYYY-MM-DD (defaults to today)

    Returns:
        True if attendance already recorded for today
    """
    if today is None:
        today = date.today().isoformat()

    conn = get_connection()
    row = conn.execute(
        "SELECT id FROM attendance WHERE user_id = ? AND date = ?",
        (user_id, today)
    ).fetchone()
    conn.close()
    return row is not None


def mark_attendance(user_id: str, name: str, status: str = "Present", lat: float = None, lng: float = None, verified: bool = None) -> dict:
    """
    Insert an attendance record for a user (duplicate-safe).

    Args:
        user_id: User's unique ID
        name:    User's full name
        status:  'Present' or 'Late'
        lat:     Latitude
        lng:     Longitude
        verified: Whether location is verified

    Returns:
        dict with 'success', 'message', 'already_marked' keys
    """
    today = date.today().isoformat()
    now   = datetime.now().strftime("%H:%M:%S")

    # Prevent duplicate entries for the same day
    if is_already_marked(user_id, today):
        return {
            "success":        True,
            "already_marked": True,
            "message":        f"{name} already marked for today",
        }

    try:
        conn = get_connection()
        conn.execute("""
            INSERT INTO attendance (user_id, name, date, time, status, lat, lng, verified)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (user_id, name, today, now, status, lat, lng, verified))
        conn.commit()
        conn.close()

        logger.info("Attendance marked: %s (%s) at %s %s", name, user_id, today, now)
        return {
            "success":        True,
            "already_marked": False,
            "message":        f"Attendance marked for {name}",
            "time":           now,
            "date":           today,
        }
    except Exception as e:
        logger.error("Error marking attendance: %s", e)
        return {"success": False, "already_marked": False, "message": str(e)}


def get_attendance_logs(filter_date: str = None, filter_name: str = None) -> list:
    """
    Retrieve attendance records with optional filters.

    Args:
        filter_date: 'YYYY-MM-DD' to filter by a specific date
        filter_name: Partial name match filter

    Returns:
        List of dicts with all attendance fields
    """
    conn   = get_connection()
    query  = "SELECT * FROM attendance WHERE 1=1"
    params = []

    if filter_date:
        query  += " AND date = ?"
        params.append(filter_date)

    if filter_name:
        query  += " AND name LIKE ?"
        params.append(f"%{filter_name}%")

    query += " ORDER BY date DESC, time DESC"
    rows  = conn.execute(query, params).fetchall()
    conn.close()

    return [dict(row) for row in rows]


def get_today_count() -> int:
    """Return number of successful attendance records for today."""
    today = date.today().isoformat()
    conn  = get_connection()
    count = conn.execute(
        "SELECT COUNT(*) FROM attendance WHERE date = ? AND status = 'Present'", (today,)
    ).fetchone()[0]
    conn.close()
    return count


def get_recent_activity(limit: int = 10) -> list:
    """Return the most recent attendance entries for the dashboard."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT name, user_id, date, time, status FROM attendance ORDER BY id DESC LIMIT ?",
        (limit,)
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


# ── Notification Settings ─────────────────────────────────────────────────────

def get_notification_settings() -> dict:
    """
    Fetch all notification settings as a flat dict.

    Returns:
        dict with all keys from notification_settings table.
        Boolean-like keys ('email_enabled', 'sms_enabled') are
        returned as Python booleans.
    """
    conn = get_connection()
    rows = conn.execute("SELECT key, value FROM notification_settings").fetchall()
    conn.close()

    settings = {row["key"]: row["value"] for row in rows}

    # Convert string booleans to actual booleans
    for bool_key in ("email_enabled", "sms_enabled"):
        settings[bool_key] = settings.get(bool_key, "0") in ("1", "true", "True")

    return settings


def save_notification_settings(updates: dict) -> bool:
    """
    Persist notification settings to the database.

    Args:
        updates: dict of {key: value} pairs to upsert

    Returns:
        True on success
    """
    try:
        conn = get_connection()
        for key, value in updates.items():
            # Convert booleans to string "1"/"0" for storage
            if isinstance(value, bool):
                value = "1" if value else "0"
            conn.execute(
                "INSERT OR REPLACE INTO notification_settings (key, value) VALUES (?, ?)",
                (key, str(value))
            )
        conn.commit()
        conn.close()
        logger.info("Notification settings saved: %s", list(updates.keys()))
        return True
    except Exception as e:
        logger.error("Error saving notification settings: %s", e)
        return False
