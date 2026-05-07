from __future__ import annotations

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from pathlib import Path

from fastapi import FastAPI

from .config import settings
from .db import migrate_database
from .routes import api_router


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    migrate_database(Path(settings.sqlite_path))
    yield


app = FastAPI(title="DMC Assistant Cloud", version=settings.version, lifespan=lifespan)
app.include_router(api_router)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {
        "status": "ok",
        "ocr_provider": settings.ocr_provider,
    }
