from __future__ import annotations

from fastapi import APIRouter, Depends

from ..auth import require_api_bearer
from ..license_service import LicenseRepository
from ..schemas import CloudLicenseAdminResponse, CloudLicenseUpsertRequest


router = APIRouter(dependencies=[Depends(require_api_bearer)])


def get_license_repository() -> LicenseRepository:
    return LicenseRepository()


@router.get("/licenses", response_model=list[CloudLicenseAdminResponse])
def list_licenses() -> list[CloudLicenseAdminResponse]:
    return get_license_repository().list_licenses()


@router.put("/licenses/{license_key}", response_model=CloudLicenseAdminResponse)
def upsert_license(
    license_key: str,
    request: CloudLicenseUpsertRequest,
) -> CloudLicenseAdminResponse:
    return get_license_repository().upsert_license(
        license_key=license_key,
        request=request,
    )
