from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    app_name: str = "dmc-cloud"
    version: str = "0.1.0"


settings = Settings()
