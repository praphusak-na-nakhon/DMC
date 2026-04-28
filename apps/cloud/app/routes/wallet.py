from __future__ import annotations

from fastapi import APIRouter, Depends

from ..account_service import AccountRepository, SessionRecord
from ..auth import require_account_session
from ..schemas import WalletResponse


router = APIRouter()


@router.get("", response_model=WalletResponse)
def get_wallet(session: SessionRecord = Depends(require_account_session)) -> WalletResponse:
    return AccountRepository().get_wallet(session.user_id)
