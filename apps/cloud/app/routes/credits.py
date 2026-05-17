from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from ..account_service import AccountRepository, SessionRecord
from ..auth import require_account_session
from ..rate_limit import rate_limit
from ..schemas import (
    CreditCaptureRequest,
    CreditReleaseRequest,
    CreditReservationRequest,
    CreditReservationResponse,
)


router = APIRouter(dependencies=[Depends(rate_limit(scope="credits", limit=300, window_seconds=60))])
RESERVED_IDEMPOTENCY_PREFIXES = ("ocr:",)


def _reject_reserved_idempotency_key(idempotency_key: str | None) -> None:
    if idempotency_key and idempotency_key.startswith(RESERVED_IDEMPOTENCY_PREFIXES):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="reserved idempotency key")


@router.post("/reservations", response_model=CreditReservationResponse)
def reserve_credits(
    request: CreditReservationRequest,
    session: SessionRecord = Depends(require_account_session),
) -> CreditReservationResponse:
    return AccountRepository().reserve_credits(session.user_id, request)


@router.post("/reservations/{reservation_id}/capture", response_model=CreditReservationResponse)
def capture_credits(
    reservation_id: str,
    request: CreditCaptureRequest,
    session: SessionRecord = Depends(require_account_session),
) -> CreditReservationResponse:
    _reject_reserved_idempotency_key(request.idempotency_key)
    return AccountRepository().capture_credits(session.user_id, reservation_id, request)


@router.post("/reservations/{reservation_id}/release", response_model=CreditReservationResponse)
def release_credits(
    reservation_id: str,
    request: CreditReleaseRequest,
    session: SessionRecord = Depends(require_account_session),
) -> CreditReservationResponse:
    _reject_reserved_idempotency_key(request.idempotency_key)
    return AccountRepository().release_credits(session.user_id, reservation_id, request)
