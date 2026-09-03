from __future__ import annotations

from typing import Callable

import pytest

from dmc_sidecar.ai.credentials import WindowsCredentialStore
from dmc_sidecar.errors import DomainError


class FakeWinVaultBackend:
    def __init__(self) -> None:
        self._credentials: dict[tuple[str, str], str] = {}
        self.failure: Exception | None = None
        self.delete_calls = 0

    def get_password(self, service_name: str, username: str) -> str | None:
        self._raise_if_configured()
        return self._credentials.get((service_name, username))

    def set_password(self, service_name: str, username: str, password: str) -> None:
        self._raise_if_configured()
        self._credentials[(service_name, username)] = password

    def delete_password(self, service_name: str, username: str) -> None:
        self._raise_if_configured()
        self.delete_calls += 1
        del self._credentials[(service_name, username)]

    def _raise_if_configured(self) -> None:
        if self.failure is not None:
            raise self.failure


def test_windows_credential_store_round_trips_through_stable_winvault_identity() -> None:
    backend = FakeWinVaultBackend()
    store = WindowsCredentialStore(backend=backend)

    assert store.get("gemini") is None
    store.set("gemini", "secret-value")

    assert store.get("gemini") == "secret-value"
    assert backend._credentials == {("dmc-assistant.ai", "provider:gemini"): "secret-value"}
    assert store.delete("gemini") is True
    assert store.get("gemini") is None


def test_windows_credential_store_overwrites_an_existing_provider_secret() -> None:
    backend = FakeWinVaultBackend()
    store = WindowsCredentialStore(backend=backend)
    store.set("gemini", "old-secret")

    store.set("gemini", "new-secret")

    assert store.get("gemini") == "new-secret"


def test_windows_credential_store_does_not_delete_a_missing_secret() -> None:
    backend = FakeWinVaultBackend()
    store = WindowsCredentialStore(backend=backend)

    assert store.delete("gemini") is False
    assert backend.delete_calls == 0


def test_windows_credential_store_rejects_blank_api_keys() -> None:
    store = WindowsCredentialStore(backend=FakeWinVaultBackend())

    with pytest.raises(DomainError) as exc_info:
        store.set("gemini", "   ")

    assert exc_info.value.code == "AI_API_KEY_REQUIRED"


@pytest.mark.parametrize(
    "operation",
    [
        lambda store: store.get("gemini"),
        lambda store: store.set("gemini", "secret-value"),
        lambda store: store.delete("gemini"),
    ],
    ids=["get", "set", "delete"],
)
def test_windows_credential_store_redacts_backend_failures(
    operation: Callable[[WindowsCredentialStore], object],
) -> None:
    sensitive_backend_error = RuntimeError("credential backend rejected secret-value")
    backend = FakeWinVaultBackend()
    backend.failure = sensitive_backend_error
    store = WindowsCredentialStore(backend=backend)

    with pytest.raises(DomainError) as exc_info:
        operation(store)

    assert exc_info.value.code == "AI_CREDENTIAL_STORE_UNAVAILABLE"
    assert "secret-value" not in str(exc_info.value)
