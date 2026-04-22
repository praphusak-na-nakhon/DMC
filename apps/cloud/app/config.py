from __future__ import annotations

import os
from pydantic import BaseModel, ConfigDict


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    app_name: str = "dmc-cloud"
    version: str = "0.1.0"
    api_bearer_token: str = os.getenv("DMC_CLOUD_API_BEARER_TOKEN", "dmc-dev-token")
    config_signing_key_id: str = os.getenv("DMC_CLOUD_CONFIG_SIGNING_KEY_ID", "dev-2026-01")
    config_signing_private_key_hex: str = os.getenv(
        "DMC_CLOUD_CONFIG_SIGNING_PRIVATE_KEY_HEX",
        "affb171844b95521a4d9a844da801d480577ca29d141eb5113da47acf182a088",
    )


settings = Settings()
