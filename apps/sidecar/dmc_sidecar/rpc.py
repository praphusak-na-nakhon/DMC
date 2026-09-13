from __future__ import annotations

import sys
import threading
from pathlib import Path
from typing import Any, Callable

from pydantic import ValidationError

from . import __version__
from .ai.base import AiSettingsResponse, OcrDocumentRequest, SecretStore
from .ai.credentials import WindowsCredentialStore
from .ai.registry import ProviderRegistry, build_provider_registry
from .backup import create_backup_archive, restore_backup_archive
from .browser_runtime import bootstrap_browser_runtime, get_browser_runtime_status
from .config import default_data_dir, sqlite_path
from .db import get_database_metadata
from .errors import DomainError
from .current_students import (
    ExportDmcFormJsonRequest,
    ExportCurrentStudentsBlankFormRequest,
    ExportCurrentStudentsImportExcelRequest,
    PreviewDmcFormJsonRequest,
    ReconcileCurrentStudentsRequest,
    ValidateCurrentStudentsImportFormRequest,
    export_dmc_form_json,
    export_current_students_blank_form,
    export_current_students_import_excel,
    preview_dmc_form_json,
    reconcile_current_students,
    validate_current_students_import_form,
)
from .job_store import JobStore
from .modules import get_module
from .runtime import JobManager, build_event_notification, utc_now
from .schemas import (
    AiProviderRequest,
    ArchiveJobsRequest,
    ExportStudentBasicInfoFormRequest,
    FilePathRequest,
    JobIdRequest,
    PingResponse,
    RpcErrorData,
    RpcErrorResponse,
    RpcRequest,
    RpcSuccessResponse,
    SaveAiApiKeyRequest,
    StartJobRequest,
    ValidateExcelRequest,
)
from .student_basic_info import export_student_basic_info_form


_AI_RPC_METHODS = {"get_ai_settings", "save_ai_api_key", "test_ai_connection", "delete_ai_api_key", "ocr_document"}


def _safe_validation_errors(exc: ValidationError) -> list[dict[str, str]]:
    """Return validation metadata without client-controlled inputs or contexts."""
    return [
        {
            "type": str(error.get("type", "validation_error")),
            "message": str(error.get("msg", "Invalid request.")),
        }
        for error in exc.errors()
    ]


