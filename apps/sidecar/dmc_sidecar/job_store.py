from __future__ import annotations

import json
import sqlite3
from typing import Any

from .checkpoint import JobCheckpoint
from .db import connect, utc_now


class JobStore:
    def _checkpoint_payload(self, checkpoint: JobCheckpoint) -> str:
        return checkpoint.model_dump_json(exclude={"results"})

    def create_pending_job(self, job_id: str, module: str, source_file: str) -> None:
        with connect() as connection:
            connection.execute(
                """
                INSERT INTO job (id, module, status, source_file)
                VALUES (?, ?, 'pending', ?)
                """,
                (job_id, module, source_file),
            )

    def mark_running(
        self,
        job_id: str,
        *,
        total_records: int,
        checkpoint: JobCheckpoint | None = None,
        started_at: str | None = None,
    ) -> None:
        with connect() as connection:
            connection.execute(
                """
                UPDATE job
                SET status = 'running',
                    total_records = ?,
                    started_at = COALESCE(started_at, ?),
                    current_page = COALESCE(?, current_page),
                    awaiting_auth = COALESCE(?, awaiting_auth),
                    auth_reason = COALESCE(?, auth_reason),
                    report_path = COALESCE(?, report_path),
                    review_report_path = COALESCE(?, review_report_path),
                    stopped_item_json = COALESCE(?, stopped_item_json),
                    level_label = COALESCE(?, level_label),
                    checkpoint_json = COALESCE(?, checkpoint_json)
                WHERE id = ?
                """,
                (
                    total_records,
                    started_at,
                    checkpoint.next_page if checkpoint is not None else None,
                    (1 if checkpoint.awaiting_auth else 0) if checkpoint is not None else None,
                    checkpoint.auth_reason if checkpoint is not None else None,
                    checkpoint.report_path if checkpoint is not None else None,
                    checkpoint.review_report_path if checkpoint is not None else None,
                    (
                        json.dumps(checkpoint.stopped_item, ensure_ascii=False)
                        if checkpoint is not None and checkpoint.stopped_item is not None
                        else None
                    ),
                    checkpoint.level_label if checkpoint is not None else None,
                    self._checkpoint_payload(checkpoint) if checkpoint is not None else None,
                    job_id,
                ),
            )

    def set_status(self, job_id: str, status: str) -> None:
        with connect() as connection:
            connection.execute(
                "UPDATE job SET status = ? WHERE id = ?",
                (status, job_id),
            )

    def save_checkpoint(self, job_id: str, checkpoint: JobCheckpoint) -> None:
        with connect() as connection:
            connection.execute(
                """
                UPDATE job
                SET processed = ?,
                    succeeded = ?,
                    failed = ?,
                    current_page = ?,
                    awaiting_auth = ?,
                    auth_reason = ?,
                    report_path = ?,
                    review_report_path = ?,
                    stopped_item_json = ?,
                    level_label = ?,
                    checkpoint_json = ?
                WHERE id = ?
                """,
                (
                    checkpoint.processed,
                    checkpoint.succeeded,
                    checkpoint.failed,
                    checkpoint.next_page,
                    1 if checkpoint.awaiting_auth else 0,
                    checkpoint.auth_reason,
                    checkpoint.report_path,
                    checkpoint.review_report_path,
                    json.dumps(checkpoint.stopped_item, ensure_ascii=False) if checkpoint.stopped_item is not None else None,
                    checkpoint.level_label,
                    self._checkpoint_payload(checkpoint),
                    job_id,
                ),
            )

    def append_results(self, job_id: str, results: list[dict[str, Any]]) -> None:
        if not results:
            return
        with connect() as connection:
            connection.executemany(
                """
                INSERT INTO job_record (
                    job_id, page, portal_row_index, matched_order, result_json, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(job_id, page, portal_row_index) DO UPDATE SET
                    matched_order = excluded.matched_order,
                    result_json = excluded.result_json,
                    created_at = excluded.created_at
                """,
                [
                    (
                        job_id,
                        int(result.get("page") or 0),
                        int(result.get("portal_row_index") or 0),
                        int(result["matched_order"]) if result.get("matched_order") is not None else None,
                        json.dumps(result, ensure_ascii=False),
                        _utc_now_for_record(),
                    )
                    for result in results
                    if result.get("portal_row_index") is not None
                ],
            )

    def list_results(self, job_id: str) -> list[dict[str, Any]]:
        with connect() as connection:
            rows = connection.execute(
                """
                SELECT result_json
                FROM job_record
                WHERE job_id = ?
                ORDER BY page ASC, portal_row_index ASC
                """,
                (job_id,),
            ).fetchall()
        return [json.loads(row["result_json"]) for row in rows]

    def mark_done(self, job_id: str, checkpoint: JobCheckpoint, finished_at: str) -> None:
        with connect() as connection:
            connection.execute(
                """
                UPDATE job
                SET status = 'done',
                    processed = ?,
                    succeeded = ?,
                    failed = ?,
                    finished_at = ?,
                    current_page = ?,
                    awaiting_auth = ?,
                    auth_reason = ?,
                    report_path = ?,
                    review_report_path = ?,
                    stopped_item_json = ?,
                    level_label = ?,
                    checkpoint_json = ?
                WHERE id = ?
                """,
                (
                    checkpoint.processed,
                    checkpoint.succeeded,
                    checkpoint.failed,
                    finished_at,
                    checkpoint.next_page,
                    1 if checkpoint.awaiting_auth else 0,
                    checkpoint.auth_reason,
                    checkpoint.report_path,
                    checkpoint.review_report_path,
                    json.dumps(checkpoint.stopped_item, ensure_ascii=False) if checkpoint.stopped_item is not None else None,
                    checkpoint.level_label,
                    self._checkpoint_payload(checkpoint),
                    job_id,
                ),
            )

    def mark_failed(
        self,
        job_id: str,
        checkpoint: JobCheckpoint | None,
        finished_at: str,
    ) -> None:
        payload = self._checkpoint_payload(checkpoint) if checkpoint is not None else None
        processed = checkpoint.processed if checkpoint is not None else 0
        succeeded = checkpoint.succeeded if checkpoint is not None else 0
        failed = checkpoint.failed if checkpoint is not None else 0
        with connect() as connection:
            connection.execute(
                """
                UPDATE job
                SET status = 'failed',
                    processed = ?,
                    succeeded = ?,
                    failed = ?,
                    finished_at = ?,
                    checkpoint_json = COALESCE(?, checkpoint_json)
                WHERE id = ?
                """,
                (processed, succeeded, failed, finished_at, payload, job_id),
            )

    def load_checkpoint(self, job_id: str) -> JobCheckpoint | None:
        with connect() as connection:
            row = connection.execute(
                "SELECT checkpoint_json FROM job WHERE id = ?",
                (job_id,),
            ).fetchone()
        if row is None or not row["checkpoint_json"]:
            return None
        checkpoint = JobCheckpoint.model_validate_json(row["checkpoint_json"])
        persisted_results = self.list_results(job_id)
        if persisted_results:
            checkpoint.results = persisted_results
        return checkpoint

    def get_job_record(self, job_id: str) -> dict[str, Any] | None:
        with connect() as connection:
            row = connection.execute("SELECT * FROM job WHERE id = ?", (job_id,)).fetchone()
        if row is None:
            return None
        return dict(row)

    def list_jobs(self, limit: int = 20) -> list[dict[str, Any]]:
        with connect() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM job
                ORDER BY COALESCE(started_at, finished_at, id) DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._status_from_row(row) for row in rows]

    def get_status(self, job_id: str) -> dict[str, Any] | None:
        with connect() as connection:
            row = connection.execute("SELECT * FROM job WHERE id = ?", (job_id,)).fetchone()
        if row is None:
            return None

        return self._status_from_row(row)

    def _status_from_row(self, row: sqlite3.Row) -> dict[str, Any]:
        stopped_item = json.loads(row["stopped_item_json"]) if row["stopped_item_json"] else None

        return {
            "job_id": row["id"],
            "module": row["module"],
            "status": row["status"],
            "source_file": row["source_file"],
            "processed": row["processed"],
            "total": row["total_records"],
            "succeeded": row["succeeded"],
            "failed": row["failed"],
            "current_page": row["current_page"],
            "needs_auth": bool(row["awaiting_auth"]),
            "auth_reason": row["auth_reason"],
            "report_path": row["report_path"],
            "review_report_path": row["review_report_path"],
            "stopped_item": stopped_item,
            "started_at": row["started_at"],
            "finished_at": row["finished_at"],
            "level_label": row["level_label"],
        }


def _utc_now_for_record() -> str:
    return utc_now()
