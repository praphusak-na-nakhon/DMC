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
        user_id: str | None = None,
        events: list[dict[str, Any]],
    ) -> None:
        with connect(self.sqlite_path) as connection:
            now = utc_now()
            connection.executemany(
                """
                INSERT INTO telemetry_events (
                    user_id, event, app_version, payload_json, created_at
                    )
                    VALUES (?, ?, ?, ?, ?)
                    """,
                [
                    (
                        user_id,
                        str(event["event"]),
                        event.get("app_version"),
                        json.dumps(event, ensure_ascii=False),
                        now,
                    )
                    for event in events
                ],
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
                SELECT *
                FROM telemetry_events
                ORDER BY id ASC
                """
            ).fetchall()
        events: list[dict[str, Any]] = []
        for row in rows:
            data = dict(row)
            events.append(
                {
                    "user_id": data.get("user_id"),
                    "event": data["event"],
                    "app_version": data["app_version"],
                    "payload": json.loads(data["payload_json"]),
                }
            )
        return events
