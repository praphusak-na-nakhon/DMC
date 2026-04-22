from __future__ import annotations

from datetime import UTC, datetime

from .schemas import LicenseRecord


def _parse_utc(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def check_license_allows_job_start(record: LicenseRecord | None, *, now: datetime | None = None) -> None:
    if record is None:
        return

    current_time = now.astimezone(UTC) if now is not None else datetime.now(UTC)
    if current_time > _parse_utc(record.offline_grace_until):
        raise RuntimeError("LICENSE_OFFLINE_GRACE_EXPIRED")
