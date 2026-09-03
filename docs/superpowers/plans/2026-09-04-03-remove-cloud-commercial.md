# Remove Cloud and Commercial Systems Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the DMC-owned cloud, account/credit/telemetry systems, remote configuration, and self-updater after local Gemini BYOK is operational.

**Architecture:** Simplify the sidecar job runtime and persistence first, then remove desktop commercial state, replace remote Graduation config with a static loader, remove Tauri updater/release configuration, and finally delete cloud source and obsolete contracts. Existing local data is intentionally reset.

**Tech Stack:** React 18, TypeScript, Vitest, Python 3.11+, Pydantic 2, SQLite, pytest, Tauri 2, Rust, GitHub Actions

**Spec:** `docs/superpowers/specs/2026-09-04-local-first-byok-refactor-design.md`

## Global Constraints

- Complete `2026-09-04-02-local-gemini-byok.md` before starting this plan.
- The application must make no request to a DMC-owned backend.
- Preserve direct Gemini and DMC portal network access.
- Existing account, credit, telemetry, job history, checkpoints, and cloud data do not require migration.
- Manual Windows packaging remains; self-update is removed.
- Keep the user's existing `build_windows_bundle.ps1` PyInstaller probe fix.

---

### Task 1: Remove account, credit, and telemetry from sidecar runtime

**Files:**
- Modify: `apps/sidecar/dmc_sidecar/rpc.py`
- Modify: `apps/sidecar/dmc_sidecar/runtime.py`
- Modify: `apps/sidecar/dmc_sidecar/job_store.py`
- Modify: `apps/sidecar/dmc_sidecar/schemas.py`
- Modify: `apps/sidecar/dmc_sidecar/config.py`
- Modify: `apps/sidecar/dmc_sidecar/modules/graduation.py`
- Modify: `apps/sidecar/dmc_sidecar/modules/current_students.py`
- Modify: `apps/sidecar/tests/test_rpc.py`
- Modify: `apps/sidecar/tests/test_workflow_e2e.py`
- Delete: `apps/sidecar/dmc_sidecar/account_client.py`
- Delete: `apps/sidecar/dmc_sidecar/account_store.py`
- Delete: `apps/sidecar/dmc_sidecar/telemetry.py`
- Delete: `apps/sidecar/tests/test_account_client.py`
- Delete: `apps/sidecar/tests/test_telemetry.py`

**Interfaces:**
- Consumes: local module registry, browser runtime, `JobStore`
- Produces: `JobManager.start_job(job_id, module_name, excel_path, options)` and credit-free job snapshots/events

- [ ] **Step 1: Replace credit-start tests with free-start tests**

Add a focused contract:

```python
@pytest.mark.parametrize("module_name", ["graduation", "currentStudents"])
def test_live_job_starts_without_account_or_credit(
    monkeypatch,
    tmp_path: Path,
    module_name: str,
) -> None:
    monkeypatch.setattr(config, "default_data_dir", lambda: tmp_path)
    server = RpcServer(emit_notification=lambda payload: None, secret_store=InMemorySecretStore())
    monkeypatch.setattr("dmc_sidecar.rpc.get_browser_runtime_status", lambda: _ready_browser_status(tmp_path))
    started: dict[str, object] = {}
    monkeypatch.setattr(server.job_manager, "start_job", lambda **kwargs: started.update(kwargs))

    response = _rpc_call(server, "start_job", {
        "job_id": "job-local-free",
        "module": module_name,
        "excel_path": "C:\\data\\m3.xlsx",
        "options": {"dry_run": False},
    })

    assert response["result"] == {"accepted": True, "job_id": "job-local-free"}
    assert set(started) == {"job_id", "module_name", "excel_path", "options"}
```

Add an equivalent resume test proving no reservation is created. This parameterization is the retained-workflow gate for both browser automation modules.

- [ ] **Step 2: Run focused tests and verify failure**

Run: `.\.venv\Scripts\python -m pytest apps/sidecar/tests/test_rpc.py -k "without_account_or_credit" -v`

