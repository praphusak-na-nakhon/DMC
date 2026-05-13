from __future__ import annotations

import json
import time
from pathlib import Path
from types import SimpleNamespace

from dmc_sidecar import config
from dmc_sidecar.checkpoint import JobCheckpoint
from dmc_sidecar.errors import DomainError
from dmc_sidecar.job_store import JobStore
from dmc_sidecar.rpc import RpcServer
from dmc_sidecar.runtime import build_event_notification
from dmc_sidecar.typhoon_ocr import TyphoonOcrDmcFormResponse


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


def _wait_until(assertion, *, timeout: float = 3.0) -> None:  # noqa: ANN001
    deadline = time.time() + timeout
    last_error: AssertionError | None = None
    while time.time() < deadline:
        try:
            result = assertion()
            if result is False:
                raise AssertionError("condition not satisfied")
            return
        except AssertionError as exc:
            last_error = exc
            time.sleep(0.02)
    if last_error is not None:
        raise last_error
    raise AssertionError("condition not satisfied")


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


def test_ocr_dmc_form_with_typhoon_rpc(monkeypatch, tmp_path: Path) -> None:  # noqa: ANN001
    captured: dict[str, object] = {}
    source_path = tmp_path / "form.pdf"
    source_path.write_bytes(b"%PDF-1.7\n1 0 obj << /Type /Page >> endobj\n%%EOF")

    def fake_ocr(request) -> TyphoonOcrDmcFormResponse:  # noqa: ANN001
        captured["request"] = request
        return TyphoonOcrDmcFormResponse(
            model="typhoon-ocr",
            source_path=request.source_path,
            markdown_path="C:\\dmc\\.dmc-assistant-data\\ocr\\typhoonocr\\form.md",
            cached=False,
            pages_processed=1,
            pages_estimated=1,
            average_confidence=None,
            file_sha256="abc123",
            created_at="2026-05-11T00:00:00+00:00",
        )

    reservations: list[dict[str, object]] = []
    captures: list[dict[str, object]] = []

    def fake_reserve(*args: object, **kwargs: object) -> SimpleNamespace:
        reservations.append(dict(kwargs))
        return SimpleNamespace(reservation_id="reservation-ocr-1")

    def fake_capture(*args: object, **kwargs: object) -> SimpleNamespace:
        captures.append(dict(kwargs))
        return SimpleNamespace(reservation_id=kwargs["reservation_id"])

    monkeypatch.setattr("dmc_sidecar.rpc.ocr_dmc_form_with_typhoon", fake_ocr)
    monkeypatch.setattr("dmc_sidecar.rpc.reserve_credits", fake_reserve)
    monkeypatch.setattr("dmc_sidecar.rpc.capture_credits", fake_capture)
    server = RpcServer(emit_notification=lambda payload: None)

    response = _rpc_call(
        server,
        "ocr_dmc_form_with_typhoon",
        {
            "source_path": str(source_path),
            "api_key": None,
            "model": "typhoon-ocr",
            "force_refresh": False,
        },
    )

    assert response["result"]["engine"] == "typhoonocr"
    assert response["result"]["markdown_path"].endswith("form.md")
    assert response["result"]["credits_charged"] == 3
    assert response["result"]["charged"] is True
    assert captured["request"].source_path == str(source_path)
    assert reservations[0]["module"] == "formConverter"
    assert reservations[0]["units"] == 3
    assert captures[0]["units"] == 3


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
    assert response["result"]["items"][0]["run_summary"] is None


