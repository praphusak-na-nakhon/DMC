from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path

from dmc_sidecar import config, module_config


class FakeResponse:
    def __init__(self, status: int, payload: dict[str, object] | None = None) -> None:
        self.status = status
        self._payload = payload

    def read(self) -> bytes:
        return json.dumps(self._payload or {}).encode("utf-8")

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


def sign_payload(secret: str, version: str, payload: dict[str, object]) -> str:
    digest = hmac.new(
        secret.encode("utf-8"),
        module_config._canonical_payload(version, payload),  # noqa: SLF001
        hashlib.sha256,
    ).hexdigest()
    return f"hmac-sha256:{digest}"


def test_sync_module_config_downloads_and_caches_verified_payload(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(config, "default_data_dir", lambda: tmp_path)
    monkeypatch.setattr(module_config, "cloud_base_url", lambda: "https://cloud.example.test")
    monkeypatch.setattr(module_config, "cloud_api_bearer_token", lambda: "token-1")
    monkeypatch.setattr(module_config, "config_signing_secret", lambda: "secret-1")

    bundled = module_config.load_effective_config("graduation")
    payload = dict(bundled.config)
    payload["version"] = "0.2.0"
    payload["login_url"] = "https://portal.example.test/login"
    response_payload = {
        "version": "0.2.0",
        "config": payload,
        "signature": sign_payload("secret-1", "0.2.0", payload),
    }

    monkeypatch.setattr(
        module_config,
        "urlopen",
        lambda request, timeout=10: FakeResponse(200, response_payload),
    )

    state = module_config.sync_module_config("graduation")

    assert state.version == "0.2.0"
    assert state.source == "cloud"
    assert state.signature_verified is True
    assert state.updated is True
    assert state.last_error is None
    assert state.config_path.exists()

    reloaded = module_config.load_effective_config("graduation")
    assert reloaded.version == "0.2.0"
    assert reloaded.source == "cached"
    assert reloaded.signature_verified is True


def test_sync_module_config_rejects_invalid_signature_and_keeps_local_state(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(config, "default_data_dir", lambda: tmp_path)
    monkeypatch.setattr(module_config, "cloud_base_url", lambda: "https://cloud.example.test")
    monkeypatch.setattr(module_config, "cloud_api_bearer_token", lambda: "token-1")
    monkeypatch.setattr(module_config, "config_signing_secret", lambda: "secret-1")

    monkeypatch.setattr(
        module_config,
        "urlopen",
        lambda request, timeout=10: FakeResponse(
            200,
            {
                "version": "0.9.0",
                "config": {"module": "graduation", "version": "0.9.0"},
                "signature": "hmac-sha256:deadbeef",
            },
        ),
    )

    state = module_config.sync_module_config("graduation")

    assert state.source == "bundled"
    assert state.signature_verified is False
    assert state.updated is False
    assert state.last_error == "CONFIG_SIGNATURE_INVALID"