Expected: FAIL because live start currently requires account state and returns credit fields.

- [ ] **Step 3: Simplify runtime data structures**

Change the job context and manager signatures to:

```python
@dataclass
class JobContext:
    job_id: str
    options: dict[str, object]
    control: JobControl
    snapshot: JobSnapshot
    job_store: JobStore
    emit_event: Callable[[dict[str, Any]], None]


def start_job(
    self,
    *,
    job_id: str,
    module_name: str,
    excel_path: Path,
    options: dict[str, object],
) -> None:
```

Remove account store, telemetry client, credit fields, finalization helpers, and stale-reservation recovery from `runtime.py`.

- [ ] **Step 4: Simplify RPC startup and resume**

`start_job` validates browser availability, creates a pending job, and starts `JobManager` directly. Return exactly:

```python
{"accepted": True, "job_id": start_params.job_id}
```

Delete account/wallet/catalog RPC methods, OCR credit wrappers, background reservation threads, and credit recovery helpers. Resume uses the same four-argument job-manager interface.

- [ ] **Step 5: Remove account-scoped browser profiles**

Add `automation_profile_dir()` in `config.py` returning `profiles_dir() / "default"`. Update Graduation and Current Students modules to use it without reading an account session.

- [ ] **Step 6: Delete commercial sidecar modules and obsolete tests**

Delete the account and telemetry files listed above. Remove account, wallet, reservation, and credit models from `schemas.py`.

- [ ] **Step 7: Run sidecar verification**

Run:

```powershell
.\.venv\Scripts\python -m pytest apps/sidecar/tests/test_rpc.py apps/sidecar/tests/test_workflow_e2e.py -v
corepack pnpm run sidecar:typecheck
corepack pnpm run sidecar:test
```

Expected: free-start/resume tests and the remaining suite pass.

- [ ] **Step 8: Commit runtime simplification**

```powershell
git add apps/sidecar/dmc_sidecar apps/sidecar/tests
git commit -m "refactor: remove sidecar account and credit runtime"
```

---

### Task 2: Reset local persistence to retained job data

**Files:**
- Modify: `apps/sidecar/dmc_sidecar/db.py`
- Modify: `apps/sidecar/dmc_sidecar/job_store.py`
- Modify: `apps/sidecar/dmc_sidecar/backup.py`
- Modify: `apps/sidecar/tests/test_backup.py`
- Modify: `apps/sidecar/tests/test_rpc.py`

**Interfaces:**
- Consumes: retained job/checkpoint/job-record persistence
- Produces: schema generation 2 containing only `job`, `job_record`, and schema metadata; old databases are reset

- [ ] **Step 1: Write a destructive-reset schema test**

Create an old-shape database fixture containing `account_session`, `telemetry_queue`, and a credit column, then run `migrate_database`:

```python
metadata = get_database_metadata(config.sqlite_path())
assert metadata["schema_generation"] == 2
assert set(metadata["tables"]) == {"job", "job_record", "schema_metadata"}
assert "credit_status" not in metadata["job_columns"]
```

Also update backup tests to stop constructing `WalletSnapshot`.

- [ ] **Step 2: Run persistence tests and verify failure**

Run: `.\.venv\Scripts\python -m pytest apps/sidecar/tests/test_backup.py -v`

Expected: FAIL because the current schema contains account, telemetry, and credit fields.

- [ ] **Step 3: Replace migrations with a generation-based baseline**

Define `SCHEMA_GENERATION = 2`. On open, read `schema_metadata`; if the generation is absent or different, drop local application tables and create a clean schema in one transaction. The new `job` table keeps job status, source, counts, paths, summaries, timestamps, and checkpoint JSON but has no account or credit columns.

- [ ] **Step 4: Simplify `JobStore` serialization**

Remove `update_credit_status`, stale-credit queries, credit arguments to `create_pending_job`, and credit keys from status dictionaries. Keep status transitions, checkpoint persistence, record summaries, archive behavior, and completion reports.

- [ ] **Step 5: Restrict backup contents**

