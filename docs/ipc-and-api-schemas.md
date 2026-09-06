# Local IPC Schemas

Desktop and sidecar exchange newline-delimited JSON-RPC only on the local process boundary. Every request is `{ "jsonrpc":"2.0", "id":string|number, "method":string, "params":object }`; every response contains the same `id` plus either `result` or `error`.

```json
{ "jsonrpc":"2.0", "id":"req-1", "error": { "code":"AI_API_KEY_REQUIRED", "message":"..." } }
```

Errors use stable domain codes; `message` is diagnostic text and must not contain a key or raw PII. The desktop maps known codes to Thai next-action copy.

## Readiness and local data

| Method | Required params | Result |
|---|---|---|
| `ping` | `{}` | `{ "value":"pong" }` |
| `get_database_status` | `{}` | `{ path, schema_generation:2, tables:["job","job_record","schema_metadata"], job_columns:string[] }` |
| `get_browser_runtime_status` | `{}` | `{ state:"ready"|"missing"|"installing"|"failed", installed:boolean, install_dir, executable_path?, guidance? }` |
| `create_backup` | `{}` | `{ backup_path }` |
| `restore_backup` | `{ archive_path }` | `{ restored_from, safety_backup_path, database_path }` |

Backup content is local database, reports, and OCR cache only. Browser profile, credential-store secrets, and config cache never appear in a backup result.

## AI settings and OCR

Only `{ "provider":"gemini" }` is valid in v1. Provider-neutral fields remain deliberate interface boundaries.

```json
// get_ai_settings / save_ai_api_key / delete_ai_api_key result
{ "provider":"gemini", "configured":true }

// save_ai_api_key params
{ "provider":"gemini", "api_key":"submitted-only" }

// test_ai_connection result
{ "provider":"gemini", "ok":true, "model":"gemini-3.5-flash" }
```

`save_ai_api_key` stores only in Windows Credential Manager and never returns `api_key`; it does not call Gemini. `test_ai_connection` is the explicit minimal authenticated metadata request. Missing key, invalid key, and unavailable credential-store conditions are structured errors.

```json
// ocr_document params
{ "path":"C:\\private\\form.pdf", "provider":"gemini", "model":"gemini-3.5-flash", "processing_mode":"standard" }
// result
{ "provider":"gemini", "model":"gemini-3.5-flash", "markdown_path":"...", "structured_json_path":"...", "usage_metadata":{} }
```

OCR output paths and usage metadata are local result data. The selected document is sent directly to Gemini; no secret is included in this contract.

## Jobs and module operations

`validate_excel({ module:"graduation", path })` returns `{ module, detected_level, rows_total, rows_accepted, warnings, preview }`. `start_job` requires `{ job_id, module:"graduation", excel_path, options }`, where options include `dry_run`, `min_score`, `resume_current`, and `stop_on_review`; its result is `{ accepted, job_id, status }`.

`get_job_status`, `pause_job`, `resume_job`, `resume_existing_job`, and `cancel_job` return a local job snapshot/action `{ job_id, status, ...counts, report_path?, review_report_path? }`. Current Students validation/export and Student Basic Info export accept selected local paths and return local output paths, warnings, and summaries.

Events are `progress`, `record_done`, `needs_auth`, `job_done`, `job_stopped`, and `error`. `progress` contains `job_id`, processed/succeeded/failed counts, optional total/page, and authentication state. `needs_auth` contains `{ job_id, reason }` and means the DMC portal requires the user to authenticate in local Chromium. `job_done` follows report persistence and contains `{ job_id, status, processed, succeeded, failed, report_path, review_report_path }`.

A dry run may navigate and match but never submits a portal save. Paths, previews, reports, OCR outputs, and errors can contain PII and must not be broadly logged.
