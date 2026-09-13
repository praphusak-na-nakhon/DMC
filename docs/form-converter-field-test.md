# Form Converter Field Test

This is an authorized opt-in live Gemini procedure. Use protected sample documents and a disposable key. The supplied `GEMINI_API_KEY` is process-only: the runner uses an in-memory store and never reads, writes, or deletes Windows Credential Manager. It is not evidence for the Windows sentinel persistence gate.

```powershell
$env:GEMINI_API_KEY = "<key>"
corepack pnpm run form-converter:field-test -- --pdf-dir "C:\\dmc-field-test\\form-pdfs" --output-dir "C:\\dmc-field-test\\results"
Remove-Item Env:GEMINI_API_KEY
```

Prefer the environment variable to a command-line key. Never print the key or raw provider errors. Review local results before export; record the manual outcome separately. Automated tests use fakes and do not make live Gemini calls.
