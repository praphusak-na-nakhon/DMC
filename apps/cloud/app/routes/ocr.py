from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from starlette.concurrency import run_in_threadpool

from ..account_service import AccountRepository, SessionRecord
from ..auth import require_account_session
from ..config import settings
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


def _credits_required(request: OcrFormConverterRequest) -> int:
    return request.page_count * settings.form_converter_ocr_credits_per_page


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
    capture_key = f"ocr:{request_key}:capture"
    request_store = OcrRequestStore()
    cached_response = request_store.completed_response(user_id=session.user_id, request_key=request_key)
    if cached_response is not None:
        return cached_response

    if repository.has_credit_transaction(
        user_id=session.user_id,
        reservation_id=request.credit_reservation_id,
        transaction_type="capture",
        idempotency_key=capture_key,
    ):
        provider_response = request_store.provider_response(
            user_id=session.user_id,
            request_key=request_key,
        )
        if provider_response is not None:
            request_store.mark_done(user_id=session.user_id, request_key=request_key)
            return provider_response
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="OCR request was already captured but cached response is unavailable",
        )

    if reservation.status != "active":
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="active form converter credit reservation is required",
        )
    credits_required = _credits_required(request)
    remaining_units = reservation.units_reserved - reservation.units_captured - reservation.units_released
    if remaining_units < credits_required:
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
    captured = False
    try:
        response = await run_in_threadpool(run_form_converter_ocr, request)
        request_store.mark_provider_done(user_id=session.user_id, request_key=request_key, response=response)
        latest = repository.get_reservation(session.user_id, request.credit_reservation_id)
        target_captured = latest.units_captured + credits_required
        repository.capture_credits(
            session.user_id,
            request.credit_reservation_id,
            CreditCaptureRequest(
                units=target_captured,
                idempotency_key=capture_key,
            ),
        )
        captured = True
        request_store.mark_done(user_id=session.user_id, request_key=request_key)
    except Exception as exc:
        if not captured:
            request_store.mark_failed(
                user_id=session.user_id,
                request_key=request_key,
                error_detail=_safe_ocr_error_detail(exc),
            )
        raise
    return response


def _safe_ocr_error_detail(exc: Exception) -> str:
    if isinstance(exc, HTTPException):
        detail = exc.detail
        if isinstance(detail, str):
            normalized = detail.replace("_", "").replace("-", "").replace(":", "").replace(".", "")
            if 0 < len(detail) <= 120 and normalized.isalnum() and detail.upper() == detail:
                return detail
        return f"HTTP_{exc.status_code}"
    return exc.__class__.__name__.upper()
