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


def _activate_device(monkeypatch, tmp_path: Path) -> None:
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
    assert response.status_code == 200


def test_license_activate_contract_keys_are_stable(monkeypatch, tmp_path: Path) -> None:
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

    assert response.status_code == 200
    assert set(response.json()) == {
        "status",
        "license_tier",
        "school_size_tier",
        "billing_interval",
        "student_count_total",
        "expires_at",
        "modules_enabled",
        "max_devices",
        "offline_grace_days",
    }


def test_license_activate_rejects_extra_contract_fields(monkeypatch, tmp_path: Path) -> None:
    _configure(monkeypatch, tmp_path)
    response = client.post(
        "/v1/license/activate",
        json={
            "license_key": "DMC-TEST-0001",
            "device_id": "device-contract",
            "device_name": "desktop-contract",
            "app_version": "0.1.0",
            "unexpected": "field",
        },
    )

    assert response.status_code == 422


def test_telemetry_contract_rejects_nested_pii(monkeypatch, tmp_path: Path) -> None:
    _activate_device(monkeypatch, tmp_path)
    store = TelemetryStore(settings.sqlite_path)
    response = client.post(
        "/v1/telemetry",
        headers={
            "X-DMC-License-Key": "DMC-TEST-0001",
            "X-DMC-Device-Id": "device-contract",
        },
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
