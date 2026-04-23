from __future__ import annotations

import json
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Response

from ..config_signing import sign_config_payload
from ..schemas import ConfigResponse


router = APIRouter()
MODULE_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_-]*$")


@router.get("/{module}", response_model=ConfigResponse)
def get_module_config(module: str, current_version: str = Query(default="")) -> ConfigResponse | Response:
    if not MODULE_NAME_PATTERN.fullmatch(module):
        raise HTTPException(status_code=400, detail="invalid module name")

    config_path = (
        Path(__file__).resolve().parents[4]
        / "packages"
        / "module-configs"
        / module
        / "v1.json"
    )
    if not config_path.exists():
        raise HTTPException(status_code=404, detail="module config not found")

    payload = json.loads(config_path.read_text(encoding="utf-8"))
    version = str(payload["version"])
    if current_version == version:
        return Response(status_code=204)
    try:
        signature = sign_config_payload(version, payload)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return ConfigResponse(
        version=version,
        config=payload,
        signature=signature,
    )
