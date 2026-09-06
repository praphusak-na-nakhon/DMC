# DMC Assistant

DMC Assistant is a local-first Windows desktop tool for school staff using the DMC / OBEC portal.

## Modules

- Graduation — validate an Excel roster and fill post-graduation statuses.
- Current Students — validate sources and prepare import workbooks.
- Form Converter — use Gemini OCR for a selected document, review, and export locally.
- Student Basic Info — create a basic-information workbook from DMC data.

DMC portal authentication remains necessary in the local Chromium window when the portal requires it. It is not an application identity feature.

## Local data and AI

The local database, reports, OCR cache, and input/output files may contain student PII. Backup/restore includes only database, reports, and OCR cache; browser profile, Windows Credential Manager keys, and config cache are excluded.

Form Converter v1 registers Gemini only behind provider-neutral interfaces. The Gemini key is entered in Home AI settings and stored exclusively in Windows Credential Manager. The application supports save, configured status, explicit connection test, and delete—never key readback. Save makes no Gemini request; the explicit test uses minimal authenticated metadata. Selected documents go directly to Gemini. Provider availability, quota, and cost are the user's responsibility; the app is free.

## Development and verification

```powershell
corepack pnpm run desktop:typecheck
corepack pnpm run desktop:test
corepack pnpm run desktop:build
cargo test --manifest-path apps/desktop/src-tauri/Cargo.toml
cargo check --manifest-path apps/desktop/src-tauri/Cargo.toml
corepack pnpm run sidecar:typecheck
corepack pnpm run sidecar:test
corepack pnpm run release:check
corepack pnpm run form-converter:check
corepack pnpm run smoke:local
```

Use a temporary `DMC_DATA_DIR` and isolated `PLAYWRIGHT_BROWSERS_PATH` for smoke. It uses a loopback portal and neither DMC nor Gemini.

Native Cargo checks remain required. In the current Windows development environment they are blocked before application compilation by missing `dlltool.exe` / MSVC C++ Build Tools; do not remove the CI gates or treat this as a passing result. Windows sentinel persistence and live Gemini field testing are authorized manual acceptance gates.

## Packaging

Build, download, and install the MSI manually. Authenticode is optional and authorized separately. The application does not update itself. Release input version only controls tag/title; manually align checked-in Tauri, Cargo, and package versions before packaging.