class RpcServer:
    def __init__(
        self,
        emit_notification: Callable[[dict[str, Any]], None],
        *,
        secret_store: SecretStore | None = None,
        provider_registry: ProviderRegistry | None = None,
    ) -> None:
        self.emit_notification = emit_notification
        self.secret_store = secret_store if secret_store is not None else WindowsCredentialStore()
        self.provider_registry = provider_registry if provider_registry is not None else build_provider_registry(self.secret_store)
        self.job_store = JobStore()
        self.job_manager = JobManager(
            job_store=self.job_store,
            emit_notification=emit_notification,
        )

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
                    details={"errors": _safe_validation_errors(exc)},
                ),
            )
        return response.model_dump_json(ensure_ascii=True)

    def dispatch(self, request: RpcRequest) -> RpcSuccessResponse | RpcErrorResponse:
        try:
            if request.method == "ping":
                result = PingResponse(sidecar_version=__version__).model_dump()
                return RpcSuccessResponse(id=request.id, result=result)

            if request.method == "get_ai_settings":
                ai_params = AiProviderRequest.model_validate(request.params)
                result = AiSettingsResponse(
                    provider=ai_params.provider,
                    configured=self.secret_store.get(ai_params.provider) is not None,
                ).model_dump()
                return RpcSuccessResponse(id=request.id, result=result)

            if request.method == "save_ai_api_key":
                ai_params = SaveAiApiKeyRequest.model_validate(request.params)
                self.secret_store.set(ai_params.provider, ai_params.api_key.get_secret_value())
                result = AiSettingsResponse(provider=ai_params.provider, configured=True).model_dump()
                return RpcSuccessResponse(id=request.id, result=result)

            if request.method == "test_ai_connection":
                ai_params = AiProviderRequest.model_validate(request.params)
                result = self.provider_registry.get(ai_params.provider).test_connection().model_dump()
                return RpcSuccessResponse(id=request.id, result=result)

            if request.method == "delete_ai_api_key":
                ai_params = AiProviderRequest.model_validate(request.params)
                self.secret_store.delete(ai_params.provider)
                result = AiSettingsResponse(provider=ai_params.provider, configured=False).model_dump()
                return RpcSuccessResponse(id=request.id, result=result)

            if request.method == "ocr_document":
                ocr_params = OcrDocumentRequest.model_validate(request.params)
                if not self.secret_store.get(ocr_params.provider):
                    raise DomainError("AI_API_KEY_REQUIRED")
                result = self.provider_registry.get(ocr_params.provider).ocr_document(ocr_params).model_dump()
                return RpcSuccessResponse(id=request.id, result=result)

            if request.method == "validate_excel":
                validate_params = ValidateExcelRequest.model_validate(request.params)
                module = get_module(validate_params.module)
                try:
                    result = module.validate_excel(Path(validate_params.path)).model_dump()
                except ImportError as exc:
                    if "openpyxl" in str(exc).lower():
                        raise DomainError(
                            "EXCEL_READER_MISSING",
                            "Excel reader dependency is missing. Install openpyxl and rebuild the sidecar.",
                        ) from exc
                    raise
                return RpcSuccessResponse(id=request.id, result=result)

            if request.method == "validate_current_student_sources":
                current_students_params = ReconcileCurrentStudentsRequest.model_validate(request.params)
                result = reconcile_current_students(current_students_params).model_dump()
                return RpcSuccessResponse(id=request.id, result=result)

            if request.method == "export_current_student_import_excel":
                current_students_export_params = ExportCurrentStudentsImportExcelRequest.model_validate(request.params)
                result = export_current_students_import_excel(current_students_export_params).model_dump()
                return RpcSuccessResponse(id=request.id, result=result)

            if request.method == "preview_dmc_form_json":
                form_json_preview_params = PreviewDmcFormJsonRequest.model_validate(request.params)
                result = preview_dmc_form_json(form_json_preview_params).model_dump()
                return RpcSuccessResponse(id=request.id, result=result)

            if request.method == "export_dmc_form_json":
                form_json_export_params = ExportDmcFormJsonRequest.model_validate(request.params)
                result = export_dmc_form_json(form_json_export_params).model_dump()
                return RpcSuccessResponse(id=request.id, result=result)

            if request.method == "export_current_student_blank_form":
                current_students_blank_params = ExportCurrentStudentsBlankFormRequest.model_validate(request.params)
                result = export_current_students_blank_form(current_students_blank_params).model_dump()
                return RpcSuccessResponse(id=request.id, result=result)

            if request.method == "validate_current_student_import_form":
                current_students_import_params = ValidateCurrentStudentsImportFormRequest.model_validate(request.params)
                result = validate_current_students_import_form(current_students_import_params).model_dump()
                return RpcSuccessResponse(id=request.id, result=result)

            if request.method == "get_browser_runtime_status":
                result = get_browser_runtime_status().model_dump()
                return RpcSuccessResponse(id=request.id, result=result)

            if request.method == "bootstrap_browser_runtime":
                result = bootstrap_browser_runtime(emit_progress=self.emit_notification).model_dump()
                return RpcSuccessResponse(id=request.id, result=result)

            if request.method == "get_database_status":
                return RpcSuccessResponse(id=request.id, result=get_database_metadata(sqlite_path()))

            if request.method == "create_backup":
                backup_params = FilePathRequest.model_validate(request.params) if request.params else None
                backup_path = (
                    create_backup_archive(_backup_rpc_path(backup_params.path, must_exist=False))
                    if backup_params and backup_params.path
                    else create_backup_archive()
                )
                return RpcSuccessResponse(id=request.id, result={"backup_path": str(backup_path)})

            if request.method == "restore_backup":
                restore_params = FilePathRequest.model_validate(request.params)
                if self.job_manager.runtime_statuses():
                    return self._error(
                        request.id,
                        code="RESTORE_REQUIRES_IDLE",
                        message="Stop active jobs before restoring a backup.",
                    )
                result = restore_backup_archive(_backup_rpc_path(restore_params.path, must_exist=True))
                return RpcSuccessResponse(id=request.id, result=result)

            if request.method == "start_job":
                start_params = StartJobRequest.model_validate(request.params)
                browser_runtime = get_browser_runtime_status()
                if not browser_runtime.installed:
                    return self._error(
                        request.id,
                        code="PLAYWRIGHT_BROWSER_MISSING",
                        message="Chromium browser runtime is not installed.",
                        details=browser_runtime.model_dump(),
                    )
                self.job_store.create_pending_job(
                    job_id=start_params.job_id,
                    module=start_params.module,
                    source_file=start_params.excel_path,
                )
                try:
                    self.job_manager.start_job(
                        job_id=start_params.job_id,
                        module_name=start_params.module,
                        excel_path=Path(start_params.excel_path),
                        options=start_params.options,
                    )
                except Exception:
                    self.job_store.mark_start_failed(start_params.job_id, finished_at=utc_now())
                    raise
                return RpcSuccessResponse(
                    id=request.id,
                    result={"accepted": True, "job_id": start_params.job_id},
                )

            if request.method == "export_student_basic_info_form":
                student_form_params = ExportStudentBasicInfoFormRequest.model_validate(request.params)
                result = export_student_basic_info_form(
                    excel_path=Path(student_form_params.excel_path),
                    template_path=(
                        Path(student_form_params.template_path)
                        if student_form_params.template_path is not None
                        else None
                    ),
                ).model_dump()
                return RpcSuccessResponse(id=request.id, result=result)

            if request.method == "get_job_status":
                job_params = JobIdRequest.model_validate(request.params)
                job_id = job_params.job_id.strip()
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
                list_params = request.params if isinstance(request.params, dict) else {}
                limit = int(list_params.get("limit", 20))
                return RpcSuccessResponse(id=request.id, result={"items": self.job_store.list_jobs(limit=limit)})

            if request.method == "archive_old_jobs":
                if self.job_manager.runtime_statuses():
                    return self._error(
                        request.id,
                        code="ARCHIVE_REQUIRES_IDLE",
                        message="Stop active jobs before archiving job history.",
                    )
                archive_params = ArchiveJobsRequest.model_validate(request.params)
                result = self.job_store.archive_old_jobs(keep_latest=archive_params.keep_latest)
                return RpcSuccessResponse(id=request.id, result=result)

            return self._error(
                request.id,
                code="RPC_METHOD_NOT_FOUND",
                message="Unsupported method.",
            )
        except ValidationError as exc:
            return self._error(
                request.id,
                code="RPC_INVALID_REQUEST",
                message="Request params do not match the method schema.",
                details={"errors": _safe_validation_errors(exc)},
            )
        except DomainError as exc:
            return self._error(
                request.id,
                code=exc.code,
                message=exc.user_message,
                details={} if request.method in _AI_RPC_METHODS else exc.details,
            )
        except RuntimeError:
            return self._error(
                request.id,
                code="RUNTIME_ERROR",
                message="Operation failed.",
            )
        except NotImplementedError:
            return self._error(
                request.id,
                code="METHOD_NOT_IMPLEMENTED",
                message="Requested operation is not implemented.",
            )
        except Exception as exc:  # pragma: no cover - defensive boundary
            print(f"[sidecar] unexpected rpc error: {exc.__class__.__name__}", file=sys.stderr)
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

        if record["status"] not in {"paused", "stopped_on_review"}:
            return self._error(
                request_id,
                code="JOB_NOT_RESUMABLE",
                message=f"Job status '{record['status']}' cannot be resumed.",
            )
        browser_runtime = get_browser_runtime_status()
        if not browser_runtime.installed:
            return self._error(
                request_id,
                code="PLAYWRIGHT_BROWSER_MISSING",
                message="Chromium browser runtime is not installed.",
                details=browser_runtime.model_dump(),
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


def run_stdio_server() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="strict")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")
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


def _backup_rpc_path(raw_path: str, *, must_exist: bool) -> Path:
    raw = raw_path.strip()
    if not raw:
        raise DomainError("BACKUP_PATH_INVALID", "Backup path is invalid.")
    candidate = Path(raw).expanduser()
    if candidate.is_absolute():
        resolved = candidate.resolve()
    else:
        root = default_data_dir().resolve()
        resolved = (root / candidate).resolve()
        try:
            resolved.relative_to(root)
        except ValueError as exc:
            raise DomainError("BACKUP_PATH_INVALID", "Backup path is invalid.") from exc

    if resolved.suffix.lower() != ".zip":
        raise DomainError("BACKUP_PATH_UNSUPPORTED_TYPE", "Backup path must be a .zip file.")
    if must_exist:
        if not resolved.exists():
            raise DomainError("BACKUP_NOT_FOUND", "Backup file was not found.")
        if not resolved.is_file():
            raise DomainError("BACKUP_PATH_INVALID", "Backup path is invalid.")
    elif resolved.exists() and resolved.is_dir():
        raise DomainError("BACKUP_PATH_INVALID", "Backup path is invalid.")
    return resolved
