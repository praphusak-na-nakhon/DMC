# Technical Design — DMC Assistant

The Tauri/React Windows shell communicates with a local Python sidecar using JSON-RPC. The sidecar owns Playwright, validation, Gemini OCR orchestration, SQLite, reports, and local backup/restore.

```
desktop shell → local JSON-RPC → Python sidecar → local Chromium → DMC portal
                                      └────────→ Gemini for selected OCR input
```

The generation-2 SQLite schema is `job`, `job_record`, and `schema_metadata`; legacy account, job, and checkpoint data is not migrated. Browser profile is the local default. Portal authentication emits `needs_auth`, then the user authenticates in Chromium and resumes.

The desktop owns user interaction, file selection, Thai error presentation, and local sidecar lifecycle. The sidecar owns validation, browser work, job persistence, report paths, and cancellation safety. A job persists processed, succeeded, failed, checkpoint, report, and review-report state so the UI can query and resume a supported local job after restart.

Gemini is the only registered v1 provider, while the provider interface stays neutral. WinVault-backed Windows Credential Manager stores keys. Settings return only provider/configured state; saving only writes locally and testing is explicit. Selected OCR input goes directly to Gemini; structured cache and reports stay local.

Graduation loads the shipped `packages/module-configs/graduation/v1.json` byte-for-byte as the release configuration. The MSI bundles the sidecar and templates. Build and installation are manual; versions in Tauri, Cargo, and package metadata require manual alignment.

The smoke contract is intentionally source-local: a synthetic loopback portal validates `ping`, generation-2 database status, local browser readiness, static Graduation validation, portal-auth pause/resume, and a dry run with no portal save. It uses temporary data and no real portal or Gemini request.
