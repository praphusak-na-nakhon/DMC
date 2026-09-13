from __future__ import annotations

from .base import AiProvider, SecretStore
from .gemini import GeminiProvider
from ..errors import DomainError


class ProviderRegistry:
    def __init__(self, providers: list[AiProvider]) -> None:
        self._providers: dict[str, AiProvider] = {provider.provider_id: provider for provider in providers}

    def supported_provider_ids(self) -> list[str]:
        return list(self._providers)

    def get(self, provider_id: str) -> AiProvider:
        provider = self._providers.get(provider_id)
        if provider is None:
            raise DomainError("AI_PROVIDER_UNAVAILABLE")
        return provider


def build_provider_registry(secret_store: SecretStore) -> ProviderRegistry:
    return ProviderRegistry([GeminiProvider(secret_store)])
