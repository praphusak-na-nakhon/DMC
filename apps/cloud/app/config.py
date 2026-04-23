from __future__ import annotations

import os
from pathlib import Path
from pydantic import BaseModel, ConfigDict


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    app_name: str = "dmc-cloud"
    version: str = "0.1.0"
    api_bearer_token: str = os.getenv("DMC_CLOUD_API_BEARER_TOKEN", "").strip()
    config_signing_key_id: str = os.getenv("DMC_CLOUD_CONFIG_SIGNING_KEY_ID", "dev-2026-01")
    config_signing_private_key_hex: str = os.getenv(
        "DMC_CLOUD_CONFIG_SIGNING_PRIVATE_KEY_HEX",
        "",
    ).strip()
    updater_latest_version: str = os.getenv("DMC_CLOUD_UPDATER_LATEST_VERSION", "0.1.0")
    updater_pub_date: str = os.getenv("DMC_CLOUD_UPDATER_PUB_DATE", "2026-04-22T00:00:00Z")
    updater_notes: str = os.getenv("DMC_CLOUD_UPDATER_NOTES", "No update available.")
    updater_windows_x86_64_url: str = os.getenv("DMC_CLOUD_UPDATER_WINDOWS_X86_64_URL", "")
    updater_windows_x86_64_signature: str = os.getenv(
        "DMC_CLOUD_UPDATER_WINDOWS_X86_64_SIGNATURE",
        "",
    )
    sqlite_path: str = os.getenv(
        "DMC_CLOUD_SQLITE_PATH",
        str(Path(__file__).resolve().parents[3] / ".dmc-assistant-data" / "cloud" / "state.sqlite3"),
    )
    offline_grace_days: int = int(os.getenv("DMC_CLOUD_OFFLINE_GRACE_DAYS", "7"))
    trial_license_keys: str = os.getenv(
        "DMC_CLOUD_TRIAL_LICENSE_KEYS",
        "DMC-TRIAL-0001,DMC-TEST-0001,DMC-TEST-NEW,DMC-TEST-ACTIVATE",
    )


settings = Settings()
