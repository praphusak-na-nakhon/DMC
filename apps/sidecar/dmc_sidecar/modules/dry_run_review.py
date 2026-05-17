from __future__ import annotations

from typing import Any

from ..checkpoint import JobCheckpoint
from ..runtime import JobContext


DRY_RUN_REVIEW_REASON = "dry_run_review"


def should_pause_for_dry_run_review(options: dict[str, object]) -> bool:
    keep_open = options.get("keep_browser_open_after_dry_run", True)
    return bool(options.get("dry_run", False)) and not bool(options.get("headless", False)) and keep_open is not False


def pause_for_dry_run_review(
    *,
    context: JobContext,
    checkpoint: JobCheckpoint,
    module_name: str,
    page_url: str | None,
    current_page: int | None = None,
    current_record: int | None = None,
) -> None:
    stopped_item: dict[str, Any] = {
        "reason": DRY_RUN_REVIEW_REASON,
        "message": "Dry run completed. Inspect Chromium, then resume to close the browser and write reports.",
    }
    if page_url:
        stopped_item["page_url"] = page_url
    if current_page is not None:
        stopped_item["current_page"] = current_page
    if current_record is not None:
        stopped_item["current_record"] = current_record

    checkpoint.awaiting_auth = False
    checkpoint.auth_reason = None
    checkpoint.stopped_item = stopped_item
    context.snapshot.status = "paused"
    context.snapshot.needs_auth = False
    context.snapshot.auth_reason = None
    context.snapshot.stopped_item = stopped_item
    context.job_store.save_checkpoint(context.job_id, checkpoint)
    context.job_store.set_status(context.job_id, "paused")
    context.emit_event(
        {
            "type": "job_stopped",
            "job_id": context.job_id,
            "status": "paused",
            "stopped_item": stopped_item,
        }
    )
    context.emit_event(
        {
            "type": "sidecar_stderr",
            "message": f"{module_name} dry run completed; Chromium is waiting for manual review before reports are finalized.",
        }
    )

    context.control.pause()
    context.control.wait_point()
    checkpoint.stopped_item = None
    context.snapshot.status = "running"
    context.snapshot.stopped_item = None
    context.job_store.save_checkpoint(context.job_id, checkpoint)
    context.job_store.set_status(context.job_id, "running")
