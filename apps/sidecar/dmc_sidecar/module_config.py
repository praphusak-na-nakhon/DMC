from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Literal
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from pydantic import BaseModel, ConfigDict

from .config import (
    cloud_api_bearer_token,
    cloud_base_url,
    config_signing_secret,
    configs_dir,
    repo_root,
)


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class ConfigEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str
    config: dict[str, Any]
    signature: str
    verified_at: str


@dataclass(frozen=True)
class ModuleConfigState:
    module: str
    version: str
    config: dict[str, Any]
    source: Literal["bundled", "cached", "cloud"]
    signature_verified: bool
    config_path: Path
    checked_at: str
    updated: bool
    last_error: str | None


def bundled_config_path(module: str) -> Path:
    return repo_root() / "packages" / "module-configs" / module / "v1.json"


def cached_config_path(module: str) -> Path:
    return configs_dir() / f"{module}.json"


def _canonical_payload(version: str, payload: dict[str, Any]) -> bytes:
    return json.dumps(
        {
            "version": version,
            "config": payload,
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def verify_signature(version: str, payload: dict[str, Any], signature: str) -> None:
    prefix = "hmac-sha256:"
    if not signature.startswith(prefix):
        raise RuntimeError("CONFIG_SIGNATURE_INVALID")

    secret = config_signing_secret()
    if not secret:
        raise RuntimeError("CONFIG_SIGNATURE_INVALID")

    expected = hmac.new(
        secret.encode("utf-8"),
        _canonical_payload(version, payload),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(signature[len(prefix) :], expected):
        raise RuntimeError("CONFIG_SIGNATURE_INVALID")


def _read_json_file(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_bundled_state(module: str, *, last_error: str | None = None) -> ModuleConfigState:
    path = bundled_config_path(module)
    payload = _read_json_file(path)
    return ModuleConfigState(
        module=module,
        version=str(payload["version"]),
        config=payload,
        source="bundled",
        signature_verified=False,
        config_path=path,
        checked_at=utc_now(),
        updated=False,
        last_error=last_error,
    )


def _load_cached_envelope(module: str) -> ConfigEnvelope | None:
    path = cached_config_path(module)
    if not path.exists():
        return None
    return ConfigEnvelope.model_validate(_read_json_file(path))


def load_effective_config(module: str) -> ModuleConfigState:
    try:
        cached = _load_cached_envelope(module)
    except Exception:
        return _load_bundled_state(module, last_error="CONFIG_CACHE_INVALID")

    if cached is None:
        return _load_bundled_state(module)

    try:
        verify_signature(cached.version, cached.config, cached.signature)
    except RuntimeError as exc:
        return _load_bundled_state(module, last_error=str(exc))

    return ModuleConfigState(
        module=module,
        version=cached.version,
        config=cached.config,
        source="cached",
        signature_verified=True,
        config_path=cached_config_path(module),
        checked_at=utc_now(),
        updated=False,
        last_error=None,
    )


def _write_cached_envelope(module: str, envelope: ConfigEnvelope) -> Path:
    target_path = cached_config_path(module)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=str(target_path.parent),
        delete=False,
        suffix=".tmp",
    ) as handle:
        json.dump(
            envelope.model_dump(),
            handle,
            ensure_ascii=False,
            indent=2,
        )
        temp_path = Path(handle.name)
    temp_path.replace(target_path)
    return target_path


def sync_module_config(module: str, *, timeout_sec: int = 10) -> ModuleConfigState:
    local_state = load_effective_config(module)
    base_url = cloud_base_url()
    if base_url is None:
        return local_state

    query = urlencode({"current_version": local_state.version})
    request = Request(
        f"{base_url}/v1/config/{module}?{query}",
        headers={
            "Authorization": f"Bearer {cloud_api_bearer_token()}",
            "Accept": "application/json",
        },
        method="GET",
    )

    try:
        with urlopen(request, timeout=timeout_sec) as response:
            status_code = getattr(response, "status", None)
            if status_code is None:
                status_code = response.getcode()
            if status_code == 204:
                return replace(local_state, checked_at=utc_now(), updated=False)
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        if exc.code == 304:
            return replace(local_state, checked_at=utc_now(), updated=False)
        return replace(
            local_state,
            checked_at=utc_now(),
            updated=False,
            last_error=f"HTTP_{exc.code}",
        )
    except URLError:
        return replace(
            local_state,
            checked_at=utc_now(),
            updated=False,
            last_error="CONFIG_SYNC_UNAVAILABLE",
        )

    version = str(payload["version"])
    config = dict(payload["config"])
    signature = str(payload["signature"])

    try:
        verify_signature(version, config, signature)
    except RuntimeError as exc:
        return replace(
            local_state,
            checked_at=utc_now(),
            updated=False,
            last_error=str(exc),
        )

    envelope = ConfigEnvelope(
        version=version,
        config=config,
        signature=signature,
        verified_at=utc_now(),
    )
    config_path = _write_cached_envelope(module, envelope)
    return ModuleConfigState(
        module=module,
        version=version,
        config=config,
        source="cloud",
        signature_verified=True,
        config_path=config_path,
        checked_at=envelope.verified_at,
        updated=True,
        last_error=None,
    )
