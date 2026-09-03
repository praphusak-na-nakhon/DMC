from __future__ import annotations

from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict


AiProviderId = Literal["gemini"]


class AiSettingsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: AiProviderId
    configured: bool


class AiConnectionTestResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: AiProviderId
    ok: bool
    tested_at: str
    message: str


class OcrDocumentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: AiProviderId
    source_path: str
    model: str = "gemini-3.5-flash"
    processing_mode: Literal["standard", "batch"] = "batch"
    force_refresh: bool = False


class OcrUsageMetadata(BaseModel):
    model_config = ConfigDict(extra="allow")

    prompt_token_count: int | None = None
    candidates_token_count: int | None = None
    total_token_count: int | None = None
    cached_content_token_count: int | None = None
    thoughts_token_count: int | None = None
    input_tokens_per_page: float | None = None
    output_tokens_per_page: float | None = None
    total_tokens_per_page: float | None = None


class OcrDocumentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    module: Literal["formConverter"] = "formConverter"
    provider: AiProviderId
    model: str
    processing_mode: Literal["standard", "batch"]
    source_path: str
    markdown_path: str
    structured_json_path: str | None = None
    output_format: Literal["structured_json"] = "structured_json"
    cached: bool
    pages_processed: int
    pages_estimated: int
    average_confidence: float | None = None
    usage_metadata: OcrUsageMetadata | None = None
    provider_job_id: str | None = None
    provider_job_state: str | None = None
    file_sha256: str
    created_at: str


class SecretStore(Protocol):
    def get(self, provider: str) -> str | None: ...

    def set(self, provider: str, secret: str) -> None: ...

    def delete(self, provider: str) -> bool: ...


class AiProvider(Protocol):
    provider_id: AiProviderId

    def test_connection(self) -> AiConnectionTestResponse: ...

    def ocr_document(self, request: OcrDocumentRequest) -> OcrDocumentResponse: ...
