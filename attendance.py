"""
attendance.py - Attendance logic, CSV/Excel export
Smart Attendance System with Facial Recognition
"""

import csv
import logging
import os
from datetime import date, datetime

import pandas as pd

from config import CSV_PATH, EXCEL_PATH
from database import (
    mark_attendance as db_mark_attendance,
    get_attendance_logs,
    get_all_users,
)

logger = logging.getLogger(__name__)


# ── Mark Attendance ──────────────────────────────────────────────────────────

def mark_present(user_id: str, name: str, lat: float = None, lng: float = None, verified: bool = None, status: str = "Present") -> dict:
    """
    Mark a recognized user.
    Delegates to database.mark_attendance() which handles duplicates.

    Returns:
        dict with success, already_marked, message, date, time
    """
    result = db_mark_attendance(user_id, name, status=status, lat=lat, lng=lng, verified=verified)
    return result


# ── CSV Export ───────────────────────────────────────────────────────────────

def export_to_csv(filter_date: str = None, filter_name: str = None) -> str:
    """
    Export attendance records to a CSV file.

    Args:
        filter_date: Optional 'YYYY-MM-DD' filter
        filter_name: Optional name filter

    Returns:
        Absolute path to the generated CSV file
    """
    records = get_attendance_logs(filter_date=filter_date, filter_name=filter_name)

    fieldnames = ["id", "user_id", "name", "date", "time", "status", "marked_at", "lat", "lng", "verified"]

    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for record in records:
            # Write only the fields we want
            row = {field: record.get(field, "") for field in fieldnames}
            writer.writerow(row)

    logger.info("Exported %d records to CSV: %s", len(records), CSV_PATH)
    return CSV_PATH


# ── Excel Export ─────────────────────────────────────────────────────────────

def export_to_excel(filter_date: str = None, filter_name: str = None) -> str:
    """
    Export attendance records to an Excel (.xlsx) file with formatting.

    Args:
        filter_date: Optional 'YYYY-MM-DD' filter
        filter_name: Optional name filter

    Returns:
        Absolute path to the generated Excel file
    """
    records = get_attendance_logs(filter_date=filter_date, filter_name=filter_name)

    if not records:
        # Create empty DataFrame with correct columns
        df = pd.DataFrame(columns=["ID", "User ID", "Name", "Date", "Time", "Status", "Marked At", "Lat", "Lng", "Verified"])
    else:
        df = pd.DataFrame(records)
        # Rename columns for the Excel report
        df = df.rename(columns={
            "id":         "ID",
            "user_id":    "User ID",
            "name":       "Name",
            "date":       "Date",
            "time":       "Time",
            "status":     "Status",
            "marked_at":  "Marked At",
            "lat":        "Lat",
            "lng":        "Lng",
            "verified":   "Verified",
        })
        # Reorder columns
        df = df[["ID", "User ID", "Name", "Date", "Time", "Status", "Marked At", "Lat", "Lng", "Verified"]]

    # Write to Excel with formatting via openpyxl
    with pd.ExcelWriter(EXCEL_PATH, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Attendance")

        # Auto-fit column widths
        worksheet = writer.sheets["Attendance"]
        for col in worksheet.columns:
            max_len = max(
                len(str(cell.value)) if cell.value else 0
                for cell in col
            )
            worksheet.column_dimensions[col[0].column_letter].width = min(max_len + 4, 40)

    logger.info("Exported %d records to Excel: %s", len(records), EXCEL_PATH)
    return EXCEL_PATH


# ── Statistics ───────────────────────────────────────────────────────────────

def get_monthly_summary() -> list:
    """
    Get attendance count grouped by date for the current month.

    Returns:
        List of dicts: {date, count}
    """
    records = get_attendance_logs()

    # Group by date
    summary = {}
    for r in records:
        d = r["date"]
        summary[d] = summary.get(d, 0) + 1

    # Sort by date descending
    result = [{"date": k, "count": v} for k, v in sorted(summary.items(), reverse=True)]
    return result[:30]   # Last 30 days


def get_attendance_rate() -> float:
    """
    Compute today's attendance rate as percentage of registered users.

    Returns:
        Float 0.0–100.0
    """
    from database import get_user_count, get_today_count
    total = get_user_count()
    today = get_today_count()

    if total == 0:
        return 0.0
    return round((today / total) * 100, 1)
