from __future__ import annotations

import os
from pydantic import BaseModel, ConfigDict


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    app_name: str = "dmc-cloud"
    version: str = "0.1.0"
    api_bearer_token: str = os.getenv("DMC_CLOUD_API_BEARER_TOKEN", "dmc-dev-token")
    config_signing_secret: str = os.getenv("DMC_CLOUD_CONFIG_SIGNING_SECRET", "dmc-dev-signing-secret")


settings = Settings()