Backups include the new database plus retained reports and OCR cache. Remove remote-config cache from `_iter_data_files` and restore cleanup. Credential Manager contents are never backed up.

- [ ] **Step 6: Verify persistence and runtime**

Run:

```powershell
.\.venv\Scripts\python -m pytest apps/sidecar/tests/test_backup.py apps/sidecar/tests/test_job_completion_summary.py apps/sidecar/tests/test_rpc.py -v
corepack pnpm run sidecar:typecheck
corepack pnpm run sidecar:test
```

Expected: schema reset, backup round trip, job storage, and sidecar suite pass.

- [ ] **Step 7: Commit persistence reset**

```powershell
git add apps/sidecar/dmc_sidecar/db.py apps/sidecar/dmc_sidecar/job_store.py apps/sidecar/dmc_sidecar/backup.py apps/sidecar/tests
git commit -m "refactor: reset local job persistence"
```

---

### Task 3: Remove account and credit state from the desktop

**Files:**
- Modify: `apps/desktop/src/App.tsx`
- Modify: `apps/desktop/src/components/ModuleHome.tsx`
- Modify: `apps/desktop/src/components/ModuleHome.test.tsx`
- Modify: `apps/desktop/src/components/GraduationWizard.tsx`
- Modify: `apps/desktop/src/components/CurrentStudentsPage.tsx`
- Modify: `apps/desktop/src/components/ExistingJobsPanel.test.tsx`
- Modify: `apps/desktop/src/stores/useJobStore.ts`
- Modify: `apps/desktop/src/lib/appUi.ts`
- Modify: `apps/desktop/src/lib/appUi.test.ts`
- Modify: `apps/desktop/src/lib/moduleCatalog.ts`
- Modify: `apps/desktop/src/lib/rpcClient.ts`
- Modify: `apps/desktop/src/types/contracts.ts`
- Modify: `apps/desktop/src/types/contracts.test.ts`
- Modify: `apps/desktop/src/i18n/th.json`
- Delete: `apps/desktop/src/components/AccountSignInPage.tsx`
- Delete: `apps/desktop/src/components/CreditTopupPage.tsx`
- Delete: `apps/desktop/src/components/CreditTopupPage.test.tsx`

**Interfaces:**
- Consumes: credit-free job RPC responses and retained persistence from Tasks 1-2
- Produces: local-only navigation and job state; static module definitions without pricing attributes

- [ ] **Step 1: Rewrite Home tests for local-only behavior**

Use props containing only `onOpenModule`, `connectionState`, `errorMessage`, and `onRetryRuntime`. Assert there are no sign-in, top-up, balance, credit, or license controls:

```tsx
expect(screen.queryByText(/เครดิต|เข้าสู่ระบบ|License/i)).not.toBeInTheDocument();
```

- [ ] **Step 2: Run the focused desktop tests and verify failure**

Run: `corepack pnpm --dir apps/desktop exec vitest run src/components/ModuleHome.test.tsx src/lib/appUi.test.ts`

Expected: FAIL because commercial UI and helpers still exist.

- [ ] **Step 3: Remove commercial navigation and startup calls**

Delete account state, handlers, refresh effects, sign-in/top-up routes, module-catalog cloud loading, credit start guards, credit notifications, and account diagnostics from `App.tsx`. Startup should initialize the sidecar, database status, jobs, browser status, and retained local settings only.

- [ ] **Step 4: Simplify components and static module metadata**

Remove account/config/credit props from Home and Graduation. Remove pricing fields from `ModuleDefinition`:

```ts
export type ModuleDefinition = {
  id: ModuleId;
  status: ModuleStatus;
  icon: typeof GraduationCap;
  contract: ModuleContract;
};
```

Delete sign-in/top-up components and obsolete tests.

- [ ] **Step 5: Remove commercial types and reducers**

Delete `WalletSnapshot`, `AccountStatus`, cloud `ModuleCatalogResponse`, all credit fields/parsers, `describeCreditStatus`, account sanitization, and credit-specific event handling. `StartJobResponse` becomes:

