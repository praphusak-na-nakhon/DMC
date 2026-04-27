from __future__ import annotations

from datetime import UTC, datetime

from .config import allow_unlicensed_jobs, cloud_base_url
from .errors import DomainError
from .schemas import LicenseRecord

TRIAL_RECORD_LIMIT = 50


def parse_utc(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def check_license_allows_job_start(
    record: LicenseRecord | None,
    *,
    module_name: str | None = None,
    now: datetime | None = None,
) -> None:
    if record is None:
        if cloud_base_url() and not allow_unlicensed_jobs():
            raise DomainError("LICENSE_REQUIRED")
        return

    if record.status != "active":
        raise DomainError("LICENSE_INACTIVE")

    if module_name and module_name not in record.modules_enabled:
        raise DomainError("MODULE_NOT_LICENSED")

    current_time = now.astimezone(UTC) if now is not None else datetime.now(UTC)
    if current_time > parse_utc(record.offline_grace_until):
        raise DomainError("LICENSE_OFFLINE_GRACE_EXPIRED")


def check_license_allows_record_count(
    record: LicenseRecord | None,
    *,
    record_count: int,
    dry_run: bool,
) -> None:
    if record is None or dry_run:
        return

    if record.license_tier == "trial" and record_count > TRIAL_RECORD_LIMIT:
        raise DomainError(
            "TRIAL_RECORD_LIMIT_EXCEEDED",
            f"Trial license runs are limited to {TRIAL_RECORD_LIMIT} records.",
        )
