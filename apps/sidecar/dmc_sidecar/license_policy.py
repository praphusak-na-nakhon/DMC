from __future__ import annotations

from datetime import UTC, datetime

from .config import cloud_base_url
from .errors import DomainError
from .schemas import LicenseRecord


def parse_utc(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def check_license_allows_job_start(record: LicenseRecord | None, *, now: datetime | None = None) -> None:
    if record is None:
        if cloud_base_url():
            raise DomainError("LICENSE_REQUIRED")
        return

    current_time = now.astimezone(UTC) if now is not None else datetime.now(UTC)
    if current_time > parse_utc(record.offline_grace_until):
        raise DomainError("LICENSE_OFFLINE_GRACE_EXPIRED")
