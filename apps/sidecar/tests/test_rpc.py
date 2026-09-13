from __future__ import annotations

import json
from pathlib import Path

import pytest

from dmc_sidecar import config
from ai_fakes import InMemorySecretStore
from dmc_sidecar.ai.base import AiConnectionTestResponse, OcrDocumentRequest, OcrDocumentResponse
from dmc_sidecar.ai.registry import ProviderRegistry
from dmc_sidecar.checkpoint import JobCheckpoint
from dmc_sidecar.errors import DomainError
from dmc_sidecar.job_store import JobStore
from dmc_sidecar.rpc import RpcServer
from dmc_sidecar.runtime import build_event_notification


def _rpc_call(server: RpcServer, method: str, params: dict[str, object]) -> dict[str, object]:
    return json.loads(
        server.handle_text(
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": f"req-{method}",
                    "method": method,
                    "params": params,
                }
            )
        )
    )


def _ready_browser_status(tmp_path: Path):
    return type(
        "Status",
        (),
        {
            "installed": True,
            "model_dump": lambda self: {
                "installed": True,
                "install_dir": str(tmp_path / "ms-playwright"),
                "executable_path": str(tmp_path / "ms-playwright" / "chromium-1208" / "chrome-win" / "chrome.exe"),
                "bootstrap_supported": True,
                "bootstrap_performed": False,
                "message": "ready",
                "last_error": None,
            },
        },
    )()


