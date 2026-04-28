from __future__ import annotations

from fastapi import APIRouter, Depends

from ..account_service import AccountRepository
from ..auth import require_api_bearer
from ..license_service import LicenseRepository
from ..schemas import (
    CloudCreditTopupRequest,
    CloudLicenseAdminResponse,
    CloudLicenseUpsertRequest,
    CloudUserAdminResponse,
    CloudUserCreateRequest,
    CreditLedgerEntry,
    WalletResponse,
)


router = APIRouter(dependencies=[Depends(require_api_bearer)])


def get_license_repository() -> LicenseRepository:
    return LicenseRepository()


def get_account_repository() -> AccountRepository:
    return AccountRepository()


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


@router.post("/users", response_model=CloudUserAdminResponse)
def create_user(request: CloudUserCreateRequest) -> CloudUserAdminResponse:
    return get_account_repository().create_user(request)


@router.post("/users/{user_id}/credits/topup", response_model=WalletResponse)
def topup_user_credits(
    user_id: str,
    request: CloudCreditTopupRequest,
) -> WalletResponse:
    return get_account_repository().topup_user(user_id, request)


@router.get("/users/{user_id}/ledger", response_model=list[CreditLedgerEntry])
def user_credit_ledger(user_id: str) -> list[CreditLedgerEntry]:
    return get_account_repository().list_ledger(user_id)
