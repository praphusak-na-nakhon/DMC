from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any

import pytest
from ai_fakes import InMemorySecretStore

from dmc_sidecar import config as sidecar_config
from dmc_sidecar.checkpoint import JobCheckpoint
from dmc_sidecar.errors import DomainError
from dmc_sidecar.rpc import RpcServer
from dmc_sidecar.runtime import utc_now


def _rpc_call(server: RpcServer, method: str, params: dict[str, object]) -> dict[str, Any]:
    payload = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": f"req-{method}",
            "method": method,
            "params": params,
        }
    )
    return json.loads(server.handle_text(payload))


def _wait_until(assertion, *, timeout: float = 3.0) -> None:  # noqa: ANN001
    deadline = time.time() + timeout
    last_error: AssertionError | None = None
    while time.time() < deadline:
        try:
            result = assertion()
            if result is False:
                raise AssertionError("Condition not satisfied yet.")
            return
        except AssertionError as exc:
            last_error = exc
            time.sleep(0.05)
    if last_error is not None:
        raise last_error
    raise AssertionError("Timed out waiting for assertion.")


def _ready_browser_status(tmp_path: Path):
    class ReadyBrowserStatus:
        installed = True

        def model_dump(self) -> dict[str, object]:
            return {
                "state": "ready",
                "installed": True,
                "install_dir": str(tmp_path / "ms-playwright"),
                "executable_path": str(
                    tmp_path / "ms-playwright" / "chromium-1208" / "chrome-win" / "chrome.exe"
                ),
                "bootstrap_supported": True,
                "bootstrap_performed": True,
                "estimated_download_bytes": None,
                "required_components": [],
                "message": "Chromium browser runtime is ready.",
                "guidance": None,
                "last_error": None,
                "log_tail": [],
            }

    return ReadyBrowserStatus()


class _CompletingModule:
    def start_job(self, job_id: str, excel_path: Path, options: dict[str, object], context) -> None:  # noqa: ANN001
        checkpoint = JobCheckpoint.initial(level_label="ม.3", base_url="https://portal.example.test")
        checkpoint.options = dict(options)
        checkpoint.processed = 1
        checkpoint.succeeded = 1
        context.snapshot.total = 1
        context.snapshot.processed = 1
        context.snapshot.succeeded = 1
        context.job_store.mark_running(
            job_id,
            total_records=1,
            checkpoint=checkpoint,
            started_at=utc_now(),
        )
        context.job_store.append_results(job_id, [{
            "page": 1, "portal_row_index": 1, "matched_order": 1,
            "note": "filled", "applied": True, "status": "success",
        }])
        context.emit_progress()
        context.emit_record_done(row=1, status="success")
        context.job_store.mark_done(job_id, checkpoint=checkpoint, finished_at=utc_now())


class _ResumeAfterAuthModule:
    def start_job(self, job_id: str, excel_path: Path, options: dict[str, object], context) -> None:  # noqa: ANN001
        checkpoint = context.job_store.load_checkpoint(job_id)
        if checkpoint is None:
            checkpoint = JobCheckpoint.initial(level_label="ม.3", base_url="https://portal.example.test")
            checkpoint.options = dict(options)
            checkpoint.next_page = 3
            checkpoint.awaiting_auth = True
            checkpoint.auth_reason = "session_expired"
            context.snapshot.total = 1
            context.snapshot.current_page = 3
            context.snapshot.needs_auth = True
            context.snapshot.auth_reason = "session_expired"
            context.job_store.mark_running(
                job_id,
                total_records=1,
                checkpoint=checkpoint,
                started_at=utc_now(),
            )
            context.emit_needs_auth("session_expired")
            context.job_store.save_checkpoint(job_id, checkpoint)
            context.job_store.set_status(job_id, "paused")
            return

        checkpoint.awaiting_auth = False
        checkpoint.auth_reason = None
        checkpoint.processed = 1
        checkpoint.succeeded = 1
        context.snapshot.total = 1
        context.snapshot.current_page = checkpoint.next_page
        context.snapshot.processed = 1
        context.snapshot.succeeded = 1
        context.job_store.mark_running(
            job_id,
            total_records=1,
            checkpoint=checkpoint,
            started_at=utc_now(),
        )
        context.job_store.mark_done(job_id, checkpoint=checkpoint, finished_at=utc_now())


