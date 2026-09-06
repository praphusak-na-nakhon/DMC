# PRD — DMC Assistant

DMC Assistant is a free, local-first Windows application for Thai school staff preparing and entering DMC / OBEC data. It retains four modules: Graduation, Current Students, Form Converter, and Student Basic Info.

All application processing, reports, browser automation, and SQLite data remain local. DMC portal authentication is completed by the user in the local browser. Form Converter sends only the user-selected document directly to Gemini; result, cache, and exports remain local and may contain PII.

Gemini is the sole v1 provider, with a provider-neutral code boundary. Home AI settings stores its key only in Windows Credential Manager, reports configured state without revealing the key, and separates local save from the explicit minimal-metadata connection test. The user is responsible for Gemini availability, quota, and costs.

Backups include database, reports, and OCR cache only. Browser profile, key material, and config cache are excluded. Graduation uses the exact bundled v1 JSON values; changing portal/year/school/rule values requires a new MSI.

Distribution is a manually built and installed Windows MSI; optional Authenticode is an authorized release step. Release tag/title input does not synchronize checked-in versions automatically.

## Module requirements

| Module | Local input | Local output | Required behavior |
|---|---|---|---|
| Graduation | Excel roster | result and review reports | Validate before run; dry run never saves to DMC; pause for portal authentication and resume safely. |
| Current Students | source/template files | reviewed import workbook | Validate source conflicts and warnings before creating the workbook. |
| Form Converter | selected PDF or image | reviewed structured OCR and export | Require configured Gemini, preserve local output/cache, and require human field review. |
| Student Basic Info | DMC data file | basic-information workbook | Validate input shape and report output path and summary. |

## Acceptance rules

- The UI displays the four modules and never requires product-service access to start a local workflow.
- Portal authentication is a visible DMC step: the browser pauses work with actionable Thai guidance and the user can resume after completing it.
- AI settings report only configured/not-configured state; a key is not shown in UI, reports, diagnostics, or backup.
- Source data, local browser content, reports, OCR cache, previews, and exports are treated as PII-bearing artifacts.
- Backup/restore is limited to database, reports, and OCR cache. A restore creates its safety copy and never imports browser profile or key material.
- Graduation retains the shipped matching, selector, level-rule, and status-map semantics described in `modules/graduation-spec.md`.
