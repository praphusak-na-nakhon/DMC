from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query

from ..auth import require_api_bearer
from ..config import settings
from ..schemas import ConfigResponse


router = APIRouter(dependencies=[Depends(require_api_bearer)])


def sign_config_payload(version: str, payload: dict[str, object]) -> str:
    if not settings.config_signing_secret:
        raise HTTPException(status_code=503, detail="config signing secret is not configured")

    canonical_payload = json.dumps(
        {
            "version": version,
            "config": payload,
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    signature = hmac.new(
        settings.config_signing_secret.encode("utf-8"),
        canonical_payload,
        hashlib.sha256,
    ).hexdigest()
    return f"hmac-sha256:{signature}"


@router.get("/{module}", response_model=ConfigResponse)
def get_module_config(module: str, current_version: str = Query(default="")) -> ConfigResponse:
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
    return ConfigResponse(
        version=version,
        config=payload,
        signature=sign_config_payload(version, payload),
    )
