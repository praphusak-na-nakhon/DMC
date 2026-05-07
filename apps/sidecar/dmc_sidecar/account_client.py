from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, cast
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .account_store import AccountSessionStore
from .config import secure_cloud_base_url
from .device_identity import default_device_name, get_or_create_device_id
from .errors import DomainError
from .schemas import (
    AccountSnapshot,
    CreditReservationSnapshot,
    ModuleCatalogItem,
    ModuleCatalogResponse,
    WalletSnapshot,
)


SERVER_DETAIL_ERROR_CODES = {
    "ACCOUNT_DISABLED",
    "CREDIT_IDEMPOTENCY_CONFLICT",
    "CREDIT_RESERVATION_NOT_FOUND",
    "INSUFFICIENT_CREDITS",
    "INVALID_CREDENTIALS",
    "SIGN_IN_REQUIRED",
    "WALLET_NOT_FOUND",
}


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_account_snapshot(
    store: AccountSessionStore,
    *,
    message: str | None = None,
    last_error: str | None = None,
) -> AccountSnapshot:
    session = store.get_session()
    if session is None:
        return AccountSnapshot(
            signed_in=False,
            user_id=None,
            email=None,
            display_name=None,
            status="missing",
            token_expires_at=None,
            last_checked_at=None,
            wallet=None,
            can_start_credit_jobs=False,
            needs_attention=True,
            message=message or "SIGN_IN_REQUIRED",
            last_error=last_error,
        )
    wallet_ready = session.wallet is not None
    return AccountSnapshot(
        signed_in=True,
        user_id=session.user_id,
        email=session.email,
        display_name=session.display_name,
        status=session.status,
        token_expires_at=session.token_expires_at,
        last_checked_at=session.last_checked_at,
        wallet=session.wallet,
        can_start_credit_jobs=session.status == "active" and wallet_ready and last_error is None,
        needs_attention=session.status != "active" or not wallet_ready or last_error is not None,
        message=message,
        last_error=last_error,
    )


def _cloud_base_url() -> str:
    try:
        base_url = secure_cloud_base_url()
    except DomainError:
        raise
    if not base_url:
        raise DomainError("ACCOUNT_CLOUD_REQUIRED")
    return base_url


def _json_request(
    path: str,
    *,
    method: str = "GET",
    token: str | None = None,
    payload: dict[str, Any] | None = None,
    timeout_sec: int = 10,
) -> dict[str, Any]:
    base_url = _cloud_base_url()
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(
        f"{base_url}{path}",
        headers=headers,
        data=json.dumps(payload or {}, ensure_ascii=False).encode("utf-8") if payload is not None else None,
        method=method,
    )
    try:
        with urlopen(request, timeout=timeout_sec) as response:
            body = response.read()
    except HTTPError as exc:
        detail = _http_error_detail(exc)
        if exc.code == 401:
            if detail == "invalid email or password":
                raise DomainError("INVALID_CREDENTIALS") from exc
            raise DomainError("SIGN_IN_REQUIRED") from exc
        if exc.code == 402:
            raise DomainError("INSUFFICIENT_CREDITS") from exc
        if exc.code == 403:
            raise DomainError("ACCOUNT_DISABLED") from exc
        if exc.code == 404:
            raise DomainError("CREDIT_RESERVATION_NOT_FOUND") from exc
        if detail in SERVER_DETAIL_ERROR_CODES:
            raise DomainError(detail) from exc
        raise DomainError(f"HTTP_{exc.code}") from exc
    except URLError as exc:
        raise DomainError("ACCOUNT_CLOUD_UNAVAILABLE") from exc
    if not body:
        return {}
    return cast(dict[str, Any], json.loads(body.decode("utf-8")))


def _http_error_detail(exc: HTTPError) -> str | None:
    try:
        body = exc.read()
    except OSError:
        return None
    if not body:
        return None
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    detail = payload.get("detail")
    return detail if isinstance(detail, str) else None


def sign_in(
    store: AccountSessionStore,
    *,
    email: str,
    password: str,
    device_name: str,
    app_version: str,
) -> AccountSnapshot:
    payload = _json_request(
        "/v1/auth/login",
        method="POST",
        payload={
            "email": email,
            "password": password,
            "device_id": get_or_create_device_id(),
            "device_name": device_name or default_device_name(),
            "app_version": app_version,
        },
    )
    account = payload["account"]
    wallet = WalletSnapshot.model_validate(_json_request("/v1/wallet", token=str(payload["token"])))
    catalog = get_module_catalog_from_cloud(str(payload["token"]))
    store.save_session(
        token=str(payload["token"]),
        user_id=str(account["user_id"]),
        email=str(account["email"]),
        display_name=account.get("display_name"),
        status=str(account["status"]),
        token_expires_at=str(account["token_expires_at"]),
        checked_at=utc_now(),
        wallet=wallet,
        module_catalog=catalog.modules,
    )
    return build_account_snapshot(store, message="SIGN_IN_OK")


