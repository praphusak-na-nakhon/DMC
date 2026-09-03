# Local-First BYOK Refactor Design

**Date:** 2026-09-04
**Status:** Approved design
**Scope:** Remove cloud-backed commercial services and P-SAR, then convert DMC Assistant to a local-first application using the user's Gemini API key.

## 1. Goal

Refactor DMC Assistant into a free, local-first Windows desktop application. The retained automation and document-processing modules run on the user's device. AI-assisted OCR calls Gemini directly from the Python sidecar with an API key supplied by the user and stored in Windows Credential Manager.

The refactor intentionally breaks compatibility with existing local account, credit, job-history, checkpoint, and cloud data. No migration of those records is required.

## 2. Product Decisions

- The application is free to use.
- There is no account, sign-in, license, wallet, credit, billing, or top-up flow.
- The application has no DMC-owned cloud backend.
- Cloud OCR, telemetry upload, remote module configuration, and application self-update are removed.
- The P-SAR/SAR subsystem is removed completely and may be developed as a separate project later.
- The first AI provider is Gemini.
- Provider-facing interfaces must allow another provider to be added later without restructuring the Form Converter workflow.
- Gemini credentials persist across application restarts in Windows Credential Manager.
- Existing local application data does not need to be preserved.

## 3. Retained Product Scope

The following modules remain:

- Graduation automation
- Current Students automation
- Form Converter
- Student Basic Info workbook generation
- Local browser automation through Playwright
- Local job execution, checkpointing, reports, backups, and diagnostics where they remain relevant
- Static bundled Graduation configuration for portal URLs, selectors, rules, and status mappings
- Manual Windows packaging and release artifact generation

## 4. Target Architecture

```text
React Desktop UI
  -> Tauri command/process bridge
  -> JSON-RPC over sidecar stdin/stdout
  -> Python sidecar
       - Graduation automation
       - Current Students automation
       - Form Converter
       - Student Basic Info
       - AI provider registry
       - Gemini provider
       - Windows credential store
       - local job/checkpoint/report storage
  -> Gemini API over HTTPS with the user's credential
```

The application must not make requests to a DMC-owned backend. Network access remains necessary for the DMC portal and Gemini API.

## 5. Components and Responsibilities

### 5.1 Desktop UI

The desktop UI owns navigation, local workflow state, job presentation, and AI settings presentation.

It must:

- remove account, sign-in, wallet, credit balance, credit estimate, top-up, P-SAR, updater, and remote-config controls;
- provide an AI settings surface on the Home screen;
- allow the user to save, test, and delete a Gemini API key;
- display only credential status, provider name, and the latest connection-test result after a key is saved;
- prevent Form Converter OCR when no Gemini credential is configured;
- use provider-neutral workflow types and error messages while showing Gemini as the only selectable provider in the first release;
- never place the API key in global state, diagnostics, persisted browser storage, or rendered status output.

### 5.2 Tauri Bridge

The Tauri layer remains responsible for sidecar lifecycle, JSON-RPC transport, native file dialogs, file reveal/copy operations, close protection, and application window behavior.

It must remove updater initialization, updater commands, updater events, updater configuration, and updater-specific release wiring. Manual packaging remains supported.

Tauri must not log JSON-RPC request bodies containing credentials.

### 5.3 Python Sidecar

The sidecar remains the trusted local execution boundary. It owns automation, local persistence, AI credential operations, provider selection, OCR execution, cache generation, and reports.

It must remove:

- account client and account session storage;
- credit reservation, capture, release, refund, reconciliation, and recovery;
- cloud telemetry and its local queue;
- remote module-config synchronization, caching, and signature verification;
- P-SAR service and RPC handlers;
- cloud availability and credit eligibility checks from job startup and resume.

Graduation configuration remains a static bundled JSON resource. A small local loader validates the bundled payload but does not fetch or verify a remote envelope.

### 5.4 AI Provider Layer

Introduce a sidecar package with these conceptual units:

