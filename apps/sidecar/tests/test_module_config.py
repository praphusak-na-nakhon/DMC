from __future__ import annotations

import base64
import json
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
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

PRIVATE_KEY_SEED_HEX = "affb171844b95521a4d9a844da801d480577ca29d141eb5113da47acf182a088"
KEY_ID = "dev-2026-01"


def sign_payload(version: str, payload: dict[str, object]) -> str:
    key = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(PRIVATE_KEY_SEED_HEX))
    signature = key.sign(module_config._canonical_payload(version, payload))  # noqa: SLF001
    return f"ed25519:{KEY_ID}:{base64.b64encode(signature).decode('ascii')}"


def test_sync_module_config_downloads_and_caches_verified_payload(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(config, "default_data_dir", lambda: tmp_path)
    monkeypatch.setattr(module_config, "cloud_base_url", lambda: "https://cloud.example.test")
    monkeypatch.setattr(module_config, "cloud_api_bearer_token", lambda: "token-1")

    bundled = module_config.load_effective_config("graduation")
    payload = dict(bundled.config)
    payload["version"] = "0.2.0"
    payload["login_url"] = "https://portal.example.test/login"
    response_payload = {
        "version": "0.2.0",
        "config": payload,
        "signature": sign_payload("0.2.0", payload),
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

    monkeypatch.setattr(
        module_config,
        "urlopen",
        lambda request, timeout=10: FakeResponse(
            200,
            {
                "version": "0.9.0",
                "config": {"module": "graduation", "version": "0.9.0"},
                "signature": "ed25519:dev-2026-01:deadbeef",
            },
        ),
    )

    state = module_config.sync_module_config("graduation")

    assert state.source == "bundled"
    assert state.signature_verified is False
    assert state.updated is False
    assert state.last_error == "CONFIG_SIGNATURE_INVALID"
