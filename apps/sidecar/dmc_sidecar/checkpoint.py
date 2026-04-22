from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class JobCheckpoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    level_label: str
    base_url: str
    next_page: int = 1
    total_pages: int | None = None
    used_orders: list[int] = Field(default_factory=list)
    processed: int = 0
    succeeded: int = 0
    failed: int = 0
    results: list[dict[str, Any]] = Field(default_factory=list)
    report_path: str | None = None
    review_report_path: str | None = None
    stopped_item: dict[str, Any] | None = None
    awaiting_auth: bool = False
    auth_reason: str | None = None
    options: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def initial(cls, *, level_label: str, base_url: str) -> "JobCheckpoint":
        return cls(level_label=level_label, base_url=base_url)
