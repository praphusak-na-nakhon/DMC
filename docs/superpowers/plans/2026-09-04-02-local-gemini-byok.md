# Local Gemini BYOK Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace credit-gated Gemini OCR with a provider-neutral local AI layer that reads the user's Gemini API key from Windows Credential Manager.

**Architecture:** Add injectable credential and provider boundaries in the sidecar, expose provider-neutral AI RPC methods, then add desktop AI settings and switch Form Converter to `ocr_document`. Keep the old commercial system temporarily for non-OCR paths; Plan 03 removes it after BYOK OCR is proven.

**Tech Stack:** Python 3.11+, Pydantic 2, google-genai, keyring, pytest, React 18, TypeScript, Vitest, JSON-RPC over Tauri stdio

**Spec:** `docs/superpowers/specs/2026-09-04-local-first-byok-refactor-design.md`

## Global Constraints

- The only provider exposed in the first release is `gemini`.
- Provider contracts and UI state use provider-neutral names.
- API keys never enter SQLite, logs, diagnostics, cache metadata, or RPC responses.
- Automated tests use fake credential stores and fake Gemini clients.
- Preserve current structured OCR output, cache, batch mode, and usage metadata behavior.
- Do not perform the broader Current Students or Form Converter file split in this plan.

---

### Task 1: Introduce the credential-store boundary

**Files:**
- Create: `apps/sidecar/dmc_sidecar/ai/__init__.py`
- Create: `apps/sidecar/dmc_sidecar/ai/base.py`
- Create: `apps/sidecar/dmc_sidecar/ai/credentials.py`
- Create: `apps/sidecar/tests/test_ai_credentials.py`
- Modify: `apps/sidecar/pyproject.toml`

**Interfaces:**
- Consumes: Windows Credential Manager through `keyring`
- Produces: `SecretStore.get(provider)`, `SecretStore.set(provider, secret)`, `SecretStore.delete(provider)`, and `WindowsCredentialStore`

- [ ] **Step 1: Add failing credential-store contract tests**

Create `test_ai_credentials.py` with an in-memory contract double and a monkeypatched keyring backend:

```python
from dmc_sidecar.ai.credentials import InMemorySecretStore, WindowsCredentialStore


def test_in_memory_secret_store_round_trip() -> None:
    store = InMemorySecretStore()
    assert store.get("gemini") is None
    store.set("gemini", "secret-value")
    assert store.get("gemini") == "secret-value"
    assert store.delete("gemini") is True
    assert store.get("gemini") is None


def test_windows_store_uses_stable_service_name(monkeypatch) -> None:
    calls: list[tuple[str, str, str]] = []
    monkeypatch.setattr(
        "keyring.set_password",
        lambda service, account, secret: calls.append((service, account, secret)),
    )
    store = WindowsCredentialStore()
    store.set("gemini", "secret-value")
    assert calls == [("dmc-assistant.ai", "provider:gemini", "secret-value")]
```

- [ ] **Step 2: Run the tests and verify the package is absent**

Run: `.\.venv\Scripts\python -m pytest apps/sidecar/tests/test_ai_credentials.py -v`

Expected: FAIL because `dmc_sidecar.ai` does not exist.

- [ ] **Step 3: Define provider-neutral models and the secret protocol**

In `base.py`, define:

```python
from typing import Literal, Protocol
from pydantic import BaseModel, ConfigDict

AiProviderId = Literal["gemini"]


class AiSettingsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: AiProviderId
    configured: bool


class AiConnectionTestResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: AiProviderId
    ok: bool
    tested_at: str
    message: str


class SecretStore(Protocol):
    def get(self, provider: str) -> str | None: ...
    def set(self, provider: str, secret: str) -> None: ...
    def delete(self, provider: str) -> bool: ...
```

