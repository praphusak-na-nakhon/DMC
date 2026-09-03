# Form Converter Gemini OCR Policy

`formConverter` is local-first except for an explicit user choice to process a
scanned form with Gemini. When the user starts OCR, the sidecar submits the
selected document directly to Gemini using the user's own API key. There is no
DMC cloud OCR gateway, account session, credit reservation, or provider key in
the desktop build.

## Consent and Credentials

- The desktop UI must clearly disclose that the selected document, which may
  contain student PII, is sent to Gemini before OCR begins.
- A user may save a Gemini API key only through the manual, explicit desktop
  settings action. The sidecar stores it in Windows Credential Manager through
  `keyring.backends.Windows.WinVaultKeyring` under the DMC Assistant service
  identity; it is not written to the local data directory or SQLite database.
- The user may delete the saved key from settings. A provider connection test is
  separate and opt-in; saving a key never makes an automatic network request.
- Diagnostics, RPC responses, notifications, caches, and error messages must
  never contain the API key or raw provider exception text.

## Local Results and Cache

- OCR output, structured JSON, metadata, and usage information are retained in
  the local Gemini cache under `.dmc-assistant-data\ocr\gemini` (or
  `DMC_DATA_DIR`). These files can contain student PII and must be protected as
  local records.
- The cache key includes the input digest, model, and processing mode. A valid
  cache hit reuses structured output and usage metadata instead of repeating a
  submission; force-refresh behavior remains available through the normal OCR
  request.
- Standard and batch processing preserve page estimates, page counts, provider
  job metadata, and usage totals. Users must review extracted data before Excel
  export; OCR never submits a form to DMC.

## Testing and Field Validation

- Automated tests use fake secret stores or a fake WinVault backend and never
  call Gemini or a real Windows credential store.
- Real provider connectivity is checked only by the explicit field-test command
  described in `docs/form-converter-field-test.md`, with a process-local
  `GEMINI_API_KEY` or `--gemini-api-key`. The field-test key is never persisted.
- API keys, scanned PDFs, cache data, and field-test reports must not be added
  to version control.
