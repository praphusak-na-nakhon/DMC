from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from .job_store import JobStore
from .license_store import LicenseStore


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
            raise RuntimeError("JOB_CANCELLED")
        self._pause_event.wait()
        if self._cancel_event.is_set():
            raise RuntimeError("JOB_CANCELLED")

    @property
    def needs_auth(self) -> bool:
        return self._auth_waiting


@dataclass
class JobSnapshot:
    job_id: str
    module: str
    status: str
    processed: int = 0
    total: int | None = None
    succeeded: int = 0
    failed: int = 0
    current_page: int | None = None
    needs_auth: bool = False
    auth_reason: str | None = None
    report_path: str | None = None
    stopped_item: dict[str, Any] | None = None


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
    license_store: LicenseStore
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
        license_store: LicenseStore,
        emit_notification: Callable[[dict[str, Any]], None],
    ) -> None:
        self.job_store = job_store
        self.license_store = license_store
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
    ) -> None:
        with self._lock:
            if job_id in self._jobs:
                raise RuntimeError("JOB_ALREADY_RUNNING")

            control = JobControl()
            snapshot = JobSnapshot(job_id=job_id, module=module_name, status="running")
            context = JobContext(
                job_id=job_id,
                options=options,
                emit_event=self.emit_notification,
                control=control,
                job_store=self.job_store,
                license_store=self.license_store,
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
        active = self._require_active_job(job_id)
        active.control.pause()
        active.snapshot.status = "paused"
        self.job_store.set_status(job_id, "paused")

    def resume_job(self, job_id: str) -> None:
        active = self._require_active_job(job_id)
        active.control.resume()
        active.snapshot.status = "running"
        active.snapshot.needs_auth = False
        self.job_store.set_status(job_id, "running")

    def cancel_job(self, job_id: str) -> None:
        active = self._require_active_job(job_id)
        active.control.cancel()
        active.snapshot.status = "cancelled"
        self.job_store.set_status(job_id, "cancelled")

    def get_runtime_status(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            active = self._jobs.get(job_id)
        if active is None:
            return None
        snapshot = active.snapshot
        return {
            "job_id": snapshot.job_id,
            "module": snapshot.module,
            "status": snapshot.status,
            "processed": snapshot.processed,
            "total": snapshot.total,
            "succeeded": snapshot.succeeded,
            "failed": snapshot.failed,
            "current_page": snapshot.current_page,
            "needs_auth": snapshot.needs_auth,
            "auth_reason": snapshot.auth_reason,
            "report_path": snapshot.report_path,
            "stopped_item": snapshot.stopped_item,
        }

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
        except Exception as exc:  # pragma: no cover - background defensive path
            code = str(exc)
            checkpoint = context.job_store.load_checkpoint(context.job_id)
            if code == "JOB_CANCELLED":
                context.snapshot.status = "cancelled"
                self.job_store.set_status(context.job_id, "cancelled")
            else:
                context.snapshot.status = "failed"
                self.job_store.mark_failed(
                    context.job_id,
                    checkpoint=checkpoint,
                    finished_at=utc_now(),
                )
                self.emit_notification(
                    {
                        "type": "error",
                        "job_id": context.job_id,
                        "code": code,
                        "message": str(exc),
                    }
                )
        finally:
            with self._lock:
                self._jobs.pop(context.job_id, None)

    def _require_active_job(self, job_id: str) -> ActiveJob:
        with self._lock:
            active = self._jobs.get(job_id)
        if active is None:
            raise RuntimeError("JOB_NOT_FOUND")
        return active


def build_event_notification(payload: dict[str, Any]) -> str:
    return json.dumps(
        {
            "jsonrpc": "2.0",
            "method": "event",
            "params": payload,
        },
        ensure_ascii=False,
    )
