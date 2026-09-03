from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlparse

from .errors import DomainError


APP_NAME = "dmc-assistant"
SIDECAR_VERSION = "0.1.0"


def env_flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def repo_root() -> Path:
    override = os.getenv("DMC_REPO_ROOT", "").strip()
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[3]


def bundled_resources_root() -> Path | None:
    value = os.getenv("DMC_BUNDLED_RESOURCES_DIR", "").strip()
    if not value:
        return None
    return Path(value)


def default_data_dir() -> Path:
    override = os.getenv("DMC_DATA_DIR", "").strip()
    if override:
        return Path(override)
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


def ocr_cache_dir() -> Path:
    path = ensure_data_dir() / "ocr"
    path.mkdir(parents=True, exist_ok=True)
    return path


def backups_dir() -> Path:
    path = ensure_data_dir() / "backups"
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


def playwright_browsers_dir() -> Path:
    override = os.getenv("PLAYWRIGHT_BROWSERS_PATH", "").strip()
    if override:
        return Path(override)
    return ensure_data_dir() / "ms-playwright"


def automation_profile_dir() -> Path:
    path = profiles_dir() / "default"
    path.mkdir(parents=True, exist_ok=True)
    return path


def cloud_base_url() -> str | None:
    value = os.getenv("DMC_CLOUD_BASE_URL", "").strip()
    return value.rstrip("/") or None


def allow_production_dry_run() -> bool:
    return env_flag("DMC_ENABLE_DRY_RUN")


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
    raise DomainError("CLOUD_URL_INSECURE")


def config_signing_keys_path() -> Path:
    bundled_root = bundled_resources_root()
    if bundled_root is not None:
        return bundled_root / "shared-schemas" / "config-signing" / "keys.json"
    return repo_root() / "packages" / "shared-schemas" / "config-signing" / "keys.json"


def module_configs_root() -> Path:
    bundled_root = bundled_resources_root()
    if bundled_root is not None:
        return bundled_root / "module-configs"
    return repo_root() / "packages" / "module-configs"
