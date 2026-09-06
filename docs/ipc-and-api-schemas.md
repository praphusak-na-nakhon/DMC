# Local IPC Schemas

Desktop and sidecar exchange newline-delimited JSON-RPC locally. There is no application network API.

- `ping`, `get_database_status`, and `get_browser_runtime_status` report local readiness.
- `get_ai_settings`, `save_ai_api_key`, `test_ai_connection`, and `delete_ai_api_key` accept Gemini only and never return a key.
- `ocr_document` accepts a selected local path and returns local result paths and usage metadata.
- `validate_excel`, job controls, Current Students operations, and Student Basic Info export run locally.
- `create_backup` and `restore_backup` include database, reports, and OCR cache only.

`validate_excel` returns Graduation module, detected level, accepted/total rows, warnings, and preview. `start_job` accepts local job options including dry-run and review handling; `get_job_status`, pause, resume, cancel, list, archive, and resume-existing-job work only against local persistence. Current Students source validation/import export and Student Basic Info export also return local paths and summaries.

Events include `progress`, `record_done`, `needs_auth`, `job_done`, `job_stopped`, and `error`. `needs_auth` means DMC needs user authentication in the local browser. Paths, previews, reports, and OCR output can include PII and must not be broadly logged.

`job_done` follows report persistence and supplies processed/succeeded/failed counts plus local report and review-report paths. A dry run may navigate and match but must not submit a portal save.
