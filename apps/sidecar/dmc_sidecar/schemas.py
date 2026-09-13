from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr


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


class AiProviderRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: Literal["gemini"]


class SaveAiApiKeyRequest(AiProviderRequest):
    api_key: SecretStr = Field(min_length=1)


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

    module: Literal["graduation", "currentStudents"]
    detected_level: str
    rows_total: int
    rows_accepted: int
    warnings: list[ValidationWarning]
    preview: list[PreviewRow]


class StartJobRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str
    module: Literal["graduation", "currentStudents"]
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
