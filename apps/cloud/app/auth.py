from __future__ import annotations

import hmac

from fastapi import HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import settings


bearer_scheme = HTTPBearer(auto_error=False)


def require_api_bearer(
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

    return credentials.credentials
