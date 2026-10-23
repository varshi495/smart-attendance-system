"""Supabase database operations for users, attendance, and settings."""

import logging
import os
from datetime import date, datetime
from functools import lru_cache
from typing import Optional

import numpy as np
from postgrest.exceptions import APIError
from supabase import Client, create_client
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

_PAGE_SIZE = 1000
load_dotenv()


@lru_cache(maxsize=1)
def get_client() -> Client:
    """Create the server-side Supabase client from environment variables."""
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SECRET_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise RuntimeError(
            "Set SUPABASE_URL and SUPABASE_SECRET_KEY before starting the app. "
            "Use a Supabase secret key only on this trusted server."
        )
    return create_client(url, key)


def init_db() -> None:
    """Verify the remote schema is present and accessible."""
    client = get_client()
    try:
        for table in ("users", "attendance", "notification_settings"):
            client.table(table).select("*").limit(0).execute()
    except APIError as error:
        raise RuntimeError(
            "Supabase is reachable, but the app schema is missing or inaccessible. "
            "Apply supabase/schema.sql to the configured project."
        ) from error
    logger.info("Supabase database connection and schema verified")


def _all_rows(query) -> list:
    rows = []
    offset = 0
    while True:
        batch = query.range(offset, offset + _PAGE_SIZE - 1).execute().data or []
        rows.extend(batch)
        if len(batch) < _PAGE_SIZE:
            return rows
        offset += _PAGE_SIZE


def _encode_face(encoding: Optional[np.ndarray]) -> Optional[list]:
    if encoding is None:
        return None
    return np.asarray(encoding, dtype=float).tolist()


def _decode_face(encoding: Optional[list]) -> Optional[np.ndarray]:
    if encoding is None:
        return None
    return np.asarray(encoding, dtype=float)


def register_user(user_id: str, name: str, department: str,
                  photo_path: str, encoding: np.ndarray) -> bool:
    """Register a user and store the face encoding as a JSON numeric array."""
    client = get_client()
    existing = (
        client.table("users")
        .select("user_id")
        .eq("user_id", user_id)
        .limit(1)
        .execute()
        .data
    )
    if existing:
        logger.warning("User already exists: %s", user_id)
        return False

    try:
        client.table("users").insert({
            "user_id": user_id,
            "name": name,
            "department": department,
            "photo_path": photo_path,
            "encoding": _encode_face(encoding),
        }).execute()
    except APIError as error:
        if error.code == "23505":
            logger.warning("User already exists: %s", user_id)
            return False
        logger.exception("Error registering user %s", user_id)
        raise RuntimeError("Unable to register user in Supabase.") from error

    logger.info("Registered user: %s (%s)", name, user_id)
    return True


def update_user_encoding(user_id: str, encoding: np.ndarray) -> bool:
    """Update the face encoding for an existing user."""
    response = (
        get_client().table("users")
        .update({"encoding": _encode_face(encoding)})
        .eq("user_id", user_id)
        .select("user_id")
        .execute()
    )
    return bool(response.data)


def get_all_users() -> list:
    """Fetch registered users with face encodings decoded as NumPy arrays."""
    rows = _all_rows(
        get_client().table("users")
        .select("user_id, name, department, photo_path, encoding")
        .order("user_id")
    )
    return [
        {
            **row,
            "encoding": _decode_face(row["encoding"]),
        }
        for row in rows
    ]


def get_user_count() -> int:
    response = (
        get_client().table("users")
        .select("user_id", count="exact", head=True)
        .execute()
    )
    return response.count or 0


def get_user_by_id(user_id: str) -> Optional[dict]:
    response = (
        get_client().table("users")
        .select("user_id, name, department, photo_path")
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    return response.data[0] if response.data else None


def delete_user(user_id: str) -> bool:
    """Delete a user's attendance rows and user record."""
    client = get_client()
    try:
        client.table("attendance").delete().eq("user_id", user_id).execute()
        client.table("users").delete().eq("user_id", user_id).execute()
    except APIError as error:
        logger.exception("Error deleting user %s", user_id)
        raise RuntimeError("Unable to delete user from Supabase.") from error
    return True


def is_already_marked(user_id: str, today: str = None) -> bool:
    """Check whether attendance already exists for a user on a given date."""
    if today is None:
        today = date.today().isoformat()
    response = (
        get_client().table("attendance")
        .select("id")
        .eq("user_id", user_id)
        .eq("date", today)
        .limit(1)
        .execute()
    )
    return bool(response.data)


def mark_attendance(user_id: str, name: str, status: str = "Present",
                    lat: float = None, lng: float = None,
                    verified: bool = None) -> dict:
    """Insert an attendance record unless one already exists today."""
    today = date.today().isoformat()
    now = datetime.now().strftime("%H:%M:%S")

    if is_already_marked(user_id, today):
        return {
            "success": True,
            "already_marked": True,
            "message": f"{name} already marked for today",
        }

    try:
        get_client().table("attendance").insert({
            "user_id": user_id,
            "name": name,
            "date": today,
            "time": now,
            "status": status,
            "lat": lat,
            "lng": lng,
            "verified": verified,
        }).execute()
    except APIError as error:
        logger.exception("Error marking attendance for user %s", user_id)
        raise RuntimeError("Unable to mark attendance in Supabase.") from error

    logger.info("Attendance marked: %s (%s) at %s %s", name, user_id, today, now)
    return {
        "success": True,
        "already_marked": False,
        "message": f"Attendance marked for {name}",
        "time": now,
        "date": today,
    }


def get_attendance_logs(filter_date: str = None, filter_name: str = None) -> list:
    """Retrieve attendance records with optional date and partial-name filters."""
    query = get_client().table("attendance").select("*")
    if filter_date:
        query = query.eq("date", filter_date)
    if filter_name:
        query = query.ilike("name", f"%{filter_name}%")
    return _all_rows(query.order("date", desc=True).order("time", desc=True))


def get_today_count() -> int:
    today = date.today().isoformat()
    response = (
        get_client().table("attendance")
        .select("id", count="exact", head=True)
        .eq("date", today)
        .eq("status", "Present")
        .execute()
    )
    return response.count or 0


def get_recent_activity(limit: int = 10) -> list:
    response = (
        get_client().table("attendance")
        .select("name, user_id, date, time, status")
        .order("id", desc=True)
        .limit(limit)
        .execute()
    )
    return response.data or []


def get_notification_settings() -> dict:
    rows = _all_rows(
        get_client().table("notification_settings").select("key, value").order("key")
    )
    settings = {row["key"]: row["value"] for row in rows}
    for bool_key in ("email_enabled", "sms_enabled"):
        settings[bool_key] = settings.get(bool_key, "0") in ("1", "true", "True")
    return settings


def save_notification_settings(updates: dict) -> bool:
    client = get_client()
    try:
        for key, value in updates.items():
            if isinstance(value, bool):
                value = "1" if value else "0"
            client.table("notification_settings").upsert({
                "key": key,
                "value": str(value),
            }).execute()
    except APIError as error:
        logger.exception("Error saving notification settings")
        raise RuntimeError("Unable to save notification settings in Supabase.") from error
    logger.info("Notification settings saved: %s", list(updates.keys()))
    return True
