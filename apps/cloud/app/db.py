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
        CREATE TABLE IF NOT EXISTS telemetry_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
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
        CREATE INDEX IF NOT EXISTS idx_telemetry_events_created_at
            ON telemetry_events(created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_telemetry_events_user_created
            ON telemetry_events(user_id, created_at DESC);
        """
    )


def _account_credit_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            display_name TEXT,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS sessions (
            token TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            device_id TEXT NOT NULL,
            device_name TEXT NOT NULL,
            app_version TEXT NOT NULL,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            revoked_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS wallets (
            user_id TEXT PRIMARY KEY,
            balance INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS credit_reservations (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            job_id TEXT NOT NULL,
            module TEXT NOT NULL,
            status TEXT NOT NULL,
            units_reserved INTEGER NOT NULL,
            units_captured INTEGER NOT NULL DEFAULT 0,
            units_released INTEGER NOT NULL DEFAULT 0,
            idempotency_key TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE (user_id, job_id),
            UNIQUE (user_id, idempotency_key),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS credit_transactions (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            type TEXT NOT NULL,
            amount INTEGER NOT NULL,
            reservation_id TEXT,
            job_id TEXT,
            module TEXT,
            idempotency_key TEXT,
            note TEXT,
            created_at TEXT NOT NULL,
            UNIQUE (user_id, idempotency_key),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_sessions_user_expires
            ON sessions(user_id, expires_at DESC);
        CREATE INDEX IF NOT EXISTS idx_credit_reservations_user_status
            ON credit_reservations(user_id, status);
        CREATE INDEX IF NOT EXISTS idx_credit_transactions_user_created
            ON credit_transactions(user_id, created_at DESC);
        """
    )


def _admin_audit_and_topup_requests(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS admin_audit_log (
            id TEXT PRIMARY KEY,
            actor TEXT NOT NULL,
            action TEXT NOT NULL,
            target_type TEXT,
            target_id TEXT,
            payload_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS credit_topup_requests (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            amount INTEGER NOT NULL,
            status TEXT NOT NULL,
            note TEXT,
            payment_reference TEXT,
            requested_by TEXT NOT NULL,
            decided_by TEXT,
            topup_idempotency_key TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            decided_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_admin_audit_log_created
            ON admin_audit_log(created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_credit_topup_requests_status_created
            ON credit_topup_requests(status, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_credit_topup_requests_user_created
            ON credit_topup_requests(user_id, created_at DESC);
        """
    )


def _wallet_reserved_column(connection: sqlite3.Connection) -> None:
    existing_columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(wallets)").fetchall()
    }
    if "reserved" not in existing_columns:
        connection.execute("ALTER TABLE wallets ADD COLUMN reserved INTEGER NOT NULL DEFAULT 0")
    connection.execute(
        """
        UPDATE wallets
        SET reserved = COALESCE((
            SELECT SUM(units_reserved - units_captured - units_released)
            FROM credit_reservations
            WHERE credit_reservations.user_id = wallets.user_id
                AND credit_reservations.status = 'active'
        ), 0)
        """
    )


def _telemetry_user_id_column(connection: sqlite3.Connection) -> None:
    existing_columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(telemetry_events)").fetchall()
    }
    if "user_id" not in existing_columns:
        connection.execute("ALTER TABLE telemetry_events ADD COLUMN user_id TEXT")
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_telemetry_events_user_created
            ON telemetry_events(user_id, created_at DESC)
        """
    )


def _rate_limit_events(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS rate_limit_events (
            scope TEXT NOT NULL,
            key_hash TEXT NOT NULL,
            created_at REAL NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_rate_limit_events_scope_key_created
            ON rate_limit_events(scope, key_hash, created_at);
        CREATE INDEX IF NOT EXISTS idx_rate_limit_events_created
            ON rate_limit_events(created_at);
        """
    )


MIGRATIONS: tuple[Migration, ...] = (
    Migration(version=1, name="baseline_schema", apply=_baseline_schema),
    Migration(version=2, name="add_indexes", apply=_add_indexes),
    Migration(version=3, name="account_credit_schema", apply=_account_credit_schema),
    Migration(version=4, name="admin_audit_and_topup_requests", apply=_admin_audit_and_topup_requests),
    Migration(version=5, name="wallet_reserved_column", apply=_wallet_reserved_column),
    Migration(version=6, name="telemetry_user_id_column", apply=_telemetry_user_id_column),
    Migration(version=7, name="rate_limit_events", apply=_rate_limit_events),
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
    with open_connection(path) as connection:
        _create_migration_table(connection)
        connection.commit()
        applied_version = current_schema_version(connection)
        for migration in MIGRATIONS:
            if migration.version <= applied_version:
                continue
            try:
                migration.apply(connection)
                connection.execute(
                    """
                    INSERT INTO schema_migrations (version, name, applied_at)
                    VALUES (?, ?, ?)
                    """,
                    (migration.version, migration.name, utc_now()),
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
            applied_version = migration.version
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
def connect(path: Path, *, immediate: bool = False) -> Iterator[sqlite3.Connection]:
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