```ts
export type StartJobResponse = {
  accepted: boolean;
  job_id: string;
};
```

- [ ] **Step 6: Verify the desktop slice**

Run:

```powershell
corepack pnpm run desktop:typecheck
corepack pnpm run desktop:test
corepack pnpm run desktop:build
```

Expected: all commands exit 0 and no commercial UI remains.

- [ ] **Step 7: Commit desktop simplification**

```powershell
git add apps/desktop/src
git commit -m "refactor: remove desktop commercial flows"
```

---

### Task 4: Replace remote Graduation config with a static loader

**Files:**
- Modify: `apps/sidecar/dmc_sidecar/config.py`
- Modify: `apps/sidecar/dmc_sidecar/module_config.py`
- Modify: `apps/sidecar/dmc_sidecar/modules/graduation.py`
- Modify: `apps/sidecar/dmc_sidecar/rpc.py`
- Modify: `apps/sidecar/dmc_sidecar/schemas.py`
- Modify: `apps/sidecar/tests/test_config.py`
- Modify: `apps/sidecar/tests/test_module_config.py`
- Modify: `apps/sidecar/tests/test_rpc.py`
- Modify: `apps/desktop/src/App.tsx`
- Modify: `apps/desktop/src/components/GraduationWizard.tsx`
- Modify: `apps/desktop/src/lib/rpcClient.ts`
- Modify: `apps/desktop/src/types/contracts.ts`
- Delete: `packages/shared-schemas/config-signing/keys.json`

**Interfaces:**
- Consumes: `packages/module-configs/graduation/v1.json`
- Produces: `load_bundled_module_config("graduation") -> dict[str, object]`; no sync/status RPC

- [ ] **Step 1: Write the static-loader contract**

```python
def test_bundled_graduation_config_loads_without_cloud_or_signature(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(config, "module_configs_root", lambda: tmp_path)
    module_dir = tmp_path / "graduation"
    module_dir.mkdir()
    (module_dir / "v1.json").write_text(json.dumps({
        "module": "graduation",
        "version": "1",
        "login_url": "https://example.test/login",
        "target_url_template": "https://example.test/students?level={level_code}",
        "selectors": {},
        "status_code_map": {},
        "level_rules": {},
    }))
    payload = load_bundled_module_config("graduation")
    assert payload["login_url"] == "https://example.test/login"
```

- [ ] **Step 2: Run the module-config tests and verify failure**

Run: `.\.venv\Scripts\python -m pytest apps/sidecar/tests/test_module_config.py -v`

Expected: FAIL because the current loader expects signed envelopes and cloud synchronization.

- [ ] **Step 3: Implement and wire the static loader**

Validate the bundled JSON with a strict local Pydantic model, return the config payload, and raise `CONFIG_BUNDLED_INVALID` for malformed data. Graduation loads it before validation/run. Remove cloud URL, signing-key, cache, and sync functions.

- [ ] **Step 4: Remove config RPC/UI**

Delete `get_module_config_status` and `sync_module_config` dispatch/client/contracts, config status from the store, the sync button, and configuration telemetry messages.

- [ ] **Step 5: Verify static configuration**

Run:

```powershell
.\.venv\Scripts\python -m pytest apps/sidecar/tests/test_config.py apps/sidecar/tests/test_module_config.py apps/sidecar/tests/test_graduation_module.py -v
corepack pnpm run sidecar:typecheck
corepack pnpm run desktop:typecheck
```

Expected: tests and both typechecks pass.

- [ ] **Step 6: Commit static configuration**

```powershell
git add apps/sidecar/dmc_sidecar/config.py apps/sidecar/dmc_sidecar/module_config.py apps/sidecar/dmc_sidecar/modules/graduation.py apps/sidecar/dmc_sidecar/rpc.py apps/sidecar/dmc_sidecar/schemas.py apps/sidecar/tests/test_config.py apps/sidecar/tests/test_module_config.py apps/sidecar/tests/test_rpc.py
git add apps/desktop/src/App.tsx apps/desktop/src/components/GraduationWizard.tsx apps/desktop/src/lib/rpcClient.ts apps/desktop/src/types/contracts.ts packages/shared-schemas/config-signing/keys.json
git commit -m "refactor: use bundled graduation config only"
```

