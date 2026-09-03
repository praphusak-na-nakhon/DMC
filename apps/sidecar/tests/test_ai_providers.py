from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from google.genai.errors import ClientError

from ai_fakes import InMemorySecretStore
from dmc_sidecar.ai.base import OcrDocumentRequest
from dmc_sidecar.ai.gemini import GeminiProvider
from dmc_sidecar.ai.registry import build_provider_registry
from dmc_sidecar.errors import DomainError
from dmc_sidecar.gemini_ocr import GeminiOcrDmcFormResponse


def test_registry_exposes_only_gemini() -> None:
    assert build_provider_registry(InMemorySecretStore()).supported_provider_ids() == ["gemini"]


def test_registry_rejects_unknown_provider() -> None:
    with pytest.raises(DomainError) as exc_info:
        build_provider_registry(InMemorySecretStore()).get("openai")

    assert exc_info.value.code == "AI_PROVIDER_UNAVAILABLE"


def test_gemini_ocr_requires_a_stored_key(tmp_path: Path) -> None:
    with pytest.raises(DomainError) as exc_info:
        build_provider_registry(InMemorySecretStore()).get("gemini").ocr_document(
            OcrDocumentRequest(provider="gemini", source_path=str(tmp_path / "form.pdf"))
        )

    assert exc_info.value.code == "AI_API_KEY_REQUIRED"


def test_gemini_provider_maps_engine_response_without_legacy_credit_fields(tmp_path: Path) -> None:
    store = InMemorySecretStore()
    store.set("gemini", "secret-value")
    captured: dict[str, object] = {}

    def fake_engine(request: object, *, api_key: str) -> GeminiOcrDmcFormResponse:
        captured["request"] = request
        captured["api_key"] = api_key
        return GeminiOcrDmcFormResponse(
            model="gemini-3.5-flash",
            processing_mode="batch",
            source_path=str(tmp_path / "form.pdf"),
            markdown_path=str(tmp_path / "output.json"),
            structured_json_path=str(tmp_path / "output.json"),
            cached=False,
            pages_processed=2,
            pages_estimated=2,
            average_confidence=0.92,
            batch_job_name="batches/123",
            batch_state="JOB_STATE_SUCCEEDED",
            file_sha256="sha256",
            created_at="2026-09-04T00:00:00+00:00",
        )

    response = GeminiProvider(store, ocr_engine=fake_engine).ocr_document(
        OcrDocumentRequest(provider="gemini", source_path=str(tmp_path / "form.pdf"))
    )

    assert captured["api_key"] == "secret-value"
    assert "api_key" not in captured["request"].model_dump()  # type: ignore[union-attr]
    assert response.pages_processed == response.pages_estimated == 2
    assert response.average_confidence == 0.92
    assert response.provider == "gemini"
    assert response.provider_job_id == "batches/123"
    assert response.provider_job_state == "JOB_STATE_SUCCEEDED"
    assert not ({"credits_per_page", "credits_charged", "charged", "credit_reservation_id"} & set(response.model_dump()))


def test_gemini_connection_tests_metadata_and_closes_client() -> None:
    store = InMemorySecretStore()
    store.set("gemini", "secret-value")
    calls: list[str] = []

    class FakeClient:
        models = SimpleNamespace(get=lambda **_: calls.append("metadata"))

        def close(self) -> None:
            calls.append("close")

    response = GeminiProvider(store, client_factory=lambda **_: FakeClient()).test_connection()

    assert response.provider == "gemini"
    assert response.ok is True
    assert response.message == "Gemini connection succeeded."
    assert calls == ["metadata", "close"]


@pytest.mark.parametrize(
    ("metadata_error", "expected_code"),
    [
        (
            ClientError(403, {"error": {"status": "PERMISSION_DENIED", "message": "Authorization: Bearer secret-value"}}),
            "AI_API_KEY_INVALID",
        ),
        (httpx.ReadTimeout("Authorization: Bearer secret-value"), "AI_REQUEST_TIMEOUT"),
    ],
    ids=["sdk-authentication", "http-timeout"],
)
def test_gemini_connection_translates_raw_client_errors_and_closes_client(
    metadata_error: Exception,
    expected_code: str,
) -> None:
    store = InMemorySecretStore()
    store.set("gemini", "secret-value")
    calls: list[str] = []

    class FakeClient:
        models = SimpleNamespace(get=lambda **_: (_ for _ in ()).throw(metadata_error))

        def close(self) -> None:
            calls.append("close")

    with pytest.raises(DomainError) as exc_info:
        GeminiProvider(store, client_factory=lambda **_: FakeClient()).test_connection()

    assert exc_info.value.code == expected_code
    assert "secret-value" not in exc_info.value.user_message
    assert "secret-value" not in str(exc_info.value.details)
    assert calls == ["close"]


@pytest.mark.parametrize(
    ("vendor_code", "expected_code"),
    [
        ("GEMINIOCR_AUTH_FAILED", "AI_API_KEY_INVALID"),
        ("GEMINIOCR_RATE_LIMITED", "AI_RATE_LIMITED"),
        ("GEMINIOCR_NETWORK_ERROR", "AI_REQUEST_TIMEOUT"),
        ("GEMINIOCR_RESPONSE_INVALID", "AI_RESPONSE_INVALID"),
        ("GEMINIOCR_UNSUPPORTED_INPUT_TYPE", "AI_INPUT_UNSUPPORTED"),
        ("GEMINIOCR_BATCH_FAILED", "AI_JOB_FAILED"),
    ],
)
def test_gemini_provider_translates_and_redacts_vendor_failures(vendor_code: str, expected_code: str, tmp_path: Path) -> None:
    store = InMemorySecretStore()
    store.set("gemini", "secret-value")

    def failing_engine(_: object, *, api_key: str) -> GeminiOcrDmcFormResponse:
        raise DomainError(vendor_code, "Authorization: Bearer secret-value student document")

    with pytest.raises(DomainError) as exc_info:
        GeminiProvider(store, ocr_engine=failing_engine).ocr_document(
            OcrDocumentRequest(provider="gemini", source_path=str(tmp_path / "form.pdf"))
        )

    assert exc_info.value.code == expected_code
    assert "secret-value" not in exc_info.value.user_message
    assert "student document" not in exc_info.value.user_message
