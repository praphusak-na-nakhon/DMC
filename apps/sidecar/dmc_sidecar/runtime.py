from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from .account_client import capture_credits, release_credits
from .account_store import AccountSessionStore
from .errors import DomainError
from .job_store import JobStore
from .telemetry import TelemetryClient

PAUSABLE_STATUSES = {"running"}
RESUMABLE_STATUSES = {"paused"}
CANCELLABLE_STATUSES = {"running", "paused"}
TERMINAL_STATUSES = {"done", "failed", "cancelled", "stopped_on_review"}


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class JobControl:
    def __init__(self) -> None:
        self._pause_event = threading.Event()
        self._pause_event.set()
        self._cancel_event = threading.Event()
        self._auth_waiting = False
        self._lock = threading.Lock()

    def pause(self) -> None:
        with self._lock:
            self._pause_event.clear()

    def resume(self) -> None:
        with self._lock:
            self._auth_waiting = False
            self._pause_event.set()

    def request_auth(self) -> None:
        with self._lock:
            self._auth_waiting = True
            self._pause_event.clear()

    def cancel(self) -> None:
        self._cancel_event.set()
        self._pause_event.set()

    def wait_point(self) -> None:
        if self._cancel_event.is_set():
            raise DomainError("JOB_CANCELLED")
        self._pause_event.wait()
        if self._cancel_event.is_set():
            raise DomainError("JOB_CANCELLED")

    @property
    def needs_auth(self) -> bool:
        return self._auth_waiting


@dataclass
class JobSnapshot:
    job_id: str
    module: str
    status: str
    source_file: str = ""
    processed: int = 0
    total: int | None = None
    succeeded: int = 0
    failed: int = 0
    current_page: int | None = None
    needs_auth: bool = False
    auth_reason: str | None = None
    report_path: str | None = None
    review_report_path: str | None = None
    stopped_item: dict[str, Any] | None = None
    started_at: str | None = None
    finished_at: str | None = None
    level_label: str | None = None
    credit_reservation_id: str | None = None
    credits_reserved: int = 0
    credits_captured: int = 0
    credits_refunded: int = 0
    credit_status: str | None = None


@dataclass
class ActiveJob:
    job_id: str
    module: str
    thread: threading.Thread
    control: JobControl
    snapshot: JobSnapshot


@dataclass
class JobContext:
    job_id: str
    options: dict[str, object]
    emit_event: Callable[[dict[str, Any]], None]
    control: JobControl
    job_store: JobStore
    account_store: AccountSessionStore
    snapshot: JobSnapshot

    def emit_progress(self) -> None:
        self.emit_event(
            {
                "type": "progress",
                "job_id": self.job_id,
                "processed": self.snapshot.processed,
                "total": self.snapshot.total,
                "succeeded": self.snapshot.succeeded,
                "failed": self.snapshot.failed,
                "current_page": self.snapshot.current_page,
                "needs_auth": self.snapshot.needs_auth,
                "auth_reason": self.snapshot.auth_reason,
            }
        )

    def emit_record_done(self, row: int, status: str) -> None:
        self.emit_event(
            {
                "type": "record_done",
                "job_id": self.job_id,
                "row": row,
                "status": status,
            }
        )

    def emit_needs_auth(self, reason: str) -> None:
        self.snapshot.needs_auth = True
        self.emit_event(
            {
                "type": "needs_auth",
                "job_id": self.job_id,
                "reason": reason,
            }
        )