---

### Task 5: Remove Tauri updater and cloud release configuration

**Files:**
- Modify: `apps/desktop/src-tauri/src/main.rs`
- Modify: `apps/desktop/src-tauri/Cargo.toml`
- Modify: `apps/desktop/src-tauri/Cargo.lock`
- Modify: `apps/desktop/src-tauri/tauri.conf.json`
- Modify: `apps/desktop/src-tauri/tauri.package.conf.json`
- Modify: `apps/desktop/src/App.tsx`
- Modify: `apps/desktop/src/lib/rpcClient.ts`
- Modify: `apps/desktop/src/types/contracts.ts`
- Modify: `package.json`
- Modify: `.github/workflows/release.yml`
- Modify: `.gitignore`
- Delete: `release/environments/development.json`
- Delete: `release/environments/staging.json`
- Delete: `release/environments/production.json`
- Delete: `scripts/write_release_config.py`
- Delete: `scripts/create_release_manifest.py`
- Delete: `apps/desktop/src-tauri/release-config/.gitkeep`

**Interfaces:**
- Consumes: Tauri sidecar bridge and manual packaging
- Produces: application binary without updater plugin; GitHub release publishes installable artifacts without updater manifest/signature

- [ ] **Step 1: Remove updater serialization tests and add a retained-command Rust test**

Keep `rpc_timeout_tests` and add/retain a test proving `get_account_status` is no longer special while long-running local methods still receive the long timeout. Remove updater-only Rust tests.

- [ ] **Step 2: Delete updater implementation and configuration**

Remove `tauri-plugin-updater`, `UpdaterExt`, pending update state, release-config parsing, updater commands/events, plugin registration, and updater command registration. Remove updater plugin config and release-config resources from Tauri JSON.

- [ ] **Step 3: Simplify package and release workflow**

Set packaging to:

```json
"desktop:package": "corepack pnpm run sidecar:bundle && corepack pnpm --dir apps/desktop exec tauri build --config src-tauri/tauri.package.conf.json"
```

Delete release-config and manifest scripts. The release workflow installs only sidecar dependencies, runs `ci:verify`, builds the sidecar and Tauri package, optionally Authenticode-signs MSI files, and publishes MSI/installer artifacts without `latest.json`, updater `.sig`, updater keys, or cloud variables.

- [ ] **Step 4: Remove updater UI contracts and state**

Delete updater types, RPC client methods/listeners, `App.tsx` updater state/effects/handlers, and updater copy.

- [ ] **Step 5: Regenerate and verify Rust dependencies**

Run:

```powershell
cargo check --manifest-path apps/desktop/src-tauri/Cargo.toml
cargo test --manifest-path apps/desktop/src-tauri/Cargo.toml
corepack pnpm run desktop:typecheck
corepack pnpm run desktop:test
corepack pnpm run desktop:build
```

Expected: Cargo updates `Cargo.lock`; all commands exit 0.

- [ ] **Step 6: Commit updater removal**

```powershell
git add apps/desktop package.json release scripts/write_release_config.py scripts/create_release_manifest.py .github/workflows/release.yml .gitignore
git commit -m "refactor: remove self-update infrastructure"
```

---

### Task 6: Delete cloud source and obsolete shared schemas