Implement `InMemorySecretStore` for tests and `WindowsCredentialStore` with service `dmc-assistant.ai` and account `provider:{provider}`. Empty secrets raise `DomainError("AI_API_KEY_REQUIRED")`; backend failures raise `DomainError("AI_CREDENTIAL_STORE_UNAVAILABLE")` without embedding exception text that may contain a secret.

- [ ] **Step 4: Add the runtime dependency and verify**

Add `keyring>=25.6,<26` to sidecar dependencies, install the editable sidecar, and run:

```powershell
.\.venv\Scripts\python -m pip install -e ".\apps\sidecar[dev]"
.\.venv\Scripts\python -m pytest apps/sidecar/tests/test_ai_credentials.py -v
corepack pnpm run sidecar:typecheck
```

Expected: credential tests and strict mypy pass.

- [ ] **Step 5: Commit the credential boundary**

```powershell
git add apps/sidecar/dmc_sidecar/ai apps/sidecar/tests/test_ai_credentials.py apps/sidecar/pyproject.toml
git commit -m "feat: add secure AI credential store"
```

---

### Task 2: Add the provider registry and Gemini adapter

**Files:**
- Modify: `apps/sidecar/dmc_sidecar/ai/base.py`
- Create: `apps/sidecar/dmc_sidecar/ai/registry.py`
- Create: `apps/sidecar/dmc_sidecar/ai/gemini.py`
- Create: `apps/sidecar/tests/test_ai_providers.py`
- Modify: `apps/sidecar/dmc_sidecar/gemini_ocr.py`
- Modify: `apps/sidecar/tests/test_gemini_ocr.py`

**Interfaces:**
- Consumes: `SecretStore`; existing Gemini OCR engine and cache
- Produces: `AiProvider.test_connection()`, `AiProvider.ocr_document()`, and `ProviderRegistry.get("gemini")`

- [ ] **Step 1: Write failing registry and credential-use tests**

Create `test_ai_providers.py`:

```python
import pytest
from dmc_sidecar.ai.credentials import InMemorySecretStore
from dmc_sidecar.ai.registry import build_provider_registry
from dmc_sidecar.errors import DomainError


def test_registry_exposes_only_gemini() -> None:
    registry = build_provider_registry(InMemorySecretStore())
    assert registry.supported_provider_ids() == ["gemini"]


def test_registry_rejects_unknown_provider() -> None:
    registry = build_provider_registry(InMemorySecretStore())
    with pytest.raises(DomainError, match="AI_PROVIDER_UNAVAILABLE"):
        registry.get("openai")


def test_gemini_provider_requires_stored_key() -> None:
    registry = build_provider_registry(InMemorySecretStore())
    with pytest.raises(DomainError, match="AI_API_KEY_REQUIRED"):
        registry.get("gemini").credential()
```

- [ ] **Step 2: Run focused tests and confirm failure**

Run: `.\.venv\Scripts\python -m pytest apps/sidecar/tests/test_ai_providers.py -v`

Expected: FAIL because the provider registry does not exist.

- [ ] **Step 3: Implement the protocol and registry**

Extend `base.py` with provider-neutral OCR models and protocol:

```python
class OcrDocumentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: AiProviderId = "gemini"
    source_path: str
    model: str = "gemini-3.5-flash"
    processing_mode: Literal["standard", "batch"] = "batch"
    force_refresh: bool = False


class OcrUsageMetadata(BaseModel):
    model_config = ConfigDict(extra="allow")
    prompt_token_count: int | None = None
    candidates_token_count: int | None = None
    total_token_count: int | None = None
    cached_content_token_count: int | None = None
    thoughts_token_count: int | None = None
    input_tokens_per_page: float | None = None
    output_tokens_per_page: float | None = None
    total_tokens_per_page: float | None = None


class OcrDocumentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    module: Literal["formConverter"] = "formConverter"
    provider: AiProviderId
    model: str
    processing_mode: Literal["standard", "batch"]
    source_path: str
    markdown_path: str
    structured_json_path: str | None = None
    output_format: Literal["structured_json"] = "structured_json"
    cached: bool
    pages_processed: int
    pages_estimated: int
    average_confidence: float | None = None
    usage_metadata: OcrUsageMetadata | None = None
    provider_job_id: str | None = None
    provider_job_state: str | None = None
    file_sha256: str
    created_at: str


class AiProvider(Protocol):
    provider_id: AiProviderId
    def test_connection(self) -> AiConnectionTestResponse: ...
    def ocr_document(self, request: OcrDocumentRequest) -> OcrDocumentResponse: ...
```

