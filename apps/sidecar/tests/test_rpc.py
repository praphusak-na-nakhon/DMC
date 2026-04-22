from __future__ import annotations

import json
from pathlib import Path

from dmc_sidecar import config
from dmc_sidecar.checkpoint import JobCheckpoint
from dmc_sidecar.job_store import JobStore
from dmc_sidecar.rpc import RpcServer


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
    store.mark_running("job-1", total_records=300, checkpoint=checkpoint, started_at="2026-04-22T00:00:00Z")

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


def test_resume_existing_job_rpc(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(config, "default_data_dir", lambda: tmp_path)
    store = JobStore()
    store.create_pending_job("job-1", "graduation", "C:\\data\\m3.xlsx")
    checkpoint = JobCheckpoint.initial(level_label="ม.3", base_url="https://example.test")
    checkpoint.options = {"dry_run": True, "stop_on_review": True}
    store.mark_running("job-1", total_records=300, checkpoint=checkpoint, started_at="2026-04-22T00:00:00Z")
    store.set_status("job-1", "paused")

    started: dict[str, object] = {}
    server = RpcServer(emit_notification=lambda payload: None)

    def fake_start_job(*, job_id: str, module_name: str, excel_path: Path, options: dict[str, object]) -> None:
      started["job_id"] = job_id
      started["module_name"] = module_name
      started["excel_path"] = str(excel_path)
      started["options"] = options

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

    assert response["result"]["accepted"] is True
    assert started["job_id"] == "job-1"
    assert started["module_name"] == "graduation"
    assert started["excel_path"] == "C:\\data\\m3.xlsx"
    assert started["options"] == {"dry_run": True, "stop_on_review": True}
