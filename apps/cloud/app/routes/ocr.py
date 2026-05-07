from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from starlette.concurrency import run_in_threadpool

from ..account_service import AccountRepository, SessionRecord
from ..auth import require_account_session
from ..ocr_service import run_form_converter_ocr
from ..rate_limit import rate_limit
from ..schemas import CreditCaptureRequest, OcrFormConverterRequest, OcrFormConverterResponse


router = APIRouter()


@router.post(
    "/form-converter",
    response_model=OcrFormConverterResponse,
    dependencies=[Depends(rate_limit(scope="ocr.form_converter", limit=30, window_seconds=60))],
)
async def convert_form_pdf(
    request: OcrFormConverterRequest,
    session: SessionRecord = Depends(require_account_session),
) -> OcrFormConverterResponse:
    repository = AccountRepository()
    reservation = repository.get_reservation(session.user_id, request.credit_reservation_id)
    if reservation.job_id != request.job_id or reservation.module != "formConverter" or reservation.status != "active":
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="active form converter credit reservation is required",
        )
    remaining_units = reservation.units_reserved - reservation.units_captured - reservation.units_released
    if remaining_units < request.page_count:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="credit reservation does not cover requested pages",
        )
    response = await run_in_threadpool(run_form_converter_ocr, request)
    latest = repository.get_reservation(session.user_id, request.credit_reservation_id)
    target_captured = latest.units_captured + request.page_count
    repository.capture_credits(
        session.user_id,
        request.credit_reservation_id,
        CreditCaptureRequest(
            units=target_captured,
            idempotency_key=f"ocr:{request.job_id}:{request.document_sha256}:capture:{target_captured}",
        ),
    )
    return response
