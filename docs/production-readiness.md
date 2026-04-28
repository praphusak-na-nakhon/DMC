# Production readiness

สถานะปัจจุบันเหมาะกับ staging/internal pilot แล้ว แต่ก่อนเปิดขายหรือปล่อยให้โรงเรียนใช้กว้าง ต้องผ่าน checklist นี้

## Cloud

Required environment:

```powershell
$env:DMC_CLOUD_SQLITE_PATH = "D:\dmc-cloud\state.sqlite3"
$env:DMC_CLOUD_API_BEARER_TOKEN = "<long-random-admin-token>"
$env:DMC_CLOUD_CONFIG_SIGNING_PRIVATE_KEY_HEX = "<ed25519-private-key-hex>"
$env:DMC_CLOUD_CONFIG_SIGNING_KEY_ID = "prod-YYYY-MM"
$env:DMC_CLOUD_UPDATER_LATEST_VERSION = "0.1.0"
$env:DMC_CLOUD_UPDATER_WINDOWS_X86_64_URL = "https://downloads.example.com/dmc/DMC_0.1.0_x64_en-US.msi.zip"
$env:DMC_CLOUD_UPDATER_WINDOWS_X86_64_SIGNATURE = "<tauri-updater-signature>"
```

Production deployment requirements:

- Run behind HTTPS only.
- Store secrets outside the repo, preferably in the host secret manager.
- Use a managed database or a backed-up persistent volume. SQLite is acceptable only for small controlled pilot deployments.
- Enable daily backup and restore drill.
- Log `/healthz`, `/v1/updates/manifest`, auth failures, and admin actions.
- Rotate `DMC_CLOUD_API_BEARER_TOKEN` on staff changes.

## Admin credit operations

Preferred flow:

1. Admin creates or updates user with `seed-user`.
2. Admin creates top-up request after seeing a payment notification.
3. A second admin or the same authorized admin approves the request after checking payment evidence.
4. System writes wallet ledger and admin audit log.

Commands:

```powershell
.\.venv\Scripts\python.exe apps\cloud\scripts\manage_accounts.py seed-user `
  --email teacher@example.test `
  --password "<temporary-password>" `
  --display-name "Teacher Demo"

.\.venv\Scripts\python.exe apps\cloud\scripts\manage_accounts.py request-topup `
  --email teacher@example.test `
  --amount 500 `
  --payment-reference "receipt-001"

.\.venv\Scripts\python.exe apps\cloud\scripts\manage_accounts.py decide-topup `
  --request-id "<request_id>" `
  --decision approved `
  --idempotency-key "receipt-001"
```

Audit endpoints:

- `GET /v1/admin/audit`
- `GET /v1/admin/credits/topup-requests`
- `GET /v1/admin/users/{user_id}/ledger`

## Release and auto-update

Production release must include:

- Bundled sidecar built with `corepack pnpm run sidecar:bundle`
- Desktop package built with `corepack pnpm run desktop:package`
- Signed Windows installer
- Tauri updater signature
- Release manifest served by cloud `/v1/updates/manifest`
- Public updater key embedded in release config

Production readiness command:

```powershell
.\.venv\Scripts\python.exe scripts\check_release_readiness.py `
  --environment production `
  --cloud-base-url "https://cloud.example.com" `
  --updater-endpoint "https://cloud.example.com/v1/updates/manifest?current_version={current_version}&target={target}&arch={arch}" `
  --updater-public-key "<tauri-updater-public-key>"
```

## Current limitations

- No payment gateway integration yet.
- Admin API still uses bearer token, not role-based admin login.
- Cloud DB production choice and hosting are deployment decisions.
- Field performance for 1,000-5,000 students still needs real school pilot data.
- Legal/ToS decision for automating DMC and ThaID must be approved before broad release.
