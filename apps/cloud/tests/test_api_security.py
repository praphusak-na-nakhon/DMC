from __future__ import annotations

import base64
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient
from starlette.requests import Request

from app.config import settings
from app.config_signing import canonical_config_payload, sign_config_payload
from app.main import app
from app.rate_limit import client_rate_limit_key
from app.telemetry_store import TelemetryStore


client = TestClient(app)
TEST_API_BEARER_TOKEN = "dmc-test-token"
TEST_PRIVATE_KEY_SEED_HEX = "affb171844b95521a4d9a844da801d480577ca29d141eb5113da47acf182a088"


def setup_test_security(monkeypatch) -> None:
    monkeypatch.setattr(settings, "api_bearer_token", TEST_API_BEARER_TOKEN)
    monkeypatch.setattr(settings, "config_signing_private_key_hex", TEST_PRIVATE_KEY_SEED_HEX)
    monkeypatch.setattr(settings, "config_signing_key_id", "dev-2026-01")


def auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {settings.api_bearer_token}"}


def use_temp_cloud_db(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(settings, "sqlite_path", str(tmp_path / "cloud-state.sqlite3"))


def account_auth_headers(monkeypatch, tmp_path: Path) -> dict[str, str]:
    setup_test_security(monkeypatch)
    use_temp_cloud_db(monkeypatch, tmp_path)
    create = client.post(
        "/v1/admin/users",
        headers=auth_headers(),
        json={
            "email": "teacher@example.test",
            "password": "correct-password",
            "display_name": "Teacher",
            "status": "active",
        },
    )
    assert create.status_code == 200
    login = client.post(
        "/v1/auth/login",
        json={
            "email": "teacher@example.test",
            "password": "correct-password",
            "device_id": "device-1",
            "device_name": "desktop-01",
            "app_version": "0.1.0",
        },
    )
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['token']}"}


def test_healthz_is_public() -> None:
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["ocr_provider"] in {"mock", "openai", "gemini"}


def test_admin_requires_bearer() -> None:
    settings.api_bearer_token = TEST_API_BEARER_TOKEN
    response = client.get("/v1/admin/users")
    assert response.status_code == 401


def test_rate_limit_client_key_only_trusts_configured_proxy(monkeypatch) -> None:
    def request_for(host: str, forwarded_for: str):
        return Request(
            {
                "type": "http",
                "method": "GET",
                "path": "/healthz",
                "headers": [(b"x-forwarded-for", forwarded_for.encode("ascii"))],
                "client": (host, 12345),
            }
        )

    monkeypatch.setattr(settings, "trusted_proxy_hosts", "")
    direct_request = request_for("203.0.113.10", "198.51.100.1")
    assert client_rate_limit_key(direct_request) == "203.0.113.10"

    monkeypatch.setattr(settings, "trusted_proxy_hosts", "203.0.113.10")
    proxied_request = request_for("203.0.113.10", "198.51.100.1, 203.0.113.10")
    assert client_rate_limit_key(proxied_request) == "198.51.100.1"

    spoofed_request = request_for("203.0.113.10", "192.0.2.99, 198.51.100.1")
    assert client_rate_limit_key(spoofed_request) == "198.51.100.1"


def test_license_routes_are_removed(monkeypatch, tmp_path: Path) -> None:
    setup_test_security(monkeypatch)
    use_temp_cloud_db(monkeypatch, tmp_path)
    activate = client.post(
        "/v1/license/activate",
        json={
            "license_key": "DMC-TEST-0001",
            "device_id": "device-1",
            "device_name": "desktop-01",
            "app_version": "0.1.0",
        },
    )
    heartbeat = client.get("/v1/license/heartbeat")
    admin = client.get("/v1/admin/licenses", headers=auth_headers())

    assert activate.status_code == 404
    assert heartbeat.status_code == 404
    assert admin.status_code == 404


def test_config_returns_signed_payload(monkeypatch) -> None:
    setup_test_security(monkeypatch)
    response = client.get("/v1/config/graduation")
    assert response.status_code == 200
    payload = response.json()
    assert payload["signature"].startswith(f"ed25519:{settings.config_signing_key_id}:")
    expected = sign_config_payload(payload["version"], payload["config"])
    assert payload["signature"] == expected

    _, _, encoded_signature = payload["signature"].split(":", 2)
    verify_key = Ed25519PrivateKey.from_private_bytes(
        bytes.fromhex(settings.config_signing_private_key_hex)
    ).public_key()
    verify_key.verify(
        base64.b64decode(encoded_signature),
        canonical_config_payload(payload["version"], payload["config"]),
    )


