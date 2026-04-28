from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..account_service import AccountRepository
from ..auth import require_api_bearer
from ..license_service import LicenseRepository
from ..schemas import (
    CloudCreditTopupRequest,
    CloudLicenseAdminResponse,
    CloudLicenseUpsertRequest,
    CloudUserAdminResponse,
    CloudUserCreateRequest,
    CloudUserUpdateRequest,
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


@router.get("/users", response_model=list[CloudUserAdminResponse])
def list_users(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[CloudUserAdminResponse]:
    return get_account_repository().list_users(limit=limit, offset=offset)


@router.get("/users/{user_id}", response_model=CloudUserAdminResponse)
def get_user(user_id: str) -> CloudUserAdminResponse:
    user = get_account_repository().get_user_admin(user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")
    return user


@router.patch("/users/{user_id}", response_model=CloudUserAdminResponse)
def update_user(user_id: str, request: CloudUserUpdateRequest) -> CloudUserAdminResponse:
    return get_account_repository().update_user(user_id, request)


@router.get("/users/{user_id}/wallet", response_model=WalletResponse)
def user_wallet(user_id: str) -> WalletResponse:
    user = get_account_repository().get_user_admin(user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")
    return user.wallet


@router.post("/users/{user_id}/credits/topup", response_model=WalletResponse)
def topup_user_credits(
    user_id: str,
    request: CloudCreditTopupRequest,
) -> WalletResponse:
    return get_account_repository().topup_user(user_id, request)


@router.get("/users/{user_id}/ledger", response_model=list[CreditLedgerEntry])
def user_credit_ledger(user_id: str) -> list[CreditLedgerEntry]:
    return get_account_repository().list_ledger(user_id)
