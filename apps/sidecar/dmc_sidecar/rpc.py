from __future__ import annotations

import re
import sys
import threading
import traceback
import uuid
from pathlib import Path
from typing import Any, Callable

from pydantic import ValidationError

from .account_client import (
    build_account_snapshot,
    cached_module_catalog,
    capture_credits,
    get_module_catalog,
    refresh_wallet,
    release_credits,
    reserve_credits,
    sign_in,
    sign_out,
)
from .account_store import AccountSessionStore

from . import __version__
from .akson_ocr import (
    AKSON_OCR_CREDITS_PER_PAGE,
    AksonOcrDmcFormRequest,
    AksonOcrDmcFormResponse,
    ocr_dmc_form_with_akson,
    prepare_akson_ocr_request,
)
from .backup import create_backup_archive, restore_backup_archive
from .browser_runtime import bootstrap_browser_runtime, get_browser_runtime_status
from .checkpoint import JobCheckpoint
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
    load_dmc_transfer_in_import_records,
    preview_dmc_form_json,
    reconcile_current_students,
    validate_current_students_import_form,
)
from .job_store import JobStore
from .module_config import load_effective_config, sync_module_config
from .modules import get_module
from .p_sar_readiness import PsarReadinessService
from .runtime import JobManager, build_event_notification, utc_now
from .schemas import (
    AddPsarEvidenceRequest,
    ArchiveJobsRequest,
    ExportStudentBasicInfoFormRequest,
    FilePathRequest,
    GeneratePsarReportRequest,
    JobIdRequest,
    ModuleConfigRequest,
    ModuleConfigStatus,
    PingResponse,
    PsarReadinessRequest,
    RpcErrorData,
    RpcErrorResponse,
    RpcRequest,
    RpcSuccessResponse,
    SignInRequest,
    StartJobRequest,
    ValidateExcelRequest,
)
from .student_basic_info import export_student_basic_info_form
from .telemetry import TelemetryClient


