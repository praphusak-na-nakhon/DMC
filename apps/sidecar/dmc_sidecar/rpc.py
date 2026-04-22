from __future__ import annotations

import re
import sys
import threading
from pathlib import Path
from typing import Any, Callable

from pydantic import ValidationError

from . import __version__
from .job_store import JobStore
from .license_client import activate_license, build_license_status_snapshot, refresh_license_status
from .license_store import LicenseStore
from .module_config import load_effective_config, sync_module_config
from .modules import get_module
from .runtime import JobManager, build_event_notification
from .schemas import (
    ActivateLicenseRequest,
    JobIdRequest,
    ModuleConfigRequest,
    ModuleConfigStatus,
    PingResponse,
    RpcErrorData,
    RpcErrorResponse,
    RpcRequest,
    RpcSuccessResponse,
    StartJobRequest,
    ValidateExcelRequest,
)
from .telemetry import TelemetryClient


class RpcServer:
    def __init__(self, emit_notification: Callable[[dict[str, Any]], None]) -> None:
        self.job_store = JobStore()
        self.license_store = LicenseStore()
        self.telemetry = TelemetryClient(license_store=self.license_store)
        self.job_manager = JobManager(
            job_store=self.job_store,
            license_store=self.license_store,
            telemetry=self.telemetry,
            emit_notification=emit_notification,
        )
        self.telemetry.record_app_started(app_version=__version__, platform=sys.platform)

    def handle_text(self, raw_text: str) -> str:
        try:
            request = RpcRequest.model_validate_json(raw_text)
            response = self.dispatch(request)
        except ValidationError as exc:
            response = RpcErrorResponse(
                id=None,
                error=RpcErrorData(
                    code="RPC_INVALID_REQUEST",
                    message="Request payload does not match the JSON-RPC schema.",
                    details={"errors": exc.errors()},
                ),
            )
        return response.model_dump_json()

    def dispatch(self, request: RpcRequest) -> RpcSuccessResponse | RpcErrorResponse:
        try:
            if request.method == "ping":
                result = PingResponse(sidecar_version=__version__).model_dump()
                return RpcSuccessResponse(id=request.id, result=result)

            if request.method == "validate_excel":
                params = ValidateExcelRequest.model_validate(request.params)
                module = get_module(params.module)
                result = module.validate_excel(Path(params.path)).model_dump()
                return RpcSuccessResponse(id=request.id, result=result)

            if request.method == "get_module_config_status":
                params = ModuleConfigRequest.model_validate(request.params)
                state = load_effective_config(params.module)
                result = ModuleConfigStatus(
                    module=params.module,
                    version=state.version,
                    source=state.source,
                    signature_verified=state.signature_verified,
                    config_path=str(state.config_path),
                    checked_at=state.checked_at,
                    updated=state.updated,
                    last_error=state.last_error,
                ).model_dump()
                return RpcSuccessResponse(id=request.id, result=result)

            if request.method == "get_license_status":
                result = build_license_status_snapshot(self.license_store.get_license()).model_dump()
                return RpcSuccessResponse(id=request.id, result=result)

            if request.method == "activate_license":
                params = ActivateLicenseRequest.model_validate(request.params)
                snapshot = activate_license(
                    self.license_store,
                    license_key=params.license_key,
                    device_name=params.device_name,
                    app_version=params.app_version,
                )
                self.telemetry.record_license_checked(
                    result=snapshot.message or snapshot.status,
                    offline_mode=snapshot.offline_mode,
                )
                return RpcSuccessResponse(id=request.id, result=snapshot.model_dump())

            if request.method == "refresh_license_status":
                snapshot = refresh_license_status(self.license_store)
                self.telemetry.record_license_checked(
                    result=snapshot.message or snapshot.status,
                    offline_mode=snapshot.offline_mode,
                )
                result = snapshot.model_dump()
                return RpcSuccessResponse(id=request.id, result=result)

            if request.method == "sync_module_config":
                params = ModuleConfigRequest.model_validate(request.params)
                previous_state = load_effective_config(params.module)
                state = sync_module_config(params.module)
                if state.updated:
                    self.telemetry.record_config_updated(
                        module=params.module,
                        from_version=previous_state.version,
                        to_version=state.version,
                    )
                result = ModuleConfigStatus(
                    module=params.module,
                    version=state.version,
                    source=state.source,
                    signature_verified=state.signature_verified,
                    config_path=str(state.config_path),
                    checked_at=state.checked_at,
                    updated=state.updated,
                    last_error=state.last_error,
                ).model_dump()
                return RpcSuccessResponse(id=request.id, result=result)

            if request.method == "start_job":
                params = StartJobRequest.model_validate(request.params)
                self.job_store.create_pending_job(
                    job_id=params.job_id,
                    module=params.module,
                    source_file=params.excel_path,
                )
                self.job_manager.start_job(
                    job_id=params.job_id,
                    module_name=params.module,
                    excel_path=Path(params.excel_path),
                    options=params.options,
                )
                return RpcSuccessResponse(
                    id=request.id,
                    result={"accepted": True, "job_id": params.job_id},
                )

            if request.method == "get_job_status":
                params = JobIdRequest.model_validate(request.params)
                job_id = params.job_id.strip()
                status = self.job_manager.get_runtime_status(job_id) or self.job_store.get_status(job_id)
                if status is None:
                    return self._error(
                        request.id,
                        code="JOB_NOT_FOUND",
                        message="Job not found.",
                    )
                return RpcSuccessResponse(id=request.id, result=status)

            if request.method == "pause_job":
                return self._set_job_status(request.id, request.params, "paused")

            if request.method == "resume_job":
                return self._set_job_status(request.id, request.params, "running")

            if request.method == "resume_existing_job":
                return self._resume_existing_job(request.id, request.params)

            if request.method == "cancel_job":
                return self._set_job_status(request.id, request.params, "cancelled")

            if request.method == "list_jobs":
                limit = int(request.params.get("limit", 20))
                return RpcSuccessResponse(id=request.id, result={"items": self.job_store.list_jobs(limit=limit)})

            return self._error(
                request.id,
                code="RPC_METHOD_NOT_FOUND",
                message=f"Unsupported method: {request.method}",
            )
        except RuntimeError as exc:
            error_code = self._safe_runtime_error_code(exc)
            return self._error(
                request.id,
                code=error_code,
                message=self._runtime_error_message(error_code),
            )
        except NotImplementedError as exc:
            return self._error(
                request.id,
                code="METHOD_NOT_IMPLEMENTED",
                message="Requested operation is not implemented.",
            )
        except Exception as exc:  # pragma: no cover - defensive boundary
            print(f"[sidecar] unexpected rpc error: {exc!r}", file=sys.stderr)
            return self._error(
                request.id,
                code="UNEXPECTED_ERROR",
                message="Unexpected internal error.",
            )

    def _set_job_status(
        self,
        request_id: str | int | None,
        params: dict[str, Any],
        status: str,
    ) -> RpcSuccessResponse | RpcErrorResponse:
        job_id = str(params.get("job_id", "")).strip()
        snapshot = self.job_manager.get_runtime_status(job_id) or self.job_store.get_status(job_id)
        if snapshot is None:
            return self._error(request_id, code="JOB_NOT_FOUND", message="Job not found.")

        if status == "paused":
            self.job_manager.pause_job(job_id)
        elif status == "running":
            self.job_manager.resume_job(job_id)
        elif status == "cancelled":
            self.job_manager.cancel_job(job_id)

        return RpcSuccessResponse(id=request_id, result={"job_id": job_id, "status": status})

    def _resume_existing_job(
        self,
        request_id: str | int | None,
        params: dict[str, Any],
    ) -> RpcSuccessResponse | RpcErrorResponse:
        payload = JobIdRequest.model_validate(params)
        job_id = payload.job_id.strip()

        runtime_status = self.job_manager.get_runtime_status(job_id)
        if runtime_status is not None:
            return RpcSuccessResponse(
                id=request_id,
                result={"accepted": True, "job_id": job_id, "status": runtime_status["status"]},
            )

        record = self.job_store.get_job_record(job_id)
        checkpoint = self.job_store.load_checkpoint(job_id)
        if record is None or checkpoint is None:
            return self._error(
                request_id,
                code="JOB_NOT_FOUND",
                message="Job not found.",
            )

        if record["status"] in {"done", "cancelled"}:
            return self._error(
                request_id,
                code="JOB_NOT_RESUMABLE",
                message=f"Job status '{record['status']}' cannot be resumed.",
            )

        self.job_manager.start_job(
            job_id=job_id,
            module_name=record["module"],
            excel_path=Path(record["source_file"]),
            options=checkpoint.options,
        )
        return RpcSuccessResponse(
            id=request_id,
            result={"accepted": True, "job_id": job_id, "status": "running"},
        )

    def _error(
        self,
        request_id: str | int | None,
        *,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> RpcErrorResponse:
        return RpcErrorResponse(
            id=request_id,
            error=RpcErrorData(
                code=code,
                message=message,
                details=details or {},
            ),
        )

    def _safe_runtime_error_code(self, exc: RuntimeError) -> str:
        raw = str(exc).strip()
        if re.fullmatch(r"[A-Z][A-Z0-9_]*", raw):
            return raw
        return "RUNTIME_ERROR"

    def _runtime_error_message(self, code: str) -> str:
        if code == "RUNTIME_ERROR":
            return "Operation failed."
        return code


def run_stdio_server() -> int:
    write_lock = threading.Lock()

    def emit_notification(payload: dict[str, Any]) -> None:
        with write_lock:
            sys.stdout.write(build_event_notification(payload) + "\n")
            sys.stdout.flush()

    server = RpcServer(emit_notification=emit_notification)
    while True:
        line = sys.stdin.readline()
        if line == "":
            break
        raw = line.strip()
        if not raw:
            continue
        response_text = server.handle_text(raw)
        with write_lock:
            sys.stdout.write(response_text + "\n")
            sys.stdout.flush()
    return 0
