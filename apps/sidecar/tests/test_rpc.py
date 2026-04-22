from __future__ import annotations

import json
from pathlib import Path

from dmc_sidecar import config
from dmc_sidecar.checkpoint import JobCheckpoint
from dmc_sidecar.job_store import JobStore
from dmc_sidecar.license_store import LicenseStore
from dmc_sidecar.rpc import RpcServer
from dmc_sidecar.schemas import LicenseRecord


def test_ping_rpc() -> None:
    server = RpcServer(emit_notification=lambda payload: None)
    payload = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": "req-1",
            "method": "ping",
            "params": {},
        }
    )

    response = json.loads(server.handle_text(payload))

    assert response["result"]["value"] == "pong"
    assert response["result"]["sidecar_version"] == "0.1.0"


def test_list_jobs_rpc(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(config, "default_data_dir", lambda: tmp_path)
    store = JobStore()
    store.create_pending_job("job-1", "graduation", "C:\\data\\m3.xlsx")
    checkpoint = JobCheckpoint.initial(level_label="ม.3", base_url="https://example.test")
    checkpoint.options = {"dry_run": True}
    store.mark_running(
        "job-1",
        total_records=300,
        checkpoint=checkpoint,
        started_at="2026-04-22T00:00:00Z",
    )

    server = RpcServer(emit_notification=lambda payload: None)
    payload = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": "req-2",
            "method": "list_jobs",
            "params": {"limit": 10},
        }
    )

    response = json.loads(server.handle_text(payload))

    assert response["result"]["items"][0]["job_id"] == "job-1"
    assert response["result"]["items"][0]["source_file"] == "C:\\data\\m3.xlsx"


def test_get_module_config_status_rpc(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(config, "default_data_dir", lambda: tmp_path)
    server = RpcServer(emit_notification=lambda payload: None)
    payload = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": "req-config",
            "method": "get_module_config_status",
            "params": {"module": "graduation"},
        }
    )

    response = json.loads(server.handle_text(payload))

    assert response["result"]["module"] == "graduation"
    assert response["result"]["source"] == "bundled"
    assert response["result"]["version"] == "0.1.0"


def test_get_license_status_rpc(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(config, "default_data_dir", lambda: tmp_path)
    store = LicenseStore()
    store.save_activation(
        LicenseRecord(
            license_key="DMC-TEST-0005",
            status="active",
            device_id="device-5",
            license_tier="trial",
            school_size_tier="le_500",
            billing_interval=None,
            student_count_total=100,
            modules_enabled=["graduation"],
            max_devices=3,
            activated_at="2026-04-22T00:00:00Z",
            expires_at="2026-05-06T00:00:00Z",
            last_checked_at="2026-04-22T00:00:00Z",
            offline_grace_until="2026-05-01T00:00:00Z",
        )
    )

    server = RpcServer(emit_notification=lambda payload: None)
    payload = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": "req-license",
            "method": "get_license_status",
            "params": {},
        }
    )

    response = json.loads(server.handle_text(payload))

    assert response["result"]["configured"] is True
    assert response["result"]["status"] == "active"
    assert response["result"]["modules_enabled"] == ["graduation"]


def test_resume_existing_job_rpc_uses_checkpoint_state_after_pause(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(config, "default_data_dir", lambda: tmp_path)
    store = JobStore()
    store.create_pending_job("job-1", "graduation", "C:\\data\\m3.xlsx")
    checkpoint = JobCheckpoint.initial(level_label="ม.3", base_url="https://example.test")
    checkpoint.options = {"dry_run": True, "stop_on_review": True, "min_score": 80}
    checkpoint.next_page = 4
    checkpoint.processed = 180
    checkpoint.succeeded = 175
    checkpoint.failed = 5
    checkpoint.awaiting_auth = True
    checkpoint.auth_reason = "session_expired"
    store.mark_running(
        "job-1",
        total_records=300,
        checkpoint=checkpoint,
        started_at="2026-04-22T00:00:00Z",
    )
    store.set_status("job-1", "paused")

    server = RpcServer(emit_notification=lambda payload: None)
    before_resume = server.job_store.get_status("job-1")
    started: dict[str, object] = {}

    def fake_start_job(*, job_id: str, module_name: str, excel_path: Path, options: dict[str, object]) -> None:
        started["job_id"] = job_id
        started["module_name"] = module_name
        started["excel_path"] = str(excel_path)
        started["options"] = dict(options)

    monkeypatch.setattr(server.job_manager, "start_job", fake_start_job)

    payload = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": "req-3",
            "method": "resume_existing_job",
            "params": {"job_id": "job-1"},
        }
    )

    response = json.loads(server.handle_text(payload))
    after_resume = server.job_store.get_status("job-1")

    assert before_resume is not None
    assert before_resume["status"] == "paused"
    assert before_resume["current_page"] == 4
    assert before_resume["needs_auth"] is True
    assert before_resume["auth_reason"] == "session_expired"

    assert response["result"]["accepted"] is True
    assert started["job_id"] == "job-1"
    assert started["module_name"] == "graduation"
    assert started["excel_path"] == "C:\\data\\m3.xlsx"
    assert started["options"] == {"dry_run": True, "stop_on_review": True, "min_score": 80}

    assert after_resume is not None
    assert after_resume["current_page"] == 4
    assert after_resume["needs_auth"] is True
    assert after_resume["auth_reason"] == "session_expired"


def test_resume_existing_job_rejects_done_job(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(config, "default_data_dir", lambda: tmp_path)
    store = JobStore()
    store.create_pending_job("job-2", "graduation", "C:\\data\\m6.xlsx")
    checkpoint = JobCheckpoint.initial(level_label="ม.6", base_url="https://example.test")
    checkpoint.options = {"dry_run": False}
    store.mark_done("job-2", checkpoint=checkpoint, finished_at="2026-04-22T01:00:00Z")

    server = RpcServer(emit_notification=lambda payload: None)
    payload = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": "req-4",
            "method": "resume_existing_job",
            "params": {"job_id": "job-2"},
        }
    )

    response = json.loads(server.handle_text(payload))

    assert response["error"]["code"] == "JOB_NOT_RESUMABLE"