def test_archive_old_jobs_rpc_keeps_latest_terminal_jobs(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(config, "default_data_dir", lambda: tmp_path)
    store = JobStore()
    for index in range(5):
        job_id = f"job-{index}"
        store.create_pending_job(job_id, "graduation", f"C:\\data\\m3-{index}.xlsx")
        checkpoint = JobCheckpoint.initial(level_label="เธก.3", base_url="https://example.test")
        store.mark_done(job_id, checkpoint=checkpoint, finished_at=f"2026-04-22T00:0{index}:00Z")
    store.create_pending_job("job-active", "graduation", "C:\\data\\active.xlsx")
    store.set_status("job-active", "running")

    server = RpcServer(emit_notification=lambda payload: None)
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


def test_get_browser_runtime_status_rpc(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(config, "default_data_dir", lambda: tmp_path)
    server = RpcServer(emit_notification=lambda payload: None)
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
    server = RpcServer(emit_notification=lambda payload: None)
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
    server = RpcServer(emit_notification=lambda payload: None)

    response = _rpc_call(server, "create_backup", {"path": "../escape.zip"})

    assert response["error"]["code"] == "BACKUP_PATH_INVALID"


def test_restore_backup_rpc_requires_idle(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(config, "default_data_dir", lambda: tmp_path)
    server = RpcServer(emit_notification=lambda payload: None)
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
    server = RpcServer(emit_notification=lambda payload: None)
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


def test_live_start_requires_account_session_before_job_starts(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(config, "default_data_dir", lambda: tmp_path)
    monkeypatch.setattr("dmc_sidecar.rpc.get_browser_runtime_status", lambda: _ready_browser_status(tmp_path))
    server = RpcServer(emit_notification=lambda payload: None)
    started: list[str] = []
    monkeypatch.setattr(server.job_manager, "start_job", lambda **_: started.append("started"))

    response = _rpc_call(
        server,
        "start_job",
        {
            "job_id": "job-credit-session",
            "module": "graduation",
            "excel_path": "C:\\data\\m3.xlsx",
            "options": {"dry_run": False, "estimated_credits": 3},
        },
    )

    assert response["error"]["code"] == "SIGN_IN_REQUIRED"
    assert started == []
    assert server.job_store.get_job_record("job-credit-session") is None


def test_live_start_reports_credit_reservation_failure_from_background(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(config, "default_data_dir", lambda: tmp_path)
    monkeypatch.setattr("dmc_sidecar.rpc.get_browser_runtime_status", lambda: _ready_browser_status(tmp_path))
    monkeypatch.setattr(
        "dmc_sidecar.rpc.reserve_credits",
        lambda *args, **kwargs: (_ for _ in ()).throw(DomainError("INSUFFICIENT_CREDITS")),
    )
    server = RpcServer(emit_notification=lambda payload: None)
    monkeypatch.setattr(server.account_store, "get_session", lambda: SimpleNamespace(token="token"))
    started: list[str] = []
    monkeypatch.setattr(server.job_manager, "start_job", lambda **_: started.append("started"))

    response = _rpc_call(
        server,
        "start_job",
        {
            "job_id": "job-credit-low",
            "module": "graduation",
            "excel_path": "C:\\data\\m3.xlsx",
            "options": {"dry_run": False, "estimated_credits": 3},
        },
    )

    assert response["result"]["accepted"] is True
    assert started == []
    _wait_until(lambda: (server.job_store.get_status("job-credit-low") or {}).get("status") == "failed")
    status = server.job_store.get_status("job-credit-low")
    assert status is not None
    assert status["credit_status"] == "start_failed:INSUFFICIENT_CREDITS"


def test_live_start_reports_account_cloud_failure_from_background(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(config, "default_data_dir", lambda: tmp_path)
    monkeypatch.setattr("dmc_sidecar.rpc.get_browser_runtime_status", lambda: _ready_browser_status(tmp_path))
    monkeypatch.setattr(
        "dmc_sidecar.rpc.reserve_credits",
        lambda *args, **kwargs: (_ for _ in ()).throw(DomainError("ACCOUNT_CLOUD_UNAVAILABLE")),
    )
    server = RpcServer(emit_notification=lambda payload: None)
    monkeypatch.setattr(server.account_store, "get_session", lambda: SimpleNamespace(token="token"))
    started: list[str] = []
    monkeypatch.setattr(server.job_manager, "start_job", lambda **_: started.append("started"))

    response = _rpc_call(
        server,
        "start_job",
        {
            "job_id": "job-cloud-down",
            "module": "graduation",
            "excel_path": "C:\\data\\m3.xlsx",
            "options": {"dry_run": False, "estimated_credits": 3},
        },
    )

    assert response["result"]["accepted"] is True
    assert started == []
    _wait_until(lambda: (server.job_store.get_status("job-cloud-down") or {}).get("status") == "failed")
    status = server.job_store.get_status("job-cloud-down")
    assert status is not None
    assert status["credit_status"] == "start_failed:ACCOUNT_CLOUD_UNAVAILABLE"


def test_rpc_server_reaps_reserving_jobs_from_previous_process(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(config, "default_data_dir", lambda: tmp_path)
    store = JobStore()
    store.create_pending_job(
        job_id="job-interrupted-reserve",
        module="graduation",
        source_file="C:\\data\\m3.xlsx",
        credits_reserved=3,
        credit_status="reserving",
    )
    notifications: list[dict[str, object]] = []

    server = RpcServer(emit_notification=notifications.append)

    status = server.job_store.get_status("job-interrupted-reserve")
    assert status is not None
    assert status["status"] == "failed"
    assert status["credit_status"] == "start_failed:RESTART_DURING_RESERVATION"
    assert any("interrupted credit reservation" in str(item.get("message")) for item in notifications)


def test_rpc_server_releases_reaped_cloud_reservation(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(config, "default_data_dir", lambda: tmp_path)
    store = JobStore()
    store.create_pending_job(
        job_id="job-interrupted-cloud-reserve",
        module="graduation",
        source_file="C:\\data\\m3.xlsx",
        credit_reservation_id="reservation-old",
        credits_reserved=4,
        credit_status="reserving",
    )
    released: list[dict[str, object]] = []
    monkeypatch.setattr(
        "dmc_sidecar.rpc.AccountSessionStore.get_session",
        lambda self: SimpleNamespace(token="token"),
    )
    monkeypatch.setattr(
        "dmc_sidecar.rpc.release_credits",
        lambda *args, **kwargs: released.append(dict(kwargs)) or SimpleNamespace(reservation_id="reservation-old"),
    )
    monkeypatch.setattr(
        "dmc_sidecar.rpc.reserve_credits",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("known reservation should be released directly")),
    )

    server = RpcServer(emit_notification=lambda payload: None)

    assert released == [
        {
            "reservation_id": "reservation-old",
            "units": 4,
            "idempotency_key": "job-interrupted-cloud-reserve:reaper:release",
        }
    ]
    status = server.job_store.get_status("job-interrupted-cloud-reserve")
    assert status is not None
    assert status["status"] == "failed"
    assert status["credit_status"] == "start_failed:RESTART_DURING_RESERVATION"


def test_live_start_reserves_credits_in_background_before_starting_job(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(config, "default_data_dir", lambda: tmp_path)
    monkeypatch.setattr("dmc_sidecar.rpc.get_browser_runtime_status", lambda: _ready_browser_status(tmp_path))
    reserved: dict[str, object] = {}
    started: dict[str, object] = {}

    def fake_reserve_credits(*args: object, job_id: str, module: str, units: int, idempotency_key: str, **_: object):
        reserved.update(
            {
                "job_id": job_id,
                "module": module,
                "units": units,
                "idempotency_key": idempotency_key,
            }
        )
        return SimpleNamespace(reservation_id="reservation-1")

    def fake_start_job(**kwargs: object) -> None:
        started.update(kwargs)

    monkeypatch.setattr("dmc_sidecar.rpc.reserve_credits", fake_reserve_credits)
    server = RpcServer(emit_notification=lambda payload: None)
    monkeypatch.setattr(server.account_store, "get_session", lambda: SimpleNamespace(token="token"))
    monkeypatch.setattr(server.job_manager, "start_job", fake_start_job)

    response = _rpc_call(
        server,
        "start_job",
        {
            "job_id": "job-credit-ok",
            "module": "graduation",
            "excel_path": "C:\\data\\m3.xlsx",
            "options": {"dry_run": False, "estimated_credits": 7},
        },
    )

    assert response["result"] == {
        "accepted": True,
        "job_id": "job-credit-ok",
        "credit_reservation_id": None,
        "credits_reserved": 7,
    }
    _wait_until(lambda: started.get("credit_reservation_id") == "reservation-1")
    assert reserved == {
        "job_id": "job-credit-ok",
        "module": "graduation",
        "units": 7,
        "idempotency_key": "job-credit-ok:reserve",
    }
    assert started["credit_reservation_id"] == "reservation-1"
    assert started["credits_reserved"] == 7
    status = server.job_store.get_status("job-credit-ok")
    assert status is not None
    assert status["credit_reservation_id"] == "reservation-1"
    assert status["credits_reserved"] == 7


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


def test_resume_existing_job_re_reserves_finalized_credit_reservation(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(config, "default_data_dir", lambda: tmp_path)
    store = JobStore()
    store.create_pending_job(
        "job-credit-finalized",
        "graduation",
        "C:\\data\\m6.xlsx",
        credit_reservation_id="reservation-finalized",
        credits_reserved=10,
        credit_status="reserved",
    )
    checkpoint = JobCheckpoint.initial(level_label="เธก.6", base_url="https://example.test")
    checkpoint.options = {"dry_run": False}
    store.mark_running(
        "job-credit-finalized",
        total_records=10,
        checkpoint=checkpoint,
        started_at="2026-04-22T00:00:00Z",
    )
    store.set_status("job-credit-finalized", "paused")
    store.update_credit_status("job-credit-finalized", credit_status="finalized")

    server = RpcServer(emit_notification=lambda payload: None)
    monkeypatch.setattr("dmc_sidecar.rpc.get_browser_runtime_status", lambda: _ready_browser_status(tmp_path))
    reservations: list[dict[str, object]] = []

    def fake_reserve_credits(*args: object, **kwargs: object) -> object:
        reservations.append(dict(kwargs))
        return SimpleNamespace(reservation_id="reservation-resume-1")

    started: dict[str, object] = {}

    def fake_start_job(**kwargs: object) -> None:
        started.update(kwargs)

    monkeypatch.setattr("dmc_sidecar.rpc.reserve_credits", fake_reserve_credits)
    monkeypatch.setattr(server.job_manager, "start_job", fake_start_job)
    payload = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": "req-finalized-credit",
            "method": "resume_existing_job",
            "params": {"job_id": "job-credit-finalized"},
        }
    )

    response = json.loads(server.handle_text(payload))

    assert response["result"]["accepted"] is True
    assert reservations[0]["units"] == 10
    assert str(reservations[0]["job_id"]).startswith("job-credit-finalized:resume:")
    assert started["credit_reservation_id"] == "reservation-resume-1"
    assert started["credits_reserved"] == 10
    status = server.job_store.get_status("job-credit-finalized")
    assert status is not None
    assert status["credit_reservation_id"] == "reservation-resume-1"
    assert status["credit_status"] == "reserved"


def test_rpc_sanitizes_unexpected_exception_messages(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(config, "default_data_dir", lambda: tmp_path)
    server = RpcServer(emit_notification=lambda payload: None)

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
    server = RpcServer(emit_notification=lambda payload: None)

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
    server = RpcServer(emit_notification=lambda payload: None)

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