`ProviderRegistry.get` must raise `AI_PROVIDER_UNAVAILABLE` for IDs not registered.

- [ ] **Step 4: Adapt the existing Gemini engine**

Keep parsing, batching, structured output, and cache mechanics in `gemini_ocr.py`. Remove credit fields from its response and accept `api_key` as an internal keyword-only parameter rather than a public RPC request field. `GeminiProvider` retrieves the secret, invokes the engine, maps `engine` to `provider`, maps batch job fields to `provider_job_id`/`provider_job_state`, and translates `GEMINIOCR_*`/SDK exceptions to the `AI_*` error catalog.

Add parameterized fake-client tests for invalid credentials, rate limiting, timeout, invalid provider output, unsupported input, and terminal job failure. Each case must assert its corresponding `AI_*` code and confirm that exception text containing `Authorization: Bearer secret-value` is redacted from the returned detail and captured logs.

Connection testing must call Gemini model metadata, close the client in `finally`, and return:

```python
AiConnectionTestResponse(
    provider="gemini",
    ok=True,
    tested_at=utc_now(),
    message="Gemini connection succeeded.",
)
```

- [ ] **Step 5: Update OCR engine tests and verify**

Change existing tests to pass the key through the adapter and assert that response/cache metadata has no `credits_per_page`, `credits_charged`, `charged`, or `credit_reservation_id` fields.

Run:

```powershell
.\.venv\Scripts\python -m pytest apps/sidecar/tests/test_ai_providers.py apps/sidecar/tests/test_gemini_ocr.py -v
corepack pnpm run sidecar:typecheck
```

Expected: provider and OCR tests pass; strict mypy succeeds.

- [ ] **Step 6: Commit the provider layer**

```powershell
git add apps/sidecar/dmc_sidecar/ai apps/sidecar/dmc_sidecar/gemini_ocr.py apps/sidecar/tests/test_ai_providers.py apps/sidecar/tests/test_gemini_ocr.py
git commit -m "feat: add provider-neutral Gemini OCR"
```

---

### Task 3: Expose AI credential and OCR RPC methods

**Files:**
- Modify: `apps/sidecar/dmc_sidecar/schemas.py`
- Modify: `apps/sidecar/dmc_sidecar/rpc.py`
- Modify: `apps/sidecar/tests/test_rpc.py`

**Interfaces:**
- Consumes: `SecretStore`, `ProviderRegistry`, and provider-neutral AI models
- Produces: `get_ai_settings`, `save_ai_api_key`, `test_ai_connection`, `delete_ai_api_key`, `ocr_document`

- [ ] **Step 1: Add failing JSON-RPC contract tests**

Add tests using an injected `InMemorySecretStore`:

