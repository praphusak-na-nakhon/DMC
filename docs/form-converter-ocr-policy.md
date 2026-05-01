# Form Converter Cloud AI Policy

The `formConverter` module is an explicit exception to the original local-only
student PII rule in the MVP PRD. It may send scanned student-history form
content to the cloud OCR gateway only after the signed-in user confirms AI
processing consent in the desktop app.

Guardrails:

- Cloud OCR requests require an authenticated account session and credit
  reservation.
- The cloud gateway must not persist the uploaded PDF or extracted student
  fields after the request completes.
- Telemetry, logs, admin audit, and credit ledger payloads must remain PII-free.
- Exported Excel and review reports are local-only artifacts.
- Users must review OCR output before Excel export; no direct DMC submission is
  performed by this module.
- Approved AI providers are configured by `DMC_OCR_PROVIDER`; v1 supports
  `mock`, `openai`, and `gemini`. Provider API keys must stay in the cloud
  staging/production environment, not in desktop builds or committed files.
