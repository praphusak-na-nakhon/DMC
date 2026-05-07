from __future__ import annotations

import json
from pathlib import Path

from dmc_sidecar import config
from dmc_sidecar.account_store import AccountSessionStore
from dmc_sidecar.schemas import WalletSnapshot
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

    account_store = AccountSessionStore()
    account_store.save_session(
        token="account-token",
        user_id="user-1",
        email="teacher@example.test",
        display_name="Teacher",
        status="active",
        token_expires_at="2026-05-06T00:00:00Z",
        checked_at="2026-04-22T00:00:00Z",
        wallet=WalletSnapshot(user_id="user-1", balance=10, reserved=0, available=10),
    )

    captured: list[dict[str, object]] = []

    def fake_urlopen(request, timeout=10):  # noqa: ANN001
        headers = {key.lower(): value for key, value in request.header_items()}
        captured.append(
            {
                "body": json.loads(request.data.decode("utf-8")),
                "authorization": headers.get("authorization"),
            }
        )
        return FakeResponse({"accepted": len(captured[-1]["body"]["events"]), "rejected": 0})

    monkeypatch.setattr("dmc_sidecar.telemetry.urlopen", fake_urlopen)

    client = TelemetryClient(account_store=account_store, background_flush=False)
    client.record_app_started(app_version="0.1.0", platform="win32")

    assert len(captured) == 1
    assert captured[0]["body"]["events"][0]["event"] == "app_started"
    assert captured[0]["authorization"] == "Bearer account-token"
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


def test_validate_telemetry_event_rejects_name_fields() -> None:
    payload = {
        "event": "job_completed",
        "ts": "2026-04-22T00:00:00Z",
        "module": "graduation",
        "total": 300,
        "succeeded": 290,
        "failed": 10,
        "duration_sec": 95,
        "first_name": "สมชาย",
    }

    try:
        validate_telemetry_event(payload)
    except Exception as exc:  # noqa: BLE001
        assert "first_name" in str(exc)
    else:  # pragma: no cover - defensive
        raise AssertionError("expected telemetry validation to reject first_name")
