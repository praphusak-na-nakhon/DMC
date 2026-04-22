from __future__ import annotations

import uuid

from .db import connect


DEVICE_ID_KEY = "device_id"


def get_or_create_device_id() -> str:
    with connect() as connection:
        row = connection.execute(
            "SELECT value FROM app_state WHERE key = ?",
            (DEVICE_ID_KEY,),
        ).fetchone()
        if row is not None:
            return str(row["value"])

        device_id = str(uuid.uuid4())
        connection.execute(
            """
            INSERT INTO app_state (key, value)
            VALUES (?, ?)
            """,
            (DEVICE_ID_KEY, device_id),
        )
        return device_id
