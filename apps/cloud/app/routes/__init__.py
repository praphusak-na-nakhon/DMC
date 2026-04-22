from fastapi import APIRouter

from .billing import router as billing_router
from .config import router as config_router
from .license import router as license_router
from .telemetry import router as telemetry_router


api_router = APIRouter()
api_router.include_router(license_router, prefix="/v1/license", tags=["license"])
api_router.include_router(config_router, prefix="/v1/config", tags=["config"])
api_router.include_router(telemetry_router, prefix="/v1/telemetry", tags=["telemetry"])
api_router.include_router(billing_router, prefix="/v1/billing", tags=["billing"])
