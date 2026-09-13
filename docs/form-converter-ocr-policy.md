# Form Converter OCR Policy

Form Converter has no application intermediary: its selected document goes directly to Gemini. The local database, OCR cache, reports, and exports may contain PII. Protect them and review extracted fields before export.

Gemini is the v1 provider behind provider-neutral interfaces. Its API key persists only in Windows Credential Manager; configured status has no key readback. Save stays local. Explicit testing makes a minimal authenticated metadata request. Users are responsible for provider quotas and costs.

Backup includes database, reports, and OCR cache only; browser profile, key material, and config cache are excluded. Automated tests use fakes. Live Gemini calls belong only to the authorized field-test procedure.
