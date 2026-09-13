# Production Readiness — Manual Windows Release

`desktop:package` bundles the local sidecar and produces an MSI with bundled-sidecar and templates resources. An authorized operator distributes and installs the MSI manually; optional Authenticode is separate. The application does not update itself.

Release input version controls tag/title only. Before packaging, manually align Tauri, Cargo, and package versions. Graduation's bundled v1 JSON contains exact portal, school, year, selector, and rule values; modify it only for a new shipped MSI.

Run the release checklist below using temporary data plus isolated browser binaries. Keep real portal credentials, Gemini keys, and PII out of tests and output.

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

The smoke command must have a fresh temporary `DMC_DATA_DIR` and an absolute `PLAYWRIGHT_BROWSERS_PATH` with Chromium installed; it exercises a loopback portal only. Cargo test/check are required native gates and need a working Windows Rust toolchain, C++ build tools, and an execution policy that permits them.

Task 9 evidence from 2026-09-06 UTC: local native checks were blocked before application compilation by Windows Application Control (OS error 4551). The package attempt staged a fresh sidecar, then failed at Cargo metadata under the same policy; it produced no MSI. This is dated evidence for that machine, not a universal build result. Native compilation, MSI installation, and manual acceptance remain unverified.

Windows sentinel persistence and live field testing are required authorized manual acceptance activities; this document does not claim either has passed.
