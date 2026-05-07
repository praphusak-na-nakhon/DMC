from __future__ import annotations

import pytest

from app.ocr_service import OcrProviderError, _extract_json_object, _read_provider_response


def test_extract_json_object_returns_first_valid_object() -> None:
    assert _extract_json_object('prefix {"ok": true} suffix {"second": true}') == '{"ok": true}'


def test_read_provider_response_rejects_oversized_response() -> None:
    class OversizedResponse:
        def read(self, size: int) -> bytes:
            return b"x" * size

    with pytest.raises(OcrProviderError, match="OCR_PROVIDER_RESPONSE_TOO_LARGE"):
        _read_provider_response(OversizedResponse())
