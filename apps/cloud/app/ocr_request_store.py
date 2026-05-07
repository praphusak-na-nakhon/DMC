from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from .config import settings
from .db import connect, utc_now
from .schemas import OcrFormConverterResponse


OCR_PROCESSING_STALE_MINUTES = 15


@dataclass(frozen=True)
class OcrRequestClaim:
    claimed: bool
    response: OcrFormConverterResponse | None = None
    processing: bool = False


class OcrRequestStore:
    def __init__(self, sqlite_path: str | None = None) -> None:
        self.sqlite_path = Path(sqlite_path or settings.sqlite_path)

    def completed_response(
        self,
        *,
        user_id: str,
        request_key: str,
    ) -> OcrFormConverterResponse | None:
        with connect(self.sqlite_path) as connection:
            row = connection.execute(
                """
                SELECT response_json
                FROM ocr_form_converter_requests
                WHERE user_id = ? AND request_key = ? AND status = 'done'
                """,
                (user_id, request_key),
            ).fetchone()
        if row is None or not row["response_json"]:
            return None
        return OcrFormConverterResponse.model_validate_json(str(row["response_json"]))

    def provider_response(
        self,
        *,
        user_id: str,
        request_key: str,
    ) -> OcrFormConverterResponse | None:
        with connect(self.sqlite_path) as connection:
            row = connection.execute(
                """
                SELECT response_json
                FROM ocr_form_converter_requests
                WHERE user_id = ? AND request_key = ? AND status = 'provider_done'
                """,
                (user_id, request_key),
            ).fetchone()
        if row is None or not row["response_json"]:
            return None
        return OcrFormConverterResponse.model_validate_json(str(row["response_json"]))

    def claim_processing(
        self,
        *,
        user_id: str,
        request_key: str,
        job_id: str,
        reservation_id: str,
        template_type: str,
        document_sha256: str,
        page_count: int,
    ) -> OcrRequestClaim:
        now = utc_now()
        stale_before = (
            datetime.now(UTC) - timedelta(minutes=OCR_PROCESSING_STALE_MINUTES)
        ).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        with connect(self.sqlite_path, immediate=True) as connection:
            row = connection.execute(
                """
                SELECT *
                FROM ocr_form_converter_requests
                WHERE user_id = ? AND request_key = ?
                """,
                (user_id, request_key),
            ).fetchone()
            if row is not None:
                if row["status"] == "done" and row["response_json"]:
                    return OcrRequestClaim(
                        claimed=False,
                        response=OcrFormConverterResponse.model_validate_json(str(row["response_json"])),
                    )
                if row["status"] == "provider_done" and str(row["updated_at"]) > stale_before:
                    return OcrRequestClaim(claimed=False, processing=True)
                if row["status"] == "processing" and str(row["updated_at"]) > stale_before:
                    return OcrRequestClaim(claimed=False, processing=True)
                connection.execute(
                    """
                    UPDATE ocr_form_converter_requests
                    SET status = 'processing',
                        error_detail = NULL,
                        updated_at = ?
                    WHERE user_id = ? AND request_key = ?
                    """,
                    (now, user_id, request_key),
                )
                return OcrRequestClaim(claimed=True)

            connection.execute(
                """
                INSERT INTO ocr_form_converter_requests (
                    user_id, request_key, job_id, reservation_id, template_type,
                    document_sha256, page_count, status, response_json,
                    error_detail, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, 'processing', NULL, NULL, ?, ?)
                """,
                (
                    user_id,
                    request_key,
                    job_id,
                    reservation_id,
                    template_type,
                    document_sha256,
                    page_count,
                    now,
                    now,
                ),
            )
            return OcrRequestClaim(claimed=True)

    def mark_provider_done(
        self,
        *,
        user_id: str,
        request_key: str,
        response: OcrFormConverterResponse,
    ) -> None:
        with connect(self.sqlite_path, immediate=True) as connection:
            connection.execute(
                """
                UPDATE ocr_form_converter_requests
                SET status = 'provider_done',
                    response_json = ?,
                    error_detail = NULL,
                    updated_at = ?
                WHERE user_id = ? AND request_key = ?
                """,
                (response.model_dump_json(), utc_now(), user_id, request_key),
            )

    def mark_done(
        self,
        *,
        user_id: str,
        request_key: str,
        response: OcrFormConverterResponse | None = None,
    ) -> None:
        with connect(self.sqlite_path, immediate=True) as connection:
            connection.execute(
                """
                UPDATE ocr_form_converter_requests
                SET status = 'done',
                    response_json = COALESCE(?, response_json),
                    error_detail = NULL,
                    updated_at = ?
                WHERE user_id = ? AND request_key = ?
                """,
                (
                    response.model_dump_json() if response is not None else None,
                    utc_now(),
                    user_id,
                    request_key,
                ),
            )

    def mark_failed(
        self,
        *,
        user_id: str,
        request_key: str,
        error_detail: str,
    ) -> None:
        with connect(self.sqlite_path, immediate=True) as connection:
            connection.execute(
                """
                UPDATE ocr_form_converter_requests
                SET status = 'failed',
                    error_detail = ?,
                    updated_at = ?
                WHERE user_id = ? AND request_key = ?
                """,
                (error_detail[:200], utc_now(), user_id, request_key),
            )
