from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from starlette.concurrency import run_in_threadpool

from ..account_service import AccountRepository, SessionRecord
from ..auth import require_account_session
from ..ocr_request_store import OcrRequestStore
from ..ocr_service import run_form_converter_ocr
from ..rate_limit import rate_limit
from ..schemas import CreditCaptureRequest, OcrFormConverterRequest, OcrFormConverterResponse


router = APIRouter()


def _ocr_request_key(request: OcrFormConverterRequest) -> str:
    return ":".join(
        [
            "form-converter",
            request.job_id,
            request.credit_reservation_id,
            request.template_type,
            request.document_sha256,
            str(request.page_count),
        ]
    )


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
    if reservation.job_id != request.job_id or reservation.module != "formConverter":
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="active form converter credit reservation is required",
        )
    request_key = _ocr_request_key(request)
    request_store = OcrRequestStore()
    cached_response = request_store.completed_response(user_id=session.user_id, request_key=request_key)
    if cached_response is not None:
        return cached_response

    if reservation.status != "active":
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
    claim = request_store.claim_processing(
        user_id=session.user_id,
        request_key=request_key,
        job_id=request.job_id,
        reservation_id=request.credit_reservation_id,
        template_type=request.template_type,
        document_sha256=request.document_sha256,
        page_count=request.page_count,
    )
    if claim.response is not None:
        return claim.response
    if claim.processing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="OCR request is already processing")
    try:
        response = await run_in_threadpool(run_form_converter_ocr, request)
        latest = repository.get_reservation(session.user_id, request.credit_reservation_id)
        target_captured = latest.units_captured + request.page_count
        repository.capture_credits(
            session.user_id,
            request.credit_reservation_id,
            CreditCaptureRequest(
                units=target_captured,
                idempotency_key=f"ocr:{request_key}:capture",
            ),
        )
        request_store.mark_done(user_id=session.user_id, request_key=request_key, response=response)
    except Exception as exc:
        request_store.mark_failed(user_id=session.user_id, request_key=request_key, error_detail=str(exc))
        raise
    return response
