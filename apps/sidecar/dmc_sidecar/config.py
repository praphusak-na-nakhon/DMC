from __future__ import annotations

import hashlib
import os
from pathlib import Path
from urllib.parse import urlparse


APP_NAME = "dmc-assistant"
SIDECAR_VERSION = "0.1.0"


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def default_data_dir() -> Path:
    return repo_root() / ".dmc-assistant-data"


def sqlite_path() -> Path:
    return default_data_dir() / "desktop.sqlite3"


def ensure_data_dir() -> Path:
    path = default_data_dir()
    path.mkdir(parents=True, exist_ok=True)
    return path


def reports_dir() -> Path:
    path = ensure_data_dir() / "reports"
    path.mkdir(parents=True, exist_ok=True)
    return path


def configs_dir() -> Path:
    path = ensure_data_dir() / "configs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def profiles_dir() -> Path:
    path = ensure_data_dir() / "profiles"
    path.mkdir(parents=True, exist_ok=True)
    return path


def profile_dir_for_license(license_key: str | None) -> Path:
    seed = license_key or "dev-unlicensed"
    profile_hash = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]
    path = profiles_dir() / profile_hash
    path.mkdir(parents=True, exist_ok=True)
    return path


def cloud_base_url() -> str | None:
    value = os.getenv("DMC_CLOUD_BASE_URL", "").strip()
    return value.rstrip("/") or None


def secure_cloud_base_url() -> str | None:
    value = cloud_base_url()
    if value is None:
        return None

    parsed = urlparse(value)
    hostname = (parsed.hostname or "").lower()
    if parsed.scheme == "https":
        return value
    if parsed.scheme == "http" and hostname in {"localhost", "127.0.0.1"}:
        return value
    raise RuntimeError("CLOUD_URL_INSECURE")


def cloud_api_bearer_token() -> str:
    return os.getenv("DMC_CLOUD_API_BEARER_TOKEN", "").strip()


def require_cloud_api_bearer_token() -> str:
    token = cloud_api_bearer_token()
    if not token:
        raise RuntimeError("CLOUD_API_TOKEN_MISSING")
    return token


def config_signing_keys_path() -> Path:
    return repo_root() / "packages" / "shared-schemas" / "config-signing" / "keys.json"
