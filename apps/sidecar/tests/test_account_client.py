from __future__ import annotations

from io import BytesIO
from urllib.error import HTTPError

import pytest

from dmc_sidecar.account_client import _json_request
from dmc_sidecar.errors import DomainError


def test_json_request_ignores_untrusted_machine_error_detail(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("dmc_sidecar.account_client._cloud_base_url", lambda: "http://127.0.0.1:8000")

    def fake_urlopen(*_args: object, **_kwargs: object) -> object:
        raise HTTPError(
            "http://127.0.0.1:8000/v1/ocr/form-converter",
            413,
            "payload too large",
            {},
            BytesIO(b'{"detail":"OCR_PAGE_LIMIT_EXCEEDED"}'),
        )

    monkeypatch.setattr("dmc_sidecar.account_client.urlopen", fake_urlopen)

    with pytest.raises(DomainError, match="HTTP_413"):
        _json_request("/v1/ocr/form-converter", method="POST", payload={})


def test_json_request_preserves_allowlisted_machine_error_detail(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("dmc_sidecar.account_client._cloud_base_url", lambda: "http://127.0.0.1:8000")

    def fake_urlopen(*_args: object, **_kwargs: object) -> object:
        raise HTTPError(
            "http://127.0.0.1:8000/v1/credits/reservations",
            409,
            "conflict",
            {},
            BytesIO(b'{"detail":"CREDIT_IDEMPOTENCY_CONFLICT"}'),
        )

    monkeypatch.setattr("dmc_sidecar.account_client.urlopen", fake_urlopen)

    with pytest.raises(DomainError, match="CREDIT_IDEMPOTENCY_CONFLICT"):
        _json_request("/v1/credits/reservations", method="POST", payload={})


def test_json_request_maps_invalid_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("dmc_sidecar.account_client._cloud_base_url", lambda: "http://127.0.0.1:8000")

    def fake_urlopen(*_args: object, **_kwargs: object) -> object:
        raise HTTPError(
            "http://127.0.0.1:8000/v1/auth/login",
            401,
            "unauthorized",
            {},
            BytesIO(b'{"detail":"invalid email or password"}'),
        )

    monkeypatch.setattr("dmc_sidecar.account_client.urlopen", fake_urlopen)

    with pytest.raises(DomainError, match="INVALID_CREDENTIALS"):
        _json_request("/v1/auth/login", method="POST", payload={})