def test_database_status_exposes_generation_and_local_columns(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(config, "default_data_dir", lambda: tmp_path)
    server = RpcServer(emit_notification=lambda payload: None, secret_store=InMemorySecretStore())

    response = _rpc_call(server, "get_database_status", {})

    metadata = response["result"]
    assert metadata["schema_generation"] == 2
    assert set(metadata["tables"]) == {"job", "job_record", "schema_metadata"}
    assert "checkpoint_json" in metadata["job_columns"]
    assert "credit_status" not in metadata["job_columns"]


@pytest.mark.parametrize("module_name", ["graduation", "currentStudents"])
def test_live_job_starts_without_account_or_credit(monkeypatch, tmp_path: Path, module_name: str) -> None:
    monkeypatch.setattr(config, "default_data_dir", lambda: tmp_path)
    server = RpcServer(emit_notification=lambda payload: None, secret_store=InMemorySecretStore())
    monkeypatch.setattr("dmc_sidecar.rpc.get_browser_runtime_status", lambda: _ready_browser_status(tmp_path))
    started: dict[str, object] = {}
    monkeypatch.setattr(server.job_manager, "start_job", lambda **kwargs: started.update(kwargs))

    response = _rpc_call(server, "start_job", {
        "job_id": "job-local-free", "module": module_name,
        "excel_path": "C:\\data\\m3.xlsx", "options": {"dry_run": False},
    })

    assert response.get("result") == {"accepted": True, "job_id": "job-local-free"}, response
    assert started == {"job_id": "job-local-free", "module_name": module_name,
                       "excel_path": Path("C:\\data\\m3.xlsx"), "options": {"dry_run": False}}
    status = server.job_store.get_status("job-local-free")
    assert status is not None and status["status"] == "pending"
    assert not any("credit" in key for key in status)
    record = server.job_store.get_job_record("job-local-free")
    assert record is not None and not any("credit" in key for key in record)


@pytest.mark.parametrize("method", ["sign_in", "sign_out", "get_account_status", "refresh_wallet", "get_module_catalog"])
def test_commercial_rpc_is_unsupported(method: str) -> None:
    server = RpcServer(emit_notification=lambda payload: None, secret_store=InMemorySecretStore())
    response = _rpc_call(server, method, {})
    assert response["error"]["code"] == "RPC_METHOD_NOT_FOUND"


def test_live_start_failure_marks_local_pending_job_failed(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(config, "default_data_dir", lambda: tmp_path)
    server = RpcServer(emit_notification=lambda payload: None, secret_store=InMemorySecretStore())
    monkeypatch.setattr("dmc_sidecar.rpc.get_browser_runtime_status", lambda: _ready_browser_status(tmp_path))

    def fail_start(**kwargs: object) -> None:
        raise DomainError("JOB_ALREADY_RUNNING")

    monkeypatch.setattr(server.job_manager, "start_job", fail_start)
    response = _rpc_call(server, "start_job", {
        "job_id": "job-start-failed", "module": "graduation",
        "excel_path": "source.xlsx", "options": {"dry_run": False},
    })

    assert response["error"]["code"] == "JOB_ALREADY_RUNNING"
    status = server.job_store.get_status("job-start-failed")
    assert status is not None and status["status"] == "failed"
    assert status["finished_at"] is not None
    assert status["processed"] == 0
    assert not any("credit" in key for key in status)


@pytest.mark.parametrize("module_name", ["graduation", "currentStudents"])
@pytest.mark.parametrize("status", ["paused", "stopped_on_review"])
def test_live_job_resumes_without_account_or_credit(monkeypatch, tmp_path: Path, module_name: str, status: str) -> None:
    monkeypatch.setattr(config, "default_data_dir", lambda: tmp_path)
    server = RpcServer(emit_notification=lambda payload: None, secret_store=InMemorySecretStore())
    server.job_store.create_pending_job("job-local-resume", module_name, "C:\\data\\m3.xlsx")
    checkpoint = JobCheckpoint.initial(level_label="M3", base_url="https://portal.example.test")
    checkpoint.options = {"dry_run": False, "stop_on_review": True}
    checkpoint.processed = 1
    checkpoint.next_page = 2
    server.job_store.mark_running("job-local-resume", total_records=3, checkpoint=checkpoint, started_at="2026-09-04T00:00:00Z")
    server.job_store.save_checkpoint("job-local-resume", checkpoint)
    server.job_store.set_status("job-local-resume", status)
    monkeypatch.setattr("dmc_sidecar.rpc.get_browser_runtime_status", lambda: _ready_browser_status(tmp_path))
    started: dict[str, object] = {}
    monkeypatch.setattr(server.job_manager, "start_job", lambda **kwargs: started.update(kwargs))

    response = _rpc_call(server, "resume_existing_job", {"job_id": "job-local-resume"})

    assert response["result"] == {"accepted": True, "job_id": "job-local-resume", "status": "running"}
    assert started == {"job_id": "job-local-resume", "module_name": module_name,
                       "excel_path": Path("C:\\data\\m3.xlsx"), "options": {"dry_run": False, "stop_on_review": True}}
    persisted = server.job_store.get_status("job-local-resume")
    assert persisted is not None and persisted["processed"] == 1 and persisted["current_page"] == 2
    assert not any("credit" in key for key in persisted)


def test_ping_rpc() -> None:
    server = RpcServer(emit_notification=lambda payload: None, secret_store=InMemorySecretStore())
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


def test_unsupported_rpc_returns_method_not_found_envelope() -> None:
    server = RpcServer(emit_notification=lambda payload: None, secret_store=InMemorySecretStore())

    response = _rpc_call(server, "unsupported_method", {})

    assert response == {
        "jsonrpc": "2.0",
        "id": "req-unsupported_method",
        "error": {
            "code": "RPC_METHOD_NOT_FOUND",
            "message": "Unsupported method.",
            "details": {},
        },
    }


class _FakeAiProvider:
    provider_id = "gemini"

    def test_connection(self) -> AiConnectionTestResponse:
        return AiConnectionTestResponse(
            provider="gemini",
            ok=True,
            tested_at="2026-09-04T00:00:00+00:00",
            message="Gemini connection succeeded.",
        )

    def ocr_document(self, request: OcrDocumentRequest) -> OcrDocumentResponse:
        return OcrDocumentResponse(
            provider="gemini",
            model=request.model,
            processing_mode=request.processing_mode,
            source_path=request.source_path,
            markdown_path="C:\\data\\form.md",
            cached=False,
            pages_processed=1,
            pages_estimated=1,
            file_sha256="digest",
            created_at="2026-09-04T00:00:00+00:00",
        )


def _ai_server(store: InMemorySecretStore | None = None) -> RpcServer:
    return RpcServer(
        emit_notification=lambda payload: None,
        secret_store=store or InMemorySecretStore(),
        provider_registry=ProviderRegistry([_FakeAiProvider()]),
    )


def test_ai_key_rpc_never_returns_secret() -> None:
    store = InMemorySecretStore()
    server = _ai_server(store)

    saved = _rpc_call(server, "save_ai_api_key", {"provider": "gemini", "api_key": "secret-value"})
    status = _rpc_call(server, "get_ai_settings", {"provider": "gemini"})

    assert saved["result"] == {"provider": "gemini", "configured": True}
    assert status["result"] == {"provider": "gemini", "configured": True}
    assert "secret-value" not in json.dumps([saved, status])


def test_ai_connection_and_ocr_rpc_use_injected_provider() -> None:
    store = InMemorySecretStore()
    store.set("gemini", "configured-key")
    server = _ai_server(store)

    connection = _rpc_call(server, "test_ai_connection", {"provider": "gemini"})
    document = _rpc_call(
        server,
        "ocr_document",
        {"provider": "gemini", "source_path": "C:\\data\\form.pdf"},
    )

    assert connection["result"]["ok"] is True
    assert document["result"]["provider"] == "gemini"
    assert document["result"]["source_path"] == "C:\\data\\form.pdf"


def test_deleting_key_blocks_new_ocr_requests() -> None:
    store = InMemorySecretStore()
    store.set("gemini", "secret-value")
    server = _ai_server(store)
    deleted = _rpc_call(server, "delete_ai_api_key", {"provider": "gemini"})

    response = _rpc_call(
        server,
        "ocr_document",
        {"provider": "gemini", "source_path": "C:\\data\\form.pdf"},
    )

    assert deleted["result"] == {"provider": "gemini", "configured": False}
    assert response["error"]["code"] == "AI_API_KEY_REQUIRED"


def test_ai_rpc_validation_and_unexpected_errors_never_echo_secrets(capsys) -> None:  # noqa: ANN001
    class ExplodingProvider(_FakeAiProvider):
        def test_connection(self) -> AiConnectionTestResponse:
            raise RuntimeError("provider-secret")

    server = RpcServer(
        emit_notification=lambda payload: None,
        secret_store=InMemorySecretStore(),
        provider_registry=ProviderRegistry([ExplodingProvider()]),
    )

    malformed = json.loads(
        server.handle_text(
            json.dumps({"jsonrpc": "2.0", "id": "request-secret", "method": "ping", "params": {}, "api_key": "envelope-secret"})
        )
    )
    invalid_params = _rpc_call(
        server,
        "save_ai_api_key",
        {"provider": "provider-secret", "api_key": "param-secret", "extra": "extra-secret", "student_name": "PRIVATE_STUDENT"},
    )
    assert invalid_params["id"] == "req-save_ai_api_key"
    assert invalid_params["error"]["code"] == "RPC_INVALID_REQUEST"
    validation_errors = invalid_params["error"]["details"]["errors"]
    assert {error["type"] for error in validation_errors} == {"literal_error", "extra_forbidden"}
    assert all(set(error) == {"type", "message"} for error in validation_errors)
    invalid_method = json.loads(
        server.handle_text(
            json.dumps({"jsonrpc": "2.0", "id": "request-id", "method": "method-secret", "params": {}})
        )
    )
    unexpected = _rpc_call(server, "test_ai_connection", {"provider": "gemini"})

    visible_output = json.dumps([malformed, invalid_params, invalid_method, unexpected]) + capsys.readouterr().err
    for secret in ("envelope-secret", "param-secret", "extra-secret", "provider-secret", "method-secret", "request-secret", "PRIVATE_STUDENT", "student_name"):
        assert secret not in visible_output




def test_list_jobs_rpc(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(config, "default_data_dir", lambda: tmp_path)
    store = JobStore()
    store.create_pending_job("job-1", "graduation", "C:\\data\\m3.xlsx")
    checkpoint = JobCheckpoint.initial(level_label="ม.3", base_url="https://example.test")
    checkpoint.options = {"dry_run": True}
    store.mark_running(
        "job-1",
        total_records=3,
        checkpoint=checkpoint,
        started_at="2026-04-22T00:00:00Z",
    )
    store.append_results(
        "job-1",
        [
            {
                "page": 1,
                "portal_row_index": 1,
                "matched_order": 1,
                "matched_status_code": "201",
                "applied": False,
                "note": "dry_run",
            },
            {
                "page": 1,
                "portal_row_index": 2,
                "matched_order": None,
                "matched_status_code": "207",
                "applied": False,
                "note": "default_missing_dry_run",
            },
            {
                "page": 1,
                "portal_row_index": 3,
                "matched_order": 3,
                "matched_status_code": "",
                "applied": False,
                "note": "option_value_not_found",
            },
        ],
    )

    server = RpcServer(emit_notification=lambda payload: None, secret_store=InMemorySecretStore())
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
    assert response["result"]["items"][0]["run_summary"] is None


def test_archive_old_jobs_rpc_keeps_latest_terminal_jobs(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(config, "default_data_dir", lambda: tmp_path)
    store = JobStore()
    for index in range(5):
        job_id = f"job-{index}"
        store.create_pending_job(job_id, "graduation", f"C:\\data\\m3-{index}.xlsx")
        store.append_results(job_id, [{"page": 1, "portal_row_index": 1, "note": "dry_run"}])
        checkpoint = JobCheckpoint.initial(level_label="เธก.3", base_url="https://example.test")
        store.mark_done(job_id, checkpoint=checkpoint, finished_at=f"2026-04-22T00:0{index}:00Z")
    store.create_pending_job("job-active", "graduation", "C:\\data\\active.xlsx")
    store.set_status("job-active", "running")

    server = RpcServer(emit_notification=lambda payload: None, secret_store=InMemorySecretStore())
    payload = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": "req-archive",
            "method": "archive_old_jobs",
            "params": {"keep_latest": 2},
        }
    )

    response = json.loads(server.handle_text(payload))
    remaining_ids = {job["job_id"] for job in server.job_store.list_jobs(limit=10)}

    assert response["result"] == {"archived": 3, "kept": 2}
    assert {"job-4", "job-3", "job-active"}.issubset(remaining_ids)
    assert "job-0" not in remaining_ids
    assert store.list_results("job-0") == []
    assert store.list_results("job-4") == [{"page": 1, "portal_row_index": 1, "note": "dry_run"}]


@pytest.mark.parametrize("method", ["get_module_config_status", "sync_module_config"])
def test_config_management_rpcs_are_removed(monkeypatch, tmp_path: Path, method: str) -> None:
    monkeypatch.setattr(config, "default_data_dir", lambda: tmp_path)
    server = RpcServer(emit_notification=lambda payload: None, secret_store=InMemorySecretStore())
    payload = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": "req-config",
            "method": method,
            "params": {"module": "graduation"},
        }
    )

    response = json.loads(server.handle_text(payload))

    assert response["error"]["code"] == "RPC_METHOD_NOT_FOUND"


