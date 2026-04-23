from __future__ import annotations

import sqlite3
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
        CREATE TABLE IF NOT EXISTS license (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            license_key TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            device_id TEXT NOT NULL,
            license_tier TEXT NOT NULL,
            school_size_tier TEXT NOT NULL,
            billing_interval TEXT,
            student_count_total INTEGER NOT NULL,
            modules_enabled_json TEXT NOT NULL DEFAULT '[]',
            max_devices INTEGER NOT NULL DEFAULT 3,
            activated_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            last_checked_at TEXT NOT NULL,
            offline_grace_until TEXT NOT NULL
        );

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
            checkpoint_json TEXT
        );

        CREATE TABLE IF NOT EXISTS telemetry_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        """
    )
    _ensure_column(connection, table="license", column="status", definition="TEXT NOT NULL DEFAULT 'active'")
    _ensure_column(
        connection,
        table="license",
        column="modules_enabled_json",
        definition="TEXT NOT NULL DEFAULT '[]'",
    )


def _add_indexes(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE INDEX IF NOT EXISTS idx_job_status_started_at
            ON job(status, started_at DESC);
        CREATE INDEX IF NOT EXISTS idx_telemetry_queue_created_at
            ON telemetry_queue(created_at ASC);
        """
    )


MIGRATIONS: tuple[Migration, ...] = (
    Migration(version=1, name="baseline_schema", apply=_baseline_schema),
    Migration(version=2, name="add_indexes", apply=_add_indexes),
)


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
    with sqlite3.connect(target_path) as connection:
        connection.row_factory = sqlite3.Row
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


def get_database_metadata(path: Path | None = None) -> dict[str, object]:
    target_path = path or database_path()
    with sqlite3.connect(target_path) as connection:
        connection.row_factory = sqlite3.Row
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


@contextmanager
def connect(path: Path | None = None) -> Iterator[sqlite3.Connection]:
    target_path = path or database_path()
    migrate_database(target_path)
    connection = sqlite3.connect(target_path)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()

