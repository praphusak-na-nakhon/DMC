from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

LicenseTier = Literal["trial", "school_le_500", "school_501_1500", "school_gt_1500"]
SchoolSizeTier = Literal["le_500", "501_1500", "gt_1500"]
BillingInterval = Literal["monthly", "annual"]
LicenseStatus = Literal["active", "suspended", "expired"]
AccountStatus = Literal["active", "disabled"]
CreditReservationStatus = Literal["active", "captured", "released"]
CreditTransactionType = Literal["topup", "reserve", "capture", "release"]
ModulePricingMode = Literal["per_billable_record"]


class AuthLoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str
    password: str
    device_id: str
    device_name: str
    app_version: str


class AccountResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: str
    email: str
    display_name: str | None
    status: AccountStatus
    token_expires_at: str


class AuthLoginResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str
    account: AccountResponse


class WalletResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: str
    balance: int
    reserved: int
    available: int


class ModuleCatalogItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    enabled: bool
    requires_credits: bool
    pricing_mode: ModulePricingMode
    credit_per_unit: int
    production_dry_run_enabled: bool


class ModuleCatalogResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    modules: list[ModuleCatalogItem]


class CreditReservationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str
    module: str
    units: int = Field(ge=1)
    idempotency_key: str


class CreditReservationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reservation_id: str
    job_id: str
    module: str
    status: CreditReservationStatus
    units_reserved: int
    units_captured: int
    units_released: int
    wallet: WalletResponse


class CreditCaptureRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    units: int = Field(ge=0)
    idempotency_key: str | None = None


class CreditReleaseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    units: int = Field(ge=0)
    idempotency_key: str | None = None


class CloudUserCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str
    password: str = Field(min_length=8)
    display_name: str | None = None
    status: AccountStatus = "active"


class CloudUserAdminResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: str
    email: str
    display_name: str | None
    status: AccountStatus
    wallet: WalletResponse


class CloudCreditTopupRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount: int = Field(gt=0)
    note: str | None = None
    idempotency_key: str | None = None


class CreditLedgerEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transaction_id: str
    type: CreditTransactionType
    amount: int
    reservation_id: str | None
    job_id: str | None
    module: str | None
    note: str | None
    created_at: str


class LicenseActivateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    license_key: str
    device_id: str
    device_name: str
    app_version: str


class LicenseStateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: LicenseStatus
    license_tier: LicenseTier
    school_size_tier: SchoolSizeTier
    billing_interval: BillingInterval | None
    student_count_total: int
    expires_at: str
    modules_enabled: list[str]
    max_devices: int
    offline_grace_days: int


class CloudLicenseUpsertRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    license_key: str
    license_tier: LicenseTier
    school_size_tier: SchoolSizeTier
    billing_interval: BillingInterval | None = None
    student_count_total: int
    max_devices: int
    status: LicenseStatus
    expires_at: str
    modules_enabled: list[str]


class CloudLicenseAdminResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    license_key: str
    license_tier: LicenseTier
    school_size_tier: SchoolSizeTier
    billing_interval: BillingInterval | None
    student_count_total: int
    max_devices: int
    status: LicenseStatus
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