@pytest.mark.parametrize("module_name", ["graduation", "currentStudents"])
def test_local_live_job_completes_without_account_or_credit(monkeypatch, tmp_path: Path, module_name: str) -> None:
    monkeypatch.setattr(sidecar_config, "default_data_dir", lambda: tmp_path)
    monkeypatch.setattr("dmc_sidecar.modules.get_module", lambda name: _CompletingModule())
    monkeypatch.setattr("dmc_sidecar.rpc.get_browser_runtime_status", lambda: _ready_browser_status(tmp_path))
    notifications: list[dict[str, Any]] = []
    server = RpcServer(emit_notification=notifications.append, secret_store=InMemorySecretStore())
    started = _rpc_call(server, "start_job", {
        "job_id": "job-local-live", "module": module_name,
        "excel_path": "source.xlsx", "options": {"dry_run": False},
    })
    assert started["result"] == {"accepted": True, "job_id": "job-local-live"}
    _wait_until(lambda: (server.job_store.get_status("job-local-live") or {}).get("status") == "done")
    _wait_until(lambda: not server.job_manager.runtime_statuses())
    status = _rpc_call(server, "get_job_status", {"job_id": "job-local-live"})["result"]
    assert status["processed"] == 1
    assert status["succeeded"] == 1
    assert status["run_summary"] == {
        "dmc_rows_total": 1, "matched_from_excel": 1, "default_207": 0,
        "excel_missing": 0, "review_rows": 0, "applied_rows": 1, "dry_run_rows": 0,
    }
    assert status["completion_summary"]["succeeded"] == 1
    assert Path(status["summary_report_path"]).exists()
    assert not any("credit" in key for key in status)
    assert {event["type"] for event in notifications} >= {"progress", "record_done"}
    assert all(not any("credit" in key for key in event) for event in notifications)


@pytest.mark.parametrize("error_code,status", [("JOB_CANCELLED", "cancelled"), ("JOB_NOT_FOUND", "failed")])
def test_local_runtime_failure_preserves_checkpoint(monkeypatch, tmp_path: Path, error_code: str, status: str) -> None:
    monkeypatch.setattr(sidecar_config, "default_data_dir", lambda: tmp_path)
    notifications: list[dict[str, Any]] = []

    class _InterruptedModule:
        def start_job(self, job_id: str, excel_path: Path, options: dict[str, object], context) -> None:
            checkpoint = JobCheckpoint.initial(level_label="M3", base_url="https://portal.example.test")
            checkpoint.options = dict(options)
            checkpoint.processed = 1
            checkpoint.succeeded = 1
            checkpoint.next_page = 2
            context.job_store.mark_running(job_id, total_records=2, checkpoint=checkpoint, started_at=utc_now())
            context.job_store.save_checkpoint(job_id, checkpoint)
            raise DomainError(error_code)

    monkeypatch.setattr("dmc_sidecar.modules.get_module", lambda name: _InterruptedModule())
    monkeypatch.setattr("dmc_sidecar.rpc.get_browser_runtime_status", lambda: _ready_browser_status(tmp_path))
    server = RpcServer(emit_notification=notifications.append, secret_store=InMemorySecretStore())
    response = _rpc_call(server, "start_job", {
        "job_id": "job-interrupted", "module": "graduation",
        "excel_path": "source.xlsx", "options": {"dry_run": False},
    })
    assert response["result"]["accepted"] is True
    _wait_until(lambda: not server.job_manager.runtime_statuses())
    persisted = server.job_store.get_status("job-interrupted")
    assert persisted is not None and persisted["status"] == status
    assert persisted["processed"] == 1
    checkpoint = server.job_store.load_checkpoint("job-interrupted")
    assert checkpoint is not None and checkpoint.next_page == 2
    assert not any("credit" in key for key in persisted)
    if status == "failed":
        assert any(event.get("type") == "error" and event.get("code") == error_code for event in notifications)


