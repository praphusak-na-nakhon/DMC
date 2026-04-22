from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from ..runtime import JobContext
from ..schemas import ValidateExcelResponse


class AutomationModule(ABC):
    name: str

    @abstractmethod
    def validate_excel(self, path: Path) -> ValidateExcelResponse:
        raise NotImplementedError

    @abstractmethod
    def start_job(
        self,
        job_id: str,
        excel_path: Path,
        options: dict[str, object],
        context: JobContext,
    ) -> None:
        raise NotImplementedError
