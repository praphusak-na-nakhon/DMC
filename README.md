# DMC Assistant

Desktop automation for Thailand's DMC / student data-entry portal (BOPP OBEC), with a Python
sidecar that drives Playwright, a cloud backend for account/credit/OCR, and a React desktop shell.

## Layout

- `apps/desktop`: Tauri + React desktop shell (TypeScript, Vite, Vitest)
- `apps/sidecar`: Python sidecar for automation, Excel/PDF parsing, OCR client, and local persistence
- `apps/cloud`: FastAPI backend for accounts, credit wallet, config signing, and OCR gateway
- `packages/shared-schemas`: shared JSON schemas for IPC and API contracts, config-signing keys
- `packages/module-configs`: signed-config candidates for portal modules (e.g. `graduation`)
- `scripts/`: smoke, release-readiness, and form-converter-readiness helpers

## Modules

- `graduation` — fill ม.3/ม.6 graduation statuses into the portal from an Excel roster
- `currentStudents` — reconcile student rosters + Thai-ID CSV + OCR, build a transfer-in import form, and fill it
- `formConverter` — handwritten PDF forms → AI OCR (mock/openai/gemini) → review → Excel, credit-gated through the cloud
- `psar` — P-SAR readiness dashboard and report generation (no credits)

## Local Development

Prereqs: Node.js + pnpm (via corepack), a local Python 3.11+ with `.venv`, and Rust for Tauri.

```powershell
# Install dependencies (pnpm 10 allows esbuild's postinstall via onlyBuiltDependencies)
corepack pnpm install

# Desktop app with Tauri IPC + sidecar
corepack pnpm run desktop:dev

# Vite web shell only (no Tauri/sidecar)
corepack pnpm run desktop:web

# Cloud API (dev, reload)
corepack pnpm run cloud:dev
```

## Tests & Checks

```powershell
# Desktop typecheck + tests
corepack pnpm run desktop:typecheck
corepack pnpm run desktop:test

# Sidecar tests + strict typecheck
corepack pnpm run sidecar:test
corepack pnpm run sidecar:typecheck

# Cloud tests
corepack pnpm run cloud:test

# Full CI-equivalent gate
corepack pnpm run ci:verify
```

End-to-end smoke (bundles the sidecar, launches it, exercises RPC + a real Excel sample):

```powershell
.\.venv\Scripts\python .\scripts\smoke_local.py
```

Release/form-converter readiness checks:

```powershell
corepack pnpm run release:check
corepack pnpm run form-converter:check
```

## Notes

- `apps/desktop/src-tauri/bundled-sidecar/` is a build artifact (gitignored); `sidecar:bundle`
  regenerates it from `apps/sidecar` and `packages/module-configs`.
- `upload/` contains real student data and is gitignored — do not commit it.
- Portal automation requires an authenticated DMC session; jobs are credit-backed through the
  cloud wallet unless run as a dry run.

See `docs/` for the PRD, TDD, IPC/API schemas, module specs, and readiness checklists.
