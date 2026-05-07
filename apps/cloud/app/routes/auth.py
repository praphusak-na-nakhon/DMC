from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status

from ..account_service import AccountRepository, SessionRecord
from ..auth import require_account_session
from ..rate_limit import client_rate_limit_key, enforce_rate_limit, rate_limit
from ..schemas import AccountResponse, AuthLoginRequest, AuthLoginResponse


router = APIRouter()


def get_account_repository() -> AccountRepository:
    return AccountRepository()


@router.post("/login", response_model=AuthLoginResponse, dependencies=[Depends(rate_limit(scope="auth.login.ip", limit=60, window_seconds=60))])
def login(request: AuthLoginRequest, http_request: Request) -> AuthLoginResponse:
    normalized_email = request.email.strip().lower()
    try:
        token, account = get_account_repository().authenticate(
            email=request.email,
            password=request.password,
            device_id=request.device_id,
            device_name=request.device_name,
            app_version=request.app_version,
        )
    except HTTPException as exc:
        if exc.status_code == status.HTTP_401_UNAUTHORIZED:
            enforce_rate_limit(scope="auth.login.failed.email", key=normalized_email, limit=10, window_seconds=300)
            enforce_rate_limit(
                scope="auth.login.failed.ip_email",
                key=f"{client_rate_limit_key(http_request)}:{normalized_email}",
                limit=20,
                window_seconds=300,
            )
        raise
    return AuthLoginResponse(token=token, account=account)


@router.get("/me", response_model=AccountResponse)
def me(session: SessionRecord = Depends(require_account_session)) -> AccountResponse:
    return get_account_repository().account_response(session)


@router.post("/logout")
def logout(session: SessionRecord = Depends(require_account_session)) -> dict[str, bool]:
    get_account_repository().revoke_session(session.token)
    return {"ok": True}