def test_get_browser_runtime_status_rpc(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(config, "default_data_dir", lambda: tmp_path)
    server = RpcServer(emit_notification=lambda payload: None, secret_store=InMemorySecretStore())
    monkeypatch.setattr(
        "dmc_sidecar.rpc.get_browser_runtime_status",
        lambda: type(
            "Status",
            (),
            {
                "model_dump": lambda self: {
                    "installed": True,
                    "install_dir": str(tmp_path / "ms-playwright"),
                    "executable_path": str(tmp_path / "ms-playwright" / "chromium-1208" / "chrome-win" / "chrome.exe"),
                    "bootstrap_supported": True,
                    "bootstrap_performed": False,
                    "message": "ready",
                    "last_error": None,
                }
            },
        )(),
    )

    payload = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": "req-browser-status",
            "method": "get_browser_runtime_status",
            "params": {},
        }
    )

    response = json.loads(server.handle_text(payload))

    assert response["result"]["installed"] is True
    assert response["result"]["bootstrap_supported"] is True


def test_create_backup_rpc_returns_archive_path(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(config, "default_data_dir", lambda: tmp_path)
    server = RpcServer(emit_notification=lambda payload: None, secret_store=InMemorySecretStore())
    payload = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": "req-backup",
            "method": "create_backup",
            "params": {"path": str(tmp_path / "manual-backup.zip")},
        }
    )

    response = json.loads(server.handle_text(payload))

    assert Path(response["result"]["backup_path"]).exists()


