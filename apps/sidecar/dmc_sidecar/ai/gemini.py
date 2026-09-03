from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any, Literal

from httpx import TimeoutException

from .base import AiConnectionTestResponse, AiProviderId, OcrDocumentRequest, OcrDocumentResponse, OcrUsageMetadata, SecretStore
from ..errors import DomainError
from ..gemini_ocr import GEMINI_OCR_MODEL, GeminiOcrDmcFormRequest, GeminiOcrDmcFormResponse, ocr_dmc_form_with_gemini


GeminiOcrEngine = Callable[[GeminiOcrDmcFormRequest], GeminiOcrDmcFormResponse]
GeminiClientFactory = Callable[..., Any]


class GeminiProvider:
    provider_id: AiProviderId = "gemini"

    def __init__(
        self,
        secret_store: SecretStore,
        *,
        ocr_engine: GeminiOcrEngine = ocr_dmc_form_with_gemini,
        client_factory: GeminiClientFactory | None = None,
    ) -> None:
        self._secret_store = secret_store
        self._ocr_engine = ocr_engine
        self._client_factory = client_factory or _create_gemini_client

    def test_connection(self) -> AiConnectionTestResponse:
        api_key = self._stored_api_key()
        client: Any | None = None
        try:
            client = self._client_factory(api_key=api_key)
            client.models.get(model=GEMINI_OCR_MODEL)
        except Exception as exc:
            raise _safe_ai_error(exc) from None
        finally:
            if client is not None:
                _close_client(client)
        return AiConnectionTestResponse(
            provider="gemini",
            ok=True,
            tested_at=_utc_now(),
            message="Gemini connection succeeded.",
        )

    def ocr_document(self, request: OcrDocumentRequest) -> OcrDocumentResponse:
        if request.provider != self.provider_id:
            raise DomainError("AI_PROVIDER_UNAVAILABLE")
        api_key = self._stored_api_key()
        try:
            engine_response = self._ocr_engine(
                GeminiOcrDmcFormRequest(
                    source_path=request.source_path,
                    api_key=api_key,
                    model=request.model,
                    processing_mode=request.processing_mode,
                    force_refresh=request.force_refresh,
                )
            )
        except Exception as exc:
            raise _safe_ai_error(exc) from None
        return OcrDocumentResponse(
            provider="gemini",
            model=engine_response.model,
            processing_mode=_processing_mode(engine_response.processing_mode),
            source_path=engine_response.source_path,
            markdown_path=engine_response.markdown_path,
            structured_json_path=engine_response.structured_json_path,
            output_format=engine_response.output_format,
            cached=engine_response.cached,
            pages_processed=engine_response.pages_processed,
            pages_estimated=engine_response.pages_estimated,
            average_confidence=engine_response.average_confidence,
            usage_metadata=_usage_metadata(engine_response),
            provider_job_id=engine_response.batch_job_name,
            provider_job_state=engine_response.batch_state,
            file_sha256=engine_response.file_sha256,
            created_at=engine_response.created_at,
        )

    def _stored_api_key(self) -> str:
        value = (self._secret_store.get(self.provider_id) or "").strip()
        if not value:
            raise DomainError("AI_API_KEY_REQUIRED")
        return value


def _create_gemini_client(*, api_key: str) -> Any:
    try:
        from google import genai
    except Exception:
        raise DomainError("AI_PROVIDER_UNAVAILABLE") from None
    return genai.Client(api_key=api_key)


def _usage_metadata(response: GeminiOcrDmcFormResponse) -> OcrUsageMetadata | None:
    if response.usage_metadata is None:
        return None
    return OcrUsageMetadata.model_validate(response.usage_metadata.model_dump(exclude_none=True))


def _processing_mode(value: str) -> Literal["standard", "batch"]:
    if value == "standard":
        return "standard"
    if value == "batch":
        return "batch"
    raise DomainError("AI_RESPONSE_INVALID")


def _close_client(client: Any) -> None:
    close = getattr(client, "close", None)
    if callable(close):
        try:
            close()
        except Exception:
            return


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_ai_error(exc: Exception) -> DomainError:
    if isinstance(exc, DomainError) and exc.code.startswith("AI_"):
        return DomainError(exc.code)
    if isinstance(exc, TimeoutException):
        return DomainError("AI_REQUEST_TIMEOUT")
    status_code = _status_code(exc)
    if status_code in {401, 403}:
        return DomainError("AI_API_KEY_INVALID")
    if status_code == 429:
        return DomainError("AI_RATE_LIMITED")
    if status_code in {408, 504}:
        return DomainError("AI_REQUEST_TIMEOUT")
    code = exc.code if isinstance(exc, DomainError) else ""
    message = str(exc).upper()
    if code in {"GEMINIOCR_API_KEY_REQUIRED"}:
        return DomainError("AI_API_KEY_REQUIRED")
    if code in {"GEMINIOCR_AUTH_FAILED"} or "UNAUTHENTICATED" in message or "API_KEY" in message or "API KEY" in message:
        return DomainError("AI_API_KEY_INVALID")
    if code == "GEMINIOCR_RATE_LIMITED" or "RESOURCE_EXHAUSTED" in message or "QUOTA" in message or "429" in message:
        return DomainError("AI_RATE_LIMITED")
    if code in {"GEMINIOCR_NETWORK_ERROR", "GEMINIOCR_FILE_PROCESSING_TIMEOUT", "GEMINIOCR_BATCH_TIMEOUT"} or "TIMEOUT" in message:
        return DomainError("AI_REQUEST_TIMEOUT")
    if code in {
        "GEMINIOCR_UNSUPPORTED_INPUT_TYPE",
        "GEMINIOCR_INPUT_NOT_FOUND",
        "GEMINIOCR_INPUT_NOT_FILE",
        "GEMINIOCR_INPUT_EMPTY",
        "GEMINIOCR_FILE_TOO_LARGE",
        "GEMINIOCR_PAGE_LIMIT_EXCEEDED",
    }:
        return DomainError("AI_INPUT_UNSUPPORTED")
    if code in {"GEMINIOCR_BATCH_FAILED", "GEMINIOCR_BATCH_RESPONSE_MISSING", "GEMINIOCR_PROCESSING_FAILED"}:
        return DomainError("AI_JOB_FAILED")
    return DomainError("AI_RESPONSE_INVALID")


def _status_code(exc: Exception) -> int | None:
    for attribute in ("status_code", "code"):
        value = getattr(exc, attribute, None)
        if isinstance(value, int):
            return value
    response = getattr(exc, "response", None)
    value = getattr(response, "status_code", None)
    return value if isinstance(value, int) else None
