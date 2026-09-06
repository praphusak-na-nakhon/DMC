# PRD — DMC Assistant

DMC Assistant is a free, local-first Windows application for Thai school staff preparing and entering DMC / OBEC data. It retains four modules: Graduation, Current Students, Form Converter, and Student Basic Info.

All application processing, reports, browser automation, and SQLite data remain local. DMC portal authentication is completed by the user in the local browser. Form Converter sends only the user-selected document directly to Gemini; result, cache, and exports remain local and may contain PII.

Gemini is the sole v1 provider, with a provider-neutral code boundary. Home AI settings stores its key only in Windows Credential Manager, reports configured state without revealing the key, and separates local save from the explicit minimal-metadata connection test. The user is responsible for Gemini availability, quota, and costs.

Backups include database, reports, and OCR cache only. Browser profile, key material, and config cache are excluded. Graduation uses the exact bundled v1 JSON values; changing portal/year/school/rule values requires a new MSI.

Distribution is a manually built and installed Windows MSI; optional Authenticode is an authorized release step. Release tag/title input does not synchronize checked-in versions automatically.