def test_backup_rpc_rejects_relative_escape_path(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(config, "default_data_dir", lambda: tmp_path / "data")
    server = RpcServer(emit_notification=lambda payload: None, secret_store=InMemorySecretStore())

    response = _rpc_call(server, "create_backup", {"path": "../escape.zip"})

    assert response["error"]["code"] == "BACKUP_PATH_INVALID"


def test_restore_backup_rpc_requires_idle(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(config, "default_data_dir", lambda: tmp_path)
    server = RpcServer(emit_notification=lambda payload: None, secret_store=InMemorySecretStore())
    monkeypatch.setattr(
        server.job_manager,
        "runtime_statuses",
        lambda: [{"job_id": "job-1", "status": "running"}],
    )

    payload = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": "req-restore-busy",
            "method": "restore_backup",
            "params": {"path": str(tmp_path / "backup.zip")},
        }
    )

    response = json.loads(server.handle_text(payload))

    assert response["error"]["code"] == "RESTORE_REQUIRES_IDLE"


def test_start_job_rpc_requires_browser_runtime(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(config, "default_data_dir", lambda: tmp_path)
    server = RpcServer(emit_notification=lambda payload: None, secret_store=InMemorySecretStore())
    monkeypatch.setattr(
        "dmc_sidecar.rpc.get_browser_runtime_status",
        lambda: type(
            "Status",
            (),
            {
                "installed": False,
                "model_dump": lambda self: {
                    "installed": False,
                    "install_dir": str(tmp_path / "ms-playwright"),
                    "executable_path": None,
                    "bootstrap_supported": True,
                    "bootstrap_performed": False,
                    "message": "missing",
                    "last_error": None,
                }
            },
        )(),
    )

    payload = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": "req-start-browser",
            "method": "start_job",
            "params": {
                "job_id": "job-browser",
                "module": "graduation",
                "excel_path": "C:\\data\\m3.xlsx",
                "options": {"dry_run": True},
            },
        }
    )

    response = json.loads(server.handle_text(payload))

    assert response["error"]["code"] == "PLAYWRIGHT_BROWSER_MISSING"
    assert response["error"]["details"]["installed"] is False


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

    server = RpcServer(emit_notification=lambda payload: None, secret_store=InMemorySecretStore())
    before_resume = server.job_store.get_status("job-1")
    started: dict[str, object] = {}
    monkeypatch.setattr(
        "dmc_sidecar.rpc.get_browser_runtime_status",
        lambda: type(
            "Status",
            (),
            {
                "installed": True,
                "model_dump": lambda self: {
                    "installed": True,
                    "install_dir": str(tmp_path / "ms-playwright"),
                    "executable_path": str(tmp_path / "ms-playwright" / "chromium-1208" / "chrome-win" / "chrome.exe"),
                    "bootstrap_supported": True,
                    "bootstrap_performed": False,
                    "message": "ready",
                    "last_error": None,
                }
            },
        )(),
    )

    def fake_start_job(
        *,
        job_id: str,
        module_name: str,
        excel_path: Path,
        options: dict[str, object],
        **_: object,
    ) -> None:
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

    server = RpcServer(emit_notification=lambda payload: None, secret_store=InMemorySecretStore())
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


