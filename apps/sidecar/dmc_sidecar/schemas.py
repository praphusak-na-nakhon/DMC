from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class RpcErrorData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class RpcRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    jsonrpc: Literal["2.0"]
    id: str | int | None
    method: str
    params: dict[str, Any] = Field(default_factory=dict)


class RpcSuccessResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    jsonrpc: Literal["2.0"] = "2.0"
    id: str | int | None
    result: dict[str, Any]


class RpcErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    jsonrpc: Literal["2.0"] = "2.0"
    id: str | int | None
    error: RpcErrorData


class PingResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: Literal["pong"] = "pong"
    sidecar_version: str


class ValidateExcelRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    module: Literal["graduation"]


class ModuleConfigRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    module: Literal["graduation"]


class ActivateLicenseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    license_key: str
    device_name: str
    app_version: str


class SignInRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str
    password: str
    device_name: str
    app_version: str


class WalletSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: str
    balance: int
    reserved: int
    available: int


class AccountSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    signed_in: bool
    user_id: str | None
    email: str | None
    display_name: str | None
    status: str
    token_expires_at: str | None
    last_checked_at: str | None
    wallet: WalletSnapshot | None
    can_start_credit_jobs: bool
    needs_attention: bool
    message: str | None
    last_error: str | None


class ModuleCatalogItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    enabled: bool
    requires_credits: bool
    pricing_mode: Literal["per_billable_record"]
    credit_per_unit: int
    production_dry_run_enabled: bool


class ModuleCatalogResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    modules: list[ModuleCatalogItem]


class CreditReservationSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reservation_id: str
    job_id: str
    module: str
    status: str
    units_reserved: int
    units_captured: int
    units_released: int
    wallet: WalletSnapshot


class ValidateFormPdfRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    module: Literal["formConverter"] = "formConverter"
    template_type: str = "student_history_v1"


class FormPdfValidationWarning(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message_th: str


class ValidateFormPdfResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    module: Literal["formConverter"]
    path: str
    file_name: str
    template_type: str
    page_count: int
    estimated_records: int
    credit_estimate: int
    supported_template: bool
    requires_ai_consent: bool
    warnings: list[FormPdfValidationWarning]


class FormConversionField(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field_name: str
    label_th: str
    value: str
    confidence: float = Field(ge=0, le=1)
    status: Literal["ready", "needs_review", "invalid"]
    alternatives: list[str] = Field(default_factory=list)
    edited: bool = False


class FormConversionRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    record_id: str
    page_number: int = Field(ge=1)
    status: Literal["ready", "needs_review", "invalid"]
    fields: list[FormConversionField]


class FormConversionSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    records_total: int
    ready_records: int
    needs_review_records: int
    invalid_records: int
    exported_records: int


class StartFormConversionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str
    module: Literal["formConverter"] = "formConverter"
    pdf_path: str
    template_type: str = "student_history_v1"
    school_year: str | None = None
    confirmed_ai_processing: bool


class StartFormConversionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    accepted: bool
    job_id: str
    credit_reservation_id: str | None
    credits_reserved: int


class FormConversionStatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str
    module: Literal["formConverter"]
    status: Literal["pending", "processing", "needs_review", "reviewed", "done", "failed"]
    pdf_path: str
    template_type: str
    ocr_provider: str | None = None
    school_year: str | None
    page_count: int
    processed: int
    total: int
    records: list[FormConversionRecord]
    summary: FormConversionSummary
    excel_path: str | None
    report_path: str | None
    review_report_path: str | None
    credit_reservation_id: str | None
    credits_reserved: int
    credits_captured: int
    credits_refunded: int
    credit_status: str | None
    last_error: str | None
    review_confirmed: bool


class SaveFormReviewEditsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str
    records: list[FormConversionRecord]


class ExportFormExcelRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str


class ExportFormExcelResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str
    excel_path: str
    report_path: str
    review_report_path: str
    exported_records: int
    credit_reservation_id: str | None
    credits_captured: int
    credits_refunded: int


class ExportStudentBasicInfoFormRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    excel_path: str
    template_path: str | None = None


class StudentBasicInfoClassSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    level: str
    room: str
    sheet_name: str
    students: int


class ExportStudentBasicInfoFormResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    module: Literal["studentBasicInfo"]
    source_path: str
    output_path: str
    school_name: str | None
    school_year: str | None
    term: str | None
    rows_total: int
    students_exported: int
    classes_exported: int
    classes: list[StudentBasicInfoClassSummary]


class ValidationWarning(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    row_index: int
    message_th: str


class PreviewRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order: int
    level_label: str
    room: int | None
    student_no: str
    first_name: str
    last_name: str
    status_text: str
    status_code: str


class ValidateExcelResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    module: Literal["graduation"]
    detected_level: str
    rows_total: int
    rows_accepted: int
    warnings: list[ValidationWarning]
    preview: list[PreviewRow]


class StartJobRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str
    module: Literal["graduation"]
    excel_path: str
    options: dict[str, Any] = Field(default_factory=dict)


class JobIdRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str


class ArchiveJobsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    keep_latest: int = Field(default=20, ge=1, le=1000)


class FilePathRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str


class LicenseRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    license_key: str
    status: str = "active"
    device_id: str
    license_tier: str
    school_size_tier: str
    billing_interval: str | None
    student_count_total: int
    modules_enabled: list[str] = Field(default_factory=list)
    max_devices: int
    activated_at: str
    expires_at: str
    last_checked_at: str
    offline_grace_until: str


class LicenseStatusSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    configured: bool
    status: str
    license_tier: str | None
    school_size_tier: str | None
    billing_interval: str | None
    student_count_total: int | None
    max_devices: int | None
    modules_enabled: list[str]
    expires_at: str | None
    last_checked_at: str | None
    offline_grace_until: str | None
    offline_mode: bool
    within_offline_grace: bool
    can_start_jobs: bool
    needs_attention: bool
    message: str | None
    last_error: str | None


class ModuleConfigStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    module: Literal["graduation"]
    version: str
    source: Literal["bundled", "cached", "cloud"]
    signature_verified: bool
    config_path: str
    checked_at: str
    updated: bool
    last_error: str | None


class BrowserRuntimePackage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    install_location: str
    download_url: str
    download_bytes: int | None


class BrowserRuntimeStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: Literal["ready", "missing", "installing", "failed"]
    installed: bool
    install_dir: str
    executable_path: str | None
    bootstrap_supported: bool
    bootstrap_performed: bool
    estimated_download_bytes: int | None
    required_components: list[BrowserRuntimePackage] = Field(default_factory=list)
    message: str | None
    guidance: str | None
    last_error: str | None
    log_tail: list[str] = Field(default_factory=list)
