from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .config import cloud_api_bearer_token, cloud_base_url
from .device_identity import default_device_name, get_or_create_device_id
from .license_policy import _parse_utc
from .license_store import LicenseStore
from .schemas import LicenseRecord, LicenseStatusSnapshot


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _add_days(base: datetime, days: int) -> str:
    return (base + timedelta(days=days)).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _is_within_offline_grace(record: LicenseRecord | None, *, now: datetime | None = None) -> bool:
    if record is None:
        return False
    current_time = now.astimezone(UTC) if now is not None else datetime.now(UTC)
    return current_time <= _parse_utc(record.offline_grace_until)


def build_license_status_snapshot(
    record: LicenseRecord | None,
    *,
    message: str | None = None,
    last_error: str | None = None,
    offline_mode: bool | None = None,
) -> LicenseStatusSnapshot:
    within_offline_grace = _is_within_offline_grace(record)
    effective_offline_mode = offline_mode if offline_mode is not None else False
    cloud_enabled = cloud_base_url() is not None

    if record is None:
        return LicenseStatusSnapshot(
            configured=False,
            status="missing",
            license_tier=None,
            school_size_tier=None,
            billing_interval=None,
            student_count_total=None,
            max_devices=None,
            modules_enabled=[],
            expires_at=None,
            last_checked_at=None,
            offline_grace_until=None,
            offline_mode=False,
            within_offline_grace=False,
            can_start_jobs=not cloud_enabled,
            needs_attention=cloud_enabled or last_error is not None,
            message=message or ("LICENSE_REQUIRED" if cloud_enabled else "LICENSE_NOT_CONFIGURED"),
            last_error=last_error,
        )

    status = record.status or "active"
    can_start_jobs = status == "active" and within_offline_grace
    needs_attention = status != "active" or not within_offline_grace or last_error is not None
    return LicenseStatusSnapshot(
        configured=True,
        status=status,
        license_tier=record.license_tier,
        school_size_tier=record.school_size_tier,
        billing_interval=record.billing_interval,
        student_count_total=record.student_count_total,
        max_devices=record.max_devices,
        modules_enabled=record.modules_enabled,
        expires_at=record.expires_at,
        last_checked_at=record.last_checked_at,
        offline_grace_until=record.offline_grace_until,
        offline_mode=effective_offline_mode,
        within_offline_grace=within_offline_grace,
        can_start_jobs=can_start_jobs,
        needs_attention=needs_attention,
        message=message,
        last_error=last_error,
    )


def activate_license(
    store: LicenseStore,
    *,
    license_key: str,
    device_name: str,
    app_version: str,
    timeout_sec: int = 10,
) -> LicenseStatusSnapshot:
    base_url = cloud_base_url()
    if not base_url:
        raise RuntimeError("LICENSE_ACTIVATION_UNAVAILABLE")

    device_id = get_or_create_device_id()
    request = Request(
        f"{base_url}/v1/license/activate",
        headers={
            "Authorization": f"Bearer {cloud_api_bearer_token()}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
        data=json.dumps(
            {
                "license_key": license_key,
                "device_id": device_id,
                "device_name": device_name,
                "app_version": app_version,
            },
            ensure_ascii=False,
        ).encode("utf-8"),
        method="POST",
    )

    try:
        with urlopen(request, timeout=timeout_sec) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        if exc.code == 402:
            raise RuntimeError("NEED_RENEWAL") from exc
        if exc.code == 403:
            raise RuntimeError("LICENSE_SUSPENDED") from exc
        raise RuntimeError(f"HTTP_{exc.code}") from exc
    except URLError as exc:
        raise RuntimeError("LICENSE_ACTIVATION_UNAVAILABLE") from exc

    now = datetime.now(UTC)
    activated_at = now.replace(microsecond=0).isoformat().replace("+00:00", "Z")
    offline_grace_until = _add_days(now, int(payload["offline_grace_days"]))
    record = LicenseRecord(
        license_key=license_key,
        status=str(payload["status"]),
        device_id=device_id,
        license_tier=str(payload["license_tier"]),
        school_size_tier=str(payload["school_size_tier"]),
        billing_interval=payload.get("billing_interval"),
        student_count_total=int(payload["student_count_total"]),
        modules_enabled=[str(item) for item in payload.get("modules_enabled", [])],
        max_devices=int(payload["max_devices"]),
        activated_at=activated_at,
        expires_at=str(payload["expires_at"]),
        last_checked_at=activated_at,
        offline_grace_until=offline_grace_until,
    )
    store.save_activation(record)
    return build_license_status_snapshot(
        store.get_license(),
        message="ACTIVATION_OK",
        last_error=None,
        offline_mode=False,
    )


def refresh_license_status(
    store: LicenseStore,
    *,
    timeout_sec: int = 10,
) -> LicenseStatusSnapshot:
    record = store.get_license()
    if record is None:
        return build_license_status_snapshot(None)

    base_url = cloud_base_url()
    if not base_url:
        return build_license_status_snapshot(
            record,
            message="CLOUD_DISABLED",
            last_error="HEARTBEAT_DISABLED",
            offline_mode=True,
        )

    request = Request(
        f"{base_url}/v1/license/heartbeat",
        headers={
            "Authorization": f"Bearer {cloud_api_bearer_token()}",
            "Accept": "application/json",
            "X-DMC-License-Key": record.license_key,
            "X-DMC-Device-Id": record.device_id,
            "X-DMC-Device-Name": default_device_name(),
        },
        method="GET",
    )

    try:
        with urlopen(request, timeout=timeout_sec) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        error_code = "HEARTBEAT_FAILED"
        if exc.code == 402:
            error_code = "NEED_RENEWAL"
        elif exc.code == 403:
            error_code = "LICENSE_SUSPENDED"
        return build_license_status_snapshot(
            record,
            message=error_code,
            last_error=error_code,
            offline_mode=_is_within_offline_grace(record),
        )
    except URLError:
        return build_license_status_snapshot(
            record,
            message="HEARTBEAT_FAILED",
            last_error="HEARTBEAT_FAILED",
            offline_mode=True,
        )

    now = datetime.now(UTC)
    last_checked_at = now.replace(microsecond=0).isoformat().replace("+00:00", "Z")
    offline_grace_until = _add_days(now, int(payload["offline_grace_days"]))
    store.update_heartbeat(
        status=str(payload["status"]),
        license_tier=str(payload["license_tier"]),
        school_size_tier=str(payload["school_size_tier"]),
        billing_interval=payload.get("billing_interval"),
        student_count_total=int(payload["student_count_total"]),
        modules_enabled=[str(item) for item in payload.get("modules_enabled", [])],
        max_devices=int(payload["max_devices"]),
        expires_at=str(payload["expires_at"]),
        last_checked_at=last_checked_at,
        offline_grace_until=offline_grace_until,
    )
    updated_record = store.get_license()
    return build_license_status_snapshot(
        updated_record,
        message="HEARTBEAT_OK",
        last_error=None,
        offline_mode=False,
    )