```text
dmc_sidecar/ai/
  base.py          # provider-neutral protocols and models
  registry.py      # provider lookup and supported-provider metadata
  gemini.py        # Gemini implementation and Gemini error translation
  credentials.py   # SecretStore protocol and Windows credential implementation
```

The provider contract must cover:

- provider identity and availability;
- credential presence;
- a credential connection test that does not create an OCR job;
- OCR request execution;
- provider-neutral error translation;
- provider metadata required by the UI.

The registry exposes only `gemini` initially. Adding a provider later should require a new provider implementation and registry entry, not changes to the Form Converter orchestration.

### 5.5 Windows Credential Store

The credential implementation stores the Gemini API key in Windows Credential Manager under a stable DMC Assistant service name and a provider-specific account name.

Rules:

- saving replaces the existing key for that provider;
- status checks return only whether a key exists;
- the complete key is never returned to the desktop after saving;
- deletion removes the credential from Windows Credential Manager;
- tests use an injected in-memory fake and never touch the developer's real credential store;
- credential errors are converted to domain error codes without including the secret;
- the packaged sidecar must include the credential backend and its runtime dependencies.

## 6. RPC Contract

Use provider-neutral method names:

- `get_ai_settings`
- `save_ai_api_key`
- `test_ai_connection`
- `delete_ai_api_key`
- `ocr_document`

Every method includes `provider`, with `gemini` as the only accepted value in the first release. Credential responses include no secret or reversible masked value.

The existing Gemini-named OCR RPC and compatibility aliases for AksonOCR and Typhoon OCR are removed because backward compatibility is not required.

Job RPC responses and events remove these fields:

- `credit_reservation_id`
- `credits_reserved`
- `credits_captured`
- `credits_refunded`
- `credit_status`

Account, wallet, module-catalog-from-cloud, P-SAR, config-sync, and updater contracts are removed.

## 7. OCR Data Flow

### Credential setup

1. The user opens AI settings and enters a Gemini API key.
2. The UI sends the key once through `save_ai_api_key`.
3. The sidecar stores the key in Windows Credential Manager.
4. The RPC response reports only configured status.
5. The user may run `test_ai_connection`, which performs a minimal authenticated Gemini metadata request rather than an OCR generation request.

Saving and testing are separate actions so a temporary network failure does not prevent credential storage.

### OCR execution

1. Form Converter sends `ocr_document` with `provider: "gemini"`, source path, model, processing mode, and cache policy.
2. The provider registry resolves the Gemini implementation.
3. The provider retrieves the key from the credential store.
4. The sidecar validates the local source and cache state.
5. The Gemini provider uploads/processes the document directly with Gemini.
6. Structured JSON, usage metadata, and cache files are written locally.
7. The response contains local output metadata and never contains the API key or credit fields.

## 8. Local Persistence Reset

The new SQLite baseline contains only data still needed for local jobs, checkpoints, and job records. Account-session, wallet, credit, and telemetry tables and columns are removed.

Because migration compatibility is explicitly out of scope:

- existing job history and checkpoints may be discarded;
- the development/local database may be recreated from the new baseline;
- old account-scoped browser profiles do not need to be migrated;
- automation uses a single application-local browser profile;
- cloud and rate-limit database artifacts are deleted from the project workspace;
- API credentials never enter SQLite.

Backup and restore must be updated to include only retained local state.

## 9. P-SAR Removal

Remove all P-SAR-specific:

- desktop pages, navigation, types, RPC client functions, copy, and tests;
- sidecar schemas, service code, RPC dispatch branches, reports, and tests;
- Tauri P-SAR template handling and bundled P-SAR template;
- root/template document artifacts used exclusively by P-SAR;
- P-SAR documentation and readiness scripts;
- README, PRD, TDD, UI flow, release checklist, and schema references.

No reusable P-SAR package is retained in this repository. Extraction into another repository is a separate future task.

## 10. Cloud and Commercial-System Removal

Delete the complete `apps/cloud` application and its tests, scripts, database artifacts, and workspace commands.

Also remove:

