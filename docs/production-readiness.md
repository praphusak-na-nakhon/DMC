# Production Readiness — Manual Windows Release

`desktop:package` bundles the local sidecar and produces an MSI with bundled-sidecar and templates resources. An authorized operator distributes and installs the MSI manually; optional Authenticode is separate. The application does not update itself.

Release input version controls tag/title only. Before packaging, manually align Tauri, Cargo, and package versions. Graduation's bundled v1 JSON contains exact portal, school, year, selector, and rule values; modify it only for a new shipped MSI.

Run desktop/sidecar checks, release/form-converter readiness, and smoke using temporary data plus isolated browser binaries. Keep real portal credentials, Gemini keys, and PII out of tests and output.

Windows sentinel persistence and live field testing are required authorized manual acceptance activities; this document does not claim either has passed.
