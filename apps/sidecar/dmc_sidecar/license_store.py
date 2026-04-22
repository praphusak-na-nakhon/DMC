from __future__ import annotations

import json

from .db import connect
from .schemas import LicenseRecord


class LicenseStore:
    def save_activation(self, record: LicenseRecord) -> None:
        with connect() as connection:
            connection.execute(
                """
                INSERT INTO license (
                    id, license_key, status, device_id, license_tier, school_size_tier,
                    billing_interval, student_count_total, modules_enabled_json, max_devices,
                    activated_at, expires_at, last_checked_at, offline_grace_until
                )
                VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    license_key = excluded.license_key,
                    status = excluded.status,
                    device_id = excluded.device_id,
                    license_tier = excluded.license_tier,
                    school_size_tier = excluded.school_size_tier,
                    billing_interval = excluded.billing_interval,
                    student_count_total = excluded.student_count_total,
                    modules_enabled_json = excluded.modules_enabled_json,
                    max_devices = excluded.max_devices,
                    activated_at = excluded.activated_at,
                    expires_at = excluded.expires_at,
                    last_checked_at = excluded.last_checked_at,
                    offline_grace_until = excluded.offline_grace_until
                """,
                (
                    record.license_key,
                    record.status,
                    record.device_id,
                    record.license_tier,
                    record.school_size_tier,
                    record.billing_interval,
                    record.student_count_total,
                    json.dumps(record.modules_enabled, ensure_ascii=False),
                    record.max_devices,
                    record.activated_at,
                    record.expires_at,
                    record.last_checked_at,
                    record.offline_grace_until,
                ),
            )

    def update_heartbeat(
        self,
        *,
        status: str,
        license_tier: str,
        school_size_tier: str,
        billing_interval: str | None,
        student_count_total: int,
        modules_enabled: list[str],
        max_devices: int,
        expires_at: str,
        last_checked_at: str,
        offline_grace_until: str,
    ) -> None:
        with connect() as connection:
            connection.execute(
                """
                UPDATE license
                SET status = ?,
                    license_tier = ?,
                    school_size_tier = ?,
                    billing_interval = ?,
                    student_count_total = ?,
                    modules_enabled_json = ?,
                    max_devices = ?,
                    expires_at = ?,
                    last_checked_at = ?,
                    offline_grace_until = ?
                WHERE id = 1
                """,
                (
                    status,
                    license_tier,
                    school_size_tier,
                    billing_interval,
                    student_count_total,
                    json.dumps(modules_enabled, ensure_ascii=False),
                    max_devices,
                    expires_at,
                    last_checked_at,
                    offline_grace_until,
                ),
            )

    def get_license(self) -> LicenseRecord | None:
        with connect() as connection:
            row = connection.execute("SELECT * FROM license WHERE id = 1").fetchone()
        if row is None:
            return None
        return LicenseRecord(
            license_key=row["license_key"],
            status=row["status"],
            device_id=row["device_id"],
            license_tier=row["license_tier"],
            school_size_tier=row["school_size_tier"],
            billing_interval=row["billing_interval"],
            student_count_total=row["student_count_total"],
            modules_enabled=json.loads(row["modules_enabled_json"] or "[]"),
            max_devices=row["max_devices"],
            activated_at=row["activated_at"],
            expires_at=row["expires_at"],
            last_checked_at=row["last_checked_at"],
            offline_grace_until=row["offline_grace_until"],
        )
