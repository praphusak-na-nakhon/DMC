from __future__ import annotations

from fastapi import APIRouter

from ..schemas import TelemetryBatchRequest


router = APIRouter()


@router.post("")
def accept_telemetry(request: TelemetryBatchRequest) -> dict[str, int]:
    return {"accepted": len(request.events), "rejected": 0}
