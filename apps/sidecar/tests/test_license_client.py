from __future__ import annotations

import json
from pathlib import Path
from urllib.error import URLError

from dmc_sidecar import config
from dmc_sidecar.license_client import activate_license, build_license_status_snapshot, refresh_license_status
from dmc_sidecar.license_store import LicenseStore
from dmc_sidecar.schemas import LicenseRecord


class FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


def seed_license(store: LicenseStore) -> None:
    store.save_activation(
        LicenseRecord(
            license_key="DMC-TEST-0001",
            status="active",
            device_id="device-1",
            license_tier="trial",
            school_size_tier="le_500",
            billing_interval=None,
            student_count_total=100,
            modules_enabled=["graduation"],
            max_devices=3,
            activated_at="2026-04-22T00:00:00Z",
            expires_at="2026-05-06T00:00:00Z",
            last_checked_at="2026-04-22T00:00:00Z",
            offline_grace_until="2026-04-29T00:00:00Z",
        )
    )


def test_build_license_status_snapshot_handles_missing_license() -> None:
    snapshot = build_license_status_snapshot(None)

    assert snapshot.configured is False
    assert snapshot.status == "missing"
    assert snapshot.can_start_jobs is True


def test_build_license_status_snapshot_requires_activation_when_cloud_enabled(monkeypatch) -> None:
    monkeypatch.setattr("dmc_sidecar.license_client.cloud_base_url", lambda: "https://cloud.example.test")

    snapshot = build_license_status_snapshot(None)

    assert snapshot.configured is False
    assert snapshot.can_start_jobs is False
    assert snapshot.message == "LICENSE_REQUIRED"


def test_refresh_license_status_updates_store_from_cloud(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(config, "default_data_dir", lambda: tmp_path)
    store = LicenseStore()
    seed_license(store)

    monkeypatch.setattr("dmc_sidecar.license_client.secure_cloud_base_url", lambda: "https://cloud.example.test")
    monkeypatch.setattr("dmc_sidecar.license_client.require_cloud_api_bearer_token", lambda: "dev-token")
    monkeypatch.setattr(
        "dmc_sidecar.license_client.urlopen",
        lambda request, timeout=10: FakeResponse(
            {
                "status": "active",
                "license_tier": "school_501_1500",
                "school_size_tier": "501_1500",
                "billing_interval": "monthly",
                "student_count_total": 880,
                "expires_at": "2027-04-22T00:00:00Z",
                "modules_enabled": ["graduation"],
                "max_devices": 5,
                "offline_grace_days": 7,
            }
        ),
    )

    snapshot = refresh_license_status(store)
    loaded = store.get_license()

    assert snapshot.configured is True
    assert snapshot.status == "active"
    assert snapshot.offline_mode is False
    assert snapshot.can_start_jobs is True
    assert loaded is not None
    assert loaded.license_tier == "school_501_1500"
    assert loaded.student_count_total == 880
    assert loaded.max_devices == 5


def test_refresh_license_status_falls_back_to_offline_mode_on_network_error(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(config, "default_data_dir", lambda: tmp_path)
    store = LicenseStore()
    seed_license(store)

    monkeypatch.setattr("dmc_sidecar.license_client.secure_cloud_base_url", lambda: "https://cloud.example.test")
    monkeypatch.setattr("dmc_sidecar.license_client.require_cloud_api_bearer_token", lambda: "dev-token")

    def raise_network_error(request, timeout=10):
        raise URLError("network down")

    monkeypatch.setattr("dmc_sidecar.license_client.urlopen", raise_network_error)

    snapshot = refresh_license_status(store)

    assert snapshot.configured is True
    assert snapshot.offline_mode is True
    assert snapshot.last_error == "HEARTBEAT_FAILED"


def test_activate_license_saves_local_record(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(config, "default_data_dir", lambda: tmp_path)
    monkeypatch.setattr("dmc_sidecar.license_client.secure_cloud_base_url", lambda: "https://cloud.example.test")
    monkeypatch.setattr("dmc_sidecar.license_client.require_cloud_api_bearer_token", lambda: "dev-token")
    monkeypatch.setattr("dmc_sidecar.license_client.get_or_create_device_id", lambda: "device-activate-1")
    monkeypatch.setattr(
        "dmc_sidecar.license_client.urlopen",
        lambda request, timeout=10: FakeResponse(
            {
                "status": "active",
                "license_tier": "trial",
                "school_size_tier": "le_500",
                "billing_interval": None,
                "student_count_total": 250,
                "expires_at": "2026-05-20T00:00:00Z",
                "modules_enabled": ["graduation"],
                "max_devices": 3,
                "offline_grace_days": 7,
            }
        ),
    )

    store = LicenseStore()
    snapshot = activate_license(
        store,
        license_key="DMC-TEST-NEW",
        device_name="desktop-01",
        app_version="0.1.0",
    )
    loaded = store.get_license()

    assert snapshot.configured is True
    assert snapshot.message == "ACTIVATION_OK"
    assert loaded is not None
    assert loaded.license_key == "DMC-TEST-NEW"
    assert loaded.device_id == "device-activate-1"
    assert loaded.student_count_total == 250


def test_refresh_license_status_rejects_insecure_cloud_url(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(config, "default_data_dir", lambda: tmp_path)
    store = LicenseStore()
    seed_license(store)
    monkeypatch.setattr(
        "dmc_sidecar.license_client.secure_cloud_base_url",
        lambda: (_ for _ in ()).throw(RuntimeError("CLOUD_URL_INSECURE")),
    )

    snapshot = refresh_license_status(store)

    assert snapshot.last_error == "CLOUD_URL_INSECURE"
    assert snapshot.offline_mode is True
