from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable, Iterator

from .config import ensure_data_dir, sqlite_path


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    apply: Callable[[sqlite3.Connection], None]


def _ensure_column(
    connection: sqlite3.Connection,
    *,
    table: str,
    column: str,
    definition: str,
) -> None:
    existing_columns = {
        row["name"]
        for row in connection.execute(f"PRAGMA table_info({table})").fetchall()
    }
    if column not in existing_columns:
        connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def _create_migration_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            applied_at TEXT NOT NULL
        )
        """
    )


def _baseline_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS app_state (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS job (
            id TEXT PRIMARY KEY,
            module TEXT NOT NULL,
            status TEXT NOT NULL,
            source_file TEXT NOT NULL,
            total_records INTEGER,
            processed INTEGER NOT NULL DEFAULT 0,
            succeeded INTEGER NOT NULL DEFAULT 0,
            failed INTEGER NOT NULL DEFAULT 0,
            started_at TEXT,
            finished_at TEXT,
            current_page INTEGER,
            awaiting_auth INTEGER NOT NULL DEFAULT 0,
            auth_reason TEXT,
            report_path TEXT,
            review_report_path TEXT,
            stopped_item_json TEXT,
            level_label TEXT,
            checkpoint_json TEXT
        );

        CREATE TABLE IF NOT EXISTS job_record (
            job_id TEXT NOT NULL,
            page INTEGER NOT NULL,
            portal_row_index INTEGER NOT NULL,
            matched_order INTEGER,
            result_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            PRIMARY KEY (job_id, page, portal_row_index),
            FOREIGN KEY (job_id) REFERENCES job(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS telemetry_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        """
    )
    _ensure_job_summary_columns(connection)


def _add_indexes(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE INDEX IF NOT EXISTS idx_job_status_started_at
            ON job(status, started_at DESC);
        CREATE INDEX IF NOT EXISTS idx_telemetry_queue_created_at
            ON telemetry_queue(created_at ASC);
        CREATE INDEX IF NOT EXISTS idx_job_record_job_page
            ON job_record(job_id, page, portal_row_index);
        """
    )


def _ensure_job_summary_columns(connection: sqlite3.Connection) -> None:
    _ensure_column(connection, table="job", column="current_page", definition="INTEGER")
    _ensure_column(connection, table="job", column="awaiting_auth", definition="INTEGER NOT NULL DEFAULT 0")
    _ensure_column(connection, table="job", column="auth_reason", definition="TEXT")
    _ensure_column(connection, table="job", column="report_path", definition="TEXT")
    _ensure_column(connection, table="job", column="review_report_path", definition="TEXT")
    _ensure_column(connection, table="job", column="stopped_item_json", definition="TEXT")
    _ensure_column(connection, table="job", column="level_label", definition="TEXT")
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS job_record (
            job_id TEXT NOT NULL,
            page INTEGER NOT NULL,
            portal_row_index INTEGER NOT NULL,
            matched_order INTEGER,
            result_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            PRIMARY KEY (job_id, page, portal_row_index),
            FOREIGN KEY (job_id) REFERENCES job(id) ON DELETE CASCADE
        )
        """
    )


def _account_credit_columns(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS account_session (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            token TEXT NOT NULL,
            user_id TEXT NOT NULL,
            email TEXT NOT NULL,
            display_name TEXT,
            status TEXT NOT NULL,
            token_expires_at TEXT NOT NULL,
            signed_in_at TEXT NOT NULL,
            last_checked_at TEXT NOT NULL,
            wallet_json TEXT NOT NULL DEFAULT '{}',
            module_catalog_json TEXT NOT NULL DEFAULT '[]'
        );
        """
    )
    _ensure_column(connection, table="job", column="credit_reservation_id", definition="TEXT")
    _ensure_column(connection, table="job", column="credits_reserved", definition="INTEGER NOT NULL DEFAULT 0")
    _ensure_column(connection, table="job", column="credits_captured", definition="INTEGER NOT NULL DEFAULT 0")
    _ensure_column(connection, table="job", column="credits_refunded", definition="INTEGER NOT NULL DEFAULT 0")
    _ensure_column(connection, table="job", column="credit_status", definition="TEXT")


def _job_run_summary_column(connection: sqlite3.Connection) -> None:
    _ensure_column(connection, table="job", column="run_summary_json", definition="TEXT")


MIGRATIONS: tuple[Migration, ...] = (
    Migration(version=1, name="baseline_schema", apply=_baseline_schema),
    Migration(version=2, name="add_indexes", apply=_add_indexes),
    Migration(version=3, name="job_record_summary", apply=_ensure_job_summary_columns),
    Migration(version=4, name="account_credit_columns", apply=_account_credit_columns),
    Migration(version=5, name="job_run_summary_column", apply=_job_run_summary_column),
)

_MIGRATION_LOCK = threading.Lock()
_MIGRATED_PATHS: set[str] = set()


def database_path() -> Path:
    return sqlite_path()


def current_schema_version(connection: sqlite3.Connection) -> int:
    _create_migration_table(connection)
    row = connection.execute(
        "SELECT COALESCE(MAX(version), 0) AS version FROM schema_migrations"
    ).fetchone()
    return int(row["version"]) if row is not None else 0


def migrate_database(path: Path | None = None) -> int:
    ensure_data_dir()
    target_path = path or database_path()
    with open_connection(target_path) as connection:
        _create_migration_table(connection)
        applied_version = current_schema_version(connection)
        for migration in MIGRATIONS:
            if migration.version <= applied_version:
                continue
            migration.apply(connection)
            connection.execute(
                """
                INSERT INTO schema_migrations (version, name, applied_at)
                VALUES (?, ?, ?)
                """,
                (migration.version, migration.name, utc_now()),
            )
            applied_version = migration.version
        connection.commit()
        return applied_version


def ensure_database_ready(path: Path | None = None) -> Path:
    target_path = path or database_path()
    target_key = str(target_path.resolve())
    if target_key in _MIGRATED_PATHS:
        return target_path
    with _MIGRATION_LOCK:
        if target_key not in _MIGRATED_PATHS:
            migrate_database(target_path)
            _MIGRATED_PATHS.add(target_key)
    return target_path


def get_database_metadata(path: Path | None = None) -> dict[str, object]:
    target_path = ensure_database_ready(path)
    with open_connection(target_path) as connection:
        version = current_schema_version(connection)
        tables = [
            row["name"]
            for row in connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
                ORDER BY name ASC
                """
            ).fetchall()
        ]
    return {
        "path": str(target_path),
        "schema_version": version,
        "tables": tables,
    }


def open_connection(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path, timeout=5.0)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA synchronous=NORMAL")
    connection.execute("PRAGMA busy_timeout=5000")
    connection.execute("PRAGMA foreign_keys=ON")
    return connection


@contextmanager
def connect(path: Path | None = None, *, immediate: bool = False) -> Iterator[sqlite3.Connection]:
    target_path = ensure_database_ready(path)
    connection = open_connection(target_path)
    try:
        if immediate:
            connection.execute("BEGIN IMMEDIATE")
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
