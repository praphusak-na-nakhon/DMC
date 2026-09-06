# Local IPC Schemas

Desktop and sidecar exchange newline-delimited JSON-RPC only on the local process boundary. Every request is `{ "jsonrpc":"2.0", "id":string|number, "method":string, "params":object }`; every response contains the same `id` plus either `result` or `error`.

```json
{ "jsonrpc":"2.0", "id":"req-1", "error": { "code":"AI_API_KEY_REQUIRED", "message":"...", "details":{} } }
```

Errors use stable domain codes and always carry an object `details` (possibly empty); `message` is diagnostic text and must not contain a key or raw PII. The desktop maps known codes to Thai next-action copy.

## Readiness and local data

| Method | Required params | Result |
|---|---|---|
| `ping` | `{}` | `{ "value":"pong", "sidecar_version":string }` |
| `get_database_status` | `{}` | `{ path, schema_generation:2, tables:["job","job_record","schema_metadata"], job_columns:string[] }` |
| `get_browser_runtime_status` | `{}` | full browser-runtime status below |
| `bootstrap_browser_runtime` | `{}` | same browser-runtime status; emits progress below |
| `create_backup` | `{}` or `{ path }` | `{ backup_path }` |
| `restore_backup` | `{ path }` | `{ restored_from, safety_backup_path, database_path }` |

Backup content is local database, reports, and OCR cache only. Browser profile, credential-store secrets, and config cache never appear in a backup result.

Browser-runtime status contains `{ state:"ready"|"missing"|"installing"|"failed", installed:boolean, install_dir:string, executable_path:string|null, bootstrap_supported:boolean, bootstrap_performed:boolean, estimated_download_bytes:number|null, required_components:[{ name:string, install_location:string, download_url:string, download_bytes:number|null }], message:string|null, guidance:string|null, last_error:string|null, log_tail:string[] }`. Bootstrap additionally emits `{ phase:"checking"|"installing"|"verifying"|"ready"|"failed", message:string, percent:number|null, detail:string|null }` progress events.

## AI settings and OCR

Only `{ "provider":"gemini" }` is valid in v1. Provider-neutral fields remain deliberate interface boundaries. `get_ai_settings`, `test_ai_connection`, and `delete_ai_api_key` each require exactly that provider request; `save_ai_api_key` requires `{ provider:"gemini", api_key }`.

```json
// get_ai_settings / save_ai_api_key / delete_ai_api_key result
{ "provider":"gemini", "configured":true }

// save_ai_api_key params
{ "provider":"gemini", "api_key":"submitted-only" }

// test_ai_connection result
{ "provider":"gemini", "ok":true, "tested_at":"ISO-8601", "message":"..." }
```

`save_ai_api_key` stores only in Windows Credential Manager and never returns `api_key`; it does not call Gemini. `test_ai_connection` is the explicit minimal authenticated metadata request. Missing key, invalid key, and unavailable credential-store conditions are structured errors.

```json
// ocr_document params (model, processing_mode, force_refresh have defaults)
{ "provider":"gemini", "source_path":"C:\\private\\form.pdf", "model":"gemini-3.5-flash", "processing_mode":"standard", "force_refresh":false }
// result
{ "module":"formConverter", "provider":"gemini", "model":"...", "processing_mode":"standard|batch", "source_path":"...", "markdown_path":"...", "structured_json_path":"...|null", "output_format":"structured_json", "cached":false, "pages_processed":1, "pages_estimated":1, "average_confidence":0.9|null, "usage_metadata":{}|null, "provider_job_id":"...|null", "provider_job_state":"...|null", "file_sha256":"...", "created_at":"ISO-8601" }
```

OCR output paths and usage metadata are local result data. The selected document is sent directly to Gemini; no secret is included in this contract.

## Jobs and module operations

`validate_excel({ module:"graduation", path })` returns `{ module, detected_level, rows_total, rows_accepted, warnings, preview }`. `start_job` requires `{ job_id, module:"graduation", excel_path, options }`, where options include `dry_run`, `min_score`, `resume_current`, and `stop_on_review`; its result is `{ accepted, job_id }`.

`get_job_status`, `pause_job`, `resume_job`, `resume_existing_job`, and `cancel_job` all require `{ job_id }`. `get_job_status` returns the local snapshot with counts and optional report paths; pause/resume/cancel return `{ job_id, status }`; `resume_existing_job` returns `{ accepted, job_id, status }`. `list_jobs` accepts optional `{ limit }` and returns `{ items }`; `archive_old_jobs` accepts optional `{ keep_latest:int }` (default `20`) and returns `{ archived, kept }`. Current Students validation/export and Student Basic Info export accept selected local paths and return local output paths, warnings, and summaries.

Events are `progress`, `record_done`, `needs_auth`, `job_done`, `job_stopped`, and `error`. `progress` contains `job_id`, processed/succeeded/failed counts, optional total/page, and authentication state. `needs_auth` contains `{ job_id, reason }` and means the DMC portal requires the user to authenticate in local Chromium. `job_done` follows report persistence and contains `{ job_id, status, processed, succeeded, failed, report_path, review_report_path }`.

A dry run may navigate and match but never submits a portal save. Paths, previews, reports, OCR outputs, and errors can contain PII and must not be broadly logged.
