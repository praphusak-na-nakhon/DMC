from __future__ import annotations

import pytest

from app.ocr_service import OcrProviderError, _extract_json_object, _provider_http_error_code, _read_provider_response


def test_extract_json_object_returns_first_valid_object() -> None:
    assert _extract_json_object('prefix {"ok": true} suffix {"second": true}') == '{"ok": true}'


def test_read_provider_response_rejects_oversized_response() -> None:
    class OversizedResponse:
        def read(self, size: int) -> bytes:
            return b"x" * size

    with pytest.raises(OcrProviderError, match="OCR_PROVIDER_RESPONSE_TOO_LARGE"):
        _read_provider_response(OversizedResponse())


def test_provider_http_error_code_ignores_oversized_error_body() -> None:
    class OversizedHttpError:
        code = 429

        def read(self, size: int) -> bytes:
            return b"x" * size

    assert _provider_http_error_code("OCR_TEST", OversizedHttpError()) == "OCR_TEST_HTTP_429"  # type: ignore[arg-type]
