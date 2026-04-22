from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, status

from ..auth import require_api_bearer
from ..license_service import LicenseRepository, activate_license_request, heartbeat_license_request
from ..schemas import LicenseActivateRequest, LicenseStateResponse


router = APIRouter(dependencies=[Depends(require_api_bearer)])


def get_license_repository() -> LicenseRepository:
    return LicenseRepository()


@router.post("/activate", response_model=LicenseStateResponse)
def activate_license(request: LicenseActivateRequest) -> LicenseStateResponse:
    return activate_license_request(get_license_repository(), request)


@router.get("/heartbeat", response_model=LicenseStateResponse)
def heartbeat(
    x_dmc_license_key: str | None = Header(default=None),
    x_dmc_device_id: str | None = Header(default=None),
    x_dmc_device_name: str | None = Header(default=None),
) -> LicenseStateResponse:
    if not x_dmc_license_key or not x_dmc_device_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="missing license heartbeat headers",
        )

    return heartbeat_license_request(
        get_license_repository(),
        license_key=x_dmc_license_key,
        device_id=x_dmc_device_id,
        device_name=x_dmc_device_name or x_dmc_device_id,
    )
