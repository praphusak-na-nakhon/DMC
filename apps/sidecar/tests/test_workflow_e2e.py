from __future__ import annotations

import base64
import io
import json
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app as cloud_app
from app.telemetry_store import TelemetryStore as CloudTelemetryStore
from dmc_sidecar import config as sidecar_config
from dmc_sidecar.checkpoint import JobCheckpoint
from dmc_sidecar.license_store import LicenseStore
from dmc_sidecar.module_config import load_effective_config, sync_module_config
from dmc_sidecar.rpc import RpcServer
from dmc_sidecar.runtime import utc_now
from dmc_sidecar.schemas import LicenseRecord


class _UrlopenResponse:
    def __init__(self, *, status: int, headers: dict[str, str], body: bytes) -> None:
        self.status = status
        self.headers = headers
        self._body = body

    def read(self) -> bytes:
        return self._body

    def getcode(self) -> int:
        return self.status

    def __enter__(self) -> "_UrlopenResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:  # noqa: ANN001
        return False


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


def _make_cloud_urlopen(client: TestClient):
    def fake_urlopen(request, timeout=10):  # noqa: ANN001, ARG001
        if isinstance(request, Request):
            url = request.full_url
            method = request.get_method()
            headers = {key: value for key, value in request.header_items()}
            body = request.data
        else:
            url = str(request)
            method = "GET"
            headers = {}
            body = None

        parsed = urlsplit(url)
        path = parsed.path or "/"
        if parsed.query:
            path = f"{path}?{parsed.query}"

        response = client.request(method, path, headers=headers, content=body)
        if response.status_code >= 400:
            raise HTTPError(
                url,
                response.status_code,
                response.reason_phrase,
                hdrs=response.headers,
                fp=io.BytesIO(response.content),
            )

        return _UrlopenResponse(
            status=response.status_code,
            headers=dict(response.headers),
            body=response.content,
        )

    return fake_urlopen


def _configure_cloud_bridge(monkeypatch, tmp_path: Path, client: TestClient) -> None:
    monkeypatch.setattr(settings, "sqlite_path", str(tmp_path / "cloud-state.sqlite3"))
    monkeypatch.setattr(settings, "trial_license_keys", "DMC-E2E-0001")
    monkeypatch.setattr(sidecar_config, "default_data_dir", lambda: tmp_path)
    monkeypatch.setattr(sidecar_config, "cloud_base_url", lambda: "https://cloud.test")
    monkeypatch.setattr("dmc_sidecar.license_client.secure_cloud_base_url", lambda: "https://cloud.test")
    monkeypatch.setattr("dmc_sidecar.telemetry.secure_cloud_base_url", lambda: "https://cloud.test")
    monkeypatch.setattr("dmc_sidecar.license_client.get_or_create_device_id", lambda: "device-1")
    monkeypatch.setattr("dmc_sidecar.license_client.default_device_name", lambda: "desktop-01")
    fake_urlopen = _make_cloud_urlopen(client)
    monkeypatch.setattr("dmc_sidecar.license_client.urlopen", fake_urlopen)
    monkeypatch.setattr("dmc_sidecar.telemetry.urlopen", fake_urlopen)


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


