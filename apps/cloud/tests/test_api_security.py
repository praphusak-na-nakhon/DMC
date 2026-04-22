from __future__ import annotations

import base64

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient

from app.config import settings
from app.config_signing import canonical_config_payload, sign_config_payload
from app.main import app


client = TestClient(app)


def auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {settings.api_bearer_token}"}


def test_healthz_is_public() -> None:
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_license_activate_requires_bearer() -> None:
    response = client.post(
        "/v1/license/activate",
        json={
            "license_key": "DMC-TEST-0001",
            "device_id": "device-1",
            "device_name": "desktop-01",
            "app_version": "0.1.0",
        },
    )
    assert response.status_code == 401


def test_license_activate_accepts_valid_bearer() -> None:
    response = client.post(
        "/v1/license/activate",
        headers=auth_headers(),
        json={
            "license_key": "DMC-TEST-0001",
            "device_id": "device-1",
            "device_name": "desktop-01",
            "app_version": "0.1.0",
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "active"


def test_license_heartbeat_accepts_valid_bearer() -> None:
    response = client.get("/v1/license/heartbeat", headers=auth_headers())
    assert response.status_code == 200
    assert response.json()["status"] == "active"


def test_config_returns_signed_payload() -> None:
    response = client.get("/v1/config/graduation", headers=auth_headers())
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


def test_config_returns_204_when_current_version_matches() -> None:
    current = client.get("/v1/config/graduation", headers=auth_headers()).json()["version"]
    response = client.get(
        f"/v1/config/graduation?current_version={current}",
        headers=auth_headers(),
    )
    assert response.status_code == 204
    assert response.text == ""


def test_telemetry_requires_bearer() -> None:
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


def test_telemetry_accepts_allowlisted_payload() -> None:
    response = client.post(
        "/v1/telemetry",
        headers=auth_headers(),
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
