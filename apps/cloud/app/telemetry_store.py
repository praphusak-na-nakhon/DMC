from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import settings
from .db import connect, utc_now


class TelemetryStore:
    def __init__(self, sqlite_path: str | None = None) -> None:
        self.sqlite_path = Path(sqlite_path or settings.sqlite_path)

    def save_batch(
        self,
        *,
        license_key: str | None,
        user_id: str | None = None,
        device_id: str | None,
        events: list[dict[str, Any]],
    ) -> None:
        with connect(self.sqlite_path) as connection:
            for event in events:
                connection.execute(
                """
                INSERT INTO telemetry_events (
                    license_key, device_id, event, app_version, payload_json, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        license_key,
                        device_id,
                        str(event["event"]),
                        event.get("app_version"),
                        json.dumps(event, ensure_ascii=False),
                        utc_now(),
                    ),
                )

    def count(self) -> int:
        with connect(self.sqlite_path) as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS total FROM telemetry_events",
            ).fetchone()
        return int(row["total"]) if row is not None else 0

    def list_events(self) -> list[dict[str, Any]]:
        with connect(self.sqlite_path) as connection:
            rows = connection.execute(
                """
                SELECT license_key, device_id, event, app_version, payload_json
                FROM telemetry_events
                ORDER BY id ASC
                """
            ).fetchall()
        return [
            {
                "license_key": row["license_key"],
                "device_id": row["device_id"],
                "event": row["event"],
                "app_version": row["app_version"],
                "payload": json.loads(row["payload_json"]),
            }
            for row in rows
        ]