def test_config_returns_204_when_current_version_matches(monkeypatch) -> None:
    setup_test_security(monkeypatch)
    current = client.get("/v1/config/graduation").json()["version"]
    response = client.get(
        f"/v1/config/graduation?current_version={current}",
    )
    assert response.status_code == 204
    assert response.text == ""


def test_telemetry_requires_account_session() -> None:
    response = client.post(
        "/v1/telemetry",
        json={
            "events": [
                {
                    "event": "app_started",
                    "ts": "2026-04-22T00:00:00Z",
                    "app_version": "0.1.0",
                    "platform": "windows",
                }
            ]
        },
    )
    assert response.status_code == 401


def test_telemetry_accepts_allowlisted_payload(monkeypatch, tmp_path: Path) -> None:
    headers = account_auth_headers(monkeypatch, tmp_path)
    store = TelemetryStore(settings.sqlite_path)
    response = client.post(
        "/v1/telemetry",
        headers=headers,
        json={
            "events": [
                {
                    "event": "job_completed",
                    "ts": "2026-04-22T00:00:00Z",
                    "module": "graduation",
                    "total": 300,
                    "succeeded": 290,
                    "failed": 10,
                    "duration_sec": 95,
                }
            ]
        },
    )
    assert response.status_code == 200
    assert response.json() == {"accepted": 1, "rejected": 0}
    assert store.count() >= 1


def test_telemetry_persists_account_authorized_events(monkeypatch, tmp_path: Path) -> None:
    headers = account_auth_headers(monkeypatch, tmp_path)
    store = TelemetryStore(settings.sqlite_path)
    response = client.post(
        "/v1/telemetry",
        headers=headers,
        json={
            "events": [
                {
                    "event": "app_started",
                    "ts": "2026-04-22T00:00:00Z",
                    "app_version": "0.1.0",
                    "platform": "windows",
                }
            ]
        },
    )
    assert response.status_code == 200
    rows = store.list_events()
    assert rows[0]["user_id"] is not None
    assert rows[0]["payload"]["event"] == "app_started"


def test_updates_manifest_returns_204_when_not_configured() -> None:
    response = client.get(
        "/v1/updates/manifest",
        params={
            "current_version": settings.version,
            "target": "windows",
            "arch": "x86_64",
        },
    )
    assert response.status_code == 204
    assert response.text == ""


def test_updates_manifest_rejects_unsupported_target() -> None:
    response = client.get(
        "/v1/updates/manifest",
        params={
            "current_version": settings.version,
            "target": "linux",
            "arch": "x86_64",
        },
    )
    assert response.status_code == 400


def test_updates_manifest_returns_payload_when_artifact_is_configured(monkeypatch) -> None:
    setup_test_security(monkeypatch)
    monkeypatch.setattr(settings, "updater_latest_version", "0.2.0")
    monkeypatch.setattr(settings, "updater_windows_x86_64_url", "https://cdn.example.test/dmc.msi.zip")
    monkeypatch.setattr(settings, "updater_windows_x86_64_signature", "signature-1")
    monkeypatch.setattr(settings, "updater_notes", "Bug fixes")
    monkeypatch.setattr(settings, "updater_pub_date", "2026-04-22T09:00:00Z")

    response = client.get(
        "/v1/updates/manifest",
        params={
            "current_version": settings.version,
            "target": "windows",
            "arch": "x86_64",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "version": "0.2.0",
        "pub_date": "2026-04-22T09:00:00Z",
        "url": "https://cdn.example.test/dmc.msi.zip",
        "signature": "signature-1",
        "notes": "Bug fixes",
    }


def test_config_rejects_invalid_module_name(monkeypatch) -> None:
    setup_test_security(monkeypatch)
    response = client.get("/v1/config/..-bad")
    assert response.status_code == 400


def test_auth_returns_500_when_bearer_not_configured(monkeypatch) -> None:
    monkeypatch.setattr(settings, "api_bearer_token", "")
    response = client.get("/v1/admin/users")
    assert response.status_code == 500