- desktop account/sign-in/top-up UI and tests;
- sidecar account, wallet, credit, and telemetry modules and tests;
- account and credit fields from shared types and local database records;
- cloud environment/release configuration no longer used by manual packaging;
- obsolete license and credit JSON schemas;
- cloud, account, credit, license, billing, telemetry, remote-config, and updater documentation;
- cloud and commercial-system readiness checks from package scripts and CI.

The shared module catalog becomes a static desktop/local definition. It contains no credit attributes.

## 11. Error Model

Provider implementations translate vendor-specific failures at their boundary into these provider-neutral domain codes:

- `AI_API_KEY_REQUIRED`
- `AI_API_KEY_INVALID`
- `AI_CREDENTIAL_STORE_UNAVAILABLE`
- `AI_PROVIDER_UNAVAILABLE`
- `AI_RATE_LIMITED`
- `AI_REQUEST_TIMEOUT`
- `AI_RESPONSE_INVALID`
- `AI_INPUT_UNSUPPORTED`
- `AI_JOB_FAILED`

The desktop maps every code to concise Thai guidance. Provider detail may be included only when it is safe and contains no credential or student data.

## 12. Security and Privacy

- Student files, OCR outputs, checkpoints, and reports stay on the local device except for documents the user explicitly submits to Gemini.
- The UI must tell the user that selected documents are sent directly to Gemini for processing.
- The Gemini API key must not appear in logs, reports, diagnostics, cache metadata, SQLite, error messages, or test snapshots.
- RPC and provider exceptions must redact sensitive headers and credential-like values.
- Existing PII protections for local logging and reports remain in force.
- Removing the cloud eliminates DMC-owned storage of OCR request payloads and telemetry.

## 13. Testing Strategy

Before deleting dependencies, add or preserve characterization coverage for retained workflows where current coverage is weak, especially application startup, Graduation job startup, Current Students job startup, and sidecar event reconciliation.

Required automated coverage:

- credential save/status/delete behavior through an injected fake store;
- connection-test success and provider-neutral error translation through a fake Gemini client;
- provider registry behavior and unsupported-provider rejection;
- OCR execution and cache reuse without credit or account state;
- RPC validation for all AI settings and OCR methods;
- jobs start and resume without account, cloud, or credit checks;
- API keys never appear in SQLite, cache metadata, logs, diagnostics, or RPC responses;
- desktop AI settings interactions;
- Form Converter blocked state when a key is missing;
- Form Converter success/error rendering with provider-neutral responses;
- static Graduation configuration loading;
- absence of P-SAR, account, credit, remote-config, and updater entry points.

Verification gates:

- desktop TypeScript typecheck;
- desktop tests;
- desktop production build;
- sidecar strict mypy;
- sidecar tests;
- Rust tests and `cargo check`;
- local smoke test;
- packaged Windows build and manual Credential Manager persistence test.

No automated test calls a real Gemini endpoint by default. An explicitly invoked field test may use a developer-supplied credential outside source control.

## 14. Acceptance Criteria

- The application starts and exposes all retained modules without sign-in.
- Graduation and Current Students start without account, credit, or cloud preflight.
- Form Converter requires a configured Gemini key and calls Gemini directly from the sidecar.
- A saved key remains usable after restarting the application.
- Deleting the key immediately blocks new OCR requests.
- No application path calls a DMC-owned cloud backend.
- No P-SAR UI, source, RPC, template, test, script, or documentation remains.
- No user-facing account, credit, license, updater, or remote-config language remains.
- The repository no longer contains `apps/cloud`.
- Retained desktop, sidecar, Tauri, smoke, and packaging verification gates pass.

## 15. Implementation Constraints

- Preserve the behavior of retained automation and document-conversion workflows except where this design explicitly changes it.
- Refactor in testable vertical slices; each slice must leave the repository buildable.
- Do not combine unrelated cleanup of the large Current Students or Form Converter modules with this removal project.
- Keep the user's existing uncommitted `apps/sidecar/scripts/build_windows_bundle.ps1` change intact and resolve any necessary overlap deliberately during implementation.
- Do not commit credentials, student data, local databases, generated reports, or bundled build output.