**Files:**
- Delete: `apps/cloud/`
- Delete: `docs/cloud-staging-account-credits.md`
- Delete: `packages/shared-schemas/api/license.activate.request.schema.json`
- Delete: `packages/shared-schemas/api/license.activate.response.schema.json`
- Delete: `packages/shared-schemas/api/license.heartbeat.response.schema.json`
- Delete: `packages/shared-schemas/api/telemetry.request.schema.json`
- Delete: `packages/shared-schemas/ipc/get_license_status.request.schema.json`
- Delete: `packages/shared-schemas/ipc/get_license_status.response.schema.json`
- Delete: `packages/shared-schemas/ipc/refresh_license_status.request.schema.json`
- Delete: `packages/shared-schemas/ipc/refresh_license_status.response.schema.json`
- Delete: `packages/shared-schemas/ipc/get_module_config_status.request.schema.json`
- Delete: `packages/shared-schemas/ipc/get_module_config_status.response.schema.json`
- Delete: `packages/shared-schemas/ipc/sync_module_config.request.schema.json`
- Delete: `packages/shared-schemas/ipc/sync_module_config.response.schema.json`
- Modify: `packages/shared-schemas/README.md`
- Modify: `package.json`
- Modify: `.github/workflows/ci.yml`
- Modify: `pnpm-lock.yaml`

**Interfaces:**
- Consumes: completed local-only desktop and sidecar
- Produces: workspace and CI with no cloud package or obsolete commercial/config contracts

- [ ] **Step 1: Remove cloud commands from workspace configuration**

Delete `cloud:dev`, `cloud:backup`, `cloud:restore`, and `cloud:test`; remove `cloud:test` from `ci:verify`. CI installs `-e .\apps\sidecar[dev]` only and has no Cloud Tests step.

- [ ] **Step 2: Delete cloud and obsolete schemas**

Delete the listed paths. Keep active IPC schemas for ping, Excel validation, browser status, and browser bootstrap. Update the shared-schema README so it no longer claims cloud/API coverage.

- [ ] **Step 3: Refresh workspace metadata**

Run: `corepack pnpm install --lockfile-only`

Expected: `pnpm-lock.yaml` contains no `apps/cloud` importer.

- [ ] **Step 4: Verify cloud references are gone from executable code**

Run:

```powershell
rg -n -i "apps/cloud|cloud:test|cloud:dev|/v1/(auth|wallet|credits|ocr|telemetry|config|updates)|DMC_CLOUD_" apps packages scripts package.json .github -g "!**/target/**"
```

Expected: no matches.

- [ ] **Step 5: Commit cloud deletion**

```powershell
git add apps/cloud packages/shared-schemas package.json pnpm-lock.yaml .github/workflows/ci.yml docs/cloud-staging-account-credits.md
git commit -m "refactor: remove cloud application"
```

---

### Task 7: Rewrite product and operations documentation

**Files:**
- Modify: `README.md`
- Modify: `docs/PRD.md`
- Modify: `docs/TDD.md`
- Modify: `docs/ui-flow.md`
- Modify: `docs/ipc-and-api-schemas.md`
- Modify: `docs/production-readiness.md`
- Modify: `docs/form-converter-production-readiness.md`
- Modify: `docs/form-converter-ocr-policy.md`
- Modify: `docs/form-converter-field-test.md`
- Modify: `scripts/smoke_local.py`
- Modify: `scripts/check_release_readiness.py`
- Modify: `scripts/check_form_converter_readiness.py`

**Interfaces:**
- Consumes: final local-only architecture and commands
- Produces: documentation, smoke checks, and readiness checks matching shipped behavior

- [ ] **Step 1: Update smoke and readiness behavior**

`smoke_local.py` must exercise ping, database status, browser status, static Graduation validation, and a local dry run without cloud environment variables or license/account methods. Release readiness checks only bundle resources, manual packaging configuration, and Git ignore rules. Form Converter readiness checks the credential backend dependency and local Gemini provider registration without printing a key.

- [ ] **Step 2: Rewrite active documentation from the final architecture**

README and product documents must describe the four retained modules, local-only execution, direct Gemini document submission, Windows Credential Manager, static bundled Graduation config, and manual application upgrades. Remove account, license, credit, billing, cloud deployment, telemetry, remote config, updater, and P-SAR requirements.

- [ ] **Step 3: Run terminology gates**

Run the product-copy gate:

