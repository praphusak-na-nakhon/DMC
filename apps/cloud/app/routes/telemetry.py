from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ..account_service import AccountRepository
from ..license_service import LicenseRepository
from ..pii_guard import assert_payload_is_telemetry_safe
from ..schemas import TelemetryBatchRequest
from ..telemetry_store import TelemetryStore


router = APIRouter()
bearer_scheme = HTTPBearer(auto_error=False)


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


def verify_telemetry_session(
    credentials: HTTPAuthorizationCredentials | None,
) -> str | None:
    if credentials is None:
        return None
    if credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid telemetry auth scheme")
    return AccountRepository().get_session(credentials.credentials).user_id


@router.post("")
def accept_telemetry(
    request: TelemetryBatchRequest,
    x_dmc_license_key: str | None = Header(default=None),
    x_dmc_device_id: str | None = Header(default=None),
    credentials: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
) -> dict[str, int]:
    user_id = verify_telemetry_session(credentials)
    if user_id is None:
        verify_telemetry_device(x_dmc_license_key, x_dmc_device_id)
    payload = request.model_dump(mode="python")
    assert_payload_is_telemetry_safe(payload)
    get_telemetry_store().save_batch(
        license_key=x_dmc_license_key,
        user_id=user_id,
        device_id=x_dmc_device_id,
        events=payload["events"],
    )
    return {"accepted": len(request.events), "rejected": 0}
