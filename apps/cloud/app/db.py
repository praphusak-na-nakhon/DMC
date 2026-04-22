from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Iterator


SCHEMA_SQL = """
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


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def default_sqlite_path() -> Path:
    return Path(__file__).resolve().parents[2] / ".cloud-state.sqlite3"


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def initialize_database(path: Path) -> None:
    ensure_parent(path)
    with sqlite3.connect(path) as connection:
        connection.row_factory = sqlite3.Row
        connection.executescript(SCHEMA_SQL)
        connection.commit()


@contextmanager
def connect(path: Path) -> Iterator[sqlite3.Connection]:
    initialize_database(path)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def seven_days_from_now() -> str:
    return (datetime.now(UTC) + timedelta(days=7)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
