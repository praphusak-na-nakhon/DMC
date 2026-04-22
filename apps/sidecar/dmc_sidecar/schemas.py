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
