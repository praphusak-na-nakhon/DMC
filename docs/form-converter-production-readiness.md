# Form Converter Production Readiness

`formConverter` follows `PDF scanned form -> direct Gemini OCR -> review ->
Excel`. It is local-first, with a deliberate disclosure and user opt-in before
the PDF is submitted to Gemini. It is not ready for broad use until real-form
field testing satisfies the checks below.

## Readiness Checklist

1. Local provider and credential backend
   - Only the local `gemini` provider is registered.
   - The packaged sidecar includes `keyring` and
     `keyring.backends.Windows.WinVaultKeyring` for Windows Credential Manager.
   - Saving, deleting, and testing a stored key are separate explicit user
     actions. Saving a key does not contact Gemini.
   - `corepack pnpm run form-converter:check` verifies provider registration and
     the importable credential backend without reading a credential or calling
     Gemini.

2. Privacy and disclosure
   - The UI tells the user that the selected document is sent directly to Gemini
     before OCR starts.
   - The key never appears in RPC results, notifications, logs, diagnostics, or
     local OCR cache files.
   - OCR output, structured cache data, and review reports can contain student
     PII and remain local. They are reviewed before any Excel export.

3. OCR behavior
   - v1 supports `student_history_v1` review fields: `student_id`, `first_name`,
     `last_name`, `birth_date`, `phone`, and `address`.
   - Standard and batch paths retain page estimation, processing mode, cache
     reuse, structured JSON output, provider job state, and usage metadata.
   - A cache hit must avoid a duplicate submission for unchanged input unless
     the normal OCR request is force-refreshed.

4. Automated and field validation
   - Automated tests use fakes only; they never call a real provider or Windows
     credential store.
   - Run the deliberate local field test in
     `docs/form-converter-field-test.md` with 10-20 real forms, then 100, 1,000,
     and 5,000-page scan batches as appropriate.
   - Supply a field-test credential with `GEMINI_API_KEY` where possible. The
     field runner uses an in-memory store and does not save that key.

## Manual Windows Packaging Gate

After a Windows package is built, a release owner must manually verify this
behavior with an invalid sentinel key in an isolated test profile:

1. Save the sentinel in desktop AI settings and restart the packaged app.
2. Confirm `configured` remains true after restart while the separate connection
   test rejects the invalid key.
3. Confirm the sentinel is absent from diagnostics and local data using `rg -a`.
4. Delete the sentinel, restart, and confirm `configured` becomes false.

This gate requires explicit authorization because it writes a Windows
Credential Manager entry. Do not run it during automated tests or ordinary
development work.
