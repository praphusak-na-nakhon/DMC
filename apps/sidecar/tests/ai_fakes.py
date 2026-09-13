from __future__ import annotations


class InMemorySecretStore:
    """Test-only secret-store double shared by AI provider and RPC tests."""

    def __init__(self) -> None:
        self._secrets: dict[str, str] = {}

    def get(self, provider: str) -> str | None:
        return self._secrets.get(provider)

    def set(self, provider: str, secret: str) -> None:
        self._secrets[provider] = secret

    def delete(self, provider: str) -> bool:
        return self._secrets.pop(provider, None) is not None
