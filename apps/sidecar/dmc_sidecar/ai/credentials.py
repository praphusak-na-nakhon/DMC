from __future__ import annotations

from typing import Protocol

from ..errors import DomainError


_SERVICE_NAME = "dmc-assistant.ai"


class _CredentialBackend(Protocol):
    def get_password(self, service_name: str, username: str) -> str | None: ...

    def set_password(self, service_name: str, username: str, password: str) -> None: ...

    def delete_password(self, service_name: str, username: str) -> None: ...


class WindowsCredentialStore:
    """Stores AI secrets in Windows Credential Manager's WinVault backend."""

    def __init__(self, *, backend: _CredentialBackend | None = None) -> None:
        self._backend = backend if backend is not None else _create_winvault_backend()

    def get(self, provider: str) -> str | None:
        try:
            return self._backend.get_password(_SERVICE_NAME, _account_name(provider))
        except Exception:
            raise DomainError("AI_CREDENTIAL_STORE_UNAVAILABLE") from None

    def set(self, provider: str, secret: str) -> None:
        if not secret.strip():
            raise DomainError("AI_API_KEY_REQUIRED")
        try:
            self._backend.set_password(_SERVICE_NAME, _account_name(provider), secret)
        except Exception:
            raise DomainError("AI_CREDENTIAL_STORE_UNAVAILABLE") from None

    def delete(self, provider: str) -> bool:
        try:
            account_name = _account_name(provider)
            if self._backend.get_password(_SERVICE_NAME, account_name) is None:
                return False
            self._backend.delete_password(_SERVICE_NAME, account_name)
            return True
        except Exception:
            raise DomainError("AI_CREDENTIAL_STORE_UNAVAILABLE") from None


def _create_winvault_backend() -> _CredentialBackend:
    try:
        from keyring.backends.Windows import WinVaultKeyring

        return WinVaultKeyring()  # type: ignore[no-untyped-call]
    except Exception:
        raise DomainError("AI_CREDENTIAL_STORE_UNAVAILABLE") from None


def _account_name(provider: str) -> str:
    return f"provider:{provider}"