class JobManager:
    def __init__(
        self,
        *,
        job_store: JobStore,
        account_store: AccountSessionStore,
        telemetry: TelemetryClient,
        emit_notification: Callable[[dict[str, Any]], None],
    ) -> None:
        self.job_store = job_store
        self.account_store = account_store
        self.telemetry = telemetry
        self.emit_notification = emit_notification
        self._jobs: dict[str, ActiveJob] = {}
        self._lock = threading.Lock()

    def start_job(
        self,
        *,
        job_id: str,
        module_name: str,
        excel_path: Path,
        options: dict[str, object],
        credit_reservation_id: str | None = None,
        credits_reserved: int = 0,
    ) -> None:
        with self._lock:
            if job_id in self._jobs:
                raise DomainError("JOB_ALREADY_RUNNING")

            control = JobControl()
            snapshot = JobSnapshot(
                job_id=job_id,
                module=module_name,
                status="running",
                source_file=str(excel_path),
                credit_reservation_id=credit_reservation_id,
                credits_reserved=credits_reserved,
                credit_status="reserved" if credit_reservation_id else None,
            )
            context = JobContext(
                job_id=job_id,
                options=options,
                emit_event=self.emit_notification,
                control=control,
                job_store=self.job_store,
                account_store=self.account_store,
                snapshot=snapshot,
            )
            thread = threading.Thread(
                target=self._run_job,
                name=f"dmc-job-{job_id}",
                args=(module_name, excel_path, context),
                daemon=True,
            )
            self._jobs[job_id] = ActiveJob(
                job_id=job_id,
                module=module_name,
                thread=thread,
                control=control,
                snapshot=snapshot,
            )
            thread.start()

    def pause_job(self, job_id: str) -> None:
        with self._lock:
            active = self._jobs.get(job_id)
            if active is None:
                raise DomainError("JOB_NOT_FOUND")
            updated = self.job_store.set_status_if_current(
                job_id,
                "paused",
                current_statuses=PAUSABLE_STATUSES,
            )
            if not updated:
                raise DomainError("JOB_NOT_ACTIVE")
            active.snapshot.status = "paused"
        active.control.pause()

    def resume_job(self, job_id: str) -> None:
        with self._lock:
            active = self._jobs.get(job_id)
            if active is None:
                raise DomainError("JOB_NOT_FOUND")
            updated = self.job_store.set_status_if_current(
                job_id,
                "running",
                current_statuses=RESUMABLE_STATUSES,
            )
            if not updated:
                raise DomainError("JOB_NOT_ACTIVE")
            active.snapshot.status = "running"
            active.snapshot.needs_auth = False
            active.snapshot.auth_reason = None
        active.control.resume()

    def cancel_job(self, job_id: str) -> None:
        with self._lock:
            active = self._jobs.get(job_id)
            if active is None:
                raise DomainError("JOB_NOT_FOUND")
            updated = self.job_store.set_status_if_current(
                job_id,
                "cancelled",
                current_statuses=CANCELLABLE_STATUSES,
            )
            if not updated:
                raise DomainError("JOB_NOT_ACTIVE")
            active.snapshot.status = "cancelled"
        active.control.cancel()

    def get_runtime_status(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            active = self._jobs.get(job_id)
        if active is None:
            return None
        snapshot = active.snapshot
        persisted = self.job_store.get_status(job_id) or {}
        status = (
            persisted.get("status")
            if persisted.get("status") in TERMINAL_STATUSES
            else snapshot.status
        )
        return {
            "job_id": snapshot.job_id,
            "module": snapshot.module,
            "status": status,
            "source_file": snapshot.source_file or persisted.get("source_file", ""),
            "processed": snapshot.processed,
            "total": snapshot.total,
            "succeeded": snapshot.succeeded,
            "failed": snapshot.failed,
            "current_page": snapshot.current_page,
            "needs_auth": snapshot.needs_auth,
            "auth_reason": snapshot.auth_reason,
            "report_path": snapshot.report_path or persisted.get("report_path"),
            "review_report_path": snapshot.review_report_path or persisted.get("review_report_path"),
            "stopped_item": snapshot.stopped_item,
            "started_at": snapshot.started_at or persisted.get("started_at"),
            "finished_at": snapshot.finished_at or persisted.get("finished_at"),
            "level_label": snapshot.level_label or persisted.get("level_label"),
            "run_summary": persisted.get("run_summary"),
            "credit_reservation_id": snapshot.credit_reservation_id or persisted.get("credit_reservation_id"),
            "credits_reserved": snapshot.credits_reserved or persisted.get("credits_reserved", 0),
            "credits_captured": snapshot.credits_captured or persisted.get("credits_captured", 0),
            "credits_refunded": snapshot.credits_refunded or persisted.get("credits_refunded", 0),
            "credit_status": snapshot.credit_status or persisted.get("credit_status"),
        }

    def runtime_statuses(self) -> list[dict[str, Any]]:
        with self._lock:
            job_ids = list(self._jobs.keys())
        return [status for job_id in job_ids if (status := self.get_runtime_status(job_id)) is not None]

    def _run_job(self, module_name: str, excel_path: Path, context: JobContext) -> None:
        try:
            from .modules import get_module

            module = get_module(module_name)
            module.start_job(
                job_id=context.job_id,
                excel_path=excel_path,
                options=context.options,
                context=context,
            )
            status = self.job_store.get_status(context.job_id)
            if status is not None and status["status"] == "done":
                self._finalize_credits(context, status)
                self.telemetry.record_job_completed(
                    module=module_name,
                    total=int(status["total"] or 0),
                    succeeded=int(status["succeeded"]),
                    failed=int(status["failed"]),
                    duration_sec=_duration_seconds(status["started_at"], status["finished_at"]),
                )
            elif status is not None and status["status"] in {"failed", "cancelled", "stopped_on_review"}:
                self._finalize_credits(context, status)
        except Exception as exc:  # pragma: no cover - background defensive path
            code = str(exc)
            checkpoint = context.job_store.load_checkpoint(context.job_id)
            if code == "JOB_CANCELLED":
                context.snapshot.status = "cancelled"
                self.job_store.set_status(context.job_id, "cancelled")
                status = self.job_store.get_status(context.job_id) or {}
                self._finalize_credits(context, status)
            else:
                context.snapshot.status = "failed"
                self.job_store.mark_failed(
                    context.job_id,
                    checkpoint=checkpoint,
                    finished_at=utc_now(),
                )
                status = self.job_store.get_status(context.job_id) or {}
                self._finalize_credits(context, status)
                self.emit_notification(
                    {
                        "type": "error",
                        "job_id": context.job_id,
                        "code": code,
                        "message": str(exc),
                    }
                )
                self.telemetry.record_job_failed(
                    module=module_name,
                    error_code=code,
                    processed=context.snapshot.processed,
                )
        finally:
            with self._lock:
                self._jobs.pop(context.job_id, None)

    def _require_active_job(self, job_id: str) -> ActiveJob:
        with self._lock:
            active = self._jobs.get(job_id)
        if active is None:
            raise DomainError("JOB_NOT_FOUND")
        return active

    def _finalize_credits(self, context: JobContext, status: dict[str, Any]) -> None:
        reservation_id = context.snapshot.credit_reservation_id or status.get("credit_reservation_id")
        reserved = int(context.snapshot.credits_reserved or status.get("credits_reserved") or 0)
        if not reservation_id or reserved <= 0:
            return

        summary = status.get("run_summary") if isinstance(status.get("run_summary"), dict) else None
        if status.get("status") == "done" and summary is not None:
            capture_units = int(summary.get("applied_rows") or status.get("succeeded") or 0)
        else:
            capture_units = int(status.get("succeeded") or context.snapshot.succeeded or 0)
        capture_units = max(0, min(capture_units, reserved))
        release_units = max(reserved - capture_units, 0)

        try:
            if capture_units:
                capture_result = capture_credits(
                    context.account_store,
                    reservation_id=str(reservation_id),
                    units=capture_units,
                    idempotency_key=f"{context.job_id}:capture",
                )
                context.snapshot.credits_captured = capture_result.units_captured
            if release_units:
                release_result = release_credits(
                    context.account_store,
                    reservation_id=str(reservation_id),
                    units=release_units,
                    idempotency_key=f"{context.job_id}:release",
                )
                context.snapshot.credits_refunded = release_result.units_released
            context.snapshot.credit_status = "finalized"
            self.job_store.update_credit_status(
                context.job_id,
                credits_captured=capture_units,
                credits_refunded=release_units,
                credit_status="finalized",
            )
        except DomainError as exc:
            context.snapshot.credit_status = f"finalize_failed:{exc.code}"
            self.job_store.update_credit_status(
                context.job_id,
                credit_status=context.snapshot.credit_status,
            )
            self.emit_notification(
                {
                    "type": "sidecar_stderr",
                    "message": f"credit finalize failed: {exc.code}",
                }
            )


def build_event_notification(payload: dict[str, Any]) -> str:
    return json.dumps(
        {
            "jsonrpc": "2.0",
            "method": "event",
            "params": payload,
        },
        ensure_ascii=True,
    )


def _duration_seconds(started_at: str | None, finished_at: str | None) -> int:
    if not started_at or not finished_at:
        return 0
    try:
        started = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
        finished = datetime.fromisoformat(finished_at.replace("Z", "+00:00"))
    except ValueError:
        return 0
    return max(0, int((finished - started).total_seconds()))
