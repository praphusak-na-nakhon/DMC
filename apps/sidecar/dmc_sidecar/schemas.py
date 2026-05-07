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


EvidenceMappingStatus = Literal["accepted", "suggested", "rejected", "needs_review"]
ReadinessRequirementStatus = Literal["complete", "partial", "missing", "needs_review"]
ReadinessPriority = Literal["high", "medium", "low"]


class PsarReadinessRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: str = "default"


class AddPsarEvidenceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: str = "default"
    file_path: str


class GeneratePsarReportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: str = "default"


class PsarRequirement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requirement_id: str
    section_id: str
    section_title: str
    section_order: int
    title: str
    category: str
    required_evidence: list[str]
    optional_evidence: list[str] = Field(default_factory=list)
    weight: float = Field(gt=0)
    minimum_required_items: int = Field(ge=1)
    description: str


class PsarUploadedFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file_id: str
    file_name: str
    file_path: str
    file_type: str
    extracted_summary: str
    created_at: str
    updated_at: str


class PsarEvidenceMapping(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requirement_id: str
    evidence_type: str
    source_file_id: str
    source_file_name: str
    extracted_summary: str
    confidence_score: float = Field(ge=0, le=1)
    page_number: int | None = None
    location: str | None = None
    status: EvidenceMappingStatus
    created_at: str
    updated_at: str


class PsarReadinessRequirement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requirement_id: str
    requirement_title: str
    category: str
    description: str
    required_evidence: list[str]
    optional_evidence: list[str]
    weight: float
    minimum_required_items: int
    status: ReadinessRequirementStatus
    completion_score: float = Field(ge=0, le=1)
    missing_evidence: list[str]
    found_evidence: list[PsarEvidenceMapping]
    recommendation: str
    priority: ReadinessPriority


class PsarReadinessSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    section_id: str
    section_title: str
    completion_score: float = Field(ge=0, le=1)
    complete_count: int
    partial_count: int
    missing_count: int
    needs_review_count: int
    requirements: list[PsarReadinessRequirement]


class PsarMissingEvidenceRecommendation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_name: str
    requirement_id: str
    requirement_title: str
    section_id: str
    section_title: str
    why_needed: str
    priority: ReadinessPriority
    suggested_file_types: list[str]


class PsarReadinessResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: str
    overall_completion_score: float = Field(ge=0, le=1)
    warning_threshold: float = Field(ge=0, le=1)
    confidence_threshold: float = Field(ge=0, le=1)
    total_requirements: int
    complete_count: int
    partial_count: int
    missing_count: int
    needs_review_count: int
    sections: list[PsarReadinessSection]
    missing_evidence_recommendations: list[PsarMissingEvidenceRecommendation]
    mapped_files: list[PsarEvidenceMapping]
    uploaded_files: list[PsarUploadedFile]


class AddPsarEvidenceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: str
    file: PsarUploadedFile
    mappings: list[PsarEvidenceMapping]
    readiness: PsarReadinessResponse


class GeneratePsarReportResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: str
    report_path: str
    readiness: PsarReadinessResponse
    generated_at: str


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
