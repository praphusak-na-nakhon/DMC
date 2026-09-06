# Task 7 report

## Scope

Rewrote active product, technical, UI, local IPC, release, and Form Converter documents for the four-module local-first product. Updated `docs/modules/graduation-spec.md` to retain its matching/rule/auth/PII contract while removing retired profile and outbound-product-service statements. No scripts changed: smoke and both readiness scripts already implement the required local behavior.

## Verification

- `corepack pnpm run desktop:typecheck` — pass.
- Isolated smoke: set `PLAYWRIGHT_BROWSERS_PATH` to `.venv/playwright-browsers` and a fresh temporary `DMC_DATA_DIR`, then ran `.venv\\Scripts\\python.exe scripts\\smoke_local.py` — pass: generation 2, 2 accepted rows, dry-run done, zero portal saves.
- `corepack pnpm run release:check` — pass: `{"status":"ok"}`.
- `corepack pnpm run form-converter:check` — pass: WinVault backend, Gemini-only provider, no credential read or live provider test.
- Terminology/source gates — active documentation has no prohibited product-copy matches. Remaining source matches are intentional negative assertions, old-schema fixtures, and retired-RPC regression fixtures; no active runtime match was found.
- `git diff --check` — pass.

## Deferred or blocked gates

Desktop test/build and sidecar test/typecheck were not rerun in this documentation-only task after the available targeted checks. Rust `cargo test` and `cargo check` remain required CI gates but are known blocked before application compilation by missing `dlltool.exe` / MSVC C++ Build Tools; no skip or gate removal was made. Manual Windows sentinel persistence and live Gemini field testing remain intentionally unclaimed.

## Incident and recovery

An initial `apply_patch` targeted the parent checkout rather than the isolated worktree. No scripts changed. The parent documentation edits were reversed with apply-patch reverse diffs, then verified to leave exactly the pre-existing `apps/sidecar/scripts/build_windows_bundle.ps1` modification. All final edits use explicit `.worktrees/local-first-byok-refactor/...` paths.