def test_rpc_sanitizes_unexpected_exception_messages(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(config, "default_data_dir", lambda: tmp_path)
    server = RpcServer(emit_notification=lambda payload: None, secret_store=InMemorySecretStore())

    class BadModule:
        def validate_excel(self, path):  # noqa: ANN001
            raise ValueError("student 17217 failed to parse")

    monkeypatch.setattr("dmc_sidecar.rpc.get_module", lambda module_name: BadModule())

    payload = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": "req-unsafe",
            "method": "validate_excel",
            "params": {"module": "graduation", "path": "C:\\data\\unsafe.xlsx"},
        }
    )

    response = json.loads(server.handle_text(payload))

    assert response["error"]["code"] == "UNEXPECTED_ERROR"
    assert response["error"]["message"] == "Unexpected internal error."


def test_validate_excel_rpc_reports_missing_openpyxl(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(config, "default_data_dir", lambda: tmp_path)
    server = RpcServer(emit_notification=lambda payload: None, secret_store=InMemorySecretStore())

    class MissingExcelReaderModule:
        def validate_excel(self, path):  # noqa: ANN001
            raise ImportError("Missing optional dependency 'openpyxl'.")

    monkeypatch.setattr("dmc_sidecar.rpc.get_module", lambda module_name: MissingExcelReaderModule())

    payload = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": "req-openpyxl",
            "method": "validate_excel",
            "params": {"module": "graduation", "path": "C:\\data\\m3.xlsx"},
        }
    )

    response = json.loads(server.handle_text(payload))

    assert response["error"]["code"] == "EXCEL_READER_MISSING"
    assert "openpyxl" in response["error"]["message"]


