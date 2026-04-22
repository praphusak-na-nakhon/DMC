from __future__ import annotations

from pathlib import Path

from dmc_sidecar import config
from dmc_sidecar.checkpoint import JobCheckpoint
from dmc_sidecar.job_store import JobStore
from dmc_sidecar.license_store import LicenseStore
from dmc_sidecar.schemas import LicenseRecord


def test_license_store_roundtrip(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(config, "default_data_dir", lambda: tmp_path)
    store = LicenseStore()
    record = LicenseRecord(
        license_key="DMC-TEST-0001",
        device_id="device-1",
        license_tier="trial",
        school_size_tier="le_500",
        billing_interval=None,
        student_count_total=100,
        max_devices=3,
        activated_at="2026-04-22T00:00:00Z",
        expires_at="2026-05-06T00:00:00Z",
        last_checked_at="2026-04-22T00:00:00Z",
        offline_grace_until="2026-04-29T00:00:00Z",
    )

    store.save_activation(record)
    loaded = store.get_license()

    assert loaded is not None
    assert loaded.license_key == "DMC-TEST-0001"
    assert loaded.device_id == "device-1"


def test_heartbeat_updates_dates(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(config, "default_data_dir", lambda: tmp_path)
    store = LicenseStore()
    store.save_activation(
        LicenseRecord(
            license_key="DMC-TEST-0002",
            device_id="device-2",
            license_tier="trial",
            school_size_tier="le_500",
            billing_interval=None,
            student_count_total=100,
            max_devices=3,
            activated_at="2026-04-22T00:00:00Z",
            expires_at="2026-05-06T00:00:00Z",
            last_checked_at="2026-04-22T00:00:00Z",
            offline_grace_until="2026-04-29T00:00:00Z",
        )
    )

    store.update_heartbeat(
        last_checked_at="2026-04-23T00:00:00Z",
        offline_grace_until="2026-04-30T00:00:00Z",
    )
    loaded = store.get_license()

    assert loaded is not None
    assert loaded.last_checked_at == "2026-04-23T00:00:00Z"
    assert loaded.offline_grace_until == "2026-04-30T00:00:00Z"


def test_job_store_checkpoint_roundtrip(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(config, "default_data_dir", lambda: tmp_path)
    store = JobStore()
    store.create_pending_job("job-1", "graduation", "C:\\data\\m3.xlsx")
    checkpoint = JobCheckpoint.initial(level_label="ม.3", base_url="https://example.test")
    checkpoint.processed = 60
    checkpoint.succeeded = 55
    checkpoint.failed = 5
    checkpoint.next_page = 2
    checkpoint.used_orders = [1, 2, 3]
    checkpoint.results = [{"portal_row_index": 0, "note": "filled"}]
    checkpoint.awaiting_auth = True
    checkpoint.auth_reason = "session_expired"
    store.mark_running(
        "job-1",
        total_records=300,
        checkpoint=checkpoint,
        started_at="2026-04-22T00:00:00Z",
    )
    store.save_checkpoint("job-1", checkpoint)

    loaded = store.load_checkpoint("job-1")
    status = store.get_status("job-1")

    assert loaded is not None
    assert loaded.next_page == 2
    assert loaded.used_orders == [1, 2, 3]
    assert status is not None
    assert status["current_page"] == 2
    assert status["processed"] == 60
    assert status["needs_auth"] is True
    assert status["auth_reason"] == "session_expired"
