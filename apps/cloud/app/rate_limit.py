from __future__ import annotations

import hashlib
import time
from collections.abc import Callable
from pathlib import Path

from fastapi import HTTPException, Request, status

from .config import settings
from .db import connect


RATE_LIMIT_EVENT_TTL_SECONDS = 24 * 60 * 60


def _trusted_proxy_hosts() -> set[str]:
    return {
        host.strip()
        for host in settings.trusted_proxy_hosts.split(",")
        if host.strip()
    }


def client_rate_limit_key(request: Request) -> str:
    client_host = request.client.host if request.client is not None else "unknown"
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for and client_host in _trusted_proxy_hosts():
        forwarded_host = forwarded_for.split(",", 1)[0].strip()
        if forwarded_host:
            return forwarded_host
    return client_host


def _hash_key(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def enforce_rate_limit(*, scope: str, key: str, limit: int, window_seconds: int) -> None:
    now = time.time()
    cutoff = now - window_seconds
    key_hash = _hash_key(key)
    with connect(Path(settings.sqlite_path), immediate=True) as connection:
        connection.execute(
            "DELETE FROM rate_limit_events WHERE created_at <= ?",
            (now - RATE_LIMIT_EVENT_TTL_SECONDS,),
        )
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