```python
def test_ai_key_rpc_never_returns_secret() -> None:
    store = InMemorySecretStore()
    server = RpcServer(emit_notification=lambda payload: None, secret_store=store)

    saved = _rpc_call(server, "save_ai_api_key", {"provider": "gemini", "api_key": "secret-value"})
    status = _rpc_call(server, "get_ai_settings", {"provider": "gemini"})

    assert saved["result"] == {"provider": "gemini", "configured": True}
    assert status["result"] == {"provider": "gemini", "configured": True}
    assert "secret-value" not in json.dumps([saved, status])


def test_legacy_gemini_rpc_is_removed() -> None:
    server = RpcServer(emit_notification=lambda payload: None, secret_store=InMemorySecretStore())
    response = _rpc_call(server, "ocr_dmc_form_with_gemini", {})
    assert response["error"]["code"] == "RPC_METHOD_NOT_FOUND"


def test_deleting_key_blocks_new_ocr_requests() -> None:
    store = InMemorySecretStore({"gemini": "secret-value"})
    server = RpcServer(emit_notification=lambda payload: None, secret_store=store)
    _rpc_call(server, "delete_ai_api_key", {"provider": "gemini"})

    response = _rpc_call(server, "ocr_document", {
        "provider": "gemini",
        "source_path": "C:\\data\\form.pdf",
    })

    assert response["error"]["code"] == "AI_API_KEY_REQUIRED"
```

- [ ] **Step 2: Run the focused tests and confirm failure**

Run: `.\.venv\Scripts\python -m pytest apps/sidecar/tests/test_rpc.py -k "ai_key_rpc or legacy_gemini_rpc" -v`

Expected: FAIL because the new methods and injection point do not exist.

- [ ] **Step 3: Add request models and dependency injection**

Add strict Pydantic request models:

```python
class AiProviderRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: Literal["gemini"]


class SaveAiApiKeyRequest(AiProviderRequest):
    api_key: str = Field(min_length=1)
```

Change the server constructor to accept optional test dependencies:

```python
def __init__(
    self,
    emit_notification: Callable[[dict[str, Any]], None],
    *,
    secret_store: SecretStore | None = None,
    provider_registry: ProviderRegistry | None = None,
) -> None:
```

Production defaults use `WindowsCredentialStore` and a registry built from that same store.

- [ ] **Step 4: Implement the five RPC branches and remove aliases**

Each credential response returns only `provider` and `configured`. `test_ai_connection` delegates to the selected provider. `ocr_document` validates `OcrDocumentRequest` and delegates to the registry. Delete Gemini/Akson/Typhoon RPC aliases and the credit wrapper around OCR.

- [ ] **Step 5: Verify RPC and sidecar suites**

Run:

```powershell
.\.venv\Scripts\python -m pytest apps/sidecar/tests/test_rpc.py -v
corepack pnpm run sidecar:typecheck
corepack pnpm run sidecar:test
```

Expected: all commands exit 0 and no RPC response contains a credential.

- [ ] **Step 6: Commit the RPC migration**

```powershell
git add apps/sidecar/dmc_sidecar/schemas.py apps/sidecar/dmc_sidecar/rpc.py apps/sidecar/tests/test_rpc.py
git commit -m "feat: expose local AI settings RPC"
```

---

### Task 4: Add desktop AI contracts and client functions

**Files:**
- Modify: `apps/desktop/src/types/contracts.ts`
- Modify: `apps/desktop/src/types/contracts.test.ts`
- Modify: `apps/desktop/src/lib/rpcClient.ts`

**Interfaces:**
- Consumes: AI JSON-RPC responses from Task 3
- Produces: `AiSettings`, `AiConnectionTest`, `OcrDocumentResponse`, and typed client functions

- [ ] **Step 1: Add failing parser tests**

```ts
it("parses AI settings without accepting a secret field", () => {
  expect(parseAiSettings({ provider: "gemini", configured: true })).toEqual({
    provider: "gemini",
    configured: true,
  });
  expect(() =>
    parseAiSettings({ provider: "gemini", configured: true, api_key: "secret-value" }),
  ).toThrow();
});
```

- [ ] **Step 2: Run the parser test and verify failure**

Run: `corepack pnpm --dir apps/desktop exec vitest run src/types/contracts.test.ts`

Expected: FAIL because `parseAiSettings` does not exist.

- [ ] **Step 3: Implement strict AI types and parsers**

Add:

```ts
export type AiProviderId = "gemini";
export type AiSettings = { provider: AiProviderId; configured: boolean };
export type AiConnectionTest = {
  provider: AiProviderId;
  ok: boolean;
  tested_at: string;
  message: string;
};
export type OcrDocumentInput = {
  provider: AiProviderId;
  sourcePath: string;
  model: "gemini-3.5-flash" | "gemini-3-pro-preview";
  processingMode: "standard" | "batch";
  forceRefresh: boolean;
};
export type OcrDocumentResponse = {
  module: "formConverter";
  provider: AiProviderId;
  model: OcrDocumentInput["model"];
  processing_mode: OcrDocumentInput["processingMode"];
  source_path: string;
  markdown_path: string;
  structured_json_path: string | null;
  output_format: "structured_json";
  cached: boolean;
  pages_processed: number;
  pages_estimated: number;
  average_confidence: number | null;
  usage_metadata: Record<string, unknown> | null;
  provider_job_id: string | null;
  provider_job_state: string | null;
  file_sha256: string;
  created_at: string;
};
```

Use an exact-key assertion in credential parsers so a response containing `api_key` is rejected.

- [ ] **Step 4: Add typed RPC client methods**

Expose:

```ts
getAiSettings(provider: AiProviderId): Promise<AiSettings>
saveAiApiKey(provider: AiProviderId, apiKey: string): Promise<AiSettings>
testAiConnection(provider: AiProviderId): Promise<AiConnectionTest>
deleteAiApiKey(provider: AiProviderId): Promise<AiSettings>
ocrDocument(input: OcrDocumentInput): Promise<OcrDocumentResponse>
```

Remove `ocrDmcFormWithGemini` and all Akson/Typhoon compatibility naming from the desktop client.

- [ ] **Step 5: Verify contracts and typecheck**

Run:

```powershell
corepack pnpm --dir apps/desktop exec vitest run src/types/contracts.test.ts
corepack pnpm run desktop:typecheck
```

Expected: tests and typecheck pass.

- [ ] **Step 6: Commit desktop contracts**

```powershell
git add apps/desktop/src/types/contracts.ts apps/desktop/src/types/contracts.test.ts apps/desktop/src/lib/rpcClient.ts
git commit -m "feat: add desktop AI RPC contracts"
```

---

### Task 5: Add AI settings to the Home screen

**Files:**
- Create: `apps/desktop/src/components/AiSettingsCard.tsx`
- Create: `apps/desktop/src/components/AiSettingsCard.test.tsx`
- Modify: `apps/desktop/src/components/ModuleHome.tsx`
- Modify: `apps/desktop/src/components/ModuleHome.test.tsx`
- Modify: `apps/desktop/src/i18n/th.json`

**Interfaces:**
- Consumes: AI client functions from Task 4
- Produces: save/test/delete Gemini credential UI with no secret read-back

- [ ] **Step 1: Write component tests first**

Cover these behaviors:

```tsx
it("saves a Gemini key and clears the input", async () => {
  render(<AiSettingsCard connectionReady />);
  fireEvent.change(screen.getByLabelText("Gemini API key"), {
    target: { value: "secret-value" },
  });
  fireEvent.click(screen.getByRole("button", { name: "บันทึก API key" }));
  await waitFor(() => expect(mockRpc.saveAiApiKey).toHaveBeenCalledWith("gemini", "secret-value"));
  expect(screen.getByLabelText("Gemini API key")).toHaveValue("");
});
```

Also test configured status, test-connection feedback, deletion, and that the rendered DOM never contains `secret-value` after saving.

- [ ] **Step 2: Run the new test and confirm failure**

Run: `corepack pnpm --dir apps/desktop exec vitest run src/components/AiSettingsCard.test.tsx`

Expected: FAIL because the component does not exist.

- [ ] **Step 3: Implement the settings card**

Use a password input with `autoComplete="off"`. Keep the input in component-local state only. Load configured status when `connectionReady` becomes true. Save, test, and delete are separate actions. Include Thai disclosure text that OCR documents are sent directly to Gemini.

