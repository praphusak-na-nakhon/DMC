from __future__ import annotations

import json
from typing import Any

from .checkpoint import JobCheckpoint
from .db import connect


class JobStore:
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
                    checkpoint_json = COALESCE(?, checkpoint_json)
                WHERE id = ?
                """,
                (
                    total_records,
                    started_at,
                    checkpoint.model_dump_json() if checkpoint is not None else None,
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
                    checkpoint_json = ?
                WHERE id = ?
                """,
                (
                    checkpoint.processed,
                    checkpoint.succeeded,
                    checkpoint.failed,
                    checkpoint.model_dump_json(),
                    job_id,
                ),
            )

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
                    checkpoint_json = ?
                WHERE id = ?
                """,
                (
                    checkpoint.processed,
                    checkpoint.succeeded,
                    checkpoint.failed,
                    finished_at,
                    checkpoint.model_dump_json(),
                    job_id,
                ),
            )

    def mark_failed(
        self,
        job_id: str,
        checkpoint: JobCheckpoint | None,
        finished_at: str,
    ) -> None:
        payload = checkpoint.model_dump_json() if checkpoint is not None else None
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
        return JobCheckpoint.model_validate_json(row["checkpoint_json"])

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

    def _status_from_row(self, row) -> dict[str, Any]:
        checkpoint = None
        if row["checkpoint_json"]:
            checkpoint = JobCheckpoint.model_validate(json.loads(row["checkpoint_json"]))

        return {
            "job_id": row["id"],
            "module": row["module"],
            "status": row["status"],
            "source_file": row["source_file"],
            "processed": row["processed"],
            "total": row["total_records"],
            "succeeded": row["succeeded"],
            "failed": row["failed"],
            "current_page": checkpoint.next_page if checkpoint is not None else None,
            "needs_auth": checkpoint.awaiting_auth if checkpoint is not None else False,
            "auth_reason": checkpoint.auth_reason if checkpoint is not None else None,
            "report_path": checkpoint.report_path if checkpoint is not None else None,
            "review_report_path": checkpoint.review_report_path if checkpoint is not None else None,
            "stopped_item": checkpoint.stopped_item if checkpoint is not None else None,
            "started_at": row["started_at"],
            "finished_at": row["finished_at"],
            "level_label": checkpoint.level_label if checkpoint is not None else None,
        }
