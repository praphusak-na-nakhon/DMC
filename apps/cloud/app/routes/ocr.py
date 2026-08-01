from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from starlette.concurrency import run_in_threadpool

from ..account_service import AccountRepository, SessionRecord
from ..auth import require_account_session
from ..config import settings
from ..ocr_request_store import OcrRequestStore, OCR_PROCESSING_STALE_MINUTES
from ..ocr_service import run_form_converter_ocr, validate_form_converter_document
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


def _credits_required(page_count: int) -> int:
    return page_count * settings.form_converter_ocr_credits_per_page


def _attempt_scoped_key(base: str, attempt: int) -> str:
    return base if attempt <= 1 else f"{base}:{attempt}"


def _is_stale_updated_at(updated_at: str) -> bool:
    stale_before = (
        datetime.now(UTC) - timedelta(minutes=OCR_PROCESSING_STALE_MINUTES)
    ).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return str(updated_at) <= stale_before


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
    validated_document = validate_form_converter_document(request)
    request_key = _ocr_request_key(request)
    request_store = OcrRequestStore()
    cached_response = request_store.completed_response(user_id=session.user_id, request_key=request_key)
    if cached_response is not None:
        return cached_response

    credits_required = _credits_required(validated_document.actual_page_count)
    capture_prefix = f"ocr:{request_key}:capture"
    refund_prefix = f"ocr:{request_key}:provider-failed-refund"
    prior_capture_count = repository.count_credit_transactions_with_prefix(
        user_id=session.user_id,
        reservation_id=request.credit_reservation_id,
        transaction_type="capture",
        idempotency_key_prefix=capture_prefix,
    )
    attempt = prior_capture_count + 1
    capture_key = _attempt_scoped_key(capture_prefix, attempt)
    refund_key = _attempt_scoped_key(refund_prefix, attempt)

    if prior_capture_count > 0:
        prior_capture_key = _attempt_scoped_key(capture_prefix, prior_capture_count)
        prior_refund_key = _attempt_scoped_key(refund_prefix, prior_capture_count)
        if repository.has_credit_transaction(
            user_id=session.user_id,
            reservation_id=request.credit_reservation_id,
            transaction_type="capture",
            idempotency_key=prior_capture_key,
        ):
            provider_response = request_store.provider_response(
                user_id=session.user_id,
                request_key=request_key,
            )
            if provider_response is not None:
                request_store.mark_done(user_id=session.user_id, request_key=request_key)
                return provider_response
            prior_refunded = repository.has_credit_transaction(
                user_id=session.user_id,
                reservation_id=request.credit_reservation_id,
                transaction_type="release",
                idempotency_key=prior_refund_key,
            )
            if not prior_refunded:
                if not _stale_request_reclaimable(request_store, session.user_id, request_key):
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="OCR request was already captured but cached response is unavailable",
                    )
                # A previous attempt captured credits but crashed before caching a
                # response. Refund the stuck capture so the retry can capture again
                # under a fresh idempotency key after claim_processing reclaims the
                # stale request row below.
                try:
                    repository.refund_captured_credits(
                        session.user_id,
                        request.credit_reservation_id,
                        units=credits_required,
                        idempotency_key=prior_refund_key,
                        note="form converter OCR crashed before a response was cached",
                    )
                except Exception:
                    pass

    reservation = repository.get_reservation(session.user_id, request.credit_reservation_id)
    if reservation.status != "active":
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="active form converter credit reservation is required",
        )
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
    provider_done = False
    try:
        latest = repository.get_reservation(session.user_id, request.credit_reservation_id)
        target_captured = latest.units_captured + credits_required
        repository.capture_credits(
            session.user_id,
            request.credit_reservation_id,
            CreditCaptureRequest(
                target_captured_units=target_captured,
                idempotency_key=capture_key,
            ),
        )
        captured = True
        response = await run_in_threadpool(run_form_converter_ocr, request)
        request_store.mark_provider_done(user_id=session.user_id, request_key=request_key, response=response)
        provider_done = True
        request_store.mark_done(user_id=session.user_id, request_key=request_key)
    except Exception as exc:
        if captured and not provider_done:
            try:
                repository.refund_captured_credits(
                    session.user_id,
                    request.credit_reservation_id,
                    units=credits_required,
                    idempotency_key=refund_key,
                    note="form converter OCR provider failed before a response was cached",
                )
            except Exception:
                pass
        if not provider_done:
            request_store.mark_failed(
                user_id=session.user_id,
                request_key=request_key,
                error_detail=_safe_ocr_error_detail(exc),
            )
        raise
    return response


def _stale_request_reclaimable(
    request_store: OcrRequestStore,
    user_id: str,
    request_key: str,
) -> bool:
    """Return True when a previous OCR attempt is old enough to safely reclaim.

    A prior attempt may have captured credits but never cached a provider
    response (crash between capture and completion). After the stale window
    expires the request can be reclaimed and the capture refunded, so a client
    retry can make progress instead of hitting a permanent 409.
    """
    row = request_store.request_status(user_id=user_id, request_key=request_key)
    if row is None:
        return False
    return _is_stale_updated_at(str(row["updated_at"]))


def _safe_ocr_error_detail(exc: Exception) -> str:
    if isinstance(exc, HTTPException):
        detail = exc.detail
        if isinstance(detail, str):
            normalized = detail.replace("_", "").replace("-", "").replace(":", "").replace(".", "")
            if 0 < len(detail) <= 120 and normalized.isalnum() and detail.upper() == detail:
                return detail
        return f"HTTP_{exc.status_code}"
    return exc.__class__.__name__.upper()
