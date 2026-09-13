from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Any

from dmc_sidecar import config
from dmc_sidecar.checkpoint import JobCheckpoint
from dmc_sidecar.job_store import JobStore
from dmc_sidecar.modules.dry_run_review import pause_for_dry_run_review, should_pause_for_dry_run_review
from dmc_sidecar.runtime import ActiveJob, JobContext, JobControl, JobManager, JobSnapshot


def _wait_until(assertion, *, timeout: float = 3.0) -> None:  # noqa: ANN001
    deadline = time.time() + timeout
    last_error: AssertionError | None = None
    while time.time() < deadline:
        try:
            assertion()
            return
        except AssertionError as exc:
            last_error = exc
            time.sleep(0.02)
    if last_error is not None:
        raise last_error
    raise AssertionError("Timed out waiting for assertion.")


def test_should_pause_for_dry_run_review_only_for_visible_dry_runs() -> None:
    assert should_pause_for_dry_run_review({"dry_run": True}) is True
    assert should_pause_for_dry_run_review({"dry_run": True, "headless": True}) is False
    assert should_pause_for_dry_run_review({"dry_run": False}) is False
    assert should_pause_for_dry_run_review({"dry_run": True, "keep_browser_open_after_dry_run": False}) is False


def test_pause_for_dry_run_review_waits_until_resume(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(config, "default_data_dir", lambda: tmp_path)
    job_id = "job-dry-run-review"
    events: list[dict[str, Any]] = []
    store = JobStore()
    store.create_pending_job(job_id, "graduation", "source.xlsx")
    checkpoint = JobCheckpoint.initial(level_label="ม.3", base_url="https://example.test")
    checkpoint.processed = 2
    checkpoint.succeeded = 2
    store.mark_running(job_id, total_records=2, checkpoint=checkpoint, started_at="2026-05-17T00:00:00Z")
    control = JobControl()
    context = JobContext(
        job_id=job_id,
        options={"dry_run": True},
        emit_event=events.append,
        control=control,
        job_store=store,
        snapshot=JobSnapshot(job_id=job_id, module="graduation", status="running", processed=2, total=2, succeeded=2),
    )

    thread = threading.Thread(
        target=lambda: pause_for_dry_run_review(
            context=context,
            checkpoint=checkpoint,
            module_name="graduation",
            page_url="https://example.test/page",
            current_page=2,
        ),
        daemon=True,
    )
    thread.start()

    _wait_until(lambda: assert_event_emitted(events))
    status = store.get_status(job_id)
    assert status is not None
    assert status["status"] == "paused"
    assert status["stopped_item"]["reason"] == "dry_run_review"
    assert thread.is_alive()

    control.resume()
    thread.join(timeout=3)

    assert not thread.is_alive()
    status = store.get_status(job_id)
    assert status is not None
    assert status["status"] == "running"
    assert status["stopped_item"] is None


def test_resume_job_is_idempotent_when_active_job_is_already_running(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(config, "default_data_dir", lambda: tmp_path)
    job_id = "job-resume-idempotent"
    store = JobStore()
    store.create_pending_job(job_id, "graduation", "source.xlsx")
    checkpoint = JobCheckpoint.initial(level_label="ม.3", base_url="https://example.test")
    store.mark_running(job_id, total_records=1, checkpoint=checkpoint, started_at="2026-05-17T00:00:00Z")
    control = JobControl()
    control.pause()
    snapshot = JobSnapshot(job_id=job_id, module="graduation", status="paused", source_file="source.xlsx")
    manager = JobManager(
        job_store=store,
        emit_notification=lambda _payload: None,
    )
    manager._jobs[job_id] = ActiveJob(
        job_id=job_id,
        module="graduation",
        thread=threading.Thread(target=lambda: None),
        control=control,
        snapshot=snapshot,
    )

    manager.resume_job(job_id)

    status = store.get_status(job_id)
    assert status is not None
    assert status["status"] == "running"
    assert snapshot.status == "running"


def assert_event_emitted(events: list[dict[str, Any]]) -> None:
    assert any(event.get("type") == "job_stopped" and event.get("status") == "paused" for event in events)
