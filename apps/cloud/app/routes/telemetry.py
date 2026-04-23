from __future__ import annotations

from fastapi import APIRouter, Header

from ..pii_guard import assert_payload_is_telemetry_safe
from ..schemas import TelemetryBatchRequest
from ..telemetry_store import TelemetryStore


router = APIRouter()


def get_telemetry_store() -> TelemetryStore:
    return TelemetryStore()


@router.post("")
def accept_telemetry(
    request: TelemetryBatchRequest,
    x_dmc_license_key: str | None = Header(default=None),
    x_dmc_device_id: str | None = Header(default=None),
) -> dict[str, int]:
    payload = request.model_dump(mode="python")
    assert_payload_is_telemetry_safe(payload)
    get_telemetry_store().save_batch(
        license_key=x_dmc_license_key,
        device_id=x_dmc_device_id,
        events=payload["events"],
    )
    return {"accepted": len(request.events), "rejected": 0}
