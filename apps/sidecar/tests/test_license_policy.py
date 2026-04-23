from __future__ import annotations

from datetime import UTC, datetime

import pytest

from dmc_sidecar.errors import DomainError
from dmc_sidecar.license_policy import check_license_allows_job_start
from dmc_sidecar.schemas import LicenseRecord


def build_license(offline_grace_until: str) -> LicenseRecord:
    return LicenseRecord(
        license_key="DMC-TEST-0001",
        status="active",
        device_id="device-1",
        license_tier="trial",
        school_size_tier="le_500",
        billing_interval=None,
        student_count_total=100,
        modules_enabled=["graduation"],
        max_devices=3,
        activated_at="2026-04-22T00:00:00Z",
        expires_at="2026-05-06T00:00:00Z",
        last_checked_at="2026-04-22T00:00:00Z",
        offline_grace_until=offline_grace_until,
    )


def test_check_license_allows_job_start_allows_missing_license() -> None:
    check_license_allows_job_start(None)


def test_check_license_allows_job_start_requires_activation_when_cloud_enabled(monkeypatch) -> None:
    monkeypatch.setattr("dmc_sidecar.license_policy.cloud_base_url", lambda: "https://cloud.example.test")
    with pytest.raises(DomainError, match="LICENSE_REQUIRED"):
        check_license_allows_job_start(None)


def test_check_license_allows_job_start_rejects_expired_offline_grace() -> None:
    with pytest.raises(DomainError, match="LICENSE_OFFLINE_GRACE_EXPIRED"):
        check_license_allows_job_start(
            build_license("2026-04-22T00:00:00Z"),
            now=datetime(2026, 4, 30, tzinfo=UTC),
        )


def test_check_license_allows_job_start_accepts_valid_offline_grace() -> None:
    check_license_allows_job_start(
        build_license("2026-05-01T00:00:00Z"),
        now=datetime(2026, 4, 30, tzinfo=UTC),
    )
