from __future__ import annotations

import hashlib
import hmac

from fastapi import HTTPException, Request, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .account_service import AccountRepository, SessionRecord
from .config import settings


bearer_scheme = HTTPBearer(auto_error=False)


def require_api_bearer(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
) -> str:
    if not settings.api_bearer_token:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="cloud bearer token is not configured",
        )

    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing bearer token",
        )

    if not hmac.compare_digest(credentials.credentials, settings.api_bearer_token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="invalid bearer token",
        )

    actor = f"admin:{hashlib.sha256(credentials.credentials.encode('utf-8')).hexdigest()[:12]}"
    request.state.admin_actor = actor
    return actor


def require_account_session(
    credentials: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
) -> SessionRecord:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing account session",
        )
    return AccountRepository().get_session(credentials.credentials)
