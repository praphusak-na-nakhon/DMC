from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class DatabasePlaceholder:
    dsn: str = "postgresql://localhost/dmc_assistant"


database = DatabasePlaceholder()
