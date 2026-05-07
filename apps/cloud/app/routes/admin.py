from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from ..account_service import AccountRepository
from ..auth import require_api_bearer
from ..rate_limit import rate_limit
from ..schemas import (
    CloudCreditTopupRequest,
    CloudCreditTopupDecisionRequest,
    CloudCreditTopupRequestCreate,
    CloudCreditTopupRequestResponse,
    CloudUserAdminResponse,
    CloudUserCreateRequest,
    CloudUserUpdateRequest,
    AdminAuditEntry,
    CreditLedgerEntry,
    WalletResponse,
)


router = APIRouter(dependencies=[Depends(require_api_bearer), Depends(rate_limit(scope="admin", limit=300, window_seconds=60))])


def get_account_repository() -> AccountRepository:
    return AccountRepository()


def admin_actor(request: Request) -> str:
    actor = getattr(request.state, "admin_actor", None)
    return str(actor) if actor else "admin:unknown"


@router.post("/users", response_model=CloudUserAdminResponse)
def create_user(request: Request, payload: CloudUserCreateRequest) -> CloudUserAdminResponse:
    repository = get_account_repository()
    user = repository.create_user(payload)
    repository.record_admin_audit(
        actor=admin_actor(request),
        action="user.created",
        target_type="user",
        target_id=user.user_id,
        payload={"status": user.status},
    )
    return user


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
def update_user(user_id: str, request: Request, payload: CloudUserUpdateRequest) -> CloudUserAdminResponse:
    user = get_account_repository().update_user(user_id, payload)
    changed_fields = [
        field
        for field in ("password", "display_name", "status")
        if getattr(payload, field) is not None
    ]
    get_account_repository().record_admin_audit(
        actor=admin_actor(request),
        action="user.updated",
        target_type="user",
        target_id=user_id,
        payload={"changed_fields": changed_fields},
    )
    return user


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
    http_request: Request,
) -> WalletResponse:
    wallet = get_account_repository().topup_user(user_id, request)
    get_account_repository().record_admin_audit(
        actor=admin_actor(http_request),
        action="credit.topup.direct",
        target_type="user",
        target_id=user_id,
        payload={"amount": request.amount},
    )
    return wallet


@router.post("/users/{user_id}/credits/topup-requests", response_model=CloudCreditTopupRequestResponse)
def create_user_topup_request(
    user_id: str,
    payload: CloudCreditTopupRequestCreate,
    request: Request,
) -> CloudCreditTopupRequestResponse:
    return get_account_repository().create_topup_request(user_id, payload, actor=admin_actor(request))


@router.get("/credits/topup-requests", response_model=list[CloudCreditTopupRequestResponse])
def list_credit_topup_requests(
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[CloudCreditTopupRequestResponse]:
    return get_account_repository().list_topup_requests(status_filter=status_filter, limit=limit, offset=offset)


@router.post("/credits/topup-requests/{request_id}/decision", response_model=CloudCreditTopupRequestResponse)
def decide_credit_topup_request(
    request_id: str,
    payload: CloudCreditTopupDecisionRequest,
    request: Request,
) -> CloudCreditTopupRequestResponse:
    return get_account_repository().decide_topup_request(request_id, payload, actor=admin_actor(request))


@router.get("/audit", response_model=list[AdminAuditEntry])
def list_admin_audit(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[AdminAuditEntry]:
    return get_account_repository().list_admin_audit(limit=limit, offset=offset)


@router.get("/users/{user_id}/ledger", response_model=list[CreditLedgerEntry])
def user_credit_ledger(
    user_id: str,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[CreditLedgerEntry]:
    return get_account_repository().list_ledger(user_id, limit=limit, offset=offset)
