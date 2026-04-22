from __future__ import annotations

from fastapi import FastAPI

from .config import settings
from .routes import api_router


app = FastAPI(title="DMC Assistant Cloud", version=settings.version)
app.include_router(api_router)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}
