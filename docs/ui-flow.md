# UI Flow

Home shows Graduation, Current Students, Form Converter, Student Basic Info, local backup/restore, browser readiness, and AI settings.

AI settings lets the user enter a Gemini key, see configured state, explicitly test the connection, or delete the key. It never shows stored key material. Save does not contact Gemini.

Graduation: choose Excel, validate and review preview/warnings, choose dry run or authorized run, authenticate to DMC in local Chromium if asked, resume, and open local reports. Dry run never saves to the portal.

Current Students validates sources and writes an import workbook locally. Student Basic Info creates its workbook locally. Form Converter requires configured Gemini, sends the selected PDF/image directly to Gemini, presents a local result for field review, then exports locally. UI copy must explain provider quota/cost responsibility.

Job states are `validating`, `ready_to_run`, `running`, `paused`, `needs_auth`, `stopped_on_review`, `failed`, `done`, and `cancelled`. Use Thai, actionable copy, honest progress, close protection for active jobs, and styled destructive confirmations.