- [ ] **Step 4: Mount the card on Home and update copy**

Render `AiSettingsCard` from `ModuleHome` using `connectionState === "ready"`. Add Thai keys for configured/not-configured, save, test, delete, test success/failure, and privacy disclosure.

- [ ] **Step 5: Verify Home and settings UI**

Run:

```powershell
corepack pnpm --dir apps/desktop exec vitest run src/components/AiSettingsCard.test.tsx src/components/ModuleHome.test.tsx
corepack pnpm run desktop:typecheck
```

Expected: tests and typecheck pass.

- [ ] **Step 6: Commit the settings UI**

```powershell
git add apps/desktop/src/components/AiSettingsCard.tsx apps/desktop/src/components/AiSettingsCard.test.tsx apps/desktop/src/components/ModuleHome.tsx apps/desktop/src/components/ModuleHome.test.tsx apps/desktop/src/i18n/th.json
git commit -m "feat: add Gemini API key settings"
```

---

### Task 6: Switch Form Converter to local provider-neutral OCR

**Files:**
- Modify: `apps/desktop/src/components/FormConverterPage.tsx`
- Modify: `apps/desktop/src/components/FormConverterPage.test.tsx`
- Modify: `apps/desktop/src/lib/errorMessages.ts`
- Modify: `apps/desktop/src/i18n/th.json`

**Interfaces:**
- Consumes: `getAiSettings` and `ocrDocument`
- Produces: Form Converter requires a configured Gemini credential and renders provider-neutral OCR status

- [ ] **Step 1: Replace mocks and add missing-key behavior**

Replace `ocrDmcFormWithGemini` with `getAiSettings` and `ocrDocument`. Add:

```tsx
it("blocks OCR until a Gemini key is configured", async () => {
  mockRpc.getAiSettings.mockResolvedValue({ provider: "gemini", configured: false });
  render(<FormConverterPage onBackHome={vi.fn()} onRevealPath={vi.fn()} onRetryRuntime={vi.fn()} />);
  expect(await screen.findByText("กรุณาตั้งค่า Gemini API key ก่อนใช้ OCR")).toBeInTheDocument();
  expect(screen.getAllByRole("button", { name: "สร้างไฟล์ OCR" })[0]).toBeDisabled();
});
```

- [ ] **Step 2: Run the focused test and verify failure**

Run: `corepack pnpm --dir apps/desktop exec vitest run src/components/FormConverterPage.test.tsx`

Expected: FAIL because the page does not load AI settings and still uses the Gemini-specific RPC.

- [ ] **Step 3: Implement provider-neutral OCR calls**

Load `AiSettings` on mount, disable OCR while status is loading or unconfigured, and call:

```ts
await ocrDocument({
  provider: "gemini",
  sourcePath,
  model: "gemini-3.5-flash",
  processingMode: "batch",
  forceRefresh: false,
});
```

Remove all credit labels from OCR results. Keep page count, cache status, batch mode, confidence, token usage, save-as, and reveal-path behavior.

- [ ] **Step 4: Add provider-neutral Thai error mappings**

Map every `AI_*` code from the design. `AI_API_KEY_REQUIRED` links the user's next action to Home AI settings; rate-limit and timeout errors explicitly permit retry.

- [ ] **Step 5: Verify Form Converter and desktop**

Run:

```powershell
corepack pnpm --dir apps/desktop exec vitest run src/components/FormConverterPage.test.tsx
corepack pnpm run desktop:typecheck
corepack pnpm run desktop:test
corepack pnpm run desktop:build
```

Expected: all commands exit 0.

- [ ] **Step 6: Commit the Form Converter migration**

```powershell
git add apps/desktop/src/components/FormConverterPage.tsx apps/desktop/src/components/FormConverterPage.test.tsx apps/desktop/src/lib/errorMessages.ts apps/desktop/src/i18n/th.json
git commit -m "refactor: use local Gemini provider for OCR"
```

