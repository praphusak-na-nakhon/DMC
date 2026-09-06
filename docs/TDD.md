# Technical Design — DMC Assistant

The Tauri/React Windows shell communicates with a local Python sidecar using JSON-RPC. The sidecar owns Playwright, validation, Gemini OCR orchestration, SQLite, reports, and local backup/restore.

```
desktop shell → local JSON-RPC → Python sidecar → local Chromium → DMC portal
                                      └────────→ Gemini for selected OCR input
```

The generation-2 SQLite schema is `job`, `job_record`, and `schema_metadata`; legacy account, job, and checkpoint data is not migrated. Browser profile is the local default. Portal authentication emits `needs_auth`, then the user authenticates in Chromium and resumes.

Gemini is the only registered v1 provider, while the provider interface stays neutral. WinVault-backed Windows Credential Manager stores keys. Settings return only provider/configured state; saving only writes locally and testing is explicit. Selected OCR input goes directly to Gemini; structured cache and reports stay local.

Graduation loads the shipped `packages/module-configs/graduation/v1.json` byte-for-byte as the release configuration. The MSI bundles the sidecar and templates. Build and installation are manual; versions in Tauri, Cargo, and package metadata require manual alignment.
