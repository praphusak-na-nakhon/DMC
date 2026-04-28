from fastapi import APIRouter

from .admin import router as admin_router
from .auth import router as auth_router
from .billing import router as billing_router
from .config import router as config_router
from .credits import router as credits_router
from .license import router as license_router
from .modules import router as modules_router
from .telemetry import router as telemetry_router
from .updates import router as updates_router
from .wallet import router as wallet_router


api_router = APIRouter()
api_router.include_router(admin_router, prefix="/v1/admin", tags=["admin"])
api_router.include_router(auth_router, prefix="/v1/auth", tags=["auth"])
api_router.include_router(license_router, prefix="/v1/license", tags=["license"])
api_router.include_router(config_router, prefix="/v1/config", tags=["config"])
api_router.include_router(wallet_router, prefix="/v1/wallet", tags=["wallet"])
api_router.include_router(modules_router, prefix="/v1/modules", tags=["modules"])
api_router.include_router(credits_router, prefix="/v1/credits", tags=["credits"])
api_router.include_router(telemetry_router, prefix="/v1/telemetry", tags=["telemetry"])
api_router.include_router(billing_router, prefix="/v1/billing", tags=["billing"])
api_router.include_router(updates_router, prefix="/v1/updates", tags=["updates"])
