from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

from ..schemas import ConfigResponse


router = APIRouter()


@router.get("/{module}", response_model=ConfigResponse)
def get_module_config(module: str, current_version: str = Query(default="")) -> ConfigResponse:
    config_path = (
        Path(__file__).resolve().parents[3]
        / "packages"
        / "module-configs"
        / module
        / "v1.json"
    )
    if not config_path.exists():
        raise HTTPException(status_code=404, detail="module config not found")

    payload = json.loads(config_path.read_text(encoding="utf-8"))
    return ConfigResponse(
        version=str(payload["version"]),
        config=payload,
        signature="dev-signature-placeholder",
    )
