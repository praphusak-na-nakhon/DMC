from __future__ import annotations

import hashlib
import sqlite3
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

from fastapi import HTTPException, Request, status

from .config import settings


RATE_LIMIT_EVENT_TTL_SECONDS = 60 * 60
RATE_LIMIT_PRUNE_INTERVAL_SECONDS = 60
_MIGRATION_LOCK = threading.Lock()
_MIGRATED_PATHS: set[str] = set()


def _trusted_proxy_hosts() -> set[str]:
    return {
        host.strip()
        for host in settings.trusted_proxy_hosts.split(",")
        if host.strip()
    }


def client_rate_limit_key(request: Request) -> str:
    client_host = request.client.host if request.client is not None else "unknown"
    forwarded_for = request.headers.get("x-forwarded-for")
    trusted_hosts = _trusted_proxy_hosts()
    if not forwarded_for or client_host not in trusted_hosts:
        return client_host

    chain = [hop.strip() for hop in forwarded_for.split(",") if hop.strip()]
    chain.append(client_host)
    while chain and chain[-1] in trusted_hosts:
        chain.pop()
    return chain[-1] if chain else client_host


def _hash_key(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _rate_limit_path() -> Path:
    if settings.rate_limit_sqlite_path:
        return Path(settings.rate_limit_sqlite_path)
    return Path(settings.sqlite_path).with_name("rate-limit.sqlite3")


def _open_connection(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=1.0)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA synchronous=NORMAL")
    connection.execute("PRAGMA busy_timeout=1000")
    return connection


def _ensure_rate_limit_database(path: Path) -> Path:
    target_key = str(path.resolve())
    if target_key in _MIGRATED_PATHS:
        return path
    with _MIGRATION_LOCK:
        if target_key in _MIGRATED_PATHS:
            return path
        connection = _open_connection(path)
        try:
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
                CREATE TABLE IF NOT EXISTS rate_limit_meta (
                    key TEXT PRIMARY KEY,
                    value REAL NOT NULL
                );
                """
            )
            connection.commit()
        finally:
            connection.close()
        _MIGRATED_PATHS.add(target_key)
    return path


@contextmanager
def _connect_rate_limit(*, immediate: bool = False) -> Iterator[sqlite3.Connection]:
    path = _ensure_rate_limit_database(_rate_limit_path())
    connection = _open_connection(path)
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


def _maybe_prune(connection: sqlite3.Connection, *, now: float, window_seconds: int) -> None:
    row = connection.execute("SELECT value FROM rate_limit_meta WHERE key = 'last_pruned_at'").fetchone()
    last_pruned = float(row["value"]) if row is not None else 0.0
    if now - last_pruned < RATE_LIMIT_PRUNE_INTERVAL_SECONDS:
        return
    cutoff = now - max(RATE_LIMIT_EVENT_TTL_SECONDS, window_seconds)
    connection.execute("DELETE FROM rate_limit_events WHERE created_at <= ?", (cutoff,))
    connection.execute(
        """
        INSERT INTO rate_limit_meta (key, value)
        VALUES ('last_pruned_at', ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        (now,),
    )


def enforce_rate_limit(*, scope: str, key: str, limit: int, window_seconds: int) -> None:
    now = time.time()
    cutoff = now - window_seconds
    key_hash = _hash_key(key)
    with _connect_rate_limit(immediate=True) as connection:
        _maybe_prune(connection, now=now, window_seconds=window_seconds)
        count = connection.execute(
            """
            SELECT COUNT(*) AS count
            FROM rate_limit_events
            WHERE scope = ? AND key_hash = ? AND created_at > ?
            """,
            (scope, key_hash, cutoff),
        ).fetchone()
        if int(count["count"] if count is not None else 0) >= limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="rate limit exceeded",
            )
        connection.execute(
            """
            INSERT INTO rate_limit_events (scope, key_hash, created_at)
            VALUES (?, ?, ?)
            """,
            (scope, key_hash, now),
        )


def rate_limit(*, scope: str, limit: int, window_seconds: int) -> Callable[[Request], None]:
    def dependency(request: Request) -> None:
        enforce_rate_limit(
            scope=scope,
            key=client_rate_limit_key(request),
            limit=limit,
            window_seconds=window_seconds,
        )

    return dependency