class RpcServer:
    def __init__(self, emit_notification: Callable[[dict[str, Any]], None]) -> None:
        self.emit_notification = emit_notification
        self.job_store = JobStore()
        self.account_store = AccountSessionStore()
        self.telemetry = TelemetryClient(account_store=self.account_store)
        self.psar_readiness = PsarReadinessService()
        reaped_jobs = self._reap_interrupted_reservations()
        self.job_manager = JobManager(
            job_store=self.job_store,
            account_store=self.account_store,
            telemetry=self.telemetry,
            emit_notification=emit_notification,
        )
        if reaped_jobs:
            self._emit_background_notification(
                {
                    "type": "sidecar_stderr",
                    "message": f"marked {reaped_jobs} interrupted credit reservation job(s) as failed",
                }
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
        return response.model_dump_json(ensure_ascii=True)

    def dispatch(self, request: RpcRequest) -> RpcSuccessResponse | RpcErrorResponse:
        try:
            if request.method == "ping":
                result = PingResponse(sidecar_version=__version__).model_dump()
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

            if request.method == "ocr_dmc_form_with_akson":
                akson_ocr_params = AksonOcrDmcFormRequest.model_validate(request.params)
                result = self._ocr_dmc_form_with_akson(akson_ocr_params).model_dump()
                return RpcSuccessResponse(id=request.id, result=result)

            if request.method == "export_current_student_blank_form":
                current_students_blank_params = ExportCurrentStudentsBlankFormRequest.model_validate(request.params)
                result = export_current_students_blank_form(current_students_blank_params).model_dump()
                return RpcSuccessResponse(id=request.id, result=result)

            if request.method == "validate_current_student_import_form":
                current_students_import_params = ValidateCurrentStudentsImportFormRequest.model_validate(request.params)
                result = validate_current_students_import_form(current_students_import_params).model_dump()
                return RpcSuccessResponse(id=request.id, result=result)

            if request.method == "get_module_config_status":
                config_params = ModuleConfigRequest.model_validate(request.params)
                state = load_effective_config(config_params.module)
                result = ModuleConfigStatus(
                    module=config_params.module,
                    version=state.version,
                    source=state.source,
                    signature_verified=state.signature_verified,
                    config_path=str(state.config_path),
                    checked_at=state.checked_at,
                    updated=state.updated,
                    last_error=state.last_error,
                ).model_dump()
                return RpcSuccessResponse(id=request.id, result=result)

            if request.method == "sign_in":
                sign_in_params = SignInRequest.model_validate(request.params)
                result = sign_in(
                    self.account_store,
                    email=sign_in_params.email,
                    password=sign_in_params.password,
                    device_name=sign_in_params.device_name,
                    app_version=sign_in_params.app_version,
                ).model_dump()
                return RpcSuccessResponse(id=request.id, result=result)

            if request.method == "sign_out":
                result = sign_out(self.account_store).model_dump()
                return RpcSuccessResponse(id=request.id, result=result)

            if request.method == "get_account_status":
                result = build_account_snapshot(self.account_store).model_dump()
                return RpcSuccessResponse(id=request.id, result=result)

            if request.method == "refresh_wallet":
                result = refresh_wallet(self.account_store).model_dump()
                return RpcSuccessResponse(id=request.id, result=result)

            if request.method == "get_module_catalog":
                try:
                    result = get_module_catalog(self.account_store).model_dump()
                except DomainError:
                    result = cached_module_catalog(self.account_store).model_dump()
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

            if request.method == "sync_module_config":
                sync_params = ModuleConfigRequest.model_validate(request.params)
                previous_state = load_effective_config(sync_params.module)
                state = sync_module_config(sync_params.module)
                if state.updated:
                    self.telemetry.record_config_updated(
                        module=sync_params.module,
                        from_version=previous_state.version,
                        to_version=state.version,
                    )
                result = ModuleConfigStatus(
                    module=sync_params.module,
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
                start_params = StartJobRequest.model_validate(request.params)
                browser_runtime = get_browser_runtime_status()
                if not browser_runtime.installed:
                    return self._error(
                        request.id,
                        code="PLAYWRIGHT_BROWSER_MISSING",
                        message="Chromium browser runtime is not installed.",
                        details=browser_runtime.model_dump(),
                    )
                if not bool(start_params.options.get("dry_run", False)) and self.account_store.get_session() is None:
                    return self._error(
                        request.id,
                        code="SIGN_IN_REQUIRED",
                        message="Sign in before starting credit-backed jobs.",
                    )
                estimated_credits = start_params.options.get("estimated_credits")
                credits_reserved = estimated_credits if isinstance(estimated_credits, int) and estimated_credits > 0 else 0
                self.job_store.create_pending_job(
                    job_id=start_params.job_id,
                    module=start_params.module,
                    source_file=start_params.excel_path,
                    credits_reserved=credits_reserved,
                    credit_status="reserving" if not bool(start_params.options.get("dry_run", False)) else None,
                )
                threading.Thread(
                    target=self._prepare_and_start_job,
                    name=f"dmc-start-{start_params.job_id}",
                    args=(start_params,),
                    daemon=True,
                ).start()
                return RpcSuccessResponse(
                    id=request.id,
                    result={
                        "accepted": True,
                        "job_id": start_params.job_id,
                        "credit_reservation_id": None,
                        "credits_reserved": credits_reserved,
                    },
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

            if request.method == "get_psar_readiness":
                psar_params = PsarReadinessRequest.model_validate(request.params)
                result = self.psar_readiness.get_readiness(psar_params.project_id).model_dump()
                return RpcSuccessResponse(id=request.id, result=result)

            if request.method == "add_psar_evidence":
                evidence_params = AddPsarEvidenceRequest.model_validate(request.params)
                result = self.psar_readiness.add_evidence(
                    project_id=evidence_params.project_id,
                    file_path=evidence_params.file_path,
                ).model_dump()
                return RpcSuccessResponse(id=request.id, result=result)

            if request.method == "generate_psar_report":
                report_params = GeneratePsarReportRequest.model_validate(request.params)
                result = self.psar_readiness.generate_report(report_params.project_id).model_dump()
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
                message=f"Unsupported method: {request.method}",
            )
        except DomainError as exc:
            return self._error(
                request.id,
                code=exc.code,
                message=exc.user_message,
                details=exc.details,
            )
        except RuntimeError as exc:
            error_code = self._safe_runtime_error_code(exc)
            return self._error(
                request.id,
                code=error_code,
                message=self._runtime_error_message(error_code),
            )
        except NotImplementedError:
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

    def _ocr_dmc_form_with_akson(self, request: AksonOcrDmcFormRequest) -> AksonOcrDmcFormResponse:
        prepared = prepare_akson_ocr_request(request)
        if prepared.cached_response is not None:
            return prepared.cached_response

        credits_required = prepared.pages_estimated * AKSON_OCR_CREDITS_PER_PAGE
        job_id = f"form-ocr-akson-{prepared.file_sha256[:16]}-{uuid.uuid4().hex[:8]}"
        reservation = reserve_credits(
            self.account_store,
            job_id=job_id,
            module="formConverter",
            units=credits_required,
            idempotency_key=f"{job_id}:reserve:{request.model}",
        )
        captured = False
        try:
            response = ocr_dmc_form_with_akson(request)
            capture_credits(
                self.account_store,
                reservation_id=reservation.reservation_id,
                units=credits_required,
                idempotency_key=f"{job_id}:capture:{request.model}",
            )
            captured = True
            return response.model_copy(
                update={
                    "pages_estimated": prepared.pages_estimated,
                    "credits_per_page": AKSON_OCR_CREDITS_PER_PAGE,
                    "credits_charged": credits_required,
                    "charged": True,
                    "credit_reservation_id": reservation.reservation_id,
                }
            )
        finally:
            if not captured:
                try:
                    release_credits(
                        self.account_store,
                        reservation_id=reservation.reservation_id,
                        units=credits_required,
                        idempotency_key=f"{job_id}:release:{request.model}",
                    )
                except DomainError:
                    pass

    def _estimate_credit_units(self, start_params: StartJobRequest) -> int:
        raw_units = start_params.options.get("estimated_credits")
        if isinstance(raw_units, int) and raw_units > 0:
            return raw_units
        if start_params.module == "currentStudents":
            try:
                records = load_dmc_transfer_in_import_records(Path(start_params.excel_path))
            except Exception as exc:
                raise DomainError("CREDIT_PREFLIGHT_FAILED", "Unable to estimate credits for this job.") from exc
            return max(len(records), 1)
        module = get_module(start_params.module)
        try:
            preview = module.validate_excel(Path(start_params.excel_path))
        except Exception as exc:
            raise DomainError("CREDIT_PREFLIGHT_FAILED", "Unable to estimate credits for this job.") from exc
        return max(int(preview.rows_accepted), 1)

    def _prepare_and_start_job(self, start_params: StartJobRequest) -> None:
        credit_reservation_id: str | None = None
        credits_reserved = 0
        try:
            if not bool(start_params.options.get("dry_run", False)):
                credits_reserved = self._estimate_credit_units(start_params)
                reservation = reserve_credits(
                    self.account_store,
                    job_id=start_params.job_id,
                    module=start_params.module,
                    units=credits_reserved,
                    idempotency_key=f"{start_params.job_id}:reserve",
                )
                credit_reservation_id = reservation.reservation_id
                self.job_store.update_credit_status(
                    start_params.job_id,
                    credit_reservation_id=credit_reservation_id,
                    credits_reserved=credits_reserved,
                    credit_status="reserved",
                )
                self._emit_background_notification(
                    {
                        "type": "sidecar_stderr",
                        "message": f"credits reserved for job {start_params.job_id}: {credits_reserved}",
                    }
                )

            self.job_manager.start_job(
                job_id=start_params.job_id,
                module_name=start_params.module,
                excel_path=Path(start_params.excel_path),
                options=start_params.options,
                credit_reservation_id=credit_reservation_id,
                credits_reserved=credits_reserved,
            )
        except Exception as exc:  # pragma: no cover - defensive background path
            print(f"[sidecar] start_job background error for {start_params.job_id}: {exc!r}", file=sys.stderr)
            print(traceback.format_exc(), file=sys.stderr)
            code = exc.code if isinstance(exc, DomainError) else exc.__class__.__name__.upper()
            self.job_store.mark_start_failed(start_params.job_id, code=code, finished_at=utc_now())
            self._emit_background_notification(
                {
                    "type": "error",
                    "job_id": start_params.job_id,
                    "code": code,
                    "message": exc.user_message if isinstance(exc, DomainError) else "Job failed before it started.",
                }
            )

    def _emit_background_notification(self, payload: dict[str, Any]) -> None:
        try:
            self.emit_notification(payload)
        except Exception as exc:  # pragma: no cover - defensive notification boundary
            print(f"[sidecar] failed to emit background event: {exc!r}", file=sys.stderr)

    def _reap_interrupted_reservations(self) -> int:
        jobs = self.job_store.list_reserving_jobs()
        for job in jobs:
            self._release_interrupted_reservation(job)
        return self.job_store.mark_reserving_jobs_failed([str(job["id"]) for job in jobs])

    def _release_interrupted_reservation(self, job: dict[str, Any]) -> None:
        credits_reserved = int(job.get("credits_reserved") or 0)
        if credits_reserved <= 0 or self.account_store.get_session() is None:
            return

        job_id = str(job["id"])
        reservation_id = job.get("credit_reservation_id")
        try:
            if not reservation_id:
                reservation = reserve_credits(
                    self.account_store,
                    job_id=job_id,
                    module=str(job["module"]),
                    units=credits_reserved,
                    idempotency_key=f"{job_id}:reserve",
                )
                reservation_id = reservation.reservation_id
            release_credits(
                self.account_store,
                reservation_id=str(reservation_id),
                units=credits_reserved,
                idempotency_key=f"{job_id}:reaper:release",
            )
        except DomainError as exc:
            print(f"[sidecar] failed to release interrupted reservation for {job_id}: {exc.code}", file=sys.stderr)
        except Exception as exc:  # pragma: no cover - defensive startup path
            print(f"[sidecar] unexpected interrupted reservation release error for {job_id}: {exc!r}", file=sys.stderr)

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

        if record["status"] != "paused":
            return self._error(
                request_id,
                code="JOB_NOT_RESUMABLE",
                message=f"Job status '{record['status']}' cannot be resumed.",
            )
        credit_reservation_id = record.get("credit_reservation_id")
        credits_reserved = int(record.get("credits_reserved") or 0)
        if credit_reservation_id and record.get("credit_status") == "finalized":
            resume_attempt_id = uuid.uuid4().hex
            credits_reserved = self._estimate_resume_credit_units(record, checkpoint)
            reservation = reserve_credits(
                self.account_store,
                job_id=f"{job_id}:resume:{resume_attempt_id}",
                module=record["module"],
                units=credits_reserved,
                idempotency_key=f"{job_id}:resume:{resume_attempt_id}:reserve",
            )
            credit_reservation_id = reservation.reservation_id
            self.job_store.update_credit_status(
                job_id,
                credit_reservation_id=credit_reservation_id,
                credits_reserved=credits_reserved,
                credits_captured=0,
                credits_refunded=0,
                credit_status="reserved",
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
            credit_reservation_id=credit_reservation_id,
            credits_reserved=credits_reserved,
        )
        return RpcSuccessResponse(
            id=request_id,
            result={"accepted": True, "job_id": job_id, "status": "running"},
        )

    def _estimate_resume_credit_units(self, record: dict[str, Any], checkpoint: JobCheckpoint) -> int:
        total = int(record.get("total_records") or 0)
        processed = max(int(record.get("processed") or 0), checkpoint.processed)
        if total > processed:
            return total - processed
        previous_reserved = int(record.get("credits_reserved") or 0)
        previous_captured = int(record.get("credits_captured") or 0)
        previous_refunded = int(record.get("credits_refunded") or 0)
        return max(previous_reserved - previous_captured - previous_refunded, 1)

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