def test_validate_excel_rpc_response_is_ascii_safe(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(config, "default_data_dir", lambda: tmp_path)
    server = RpcServer(emit_notification=lambda payload: None, secret_store=InMemorySecretStore())

    class ThaiPreviewModule:
        def validate_excel(self, path):  # noqa: ANN001
            return type(
                "Result",
                (),
                {
                    "model_dump": lambda self: {
                        "module": "graduation",
                        "detected_level": "ม.3",
                        "rows_total": 1,
                        "rows_accepted": 1,
                        "warnings": [],
                        "preview": [
                            {
                                "order": 1,
                                "level_label": "ม.3",
                                "room": None,
                                "student_no": "18551",
                                "first_name": "ทวีศักดิ์",
                                "last_name": "ฝั่งขวา",
                                "status_text": "(ม.3) ศึกษาต่อ ม.4 โรงเรียนเดิม",
                                "status_code": "201",
                            }
                        ],
                    }
                },
            )()

    monkeypatch.setattr("dmc_sidecar.rpc.get_module", lambda module_name: ThaiPreviewModule())

    payload = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": "req-thai",
            "method": "validate_excel",
            "params": {"module": "graduation", "path": "C:\\data\\m3.xlsx"},
        }
    )

    response_text = server.handle_text(payload)
    response_text.encode("ascii")
    response = json.loads(response_text)

    assert response["result"]["detected_level"] == "ม.3"
    assert response["result"]["preview"][0]["first_name"] == "ทวีศักดิ์"


def test_sidecar_event_notification_is_ascii_safe() -> None:
    event_text = build_event_notification(
        {
            "type": "record_done",
            "job_id": "job-thai",
            "message": "ทวีศักดิ์",
        }
    )

    event_text.encode("ascii")
    event = json.loads(event_text)

    assert event["params"]["message"] == "ทวีศักดิ์"


@pytest.mark.parametrize("method", ["ocr_dmc_form_with_gemini", "ocr_dmc_form_with_akson", "ocr_dmc_form_with_typhoon"])
def test_legacy_ocr_rpc_is_unsupported(method: str) -> None:
    server = RpcServer(emit_notification=lambda payload: None, secret_store=InMemorySecretStore())
    response = _rpc_call(server, method, {"source_path": "missing.pdf"})
    assert response["error"]["code"] == "RPC_METHOD_NOT_FOUND"