```powershell
rg -n -i "sign.?in|wallet|credit|topup|billing|license|telemetry|remote config|updater|apps/cloud|P-SAR|psar" README.md docs apps/desktop/src -g "!docs/superpowers/**"
rg -n "AccountClient|AccountStore|WalletSnapshot|credit_reservation|telemetry_queue|sync_module_config|tauri_plugin_updater|DMC_CLOUD_|apps/cloud" apps packages scripts package.json .github -g "!**/target/**"
```

Expected: no product-copy or obsolete-runtime matches. The provider-specific Windows Credential Manager account name is intentionally allowed in `ai/credentials.py`; it is not an application account system.

- [ ] **Step 4: Run full verification**

Run:

```powershell
corepack pnpm run desktop:typecheck
corepack pnpm run desktop:test
corepack pnpm run desktop:build
cargo test --manifest-path apps/desktop/src-tauri/Cargo.toml
cargo check --manifest-path apps/desktop/src-tauri/Cargo.toml
corepack pnpm run sidecar:typecheck
corepack pnpm run sidecar:test
corepack pnpm run release:check
corepack pnpm run form-converter:check
corepack pnpm run smoke:local
```

Expected: every command exits 0.

- [ ] **Step 5: Commit final documentation and checks**

```powershell
git add README.md docs/PRD.md docs/TDD.md docs/ui-flow.md docs/ipc-and-api-schemas.md docs/production-readiness.md docs/form-converter-production-readiness.md docs/form-converter-ocr-policy.md docs/form-converter-field-test.md
git add scripts/smoke_local.py scripts/check_release_readiness.py scripts/check_form_converter_readiness.py
git commit -m "docs: describe local-first DMC Assistant"
```

---

### Task 8: Remove disposable local cloud and credit data

**Files:**
- Delete local artifact: `.cloud-staging.sqlite3`
- Delete local artifact: `rate-limit.sqlite3`
- Reset local artifact: `.dmc-assistant-data/desktop.sqlite3`

**Interfaces:**
- Consumes: explicit product decision that existing local data does not need preservation
- Produces: local workspace containing only the new schema on the next run

- [ ] **Step 1: Resolve and verify exact artifact paths**

Use `Resolve-Path` for the three explicit targets and verify each resolved path starts with `C:\Workspace\PersonalProjects\dmc\`. Do not use globs or recursive deletion against the workspace root.

- [ ] **Step 2: Remove only the verified disposable artifacts**

Use `Remove-Item -LiteralPath` for the two cloud databases and the local desktop database. Leave reports, OCR outputs, and unrelated user files untouched unless the user separately requests their deletion.

- [ ] **Step 3: Recreate and inspect the local schema**

Run the sidecar database-status RPC or backup test fixture, then inspect metadata.

Expected: schema generation 2 and only retained local tables.

- [ ] **Step 4: Report destructive cleanup**

Tell the user exactly which database files were removed and that they are not recoverable unless separately backed up.

---

### Task 9: Final acceptance verification

**Files:**
- Review: all implementation commits from Plans 01-03

**Interfaces:**
- Consumes: completed local-only refactor
- Produces: evidence for every design acceptance criterion

- [ ] **Step 1: Verify repository shape**

Run:

```powershell
Test-Path apps/cloud
Test-Path apps/sidecar/dmc_sidecar/p_sar_readiness.py
Test-Path apps/desktop/src/components/PsarReadinessPage.tsx
```

Expected: all three print `False`.

- [ ] **Step 2: Verify retained modules and network boundaries**

Run static reference searches confirming four local modules, Gemini provider registration, no DMC cloud URLs, and no updater initialization. Inspect Form Converter to confirm it calls `ocr_document` with `provider: "gemini"`.

- [ ] **Step 3: Run CI-equivalent verification from a clean shell**

Run: `corepack pnpm run ci:verify`

Expected: exit 0 with desktop, Rust, sidecar, release, and Form Converter checks passing.

- [ ] **Step 4: Build and manually inspect the Windows package**

Run: `corepack pnpm run desktop:package`

Expected: an installable Windows artifact containing the sidecar, retained templates, static Graduation config, and Credential Manager backend; no cloud, P-SAR, config-signing, release-config, or updater resources.
