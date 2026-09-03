from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Callable

import pytest

from ai_fakes import InMemorySecretStore
from dmc_sidecar.ai.credentials import WindowsCredentialStore
from dmc_sidecar.ai.gemini import GeminiProvider
from dmc_sidecar.ai.registry import build_provider_registry
from dmc_sidecar.errors import DomainError
from dmc_sidecar.gemini_ocr import GeminiOcrUsageMetadata
from dmc_sidecar.rpc import RpcServer


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


def test_saved_key_is_absent_from_persisted_ocr_cache_notifications_and_rpc_responses(monkeypatch, tmp_path) -> None:  # noqa: ANN001
    """A saved API key must remain exclusively in the credential backend."""
    # A regression in RPC serialization, notification construction, or OCR cache writes
    # should expose this literal and fail the test.
    monkeypatch.setenv("DMC_DATA_DIR", str(tmp_path / "data"))
    source_path = tmp_path / "form.pdf"
    source_path.write_bytes(b"%PDF-1.4\n1 0 obj << /Type /Page >>\nendobj\n")
    notifications: list[dict[str, object]] = []
    store = WindowsCredentialStore(backend=FakeWinVaultBackend())

    def fake_batch_generator(*args, **kwargs):  # noqa: ANN002, ANN003
        return (
            {"records": [{"record_id": "student-1", "fields": []}]},
            GeminiOcrUsageMetadata(prompt_token_count=5, total_token_count=7),
            "batches/test-job",
            "JOB_STATE_SUCCEEDED",
        )

    monkeypatch.setattr("dmc_sidecar.gemini_ocr._generate_structured_json_with_gemini_batch", fake_batch_generator)
    server = RpcServer(
        emit_notification=notifications.append,
        secret_store=store,
        provider_registry=build_provider_registry(store),
    )

    def request(method: str, params: dict[str, object]) -> str:
        return server.handle_text(
            json.dumps({"jsonrpc": "2.0", "id": method, "method": method, "params": params})
        )

    responses = [
        request("save_ai_api_key", {"provider": "gemini", "api_key": "secret-value"}),
        request("get_ai_settings", {"provider": "gemini"}),
        request("ocr_document", {"provider": "gemini", "source_path": str(source_path)}),
    ]

    assert json.loads(responses[1])["result"] == {"provider": "gemini", "configured": True}
    assert json.loads(responses[2])["result"]["cached"] is False
    assert "secret-value" not in json.dumps(responses)
    assert "secret-value" not in json.dumps(notifications)
    for path in tmp_path.rglob("*"):
        if path.is_file():
            assert b"secret-value" not in path.read_bytes()


def test_field_tool_uses_an_ephemeral_store_for_explicit_gemini_key() -> None:
    """The opt-in field tool must not touch Windows Credential Manager."""
    script_path = Path(__file__).resolve().parents[3] / "scripts" / "form_converter_field_test.py"
    spec = importlib.util.spec_from_file_location("form_converter_field_test", script_path)
    assert spec is not None and spec.loader is not None
    field_tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(field_tool)

    provider = field_tool.build_gemini_provider("secret-value")

    assert provider._secret_store.get("gemini") == "secret-value"  # noqa: SLF001
    assert provider._secret_store.delete("gemini") is True  # noqa: SLF001


def test_field_tool_redacts_provider_failure_details(monkeypatch, tmp_path) -> None:  # noqa: ANN001
    script_path = Path(__file__).resolve().parents[3] / "scripts" / "form_converter_field_test.py"
    spec = importlib.util.spec_from_file_location("form_converter_field_test", script_path)
    assert spec is not None and spec.loader is not None
    field_tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(field_tool)
    source_path = tmp_path / "form.pdf"
    source_path.write_bytes(b"%PDF-1.4\n1 0 obj << /Type /Page >>\nendobj\n")
    store = InMemorySecretStore()
    store.set("gemini", "secret-value")

    def failing_engine(request, *, api_key):  # noqa: ANN001
        raise DomainError("GEMINIOCR_AUTH_FAILED", f"Authorization: Bearer {api_key}")

    with pytest.raises(field_tool.FieldTestError, match="Gemini OCR failed: AI_API_KEY_INVALID") as exc_info:
        field_tool.run_pdf(
            GeminiProvider(store, ocr_engine=failing_engine),
            source_path,
            model="gemini-3.5-flash",
            processing_mode="batch",
        )

    assert "secret-value" not in str(exc_info.value)


def test_field_tool_console_summary_contains_only_requested_metrics() -> None:
    script_path = Path(__file__).resolve().parents[3] / "scripts" / "form_converter_field_test.py"
    spec = importlib.util.spec_from_file_location("form_converter_field_test", script_path)
    assert spec is not None and spec.loader is not None
    field_tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(field_tool)

    visible = field_tool.console_summary(
        {
            "file_name": "student-form.pdf",
            "output_path": "C:\\private\\output.json",
            "page_count": 2,
            "model": "gemini-3.5-flash",
            "processing_mode": "batch",
            "usage_totals": {"total_token_count": 42},
        }
    )

    assert visible == {
        "output_path": "C:\\private\\output.json",
        "page_count": 2,
        "model": "gemini-3.5-flash",
        "processing_mode": "batch",
        "usage_totals": {"total_token_count": 42},
    }
