from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated, Any, Literal
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from .config import secure_cloud_base_url
from .db import connect
from .errors import DomainError
from .license_store import LicenseStore


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class AppStartedEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event: Literal["app_started"]
    ts: str
    app_version: str
    platform: str


class LicenseCheckedEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event: Literal["license_checked"]
    ts: str
    result: str
    offline_mode: bool


class JobCompletedEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event: Literal["job_completed"]
    ts: str
    module: str
    total: int
    succeeded: int
    failed: int
    duration_sec: int


class JobFailedEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event: Literal["job_failed"]
    ts: str
    module: str
    error_code: str
    processed: int


class ConfigUpdatedEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event: Literal["config_updated"]
    ts: str
    module: str
    from_version: str
    to_version: str


TelemetryEvent = Annotated[
    AppStartedEvent
    | LicenseCheckedEvent
    | JobCompletedEvent
    | JobFailedEvent
    | ConfigUpdatedEvent,
    Field(discriminator="event"),
]

TELEMETRY_EVENT_ADAPTER: TypeAdapter[TelemetryEvent] = TypeAdapter(TelemetryEvent)


@dataclass(frozen=True)
class QueuedTelemetryEvent:
    id: int
    payload: dict[str, Any]


class TelemetryStore:
    def enqueue(self, payload: dict[str, Any]) -> int:
        with connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO telemetry_queue (event_json, created_at)
                VALUES (?, ?)
                """,
                (json.dumps(payload, ensure_ascii=False), utc_now()),
            )
            if cursor.lastrowid is None:
                raise RuntimeError("TELEMETRY_QUEUE_INSERT_FAILED")
            return int(cursor.lastrowid)

    def peek_batch(self, limit: int = 20) -> list[QueuedTelemetryEvent]:
        with connect() as connection:
            rows = connection.execute(
                """
                SELECT id, event_json
                FROM telemetry_queue
                ORDER BY id ASC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            QueuedTelemetryEvent(id=int(row["id"]), payload=json.loads(row["event_json"]))
            for row in rows
        ]

    def delete_many(self, ids: list[int]) -> None:
        if not ids:
            return
        placeholders = ", ".join(["?"] * len(ids))
        with connect() as connection:
            connection.execute(
                f"DELETE FROM telemetry_queue WHERE id IN ({placeholders})",
                ids,
            )

    def prune(self, max_items: int) -> None:
        with connect() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS total FROM telemetry_queue",
            ).fetchone()
            total = int(row["total"]) if row is not None else 0
            overflow = total - max_items
            if overflow <= 0:
                return
            connection.execute(
                """
                DELETE FROM telemetry_queue
                WHERE id IN (
                    SELECT id
                    FROM telemetry_queue
                    ORDER BY id ASC
                    LIMIT ?
                )
                """,
                (overflow,),
            )

    def count(self) -> int:
        with connect() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS total FROM telemetry_queue",
            ).fetchone()
        return int(row["total"]) if row is not None else 0


def validate_telemetry_event(payload: dict[str, Any]) -> dict[str, Any]:
    event = TELEMETRY_EVENT_ADAPTER.validate_python(payload)
    return event.model_dump(mode="python")


