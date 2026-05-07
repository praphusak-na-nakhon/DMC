from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.telemetry_store import TelemetryStore


client = TestClient(app)
TEST_PRIVATE_KEY_SEED_HEX = "affb171844b95521a4d9a844da801d480577ca29d141eb5113da47acf182a088"


def _configure(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(settings, "sqlite_path", str(tmp_path / "cloud-contract.sqlite3"))
    monkeypatch.setattr(settings, "api_bearer_token", "dmc-test-token")
    monkeypatch.setattr(settings, "config_signing_private_key_hex", TEST_PRIVATE_KEY_SEED_HEX)
    monkeypatch.setattr(settings, "config_signing_key_id", "dev-2026-01")


def _account_auth_headers(monkeypatch, tmp_path: Path) -> dict[str, str]:
    _configure(monkeypatch, tmp_path)
    create = client.post(
        "/v1/admin/users",
        headers={"Authorization": "Bearer dmc-test-token"},
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
            "device_id": "device-contract",
            "device_name": "desktop-contract",
            "app_version": "0.1.0",
        },
    )
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['token']}"}


def test_license_routes_are_removed(monkeypatch, tmp_path: Path) -> None:
    _configure(monkeypatch, tmp_path)
    response = client.post(
        "/v1/license/activate",
        json={
            "license_key": "DMC-TEST-0001",
            "device_id": "device-contract",
            "device_name": "desktop-contract",
            "app_version": "0.1.0",
        },
    )
    assert response.status_code == 404


def test_telemetry_contract_rejects_nested_pii(monkeypatch, tmp_path: Path) -> None:
    headers = _account_auth_headers(monkeypatch, tmp_path)
    store = TelemetryStore(settings.sqlite_path)
    response = client.post(
        "/v1/telemetry",
        headers=headers,
        json={
            "events": [
                {
                    "event": "job_failed",
                    "ts": "2026-04-22T00:00:00Z",
                    "module": "graduation",
                    "error_code": "MATCH_REVIEW",
                    "processed": 5,
                    "details": {"matched_name": "สมชาย ใจดี"},
                }
            ]
        },
    )

    assert response.status_code == 422
    assert store.count() == 0