def test_activate_heartbeat_and_start_job_workflow(monkeypatch, tmp_path: Path) -> None:
    client = TestClient(cloud_app)
    _configure_cloud_bridge(monkeypatch, tmp_path, client)
    notifications: list[dict[str, Any]] = []

    monkeypatch.setattr("dmc_sidecar.modules.get_module", lambda module_name: _CompletingModule())
    monkeypatch.setattr("dmc_sidecar.rpc.get_browser_runtime_status", lambda: _ready_browser_status(tmp_path))

    server = RpcServer(emit_notification=notifications.append)

    activate = _rpc_call(
        server,
        "activate_license",
        {
            "license_key": "DMC-E2E-0001",
            "device_name": "desktop-01",
            "app_version": "0.1.0",
        },
    )
    assert activate["result"]["status"] == "active"
    assert activate["result"]["configured"] is True

    refresh = _rpc_call(server, "refresh_license_status", {})
    assert refresh["result"]["message"] == "HEARTBEAT_OK"
    assert refresh["result"]["can_start_jobs"] is True

    started = _rpc_call(
        server,
        "start_job",
        {
            "job_id": "job-e2e-1",
            "module": "graduation",
            "excel_path": "C:\\data\\m3.xlsx",
            "options": {"dry_run": True},
        },
    )
    assert started["result"] == {"accepted": True, "job_id": "job-e2e-1"}

    _wait_until(lambda: server.job_store.get_status("job-e2e-1")["status"] == "done")
    telemetry_store = CloudTelemetryStore(settings.sqlite_path)
    _wait_until(
        lambda: "job_completed" in [row["payload"]["event"] for row in telemetry_store.list_events()]
    )

    payloads = [row["payload"]["event"] for row in telemetry_store.list_events()]
    assert "app_started" in payloads
    assert "license_checked" in payloads
    assert "job_completed" in payloads


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

    server = RpcServer(emit_notification=notifications.append)
    monkeypatch.setattr(
        server.job_manager,
        "start_job",
        lambda *, job_id, module_name, excel_path, options: started_jobs.append(
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
    assert second_start["result"] == {"accepted": True, "job_id": "job-browser"}
    assert started_jobs == [
        {
            "job_id": "job-browser",
            "module": "graduation",
            "excel_path": "C:\\data\\m3.xlsx",
            "options": {"dry_run": True},
        }
    ]


def test_session_expiry_login_resume_workflow(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(sidecar_config, "default_data_dir", lambda: tmp_path)
    notifications: list[dict[str, Any]] = []

    monkeypatch.setattr("dmc_sidecar.modules.get_module", lambda module_name: _ResumeAfterAuthModule())
    monkeypatch.setattr("dmc_sidecar.rpc.get_browser_runtime_status", lambda: _ready_browser_status(tmp_path))

    first_server = RpcServer(emit_notification=notifications.append)
    started = _rpc_call(
        first_server,
        "start_job",
        {
            "job_id": "job-auth-1",
            "module": "graduation",
            "excel_path": "C:\\data\\m3.xlsx",
            "options": {"dry_run": True},
        },
    )
    assert started["result"]["accepted"] is True

    _wait_until(lambda: first_server.job_store.get_status("job-auth-1")["status"] == "paused")
    paused_status = first_server.job_store.get_status("job-auth-1")
    assert paused_status is not None
    assert paused_status["status"] == "paused"
    assert any(event.get("type") == "needs_auth" for event in notifications)

    reopened_server = RpcServer(emit_notification=notifications.append)
    resumed = _rpc_call(reopened_server, "resume_existing_job", {"job_id": "job-auth-1"})
    assert resumed["result"]["accepted"] is True

    _wait_until(lambda: reopened_server.job_store.get_status("job-auth-1")["status"] == "done")
    done_status = reopened_server.job_store.get_status("job-auth-1")
    assert done_status is not None
    assert done_status["needs_auth"] is False
    assert done_status["status"] == "done"


def test_invalid_signed_config_falls_back_to_cached_workflow(monkeypatch, tmp_path: Path) -> None:
    bundled_root = tmp_path / "bundled"
    configs_root = tmp_path / "configs"
    keyring_path = tmp_path / "keys.json"
    bundled_path = bundled_root / "graduation" / "v1.json"
    bundled_path.parent.mkdir(parents=True, exist_ok=True)
    configs_root.mkdir(parents=True, exist_ok=True)

    bundled_path.write_text(
        json.dumps({"version": "1.0.0", "status_code_map": {"เดิม": "201"}}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    keyring_path.write_text(
        json.dumps(
            {
                "keys": [
                    {
                        "key_id": "test-key",
                        "algorithm": "ed25519",
                        "public_key_base64": base64.b64encode(public_key).decode("ascii"),
                    }
                ]
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    cached_config = {"status_code_map": {"เดิม": "201", "อื่น": "207"}}
    cached_payload = json.dumps(
        {"version": "1.0.1", "config": cached_config},
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    cached_signature = base64.b64encode(private_key.sign(cached_payload)).decode("ascii")
    (configs_root / "graduation.json").write_text(
        json.dumps(
            {
                "version": "1.0.1",
                "config": cached_config,
                "signature": f"ed25519:test-key:{cached_signature}",
                "verified_at": "2026-04-23T00:00:00Z",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr("dmc_sidecar.module_config.module_configs_root", lambda: bundled_root)
    monkeypatch.setattr("dmc_sidecar.module_config.configs_dir", lambda: configs_root)
    monkeypatch.setattr("dmc_sidecar.module_config.config_signing_keys_path", lambda: keyring_path)
    monkeypatch.setattr("dmc_sidecar.module_config.secure_cloud_base_url", lambda: "https://cloud.test")

    invalid_cloud_payload = {
        "version": "2.0.0",
        "config": {"status_code_map": {"ปลอม": "999"}},
        "signature": "ed25519:test-key:invalid-signature",
    }

    monkeypatch.setattr(
        "dmc_sidecar.module_config.urlopen",
        lambda request, timeout=10: _UrlopenResponse(  # noqa: ARG005
            status=200,
            headers={"Content-Type": "application/json"},
            body=json.dumps(invalid_cloud_payload).encode("utf-8"),
        ),
    )

    baseline_state = load_effective_config("graduation")
    synced_state = sync_module_config("graduation")
    reloaded_state = load_effective_config("graduation")

    assert baseline_state.source == "cached"
    assert baseline_state.version == "1.0.1"
    assert synced_state.source == "cached"
    assert synced_state.updated is False
    assert synced_state.last_error == "CONFIG_SIGNATURE_INVALID"
    assert reloaded_state.source == "cached"
    assert reloaded_state.version == "1.0.1"
    assert reloaded_state.config["status_code_map"]["อื่น"] == "207"


def test_backup_restore_reopen_workflow(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(sidecar_config, "default_data_dir", lambda: tmp_path)
    store = LicenseStore()
    store.save_activation(
        LicenseRecord(
            license_key="DMC-BACKUP-0001",
            status="active",
            device_id="device-backup-1",
            license_tier="trial",
            school_size_tier="le_500",
            billing_interval=None,
            student_count_total=120,
            modules_enabled=["graduation"],
            max_devices=3,
            activated_at="2026-04-22T00:00:00Z",
            expires_at="2026-05-22T00:00:00Z",
            last_checked_at="2026-04-22T00:00:00Z",
            offline_grace_until="2026-04-29T00:00:00Z",
        )
    )

    server = RpcServer(emit_notification=lambda payload: None)
    backup_path = tmp_path / "e2e-backup.zip"
    backup = _rpc_call(server, "create_backup", {"path": str(backup_path)})
    assert Path(backup["result"]["backup_path"]).exists()

    store.update_heartbeat(
        status="suspended",
        license_tier="trial",
        school_size_tier="le_500",
        billing_interval=None,
        student_count_total=120,
        modules_enabled=["graduation"],
        max_devices=3,
        expires_at="2026-05-22T00:00:00Z",
        last_checked_at="2026-04-23T00:00:00Z",
        offline_grace_until="2026-04-23T01:00:00Z",
    )
    mutated_status = _rpc_call(server, "get_license_status", {})
    assert mutated_status["result"]["status"] == "suspended"

    restored = _rpc_call(server, "restore_backup", {"path": str(backup_path)})
    assert restored["result"]["restored_from"] == str(backup_path)
    assert Path(restored["result"]["safety_backup_path"]).exists()

    reopened_server = RpcServer(emit_notification=lambda payload: None)
    restored_status = _rpc_call(reopened_server, "get_license_status", {})
    assert restored_status["result"]["status"] == "active"
    assert restored_status["result"]["license_tier"] == "trial"
