from __future__ import annotations

import os
import uuid

from .db import connect


DEVICE_ID_KEY = "device_id"


def get_or_create_device_id() -> str:
    generated_device_id = str(uuid.uuid4())
    with connect() as connection:
        connection.execute(
            """
            INSERT OR IGNORE INTO app_state (key, value)
            VALUES (?, ?)
            """,
            (DEVICE_ID_KEY, generated_device_id),
        )
        row = connection.execute(
            "SELECT value FROM app_state WHERE key = ?",
            (DEVICE_ID_KEY,),
        ).fetchone()
        if row is None:
            raise RuntimeError("DEVICE_ID_UNAVAILABLE")
        return str(row["value"])


def default_device_name() -> str:
    return os.getenv("COMPUTERNAME", "dmc-desktop").strip() or "dmc-desktop"