def test_browser_runtime_bootstrap_then_retry_start_job_workflow(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(sidecar_config, "default_data_dir", lambda: tmp_path)
    notifications: list[dict[str, Any]] = []
    browser_state = {"installed": False}
    started_jobs: list[dict[str, Any]] = []

    def fake_browser_status():
        class BrowserStatus:
            installed = browser_state["installed"]

            def model_dump(self) -> dict[str, object]:
                return {
                    "state": "ready" if browser_state["installed"] else "missing",
                    "installed": browser_state["installed"],
                    "install_dir": str(tmp_path / "ms-playwright"),
                    "executable_path": (
                        str(tmp_path / "ms-playwright" / "chromium-1208" / "chrome-win" / "chrome.exe")
                        if browser_state["installed"]
                        else None
                    ),
                    "bootstrap_supported": True,
                    "bootstrap_performed": browser_state["installed"],
                    "estimated_download_bytes": 1024,
                    "required_components": [],
                    "message": "ready" if browser_state["installed"] else "missing",
                    "guidance": None,
                    "last_error": None,
                    "log_tail": [],
                }

        return BrowserStatus()

    def fake_bootstrap_browser_runtime(*, emit_progress=None):  # noqa: ANN001
        if emit_progress is not None:
            emit_progress({"type": "browser_runtime_progress", "phase": "installing", "percent": 45})
            emit_progress({"type": "browser_runtime_progress", "phase": "ready", "percent": 100})
        browser_state["installed"] = True
        return fake_browser_status()

    monkeypatch.setattr("dmc_sidecar.rpc.get_browser_runtime_status", fake_browser_status)
    monkeypatch.setattr("dmc_sidecar.rpc.bootstrap_browser_runtime", fake_bootstrap_browser_runtime)

    server = RpcServer(emit_notification=notifications.append, secret_store=InMemorySecretStore())
    monkeypatch.setattr(
        server.job_manager,
        "start_job",
        lambda *, job_id, module_name, excel_path, options, **_: started_jobs.append(
            {
                "job_id": job_id,
                "module": module_name,
                "excel_path": str(excel_path),
                "options": dict(options),
            }
        ),
    )

    first_start = _rpc_call(
        server,
        "start_job",
        {
            "job_id": "job-browser",
            "module": "graduation",
            "excel_path": "C:\\data\\m3.xlsx",
            "options": {"dry_run": True},
        },
    )
    assert first_start["error"]["code"] == "PLAYWRIGHT_BROWSER_MISSING"

    bootstrap = _rpc_call(server, "bootstrap_browser_runtime", {})
    assert bootstrap["result"]["installed"] is True
    assert any(event.get("type") == "browser_runtime_progress" for event in notifications)

    second_start = _rpc_call(
        server,
        "start_job",
        {
            "job_id": "job-browser",
            "module": "graduation",
            "excel_path": "C:\\data\\m3.xlsx",
            "options": {"dry_run": True},
        },
    )
    assert second_start["result"] == {
        "accepted": True,
        "job_id": "job-browser",
    }
    assert started_jobs == [
        {
            "job_id": "job-browser",
            "module": "graduation",
            "excel_path": "C:\\data\\m3.xlsx",
            "options": {"dry_run": True},
        }
    ]


def test_active_job_status_matches_frontend_contract(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(sidecar_config, "default_data_dir", lambda: tmp_path)
    started = threading.Event()
    release = threading.Event()

    class _BlockingModule:
        def start_job(self, job_id: str, excel_path: Path, options: dict[str, object], context) -> None:  # noqa: ANN001
            checkpoint = JobCheckpoint.initial(level_label="ม.3", base_url="https://portal.example.test")
            checkpoint.options = dict(options)
            context.snapshot.total = 217
            context.snapshot.current_page = 1
            context.snapshot.level_label = "ม.3"
            context.job_store.mark_running(
                job_id,
                total_records=217,
                checkpoint=checkpoint,
                started_at=utc_now(),
            )
            started.set()
            release.wait(timeout=5)

    monkeypatch.setattr("dmc_sidecar.modules.get_module", lambda module_name: _BlockingModule())
    monkeypatch.setattr("dmc_sidecar.rpc.get_browser_runtime_status", lambda: _ready_browser_status(tmp_path))

    server = RpcServer(emit_notification=lambda payload: None, secret_store=InMemorySecretStore())
    try:
        started_response = _rpc_call(
            server,
            "start_job",
            {
                "job_id": "job-active-contract",
                "module": "graduation",
                "excel_path": "C:\\data\\m3.xlsx",
                "options": {"dry_run": True},
            },
        )
        assert started_response["result"]["accepted"] is True
        assert started.wait(timeout=5)

        status_response = _rpc_call(server, "get_job_status", {"job_id": "job-active-contract"})
        status = status_response["result"]

        assert status["job_id"] == "job-active-contract"
        assert status["source_file"] == "C:\\data\\m3.xlsx"
        assert status["report_path"] is None
        assert status["review_report_path"] is None
        assert status["started_at"] is not None
        assert status["level_label"] == "ม.3"
        assert not any("credit" in key for key in status)
    finally:
        release.set()
        _wait_until(lambda: not server.job_manager.runtime_statuses())


@pytest.mark.parametrize("module_name", ["graduation", "currentStudents"])
def test_session_expiry_login_resume_workflow(monkeypatch, tmp_path: Path, module_name: str) -> None:
    monkeypatch.setattr(sidecar_config, "default_data_dir", lambda: tmp_path)
    notifications: list[dict[str, Any]] = []

    monkeypatch.setattr("dmc_sidecar.modules.get_module", lambda module_name: _ResumeAfterAuthModule())
    monkeypatch.setattr("dmc_sidecar.rpc.get_browser_runtime_status", lambda: _ready_browser_status(tmp_path))

    first_server = RpcServer(emit_notification=notifications.append, secret_store=InMemorySecretStore())
    started = _rpc_call(
        first_server,
        "start_job",
        {
            "job_id": "job-auth-1",
            "module": module_name,
            "excel_path": "C:\\data\\m3.xlsx",
            "options": {"dry_run": False},
        },
    )
    assert started["result"]["accepted"] is True

    _wait_until(lambda: first_server.job_store.get_status("job-auth-1")["status"] == "paused")
    paused_status = first_server.job_store.get_status("job-auth-1")
    assert paused_status is not None
    assert paused_status["status"] == "paused"
    assert any(event.get("type") == "needs_auth" for event in notifications)

    reopened_server = RpcServer(emit_notification=notifications.append, secret_store=InMemorySecretStore())
    resumed = _rpc_call(reopened_server, "resume_existing_job", {"job_id": "job-auth-1"})
    assert resumed["result"]["accepted"] is True

    _wait_until(lambda: reopened_server.job_store.get_status("job-auth-1")["status"] == "done")
    done_status = reopened_server.job_store.get_status("job-auth-1")
    assert done_status is not None
    assert done_status["needs_auth"] is False
    assert done_status["status"] == "done"
    assert not any("credit" in key for key in done_status)
    _wait_until(lambda: not reopened_server.job_manager.runtime_statuses())


def test_invalid_bundled_config_stops_validation_and_job_workflow(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(sidecar_config, "default_data_dir", lambda: tmp_path)
    bundled_root = tmp_path / "bundled"
    bundled_path = bundled_root / "graduation" / "v1.json"
    bundled_path.parent.mkdir(parents=True)
    bundled_path.write_text('{"module": "graduation"}', encoding="utf-8")
    monkeypatch.setattr(sidecar_config, "module_configs_root", lambda: bundled_root)
    monkeypatch.setattr("dmc_sidecar.rpc.get_browser_runtime_status", lambda: _ready_browser_status(tmp_path))
    notifications: list[dict[str, Any]] = []
    server = RpcServer(emit_notification=notifications.append, secret_store=InMemorySecretStore())

    validated = _rpc_call(server, "validate_excel", {"module": "graduation", "path": "not-read.xlsx"})
    assert validated["error"]["code"] == "CONFIG_BUNDLED_INVALID"
    started = _rpc_call(server, "start_job", {
        "job_id": "bad-config-job", "module": "graduation",
        "excel_path": "not-read.xlsx", "options": {"dry_run": False},
    })
    assert started["result"]["accepted"] is True
    _wait_until(lambda: not server.job_manager.runtime_statuses())
    status = server.job_store.get_status("bad-config-job")
    assert status is not None and status["status"] == "failed"
    assert status["processed"] == 0
    assert any(event.get("type") == "error" and event.get("code") == "CONFIG_BUNDLED_INVALID" for event in notifications)
    assert not (tmp_path / "profiles").exists()


def test_backup_restore_reopen_workflow(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(sidecar_config, "default_data_dir", lambda: tmp_path)

    server = RpcServer(emit_notification=lambda payload: None, secret_store=InMemorySecretStore())
    server.job_store.create_pending_job("backup-job", "currentStudents", "source.xlsx")
    backup_path = tmp_path / "e2e-backup.zip"
    backup = _rpc_call(server, "create_backup", {"path": str(backup_path)})
    assert Path(backup["result"]["backup_path"]).exists()

    server.job_store.set_status("backup-job", "failed")
    mutated_status = _rpc_call(server, "get_job_status", {"job_id": "backup-job"})
    assert mutated_status["result"]["status"] == "failed"

    restored = _rpc_call(server, "restore_backup", {"path": str(backup_path)})
    assert restored["result"]["restored_from"] == str(backup_path)
    assert Path(restored["result"]["safety_backup_path"]).exists()

    reopened_server = RpcServer(emit_notification=lambda payload: None, secret_store=InMemorySecretStore())
    restored_status = _rpc_call(reopened_server, "get_job_status", {"job_id": "backup-job"})
    assert restored_status["result"]["status"] == "pending"
    assert restored_status["result"]["module"] == "currentStudents"
