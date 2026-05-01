from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from ..account_service import AccountRepository, SessionRecord
from ..auth import require_account_session
from ..ocr_service import run_form_converter_ocr
from ..schemas import OcrFormConverterRequest, OcrFormConverterResponse


router = APIRouter()


@router.post("/form-converter", response_model=OcrFormConverterResponse)
def convert_form_pdf(
    request: OcrFormConverterRequest,
    session: SessionRecord = Depends(require_account_session),
) -> OcrFormConverterResponse:
    reservation = AccountRepository().get_reservation(session.user_id, request.credit_reservation_id)
    if reservation.job_id != request.job_id or reservation.module != "formConverter" or reservation.status != "active":
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="active form converter credit reservation is required",
        )
    if reservation.units_reserved < request.page_count:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="credit reservation does not cover requested pages",
        )
    return run_form_converter_ocr(request)
