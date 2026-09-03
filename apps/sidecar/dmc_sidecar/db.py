from __future__ import annotations

import sqlite3
import threading
from contextlib import closing, contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterator

from .config import sqlite_path


SCHEMA_GENERATION = 2
_MIGRATION_LOCK = threading.Lock()


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _baseline_schema(connection: sqlite3.Connection) -> None:
    # Execute statements individually: executescript commits an existing transaction.
    connection.execute(
        """
        CREATE TABLE schema_metadata (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            generation INTEGER NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE job (
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
            checkpoint_json TEXT,
            run_summary_json TEXT
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE job_record (
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
    connection.execute("CREATE INDEX idx_job_status_started_at ON job(status, started_at DESC)")
    connection.execute("CREATE INDEX idx_job_record_job_page ON job_record(job_id, page, portal_row_index)")
    connection.execute(
        "INSERT INTO schema_metadata (id, generation, created_at) VALUES (1, ?, ?)",
        (SCHEMA_GENERATION, utc_now()),
    )


def database_path() -> Path:
    return sqlite_path()


def current_schema_generation(connection: sqlite3.Connection) -> int | None:
    exists = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'schema_metadata'"
    ).fetchone()
    if exists is None:
        return None
    row = connection.execute("SELECT generation FROM schema_metadata WHERE id = 1").fetchone()
    return int(row["generation"]) if row is not None else None


def _application_tables(connection: sqlite3.Connection) -> list[str]:
    return [
        str(row["name"])
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
    ]


def migrate_database(path: Path | None = None) -> int:
    target_path = path or database_path()
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with closing(open_connection(target_path)) as connection:
        if current_schema_generation(connection) == SCHEMA_GENERATION:
            return SCHEMA_GENERATION
        # All tables in this application-owned database belong to its generation.
        # Disable foreign keys before BEGIN so legacy table dependency order cannot
        # prevent the reset. Closing this connection restores the normal setting.
        connection.execute("PRAGMA foreign_keys=OFF")
        try:
            connection.execute("BEGIN IMMEDIATE")
            if current_schema_generation(connection) != SCHEMA_GENERATION:
                for table in _application_tables(connection):
                    quoted_table = table.replace('"', '""')
                    connection.execute(f'DROP TABLE "{quoted_table}"')
                _baseline_schema(connection)
            connection.commit()
        except Exception:
            connection.rollback()
            raise
    return SCHEMA_GENERATION


def ensure_database_ready(path: Path | None = None) -> Path:
    target_path = path or database_path()
    # A path may have been removed or replaced since the previous open. Check the
    # actual database every time rather than caching its pathname indefinitely.
    with _MIGRATION_LOCK:
        migrate_database(target_path)
    return target_path


def get_database_metadata(path: Path | None = None) -> dict[str, object]:
    target_path = ensure_database_ready(path)
    with closing(open_connection(target_path)) as connection:
        generation = current_schema_generation(connection)
        tables = _application_tables(connection)
        job_columns = [str(row["name"]) for row in connection.execute("PRAGMA table_info(job)").fetchall()]
    return {
        "path": str(target_path),
        "schema_generation": generation,
        "tables": tables,
        "job_columns": job_columns,
    }


def open_connection(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path, timeout=5.0)
    try:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=NORMAL")
        connection.execute("PRAGMA busy_timeout=5000")
        connection.execute("PRAGMA foreign_keys=ON")
    except Exception:
        connection.close()
        raise
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