def sign_out(store: AccountSessionStore) -> AccountSnapshot:
    session = store.get_session()
    if session is not None:
        try:
            _json_request("/v1/auth/logout", method="POST", token=session.token, payload={})
        except DomainError:
            pass
    store.clear()
    return build_account_snapshot(store, message="SIGNED_OUT")


def refresh_wallet(store: AccountSessionStore) -> AccountSnapshot:
    session = store.get_session()
    if session is None:
        return build_account_snapshot(store)
    wallet = WalletSnapshot.model_validate(_json_request("/v1/wallet", token=session.token))
    store.update_wallet(wallet, checked_at=utc_now())
    return build_account_snapshot(store, message="WALLET_REFRESHED")


def get_module_catalog_from_cloud(token: str) -> ModuleCatalogResponse:
    payload = _json_request("/v1/modules/catalog", token=token)
    return ModuleCatalogResponse.model_validate(payload)


def get_module_catalog(store: AccountSessionStore) -> ModuleCatalogResponse:
    session = store.get_session()
    if session is None:
        raise DomainError("SIGN_IN_REQUIRED")
    catalog = get_module_catalog_from_cloud(session.token)
    store.update_module_catalog(catalog.modules, checked_at=utc_now())
    return catalog


def reserve_credits(
    store: AccountSessionStore,
    *,
    job_id: str,
    module: str,
    units: int,
    idempotency_key: str,
) -> CreditReservationSnapshot:
    session = store.get_session()
    if session is None:
        raise DomainError("SIGN_IN_REQUIRED")
    payload = _json_request(
        "/v1/credits/reservations",
        method="POST",
        token=session.token,
        payload={
            "job_id": job_id,
            "module": module,
            "units": units,
            "idempotency_key": idempotency_key,
        },
    )
    reservation = CreditReservationSnapshot.model_validate(payload)
    store.update_wallet(reservation.wallet, checked_at=utc_now())
    return reservation


def capture_credits(
    store: AccountSessionStore,
    *,
    reservation_id: str,
    units: int,
    idempotency_key: str,
) -> CreditReservationSnapshot:
    session = store.get_session()
    if session is None:
        raise DomainError("SIGN_IN_REQUIRED")
    payload = _json_request(
        f"/v1/credits/reservations/{reservation_id}/capture",
        method="POST",
        token=session.token,
        payload={"units": units, "idempotency_key": idempotency_key},
    )
    reservation = CreditReservationSnapshot.model_validate(payload)
    store.update_wallet(reservation.wallet, checked_at=utc_now())
    return reservation


def release_credits(
    store: AccountSessionStore,
    *,
    reservation_id: str,
    units: int,
    idempotency_key: str,
) -> CreditReservationSnapshot:
    session = store.get_session()
    if session is None:
        raise DomainError("SIGN_IN_REQUIRED")
    payload = _json_request(
        f"/v1/credits/reservations/{reservation_id}/release",
        method="POST",
        token=session.token,
        payload={"units": units, "idempotency_key": idempotency_key},
    )
    reservation = CreditReservationSnapshot.model_validate(payload)
    store.update_wallet(reservation.wallet, checked_at=utc_now())
    return reservation


def cached_module_catalog(store: AccountSessionStore) -> ModuleCatalogResponse:
    session = store.get_session()
    if session is None or not session.module_catalog:
        return ModuleCatalogResponse(
            modules=[
                ModuleCatalogItem(
                    id="formConverter",
                    enabled=True,
                    requires_credits=False,
                    pricing_mode="per_billable_record",
                    credit_per_unit=0,
                    production_dry_run_enabled=False,
                ),
                ModuleCatalogItem(
                    id="currentStudents",
                    enabled=True,
                    requires_credits=True,
                    pricing_mode="per_billable_record",
                    credit_per_unit=1,
                    production_dry_run_enabled=False,
                ),
                ModuleCatalogItem(
                    id="psar",
                    enabled=True,
                    requires_credits=False,
                    pricing_mode="per_billable_record",
                    credit_per_unit=0,
                    production_dry_run_enabled=False,
                ),
                ModuleCatalogItem(
                    id="graduation",
                    enabled=True,
                    requires_credits=True,
                    pricing_mode="per_billable_record",
                    credit_per_unit=1,
                    production_dry_run_enabled=False,
                ),
            ]
        )
    return ModuleCatalogResponse(modules=session.module_catalog)
