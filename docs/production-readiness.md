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

The smoke command must have a fresh temporary `DMC_DATA_DIR` and an absolute `PLAYWRIGHT_BROWSERS_PATH`; it exercises a loopback portal only. Cargo test/check are required native gates. They are currently unavailable in this Windows environment before application compilation because `dlltool.exe` / MSVC C++ Build Tools are missing, and must remain unclaimed rather than removed.

Windows sentinel persistence and live field testing are required authorized manual acceptance activities; this document does not claim either has passed.
