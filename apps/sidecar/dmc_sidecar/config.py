from __future__ import annotations

import os
from pathlib import Path


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


def allow_production_dry_run() -> bool:
    return env_flag("DMC_ENABLE_DRY_RUN")


def module_configs_root() -> Path:
    bundled_root = bundled_resources_root()
    if bundled_root is not None:
        return bundled_root / "module-configs"
    return repo_root() / "packages" / "module-configs"
