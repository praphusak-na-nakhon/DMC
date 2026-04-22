from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class LicenseActivateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    license_key: str
    device_id: str
    device_name: str
    app_version: str


class LicenseStateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str | None = None
    license_tier: str
    school_size_tier: str
    billing_interval: str | None
    student_count_total: int
    expires_at: str
    modules_enabled: list[str]
    max_devices: int
    offline_grace_days: int


class CloudLicenseUpsertRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    license_key: str
    license_tier: str
    school_size_tier: str
    billing_interval: str | None = None
    student_count_total: int
    max_devices: int
    status: str
    expires_at: str
    modules_enabled: list[str]


class CloudLicenseAdminResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    license_key: str
    license_tier: str
    school_size_tier: str
    billing_interval: str | None
    student_count_total: int
    max_devices: int
    status: str
    expires_at: str
    modules_enabled: list[str]
    active_devices: int


class ConfigResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str
    config: dict[str, object]
    signature: str


class AppStartedEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event: Literal["app_started"]
    ts: str
    app_version: str
    platform: str


class LicenseCheckedEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event: Literal["license_checked"]
    ts: str
    result: str
    offline_mode: bool


class JobCompletedEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event: Literal["job_completed"]
    ts: str
    module: str
    total: int
    succeeded: int
    failed: int
    duration_sec: int


class JobFailedEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event: Literal["job_failed"]
    ts: str
    module: str
    error_code: str
    processed: int


class ConfigUpdatedEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event: Literal["config_updated"]
    ts: str
    module: str
    from_version: str
    to_version: str


TelemetryEvent = Annotated[
    AppStartedEvent
    | LicenseCheckedEvent
    | JobCompletedEvent
    | JobFailedEvent
    | ConfigUpdatedEvent,
    Field(discriminator="event"),
]


class TelemetryBatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    events: list[TelemetryEvent]
