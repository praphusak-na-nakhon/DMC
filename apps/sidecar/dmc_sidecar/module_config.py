from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError

from . import config
from .errors import DomainError


class GraduationLevelRule(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    level_code: str
    default_missing_code: str | None
    ambiguity_floor: int | None
    require_exact_student_no: bool


class GraduationConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    module: Literal["graduation"]
    version: str
    login_url: str
    target_url_template: str
    selectors: dict[str, str]
    status_code_map: dict[str, str]
    level_rules: dict[str, GraduationLevelRule]


def load_bundled_module_config(module: str) -> dict[str, object]:
    """Validate and load the configuration shipped with this application."""
    if module != "graduation":
        raise DomainError("CONFIG_BUNDLED_INVALID")
    path = config.module_configs_root() / module / "v1.json"
    try:
        payload = GraduationConfig.model_validate_json(path.read_bytes())
    except (OSError, ValidationError) as exc:
        raise DomainError("CONFIG_BUNDLED_INVALID") from exc
    return payload.model_dump()
