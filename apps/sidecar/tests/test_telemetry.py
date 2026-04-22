from __future__ import annotations

import json
from pathlib import Path

from dmc_sidecar import config
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
    monkeypatch.setattr("dmc_sidecar.telemetry.cloud_base_url", lambda: "https://cloud.example.test")
    monkeypatch.setattr("dmc_sidecar.telemetry.cloud_api_bearer_token", lambda: "token-1")

    captured: list[dict[str, object]] = []

    def fake_urlopen(request, timeout=10):  # noqa: ANN001
        captured.append(json.loads(request.data.decode("utf-8")))
        return FakeResponse({"accepted": len(captured[-1]["events"]), "rejected": 0})

    monkeypatch.setattr("dmc_sidecar.telemetry.urlopen", fake_urlopen)

    client = TelemetryClient()
    client.record_app_started(app_version="0.1.0", platform="win32")
    client.record_license_checked(result="HEARTBEAT_OK", offline_mode=False)

    assert len(captured) == 2
    assert captured[0]["events"][0]["event"] == "app_started"
    assert captured[1]["events"][0]["event"] == "license_checked"
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
