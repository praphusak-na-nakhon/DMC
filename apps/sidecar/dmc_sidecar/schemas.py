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


class LicenseRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    license_key: str
    device_id: str
    license_tier: str
    school_size_tier: str
    billing_interval: str | None
    student_count_total: int
    max_devices: int
    activated_at: str
    expires_at: str
    last_checked_at: str
    offline_grace_until: str
