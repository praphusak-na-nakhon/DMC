from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, status

from ..license_service import LicenseRepository
from ..pii_guard import assert_payload_is_telemetry_safe
from ..schemas import TelemetryBatchRequest
from ..telemetry_store import TelemetryStore


router = APIRouter()


def get_telemetry_store() -> TelemetryStore:
    return TelemetryStore()


def verify_telemetry_device(license_key: str | None, device_id: str | None) -> None:
    if not license_key or not device_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="telemetry license and device headers are required",
        )
    if not LicenseRepository().has_device(license_key=license_key, device_id=device_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="telemetry device is not activated",
        )


@router.post("")
def accept_telemetry(
    request: TelemetryBatchRequest,
    x_dmc_license_key: str | None = Header(default=None),
    x_dmc_device_id: str | None = Header(default=None),
) -> dict[str, int]:
    verify_telemetry_device(x_dmc_license_key, x_dmc_device_id)
    payload = request.model_dump(mode="python")
    assert_payload_is_telemetry_safe(payload)
    get_telemetry_store().save_batch(
        license_key=x_dmc_license_key,
        device_id=x_dmc_device_id,
        events=payload["events"],
    )
    return {"accepted": len(request.events), "rejected": 0}
