from __future__ import annotations

import json
import sqlite3
from typing import Any

from .checkpoint import JobCheckpoint
from .db import connect, utc_now


SUMMARY_FALLBACK_STATUSES = {"done", "failed", "cancelled", "stopped_on_review"}


class JobStore:
    def _checkpoint_payload(self, checkpoint: JobCheckpoint) -> str:
        return checkpoint.model_dump_json(exclude={"results"})

    def create_pending_job(
        self,
        job_id: str,
        module: str,
        source_file: str,
        *,
        credit_reservation_id: str | None = None,
        credits_reserved: int = 0,
        credit_status: str | None = None,
    ) -> None:
        with connect() as connection:
            connection.execute(
                """
                INSERT INTO job (
                    id, module, status, source_file, credit_reservation_id,
                    credits_reserved, credit_status
                )
                VALUES (?, ?, 'pending', ?, ?, ?, ?)
                """,
                (job_id, module, source_file, credit_reservation_id, credits_reserved, credit_status),
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

    def set_status_if_current(
        self,
        job_id: str,
        status: str,
        *,
        current_statuses: set[str],
    ) -> bool:
        if not current_statuses:
            return False
        placeholders = ", ".join(["?"] * len(current_statuses))
        with connect(immediate=True) as connection:
            cursor = connection.execute(
                f"""
                UPDATE job
                SET status = ?
                WHERE id = ? AND status IN ({placeholders})
                """,
                (status, job_id, *sorted(current_statuses)),
            )
            return cursor.rowcount == 1

    def update_credit_status(
        self,
        job_id: str,
        *,
        credit_reservation_id: str | None = None,
        credits_reserved: int | None = None,
        credits_captured: int | None = None,
        credits_refunded: int | None = None,
        credit_status: str | None = None,
    ) -> None:
        with connect(immediate=True) as connection:
            connection.execute(
                """
                UPDATE job
                SET credit_reservation_id = COALESCE(?, credit_reservation_id),
                    credits_reserved = COALESCE(?, credits_reserved),
                    credits_captured = COALESCE(?, credits_captured),
                    credits_refunded = COALESCE(?, credits_refunded),
                    credit_status = COALESCE(?, credit_status)
                WHERE id = ?
                """,
                (
                    credit_reservation_id,
                    credits_reserved,
                    credits_captured,
                    credits_refunded,
                    credit_status,
                    job_id,
                ),
            )

    def mark_start_failed(self, job_id: str, *, code: str, finished_at: str) -> None:
        with connect(immediate=True) as connection:
            run_summary = self._run_summary(connection, job_id, self._total_records(connection, job_id))
            connection.execute(
                """
                UPDATE job
                SET status = 'failed',
                    processed = 0,
                    succeeded = 0,
                    failed = 0,
                    finished_at = ?,
                    run_summary_json = ?,
                    credit_status = ?
                WHERE id = ?
                """,
                (
                    finished_at,
                    json.dumps(run_summary, ensure_ascii=False, sort_keys=True) if run_summary is not None else "{}",
                    f"start_failed:{code}",
                    job_id,
                ),
            )

    def reap_reserving_jobs(self, *, code: str = "RESTART_DURING_RESERVATION") -> int:
        with connect(immediate=True) as connection:
            cursor = connection.execute(
                """
                UPDATE job
                SET status = 'failed',
                    finished_at = ?,
                    run_summary_json = COALESCE(run_summary_json, '{}'),
                    credit_status = ?
                WHERE status = 'pending' AND credit_status = 'reserving'
                """,
                (utc_now(), f"start_failed:{code}"),
            )
            return int(cursor.rowcount)

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
            total_records = self._total_records(connection, job_id)
            run_summary = self._run_summary(connection, job_id, total_records)
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
                    checkpoint_json = ?,
                    run_summary_json = ?
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
                    json.dumps(run_summary, ensure_ascii=False, sort_keys=True) if run_summary is not None else None,
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
            run_summary = self._run_summary(connection, job_id, self._total_records(connection, job_id))
            connection.execute(
                """
                UPDATE job
                SET status = 'failed',
                    processed = ?,
                    succeeded = ?,
                    failed = ?,
                    finished_at = ?,
                    checkpoint_json = COALESCE(?, checkpoint_json),
                    run_summary_json = ?
                WHERE id = ?
                """,
                (
                    processed,
                    succeeded,
                    failed,
                    finished_at,
                    payload,
                    json.dumps(run_summary, ensure_ascii=False, sort_keys=True) if run_summary is not None else None,
                    job_id,
                ),
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
        backfill_limit = max(limit, 20)
        with connect() as connection:
            rows = self._list_job_rows(connection, limit=limit)
            needs_backfill = any(
                row["status"] in SUMMARY_FALLBACK_STATUSES and row["run_summary_json"] is None
                for row in rows
            )
            if not needs_backfill:
                return [self._status_from_row(row, connection) for row in rows]

        with connect(immediate=True) as connection:
            self._backfill_run_summaries(connection, limit=backfill_limit)

        with connect() as connection:
            rows = self._list_job_rows(connection, limit=limit)
            return [self._status_from_row(row, connection) for row in rows]

    def archive_old_jobs(self, *, keep_latest: int = 20) -> dict[str, int]:
        terminal_statuses = ("done", "failed", "cancelled")
        with connect() as connection:
            rows = connection.execute(
                """
                SELECT id
                FROM job
                WHERE status IN (?, ?, ?)
                ORDER BY COALESCE(finished_at, started_at, id) DESC
                """,
                terminal_statuses,
            ).fetchall()
            archived_ids = [str(row["id"]) for row in rows[keep_latest:]]
            if archived_ids:
                placeholders = ", ".join(["?"] * len(archived_ids))
                connection.execute(
                    f"DELETE FROM job WHERE id IN ({placeholders})",
                    archived_ids,
                )
            return {
                "archived": len(archived_ids),
                "kept": min(len(rows), keep_latest),
            }

    def get_status(self, job_id: str) -> dict[str, Any] | None:
        with connect() as connection:
            row = connection.execute("SELECT * FROM job WHERE id = ?", (job_id,)).fetchone()
            if row is None:
                return None

            return self._status_from_row(row, connection)

    def _status_from_row(self, row: sqlite3.Row, connection: sqlite3.Connection) -> dict[str, Any]:
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
            "run_summary": self._run_summary_from_row(row, connection),
            "credit_reservation_id": row["credit_reservation_id"],
            "credits_reserved": row["credits_reserved"],
            "credits_captured": row["credits_captured"],
            "credits_refunded": row["credits_refunded"],
            "credit_status": row["credit_status"],
        }

    def _run_summary(
        self,
        connection: sqlite3.Connection,
        job_id: str,
        total_records: int | None,
    ) -> dict[str, int] | None:
        rows = connection.execute(
            """
            SELECT matched_order, result_json
            FROM job_record
            WHERE job_id = ?
            """,
            (job_id,),
        ).fetchall()
        if not rows:
            return None

        matched_orders: set[int] = set()
        summary = {
            "dmc_rows_total": len(rows),
            "matched_from_excel": 0,
            "default_207": 0,
            "excel_missing": 0,
            "review_rows": 0,
            "applied_rows": 0,
            "dry_run_rows": 0,
        }

        for row in rows:
            try:
                result = json.loads(row["result_json"])
            except (TypeError, json.JSONDecodeError):
                result = {}

            matched_order = result.get("matched_order", row["matched_order"])
            if matched_order is not None:
                try:
                    matched_orders.add(int(matched_order))
                except (TypeError, ValueError):
                    pass

            note = str(result.get("note") or "")
            status_code = str(result.get("matched_status_code") or "")
            if note in {"filled", "dry_run"} or matched_order is not None:
                summary["matched_from_excel"] += 1
            if note in {"default_missing_dry_run", "default_missing_filled"} and status_code == "207":
                summary["default_207"] += 1
            if note.startswith("low_confidence") or note in {
                "no_match",
                "status_code_not_mapped",
                "option_value_not_found",
            }:
                summary["review_rows"] += 1
            if result.get("applied") is True:
                summary["applied_rows"] += 1
            if note == "dry_run" or note.endswith("_dry_run"):
                summary["dry_run_rows"] += 1

        accepted_total = int(total_records or 0)
        summary["excel_missing"] = max(accepted_total - len(matched_orders), 0)
        return summary

    def _total_records(self, connection: sqlite3.Connection, job_id: str) -> int | None:
        row = connection.execute("SELECT total_records FROM job WHERE id = ?", (job_id,)).fetchone()
        if row is None or row["total_records"] is None:
            return None
        return int(row["total_records"])

    def _run_summary_from_row(self, row: sqlite3.Row, connection: sqlite3.Connection) -> dict[str, int] | None:
        raw_summary = row["run_summary_json"] if "run_summary_json" in row.keys() else None
        if raw_summary:
            try:
                parsed = json.loads(raw_summary)
            except (TypeError, json.JSONDecodeError):
                pass
            else:
                if isinstance(parsed, dict):
                    return {
                        str(key): int(value)
                        for key, value in parsed.items()
                        if isinstance(value, int)
                    }
        if row["status"] not in SUMMARY_FALLBACK_STATUSES:
            return None
        return self._run_summary(connection, str(row["id"]), row["total_records"])

    def _list_job_rows(self, connection: sqlite3.Connection, *, limit: int) -> list[sqlite3.Row]:
        return connection.execute(
            """
            SELECT *
            FROM job
            ORDER BY COALESCE(started_at, finished_at, id) DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    def _backfill_run_summaries(self, connection: sqlite3.Connection, *, limit: int) -> None:
        placeholders = ", ".join(["?"] * len(SUMMARY_FALLBACK_STATUSES))
        rows = connection.execute(
            f"""
            SELECT *
            FROM job
            WHERE status IN ({placeholders})
                AND run_summary_json IS NULL
            ORDER BY COALESCE(finished_at, started_at, id) DESC
            LIMIT ?
            """,
            (*sorted(SUMMARY_FALLBACK_STATUSES), limit),
        ).fetchall()
        for row in rows:
            summary = self._run_summary(connection, str(row["id"]), row["total_records"])
            connection.execute(
                """
                UPDATE job
                SET run_summary_json = ?
                WHERE id = ?
                """,
                (
                    json.dumps(summary, ensure_ascii=False, sort_keys=True) if summary is not None else "{}",
                    row["id"],
                ),
            )


def _utc_now_for_record() -> str:
    return utc_now()
