from __future__ import annotations

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI

from .config import settings
from .db import migrate_database
from .license_service import LicenseRepository
from .routes import api_router


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    repository = LicenseRepository()
    migrate_database(repository.sqlite_path)
    repository.ensure_bootstrapped()
    yield


app = FastAPI(title="DMC Assistant Cloud", version=settings.version, lifespan=lifespan)
app.include_router(api_router)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {
        "status": "ok",
        "ocr_provider": settings.ocr_provider,
    }
