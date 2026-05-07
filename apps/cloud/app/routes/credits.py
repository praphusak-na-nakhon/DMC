from __future__ import annotations

from fastapi import APIRouter, Depends

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
    return AccountRepository().capture_credits(session.user_id, reservation_id, request)


@router.post("/reservations/{reservation_id}/release", response_model=CreditReservationResponse)
def release_credits(
    reservation_id: str,
    request: CreditReleaseRequest,
    session: SessionRecord = Depends(require_account_session),
) -> CreditReservationResponse:
    return AccountRepository().release_credits(session.user_id, reservation_id, request)