---

### Task 7: Package and security-check the credential backend

**Files:**
- Modify: `apps/sidecar/scripts/build_windows_bundle.ps1`
- Modify: `apps/sidecar/tests/test_ai_credentials.py`
- Modify: `scripts/form_converter_field_test.py`
- Modify: `scripts/check_form_converter_readiness.py`
- Modify: `docs/form-converter-field-test.md`
- Modify: `docs/form-converter-ocr-policy.md`
- Modify: `docs/form-converter-production-readiness.md`

**Interfaces:**
- Consumes: PyInstaller and Windows Credential Manager backend
- Produces: bundled sidecar with working keyring backend and a direct-Gemini opt-in field test

- [ ] **Step 1: Add a secret-leak regression test**

Use a temporary data directory, save `secret-value` into an injected fake store, execute settings and mocked OCR paths, then recursively inspect text files under the temporary data directory:

```python
for path in tmp_path.rglob("*"):
    if path.is_file():
        assert b"secret-value" not in path.read_bytes()
```

Also assert `secret-value` is absent from captured notifications and serialized RPC responses.

- [ ] **Step 2: Run the security test and confirm current gaps**

Run: `.\.venv\Scripts\python -m pytest apps/sidecar/tests/test_ai_credentials.py -v`

Expected: FAIL until all inspected outputs redact the key.

- [ ] **Step 3: Update PyInstaller inputs**

Preserve the user's existing probe fix. Add collection for the credential package/backend and replace obsolete OCR aliases:

```powershell
--hidden-import dmc_sidecar.ai.gemini `
--hidden-import keyring.backends.Windows `
--collect-all keyring `
```

Remove hidden imports for `dmc_sidecar.akson_ocr` and `dmc_sidecar.typhoon_ocr` after their compatibility modules are deleted.

- [ ] **Step 4: Convert field tooling to direct Gemini BYOK**

Change the field test to require `--gemini-api-key` or `GEMINI_API_KEY`, invoke the local provider path, and print only output path, page count, model, processing mode, and usage totals. Remove cloud URL, account credentials, reservations, captures, and releases.

- [ ] **Step 5: Update OCR documentation**

Document direct submission to Gemini, Credential Manager storage, local cache behavior, the explicit field-test command, and the rule that automated tests never call a real provider.

- [ ] **Step 6: Verify security and bundling**

Run:

```powershell
corepack pnpm run sidecar:typecheck
corepack pnpm run sidecar:test
corepack pnpm run form-converter:check
corepack pnpm run sidecar:bundle
```

Expected: all commands exit 0 and `apps/desktop/src-tauri/bundled-sidecar/dmc-sidecar.exe` is produced.

- [ ] **Step 7: Perform the packaged Windows credential check**

Run the packaged application, save the invalid sentinel `dmc-ai-key-leak-sentinel-20260904`, restart the application, and confirm configured status remains true even though connection testing rejects the invalid key. Inspect diagnostics and local data with `rg -a "dmc-ai-key-leak-sentinel-20260904" .dmc-assistant-data` and require no match. Delete the sentinel, restart again, and confirm configured status is false. A separate opt-in field test with a real key verifies provider connectivity without printing or persisting that key.

- [ ] **Step 8: Commit packaging and operational updates**

```powershell
git add apps/sidecar/tests/test_ai_credentials.py scripts/form_converter_field_test.py scripts/check_form_converter_readiness.py docs/form-converter-field-test.md docs/form-converter-ocr-policy.md docs/form-converter-production-readiness.md apps/sidecar/pyproject.toml
git add -p apps/sidecar/scripts/build_windows_bundle.ps1
git diff --cached -- apps/sidecar/scripts/build_windows_bundle.ps1
git commit -m "build: package local Gemini credentials"
```

At the interactive staging prompt, accept only the AI packaging hunks. The cached diff must not contain the user's pre-existing PyInstaller probe change.
