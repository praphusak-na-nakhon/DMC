from __future__ import annotations

import base64
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient

from app.config import settings
from app.config_signing import canonical_config_payload, sign_config_payload
from app.db import connect
from app.main import app
from app.telemetry_store import TelemetryStore


client = TestClient(app)


def auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {settings.api_bearer_token}"}


def use_temp_cloud_db(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(settings, "sqlite_path", str(tmp_path / "cloud-state.sqlite3"))


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


def test_license_activate_accepts_valid_bearer(monkeypatch, tmp_path: Path) -> None:
    use_temp_cloud_db(monkeypatch, tmp_path)
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


def test_license_heartbeat_accepts_valid_bearer(monkeypatch, tmp_path: Path) -> None:
    use_temp_cloud_db(monkeypatch, tmp_path)
    activate = client.post(
        "/v1/license/activate",
        headers=auth_headers(),
        json={
            "license_key": "DMC-TEST-0001",
            "device_id": "device-1",
            "device_name": "desktop-01",
            "app_version": "0.1.0",
        },
    )
    assert activate.status_code == 200

    response = client.get(
        "/v1/license/heartbeat",
        headers={
            **auth_headers(),
            "X-DMC-License-Key": "DMC-TEST-0001",
            "X-DMC-Device-Id": "device-1",
            "X-DMC-Device-Name": "desktop-01",
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "active"


def test_license_activate_rejects_device_limit(monkeypatch, tmp_path: Path) -> None:
    use_temp_cloud_db(monkeypatch, tmp_path)
    first = client.post(
        "/v1/license/activate",
        headers=auth_headers(),
        json={
            "license_key": "DMC-TEST-0001",
            "device_id": "device-1",
            "device_name": "desktop-01",
            "app_version": "0.1.0",
        },
    )
    assert first.status_code == 200

    with connect(Path(settings.sqlite_path)) as connection:
        connection.execute(
            "UPDATE licenses SET max_devices = 1 WHERE license_key = ?",
            ("DMC-TEST-0001",),
        )

    second = client.post(
        "/v1/license/activate",
        headers=auth_headers(),
        json={
            "license_key": "DMC-TEST-0001",
            "device_id": "device-2",
            "device_name": "desktop-02",
            "app_version": "0.1.0",
        },
    )
    assert second.status_code == 409


def test_admin_can_upsert_and_list_licenses(monkeypatch, tmp_path: Path) -> None:
    use_temp_cloud_db(monkeypatch, tmp_path)
    upsert = client.put(
        "/v1/admin/licenses/DMC-PAID-0001",
        headers=auth_headers(),
        json={
            "license_key": "DMC-PAID-0001",
            "license_tier": "standard",
            "school_size_tier": "le_1500",
            "billing_interval": "yearly",
            "student_count_total": 780,
            "max_devices": 5,
            "status": "active",
            "expires_at": "2027-04-22T00:00:00Z",
            "modules_enabled": ["graduation"],
        },
    )
    assert upsert.status_code == 200
    assert upsert.json()["license_key"] == "DMC-PAID-0001"
    assert upsert.json()["active_devices"] == 0

    listing = client.get("/v1/admin/licenses", headers=auth_headers())
    assert listing.status_code == 200
    license_keys = [item["license_key"] for item in listing.json()]
    assert "DMC-PAID-0001" in license_keys


def test_admin_upsert_rejects_mismatched_license_key(monkeypatch, tmp_path: Path) -> None:
    use_temp_cloud_db(monkeypatch, tmp_path)
    response = client.put(
        "/v1/admin/licenses/DMC-PAID-0001",
        headers=auth_headers(),
        json={
            "license_key": "DMC-PAID-0002",
            "license_tier": "standard",
            "school_size_tier": "le_1500",
            "billing_interval": "yearly",
            "student_count_total": 780,
            "max_devices": 5,
            "status": "active",
            "expires_at": "2027-04-22T00:00:00Z",
            "modules_enabled": ["graduation"],
        },
    )
    assert response.status_code == 400


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


def test_telemetry_accepts_allowlisted_payload(monkeypatch, tmp_path: Path) -> None:
    use_temp_cloud_db(monkeypatch, tmp_path)
    store = TelemetryStore(settings.sqlite_path)
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
    assert store.count() >= 1


def test_telemetry_persists_license_and_device_headers(monkeypatch, tmp_path: Path) -> None:
    use_temp_cloud_db(monkeypatch, tmp_path)
    store = TelemetryStore(settings.sqlite_path)
    response = client.post(
        "/v1/telemetry",
        headers={
            **auth_headers(),
            "X-DMC-License-Key": "DMC-TEST-0001",
            "X-DMC-Device-Id": "device-1",
        },
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
    assert rows[0]["license_key"] == "DMC-TEST-0001"
    assert rows[0]["device_id"] == "device-1"
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


def test_updates_manifest_returns_payload_when_artifact_is_configured(monkeypatch) -> None:
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
