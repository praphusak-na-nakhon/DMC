from __future__ import annotations

import json
from pathlib import Path

from dmc_sidecar import config
from dmc_sidecar.license_store import LicenseStore
from dmc_sidecar.schemas import LicenseRecord
from dmc_sidecar.telemetry import TelemetryClient, validate_telemetry_event


class FakeResponse:
    def __init__(self, payload: dict[str, int]) -> None:
        self.payload = payload

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


def test_telemetry_client_flushes_batched_events(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(config, "default_data_dir", lambda: tmp_path)
    monkeypatch.setattr("dmc_sidecar.telemetry.secure_cloud_base_url", lambda: "https://cloud.example.test")

    license_store = LicenseStore()
    license_store.save_activation(
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

    captured: list[dict[str, object]] = []

    def fake_urlopen(request, timeout=10):  # noqa: ANN001
        headers = {key.lower(): value for key, value in request.header_items()}
        captured.append(
            {
                "body": json.loads(request.data.decode("utf-8")),
                "license_key": headers.get("x-dmc-license-key"),
                "device_id": headers.get("x-dmc-device-id"),
            }
        )
        return FakeResponse({"accepted": len(captured[-1]["body"]["events"]), "rejected": 0})

    monkeypatch.setattr("dmc_sidecar.telemetry.urlopen", fake_urlopen)

    client = TelemetryClient(license_store=license_store)
    client.record_app_started(app_version="0.1.0", platform="win32")
    client.record_license_checked(result="HEARTBEAT_OK", offline_mode=False)

    assert len(captured) == 2
    assert captured[0]["body"]["events"][0]["event"] == "app_started"
    assert captured[0]["license_key"] == "DMC-TEST-0001"
    assert captured[0]["device_id"] == "device-1"
    assert captured[1]["body"]["events"][0]["event"] == "license_checked"
    assert client.store.count() == 0


def test_validate_telemetry_event_rejects_unknown_fields() -> None:
    payload = {
        "event": "job_failed",
        "ts": "2026-04-22T00:00:00Z",
        "module": "graduation",
        "error_code": "CONFIG_SIGNATURE_INVALID",
        "processed": 3,
        "student_no": "12345",
    }

    try:
        validate_telemetry_event(payload)
    except Exception as exc:  # noqa: BLE001
        assert "student_no" in str(exc)
    else:  # pragma: no cover - defensive
        raise AssertionError("expected telemetry validation to reject student_no")
