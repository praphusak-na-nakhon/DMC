# Form Converter Production Readiness

v1 registers Gemini only behind provider-neutral interfaces. Selected documents go directly to Gemini; output, reports, and cache remain local and may contain PII. Provider availability, quota, and cost belong to the user.

Gemini key settings use Windows Credential Manager WinVault. The UI saves, shows configured state, explicitly tests, and deletes without key readback. Save has no provider request. `form-converter:check` validates the WinVault dependency and Gemini registration without accessing a key.

An authorized Windows sentinel check must prove save/configured-after-restart/delete using a test secret without displaying it. It remains a manual gate. The live field test uses an in-memory process-only key and is not OS-store evidence.
