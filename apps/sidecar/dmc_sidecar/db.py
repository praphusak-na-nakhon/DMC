from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import Iterator

from .config import ensure_data_dir, sqlite_path


SCHEMA_SQL = """
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


def initialize_database() -> None:
    ensure_data_dir()
    with sqlite3.connect(sqlite_path()) as connection:
        connection.row_factory = sqlite3.Row
        connection.executescript(SCHEMA_SQL)
        _ensure_column(connection, table="license", column="status", definition="TEXT NOT NULL DEFAULT 'active'")
        _ensure_column(
            connection,
            table="license",
            column="modules_enabled_json",
            definition="TEXT NOT NULL DEFAULT '[]'",
        )
        connection.commit()


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    initialize_database()
    connection = sqlite3.connect(sqlite_path())
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()
