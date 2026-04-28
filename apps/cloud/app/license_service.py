from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

from fastapi import HTTPException, status

from .config import settings
from .db import connect
from .schemas import (
    BillingInterval,
    CloudLicenseAdminResponse,
    CloudLicenseUpsertRequest,
    LicenseActivateRequest,
    LicenseStatus,
    LicenseStateResponse,
    LicenseTier,
    SchoolSizeTier,
)


def utc_now() -> datetime:
    return datetime.now(UTC)


def to_utc_string(value: datetime) -> str:
    return value.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


@dataclass(frozen=True)
class LicenseRecord:
    license_key: str
    license_tier: str
    school_size_tier: str
    billing_interval: str | None
    student_count_total: int
    max_devices: int
    status: str
    expires_at: str
    modules_enabled: list[str]


class LicenseRepository:
    _bootstrapped_paths: set[str] = set()
    _bootstrap_lock = threading.Lock()

    def __init__(self, sqlite_path: str | None = None) -> None:
        self.sqlite_path = Path(sqlite_path or settings.sqlite_path)
        self.ensure_bootstrapped()

    def ensure_bootstrapped(self) -> None:
        target_key = str(self.sqlite_path.resolve())
        if target_key in self._bootstrapped_paths:
            return
        with self._bootstrap_lock:
            if target_key in self._bootstrapped_paths:
                return
            self.seed_trial_licenses()
            self._bootstrapped_paths.add(target_key)

    def seed_trial_licenses(self) -> None:
        keys = [item.strip() for item in settings.trial_license_keys.split(",") if item.strip()]
        if not keys:
            return

        with connect(self.sqlite_path) as connection:
            for license_key in keys:
                connection.execute(
                    """
                    INSERT INTO licenses (
                        license_key, license_tier, school_size_tier, billing_interval,
                        student_count_total, max_devices, status, expires_at, modules_enabled_json
                    )
                    VALUES (?, 'trial', 'le_500', NULL, 0, 3, 'active', ?, ?)
                    ON CONFLICT(license_key) DO NOTHING
                    """,
                    (
                        license_key,
                        to_utc_string(utc_now() + timedelta(days=settings.trial_duration_days)),
                        json.dumps(["graduation"], ensure_ascii=False),
                    ),
                )

    def get_license(self, license_key: str) -> LicenseRecord | None:
        with connect(self.sqlite_path) as connection:
            row = connection.execute(
                "SELECT * FROM licenses WHERE license_key = ?",
                (license_key,),
            ).fetchone()
        if row is None:
            return None
        return LicenseRecord(
            license_key=row["license_key"],
            license_tier=row["license_tier"],
            school_size_tier=row["school_size_tier"],
            billing_interval=row["billing_interval"],
            student_count_total=int(row["student_count_total"]),
            max_devices=int(row["max_devices"]),
            status=row["status"],
            expires_at=row["expires_at"],
            modules_enabled=json.loads(row["modules_enabled_json"] or "[]"),
        )

    def list_licenses(self) -> list[CloudLicenseAdminResponse]:
        with connect(self.sqlite_path) as connection:
            rows = connection.execute(
                """
                SELECT
                    licenses.*,
                    COUNT(device_activations.id) AS active_devices
                FROM licenses
                LEFT JOIN device_activations
                    ON device_activations.license_key = licenses.license_key
                GROUP BY licenses.license_key
                ORDER BY licenses.license_key ASC
                """
            ).fetchall()
        return [
            CloudLicenseAdminResponse(
                license_key=row["license_key"],
                license_tier=row["license_tier"],
                school_size_tier=row["school_size_tier"],
                billing_interval=row["billing_interval"],
                student_count_total=int(row["student_count_total"]),
                max_devices=int(row["max_devices"]),
                status=row["status"],
                expires_at=row["expires_at"],
                modules_enabled=json.loads(row["modules_enabled_json"] or "[]"),
                active_devices=int(row["active_devices"]),
            )
            for row in rows
        ]

    def upsert_license(
        self,
        *,
        license_key: str,
        request: CloudLicenseUpsertRequest,
    ) -> CloudLicenseAdminResponse:
        if request.license_key != license_key:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="license key in path does not match payload",
            )

        expires_at = to_utc_string(parse_utc(request.expires_at))
        with connect(self.sqlite_path) as connection:
            connection.execute(
                """
                INSERT INTO licenses (
                    license_key, license_tier, school_size_tier, billing_interval,
                    student_count_total, max_devices, status, expires_at, modules_enabled_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(license_key) DO UPDATE SET
                    license_tier = excluded.license_tier,
                    school_size_tier = excluded.school_size_tier,
                    billing_interval = excluded.billing_interval,
                    student_count_total = excluded.student_count_total,
                    max_devices = excluded.max_devices,
                    status = excluded.status,
                    expires_at = excluded.expires_at,
                    modules_enabled_json = excluded.modules_enabled_json
                """,
                (
                    request.license_key,
                    request.license_tier,
                    request.school_size_tier,
                    request.billing_interval,
                    request.student_count_total,
                    request.max_devices,
                    request.status,
                    expires_at,
                    json.dumps(request.modules_enabled, ensure_ascii=False),
                ),
            )

        record = self.get_license(request.license_key)
        if record is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="failed to persist license",
            )
        return CloudLicenseAdminResponse(
            license_key=record.license_key,
            license_tier=cast(LicenseTier, record.license_tier),
            school_size_tier=cast(SchoolSizeTier, record.school_size_tier),
            billing_interval=cast(BillingInterval | None, record.billing_interval),
            student_count_total=record.student_count_total,
            max_devices=record.max_devices,
            status=cast(LicenseStatus, record.status),
            expires_at=record.expires_at,
            modules_enabled=record.modules_enabled,
            active_devices=self.count_active_devices(record.license_key),
        )

    def upsert_device_activation(self, *, license_key: str, device_id: str, device_name: str) -> None:
        now = to_utc_string(utc_now())
        with connect(self.sqlite_path) as connection:
            connection.execute(
                """
                INSERT INTO device_activations (
                    license_key, device_id, device_name, first_seen_at, last_seen_at
                )
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(license_key, device_id) DO UPDATE SET
                    device_name = excluded.device_name,
                    last_seen_at = excluded.last_seen_at
                """,
                (license_key, device_id, device_name, now, now),
            )

    def count_active_devices(self, license_key: str) -> int:
        with connect(self.sqlite_path) as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS total FROM device_activations WHERE license_key = ?",
                (license_key,),
            ).fetchone()
        return int(row["total"]) if row is not None else 0

    def has_device(self, *, license_key: str, device_id: str) -> bool:
        with connect(self.sqlite_path) as connection:
            row = connection.execute(
                """
                SELECT 1
                FROM device_activations
                WHERE license_key = ? AND device_id = ?
                """,
                (license_key, device_id),
            ).fetchone()
        return row is not None

    def touch_device(self, *, license_key: str, device_id: str, device_name: str) -> None:
        self.upsert_device_activation(
            license_key=license_key,
            device_id=device_id,
            device_name=device_name,
        )


