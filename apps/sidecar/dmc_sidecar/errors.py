from __future__ import annotations

from typing import Any


class DomainError(Exception):
    def __init__(
        self,
        code: str,
        message: str | None = None,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message or code)
        self.code = code
        self.user_message = message or code
        self.details = details or {}
