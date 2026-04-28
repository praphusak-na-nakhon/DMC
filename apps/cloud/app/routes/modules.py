from __future__ import annotations

from fastapi import APIRouter, Depends

from ..account_service import SessionRecord, module_catalog_response
from ..auth import require_account_session
from ..schemas import ModuleCatalogResponse


router = APIRouter()


@router.get("/catalog", response_model=ModuleCatalogResponse)
def get_module_catalog(
    _session: SessionRecord = Depends(require_account_session),
) -> ModuleCatalogResponse:
    return module_catalog_response()
