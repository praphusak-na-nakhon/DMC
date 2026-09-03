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


class SecretStore(Protocol):
    def get(self, provider: str) -> str | None: ...

    def set(self, provider: str, secret: str) -> None: ...

    def delete(self, provider: str) -> bool: ...
