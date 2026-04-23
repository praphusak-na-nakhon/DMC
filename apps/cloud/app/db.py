from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable, Iterator


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    apply: Callable[[sqlite3.Connection], None]


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
        CREATE TABLE IF NOT EXISTS licenses (
            license_key TEXT PRIMARY KEY,
            license_tier TEXT NOT NULL,
            school_size_tier TEXT NOT NULL,
            billing_interval TEXT,
            student_count_total INTEGER NOT NULL,
            max_devices INTEGER NOT NULL,
            status TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            modules_enabled_json TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS device_activations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            license_key TEXT NOT NULL,
            device_id TEXT NOT NULL,
            device_name TEXT NOT NULL,
            first_seen_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL,
            UNIQUE (license_key, device_id),
            FOREIGN KEY (license_key) REFERENCES licenses(license_key)
        );

        CREATE TABLE IF NOT EXISTS telemetry_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            license_key TEXT,
            device_id TEXT,
            event TEXT NOT NULL,
            app_version TEXT,
            payload_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        """
    )


def _add_indexes(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE INDEX IF NOT EXISTS idx_device_activations_license_last_seen
            ON device_activations(license_key, last_seen_at DESC);
        CREATE INDEX IF NOT EXISTS idx_telemetry_events_created_at
            ON telemetry_events(created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_telemetry_events_license_device
            ON telemetry_events(license_key, device_id);
        """
    )


MIGRATIONS: tuple[Migration, ...] = (
    Migration(version=1, name="baseline_schema", apply=_baseline_schema),
    Migration(version=2, name="add_indexes", apply=_add_indexes),
)

_MIGRATION_LOCK = threading.Lock()
_MIGRATED_PATHS: set[str] = set()


def default_sqlite_path() -> Path:
    return Path(__file__).resolve().parents[2] / ".cloud-state.sqlite3"


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def current_schema_version(connection: sqlite3.Connection) -> int:
    _create_migration_table(connection)
    row = connection.execute(
        "SELECT COALESCE(MAX(version), 0) AS version FROM schema_migrations"
    ).fetchone()
    return int(row["version"]) if row is not None else 0


def migrate_database(path: Path) -> int:
    ensure_parent(path)
    with sqlite3.connect(path) as connection:
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


def ensure_database_ready(path: Path) -> Path:
    target_key = str(path.resolve())
    if target_key in _MIGRATED_PATHS:
        return path
    with _MIGRATION_LOCK:
        if target_key not in _MIGRATED_PATHS:
            migrate_database(path)
            _MIGRATED_PATHS.add(target_key)
    return path


def get_database_metadata(path: Path) -> dict[str, object]:
    target_path = ensure_database_ready(path)
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
def connect(path: Path) -> Iterator[sqlite3.Connection]:
    target_path = ensure_database_ready(path)
    connection = sqlite3.connect(target_path)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()
