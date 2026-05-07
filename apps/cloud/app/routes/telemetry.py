from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ..account_service import AccountRepository
from ..pii_guard import assert_payload_is_telemetry_safe
from ..rate_limit import rate_limit
from ..schemas import TelemetryBatchRequest
from ..telemetry_store import TelemetryStore


router = APIRouter()
bearer_scheme = HTTPBearer(auto_error=False)


def get_telemetry_store() -> TelemetryStore:
    return TelemetryStore()


def verify_telemetry_session(
    credentials: HTTPAuthorizationCredentials | None,
) -> str:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing telemetry account session")
    if credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid telemetry auth scheme")
    return AccountRepository().get_session(credentials.credentials).user_id


@router.post("", dependencies=[Depends(rate_limit(scope="telemetry.accept", limit=120, window_seconds=60))])
def accept_telemetry(
    request: TelemetryBatchRequest,
    credentials: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
) -> dict[str, int]:
    user_id = verify_telemetry_session(credentials)
    payload = request.model_dump(mode="python")
    try:
        assert_payload_is_telemetry_safe(payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    get_telemetry_store().save_batch(
        user_id=user_id,
        events=payload["events"],
    )
    return {"accepted": len(request.events), "rejected": 0}
