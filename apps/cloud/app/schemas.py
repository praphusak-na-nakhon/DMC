from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

AccountStatus = Literal["active", "disabled"]
CreditReservationStatus = Literal["active", "captured", "released"]
CreditTransactionType = Literal["topup", "reserve", "capture", "release"]
ModulePricingMode = Literal["per_billable_record"]
CreditTopupRequestStatus = Literal["pending", "approved", "rejected"]
OcrRecordStatus = Literal["ready", "needs_review", "invalid"]
OcrFieldStatus = Literal["ready", "needs_review", "invalid"]


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


class OcrFormConverterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str
    module: Literal["formConverter"]
    template_type: str
    page_count: int = Field(ge=1)
    credit_reservation_id: str
    document_sha256: str
    document_base64: str


class OcrFieldResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field_name: str
    label_th: str
    value: str
    confidence: float = Field(ge=0, le=1)
    status: OcrFieldStatus
    alternatives: list[str] = Field(default_factory=list)


class OcrRecordResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    record_id: str
    page_number: int = Field(ge=1)
    status: OcrRecordStatus
    fields: list[OcrFieldResponse]


class OcrFormConverterResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str
    module: Literal["formConverter"]
    template_type: str
    provider: str
    records: list[OcrRecordResponse]


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

    target_captured_units: int = Field(ge=0)
    idempotency_key: str | None = None

    @model_validator(mode="before")
    @classmethod
    def accept_deprecated_units(cls, data: object) -> object:
        if not isinstance(data, dict) or "units" not in data:
            return data
        normalized = dict(data)
        old_units = normalized.pop("units")
        if "target_captured_units" in normalized and normalized["target_captured_units"] != old_units:
            raise ValueError("units conflicts with target_captured_units")
        normalized["target_captured_units"] = old_units
        return normalized

    @property
    def units(self) -> int:
        return self.target_captured_units


class CreditReleaseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_released_units: int = Field(ge=0)
    idempotency_key: str | None = None

    @model_validator(mode="before")
    @classmethod
    def accept_deprecated_units(cls, data: object) -> object:
        if not isinstance(data, dict) or "units" not in data:
            return data
        normalized = dict(data)
        old_units = normalized.pop("units")
        if "target_released_units" in normalized and normalized["target_released_units"] != old_units:
            raise ValueError("units conflicts with target_released_units")
        normalized["target_released_units"] = old_units
        return normalized

    @property
    def units(self) -> int:
        return self.target_released_units


class CloudUserCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str
    password: str = Field(min_length=8)
    display_name: str | None = None
    status: AccountStatus = "active"


class CloudUserUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    password: str | None = Field(default=None, min_length=8)
    display_name: str | None = None
    status: AccountStatus | None = None


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


class CloudCreditTopupRequestCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount: int = Field(gt=0)
    note: str | None = None
    payment_reference: str | None = None


class CloudCreditTopupDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Literal["approved", "rejected"]
    note: str | None = None
    idempotency_key: str | None = None


class CloudCreditTopupRequestResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    user_id: str
    amount: int
    status: CreditTopupRequestStatus
    note: str | None
    payment_reference: str | None
    requested_by: str
    decided_by: str | None
    topup_idempotency_key: str | None
    created_at: str
    updated_at: str
    decided_at: str | None
    wallet: WalletResponse | None = None


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


class AdminAuditEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    audit_id: str
    actor: str
    action: str
    target_type: str | None
    target_id: str | None
    payload: dict[str, object]
    created_at: str


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
    | JobCompletedEvent
    | JobFailedEvent
    | ConfigUpdatedEvent,
    Field(discriminator="event"),
]


class TelemetryBatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    events: list[TelemetryEvent]
