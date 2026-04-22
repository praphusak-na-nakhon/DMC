from __future__ import annotations

from fastapi import APIRouter, Depends

from ..auth import require_api_bearer
from ..pii_guard import assert_payload_is_telemetry_safe
from ..schemas import TelemetryBatchRequest


router = APIRouter(dependencies=[Depends(require_api_bearer)])


@router.post("")
def accept_telemetry(request: TelemetryBatchRequest) -> dict[str, int]:
    assert_payload_is_telemetry_safe(request.model_dump(mode="python"))
    return {"accepted": len(request.events), "rejected": 0}