def _build_response(record: LicenseRecord) -> LicenseStateResponse:
    return LicenseStateResponse(
        status=cast(LicenseStatus, record.status),
        license_tier=cast(LicenseTier, record.license_tier),
        school_size_tier=cast(SchoolSizeTier, record.school_size_tier),
        billing_interval=cast(BillingInterval | None, record.billing_interval),
        student_count_total=record.student_count_total,
        expires_at=record.expires_at,
        modules_enabled=record.modules_enabled,
        max_devices=record.max_devices,
        offline_grace_days=settings.offline_grace_days,
    )


def activate_license_request(
    repository: LicenseRepository,
    request: LicenseActivateRequest,
) -> LicenseStateResponse:
    record = repository.get_license(request.license_key)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="license not found")

    if parse_utc(record.expires_at) <= utc_now():
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="license expired")

    if record.status != "active":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="license is not active")

    already_active = repository.has_device(
        license_key=request.license_key,
        device_id=request.device_id,
    )
    if not already_active and repository.count_active_devices(request.license_key) >= record.max_devices:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="device limit exceeded")

    repository.upsert_device_activation(
        license_key=request.license_key,
        device_id=request.device_id,
        device_name=request.device_name,
    )
    return _build_response(record)


def heartbeat_license_request(
    repository: LicenseRepository,
    *,
    license_key: str,
    device_id: str,
    device_name: str,
) -> LicenseStateResponse:
    record = repository.get_license(license_key)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="license not found")

    if parse_utc(record.expires_at) <= utc_now():
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail="need renewal")

    if record.status != "active":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="license is not active")

    if not repository.has_device(license_key=license_key, device_id=device_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="device is not activated")

    repository.touch_device(
        license_key=license_key,
        device_id=device_id,
        device_name=device_name,
    )
    return _build_response(record)
