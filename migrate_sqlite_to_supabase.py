"""Idempotently migrate the local SQLite database to Supabase."""

import argparse
import pickle
import sqlite3
from pathlib import Path

import numpy as np

from config import DB_PATH
from database import get_client

_BATCH_SIZE = 100


def load_local_data() -> tuple[list, list, list]:
    """Read and validate the SQLite data without modifying the source file."""
    database_uri = f"{Path(DB_PATH).resolve().as_uri()}?mode=ro"
    with sqlite3.connect(database_uri, uri=True) as connection:
        connection.row_factory = sqlite3.Row
        users = []
        for row in connection.execute(
            "SELECT user_id, name, department, photo_path, encoding, created_at FROM users"
        ):
            encoding = None
            if row["encoding"] is not None:
                decoded = pickle.loads(row["encoding"])
                vector = np.asarray(decoded, dtype=float)
                if vector.shape != (128,) or not np.isfinite(vector).all():
                    raise ValueError(
                        f"Invalid face encoding in local user record {row['user_id']!r}"
                    )
                encoding = vector.tolist()
            users.append({
                "user_id": row["user_id"],
                "name": row["name"],
                "department": row["department"] or "",
                "photo_path": row["photo_path"] or "",
                "encoding": encoding,
                "created_at": row["created_at"],
            })

        attendance = [
            {
                "source_id": row["id"],
                "user_id": row["user_id"],
                "name": row["name"],
                "date": row["date"],
                "time": row["time"],
                "status": row["status"] or "Present",
                "marked_at": row["marked_at"],
                "lat": row["lat"],
                "lng": row["lng"],
                "verified": row["verified"],
            }
            for row in connection.execute(
                "SELECT id, user_id, name, date, time, status, marked_at, "
                "lat, lng, verified FROM attendance"
            )
        ]
        settings = [
            {"key": row["key"], "value": row["value"] or ""}
            for row in connection.execute(
                "SELECT key, value FROM notification_settings"
            )
        ]
    return users, attendance, settings


def _upsert_batches(table: str, records: list, conflict_column: str) -> None:
    client = get_client()
    for start in range(0, len(records), _BATCH_SIZE):
        batch = records[start:start + _BATCH_SIZE]
        client.table(table).upsert(
            batch, on_conflict=conflict_column
        ).execute()


def migrate(apply: bool = False) -> None:
    users, attendance, settings = load_local_data()
    print(
        f"Local data: {len(users)} users, {len(attendance)} attendance records, "
        f"{len(settings)} settings."
    )
    if not apply:
        print("Preview only. Re-run with --apply to upload these records.")
        return

    _upsert_batches("users", users, "user_id")
    _upsert_batches("attendance", attendance, "source_id")
    _upsert_batches("notification_settings", settings, "key")

    client = get_client()
    expected = {
        "users": len(users),
        "attendance": len(attendance),
        "notification_settings": len(settings),
    }
    for table, expected_count in expected.items():
        actual_count = (
            client.table(table)
            .select("*", count="exact", head=True)
            .execute()
            .count
        )
        if actual_count != expected_count:
            raise RuntimeError(
                f"Migration verification failed for {table}: "
                f"expected {expected_count} rows, found {actual_count}."
            )
    print("Migration completed and row counts verified.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Upload the local users, face encodings, attendance, and settings.",
    )
    migrate(apply=parser.parse_args().apply)