class TelemetryClient:
    def __init__(
        self,
        *,
        license_store: LicenseStore | None = None,
        store: TelemetryStore | None = None,
        max_queue_size: int = 500,
        background_flush: bool = True,
    ) -> None:
        self.license_store = license_store
        self.store = store or TelemetryStore()
        self.max_queue_size = max_queue_size
        self.background_flush = background_flush
        self._flush_lock = threading.Lock()
        self._background_lock = threading.Lock()
        self._background_flush_active = False

    def record(self, payload: dict[str, Any]) -> None:
        normalized = validate_telemetry_event(payload)
        self.store.enqueue(normalized)
        self.store.prune(self.max_queue_size)
        if self.background_flush:
            self.flush_soon()
        else:
            self.flush()

    def flush_soon(self) -> None:
        try:
            base_url = secure_cloud_base_url()
        except DomainError:
            return
        if not base_url:
            return

        with self._background_lock:
            if self._background_flush_active:
                return
            self._background_flush_active = True

        def worker() -> None:
            try:
                self.flush()
            finally:
                with self._background_lock:
                    self._background_flush_active = False

        thread = threading.Thread(target=worker, name="dmc-telemetry-flush", daemon=True)
        thread.start()

    def flush(self, *, batch_size: int = 20, max_batches: int = 5) -> dict[str, Any]:
        try:
            base_url = secure_cloud_base_url()
        except DomainError as exc:
            return {"status": "error", "sent": 0, "queued": self.store.count(), "last_error": str(exc)}
        if not base_url:
            return {"status": "disabled", "sent": 0, "queued": self.store.count(), "last_error": None}

        if not self._flush_lock.acquire(blocking=False):
            return {"status": "busy", "sent": 0, "queued": self.store.count(), "last_error": None}

        sent = 0
        last_error: str | None = None
        try:
            for _ in range(max_batches):
                batch = self.store.peek_batch(limit=batch_size)
                if not batch:
                    break

                request = Request(
                    f"{base_url}/v1/telemetry",
                    headers={
                        "Accept": "application/json",
                        "Content-Type": "application/json",
                        **self._license_headers(),
                    },
                    data=json.dumps(
                        {"events": [item.payload for item in batch]},
                        ensure_ascii=False,
                    ).encode("utf-8"),
                    method="POST",
                )
                try:
                    with urlopen(request, timeout=10) as response:
                        payload = json.loads(response.read().decode("utf-8"))
                except HTTPError as exc:
                    last_error = f"HTTP_{exc.code}"
                    break
                except URLError:
                    last_error = "TELEMETRY_UNAVAILABLE"
                    break

                accepted = int(payload.get("accepted", 0))
                if accepted != len(batch):
                    last_error = "TELEMETRY_PARTIAL_ACCEPT"
                    break

                self.store.delete_many([item.id for item in batch])
                sent += accepted
        finally:
            self._flush_lock.release()

        status = "ok" if last_error is None else "error"
        return {"status": status, "sent": sent, "queued": self.store.count(), "last_error": last_error}

    def _license_headers(self) -> dict[str, str]:
        if self.license_store is None:
            return {}
        record = self.license_store.get_license()
        if record is None:
            return {}
        return {
            "X-DMC-License-Key": record.license_key,
            "X-DMC-Device-Id": record.device_id,
        }

    def record_app_started(self, *, app_version: str, platform: str) -> None:
        self.record(
            {
                "event": "app_started",
                "ts": utc_now(),
                "app_version": app_version,
                "platform": platform,
            }
        )

    def record_license_checked(self, *, result: str, offline_mode: bool) -> None:
        self.record(
            {
                "event": "license_checked",
                "ts": utc_now(),
                "result": result,
                "offline_mode": offline_mode,
            }
        )

    def record_job_completed(
        self,
        *,
        module: str,
        total: int,
        succeeded: int,
        failed: int,
        duration_sec: int,
    ) -> None:
        self.record(
            {
                "event": "job_completed",
                "ts": utc_now(),
                "module": module,
                "total": total,
                "succeeded": succeeded,
                "failed": failed,
                "duration_sec": duration_sec,
            }
        )

    def record_job_failed(self, *, module: str, error_code: str, processed: int) -> None:
        self.record(
            {
                "event": "job_failed",
                "ts": utc_now(),
                "module": module,
                "error_code": error_code,
                "processed": processed,
            }
        )

    def record_config_updated(self, *, module: str, from_version: str, to_version: str) -> None:
        self.record(
            {
                "event": "config_updated",
                "ts": utc_now(),
                "module": module,
                "from_version": from_version,
                "to_version": to_version,
            }
        )
