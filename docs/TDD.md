# TDD — DMC Assistant (Technical Design Document)

> Technical Design Document for MVP
> Version: 0.2
> Last updated: 2026-04-22
> Related: [PRD.md](./PRD.md)

---

## 1. Current Prototype Baseline

สภาพของระบบที่มีอยู่จริงใน repo ปัจจุบัน:

- มีสคริปต์ Python CLI ตัวเดียวคือ `fill_obec_portal.py`
- ใช้ `Playwright + Chromium` บนเครื่องผู้ใช้ และเก็บ browser profile ในโฟลเดอร์ local
- ผู้ใช้ต้อง login และเตรียมหน้า browser แบบ manual ก่อนเริ่มรัน
- ใช้ `pandas` อ่าน Excel และใช้ `rapidfuzz` ทำ fuzzy match ชื่อ/ห้องเรียน
- มี hardcoded `TARGET_URL`, status mapping, และสมมติฐานเรื่องคอลัมน์ไฟล์ต้นทาง
- สร้างผลลัพธ์เป็น `obec-fill-report.json`, `obec-fill-report.csv`, และ `obec-fill-review.csv` ในเครื่อง
- ยังไม่มี desktop UI, sidecar IPC, SQLite persistence, checkpoint เชิงระบบ, cloud licensing, remote config, telemetry, หรือ auto-update

เอกสารส่วนถัดไปอธิบาย **MVP target state** ที่จะสร้างต่อจาก baseline นี้

ขอบเขตของ MVP นี้เน้นงาน DMC ระดับโรงเรียนสำหรับครู/เจ้าหน้าที่ผู้รับผิดชอบโดยตรง จึงไม่รวม web dashboard สำหรับผู้บริหาร, โมดูลข้อมูลครูและบุคลากร, โมดูล EMIS/B-OBEC/Q-INFO, รายงาน 10 มิ.ย. / 10 พ.ย., multi-school mode, หรือ scheduled run

## 2. Architecture Overview

```
┌──────────────────────────────────────────────┐        ┌─────────────────────────┐
│          Desktop App (Windows)               │        │    Cloud Backend        │
│  ┌──────────────────────────────────────┐    │        │                         │
│  │   UI Layer  (Tauri + React + TS)     │    │        │   FastAPI (Python)      │
│  └──────────────┬───────────────────────┘    │        │        │                │
│                 │ IPC (JSON-RPC over stdio)  │ HTTPS  │        ▼                │
│  ┌──────────────▼───────────────────────┐    │◄──────►│   PostgreSQL            │
│  │   Python Sidecar                     │    │        │   (licenses, configs,   │
│  │   - Playwright (Chromium)            │    │        │    billing, telemetry)  │
│  │   - Excel parser (pandas)            │    │        │                         │
│  │   - Fuzzy matcher (rapidfuzz)        │    │        │   Object Storage        │
│  │   - Checkpoint / resume              │    │        │   (installer, config)   │
│  └──────────────────────────────────────┘    │        │                         │
│                                              │        │   Billing provider      │
│  Local Storage:                              │        │   webhook / admin tools │
│  - SQLite (jobs, checkpoints, reports)       │        │                         │
│  - Windows Credential Manager (secrets)      │        │                         │
│  - Per-license Playwright profile            │        │                         │
└──────────────────────────────────────────────┘        └─────────────────────────┘
```

### Boundaries
- **ข้อมูลนักเรียน (PII)** อยู่เฉพาะใน desktop และ report files ในเครื่องเป็นค่าเริ่มต้น ยกเว้น `formConverter` ที่ผู้ใช้ยินยอมส่ง PDF ไป cloud OCR gateway
- **Account/session, credit wallet/reservation, config sync, และ allow-listed telemetry** เป็นข้อมูลปกติที่ขึ้น cloud ได้โดยต้องไม่มี PII
- **Cloud OCR gateway** ต้องไม่ persist PDF ต้นฉบับหรือ field ที่อ่านได้ และต้องอยู่หลัง auth + credit reservation เสมอ
- **Playwright รันบนเครื่อง user** เพื่อให้ IP เป็นของโรงเรียนและ user ทำ QR 2FA เองได้

## 3. Tech Stack

### Desktop App
| Layer | Choice | เหตุผล |
|---|---|---|
| Shell | **Tauri 2.x** | ขนาดเล็ก, ใช้ WebView ของ Windows, security ดี |
| UI | **React 18 + TypeScript + Vite** | มาตรฐาน, component ecosystem ดี |
| UI kit | **shadcn/ui + Tailwind** | เบา, ปรับแต่งง่าย |
| State | **Zustand** | เบากว่า Redux และพอสำหรับ scope นี้ |
| Sidecar | **Python 3.11 + Playwright + pandas + rapidfuzz** | reuse `fill_obec_portal.py` เดิม |
| IPC | **Tauri sidecar (stdio) + JSON-RPC 2.0** | ตรงไปตรงมาและ debug ง่าย |
| Local DB | **SQLite** | embedded, no install |
| Secrets | **Windows DPAPI (via `keyring`)** | เก็บ credential และ secret ฝั่ง local |
| Packager | **Tauri bundler → .msi** + PyInstaller สำหรับ sidecar | เหมาะกับ Windows distribution |
| Updater | **Tauri updater** (signed manifest) | อัปเดตอัตโนมัติ |

### Cloud Backend
| Layer | Choice | เหตุผล |
|---|---|---|
| API | **FastAPI (Python 3.11)** | team คล่อง Python อยู่แล้ว |
| DB | **PostgreSQL 16** | reliable, query/reporting ยืดหยุ่น |
| Object storage | **Cloudflare R2 / S3** | เก็บ installer, signed config |
| Auth (admin) | **Clerk หรือ Supabase Auth** | ไม่ต้องดูแล auth เอง |
| Billing | **Omise / 2C2P / PromptPay manual** | final provider ยังไม่ตัดสิน |
| Hosting | **Fly.io หรือ Render** | deploy ง่าย, region ใกล้ไทย |
| Monitoring | **Sentry + BetterStack** | error tracking + uptime |

## 4. Repository Structure

```
dmc-assistant/
├── apps/
│   ├── desktop/                    # Tauri app
│   │   ├── src/                    # React UI
│   │   ├── src-tauri/              # Rust shell
│   │   │   ├── src/main.rs
│   │   │   └── tauri.conf.json
│   │   └── package.json
│   │
│   ├── sidecar/                    # Python automation
│   │   ├── dmc_sidecar/
│   │   │   ├── __main__.py         # JSON-RPC server over stdio
│   │   │   ├── rpc.py              # dispatch + schema validation
│   │   │   ├── modules/
│   │   │   │   ├── base.py         # BaseModule ABC
│   │   │   │   └── graduation.py   # reuse fill_obec_portal.py logic
│   │   │   ├── excel.py            # parsing + validation
│   │   │   ├── checkpoint.py       # resume state
│   │   │   └── config.py           # selectors loaded from disk
│   │   ├── pyproject.toml
│   │   └── tests/
│   │
│   └── cloud/                      # FastAPI backend
│       ├── app/
│       │   ├── main.py
│       │   ├── routes/
│       │   │   ├── license.py
│       │   │   ├── config.py
│       │   │   ├── telemetry.py
│       │   │   └── billing.py
│       │   ├── models/
│       │   ├── services/
│       │   └── db.py
│       ├── alembic/
│       └── pyproject.toml
│
├── packages/
│   ├── shared-schemas/             # JSON schemas ใช้ร่วม desktop ↔ cloud
│   └── module-configs/             # selector configs ของแต่ละ module
│
├── docs/
│   ├── PRD.md
│   └── TDD.md
│
└── .github/workflows/
    ├── desktop-release.yml
    ├── sidecar-build.yml
    └── cloud-deploy.yml
```

## 5. Data Models

### 5.1 Local (SQLite on device)

```sql
CREATE TABLE license (
    id                  INTEGER PRIMARY KEY,
    license_key         TEXT NOT NULL,      -- encrypted via DPAPI at rest
    device_id           TEXT NOT NULL,      -- random UUID generated on first run
    license_tier        TEXT NOT NULL,      -- 'trial'|'school_le_500'|'school_501_1500'|'school_gt_1500'
    school_size_tier    TEXT NOT NULL,      -- 'le_500'|'501_1500'|'gt_1500'
    billing_interval    TEXT,               -- 'monthly'|'annual'|NULL for trial
    student_count_total INTEGER NOT NULL,
    max_devices         INTEGER NOT NULL DEFAULT 3,
    activated_at        TEXT NOT NULL,
    expires_at          TEXT NOT NULL,
    last_checked_at     TEXT NOT NULL,
    offline_grace_until TEXT NOT NULL
);

CREATE TABLE job (
    id                  TEXT PRIMARY KEY,   -- UUID
    module              TEXT NOT NULL,      -- 'graduation' | ...
    status              TEXT NOT NULL,      -- 'pending'|'running'|'paused'|'done'|'failed'
    source_file         TEXT NOT NULL,      -- path to Excel
    total_records       INTEGER,
    processed           INTEGER DEFAULT 0,
    succeeded           INTEGER DEFAULT 0,
    failed              INTEGER DEFAULT 0,
    started_at          TEXT,
    finished_at         TEXT,
    checkpoint_json     TEXT                -- resume data
);

CREATE TABLE job_record (
    id                  INTEGER PRIMARY KEY,
    job_id              TEXT NOT NULL,
    row_index           INTEGER NOT NULL,
    status              TEXT NOT NULL,      -- 'success'|'not_found'|'review'|'error'
    message             TEXT,               -- no PII
    FOREIGN KEY (job_id) REFERENCES job(id)
);

CREATE TABLE audit_log (
    id                  INTEGER PRIMARY KEY,
    timestamp           TEXT NOT NULL,
    event               TEXT NOT NULL,      -- 'app_start'|'license_check'|'job_start'|...
    payload_json        TEXT                -- strict no-PII payload only
);
```

### 5.2 Cloud (PostgreSQL)

```sql
CREATE TABLE schools (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name                    TEXT NOT NULL,
    school_code             TEXT UNIQUE,        -- รหัส OBEC 8 หลัก
    student_count_total     INTEGER NOT NULL,
    student_count_updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    school_size_tier        TEXT NOT NULL,      -- 'le_500'|'501_1500'|'gt_1500'
    contact_email           TEXT,
    contact_phone           TEXT,
    created_at              TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE licenses (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    school_id           UUID REFERENCES schools(id),
    license_key         TEXT UNIQUE NOT NULL,   -- format: DMC-XXXX-XXXX-XXXX
    license_tier        TEXT NOT NULL,          -- 'trial'|'school_le_500'|'school_501_1500'|'school_gt_1500'
    billing_interval    TEXT,                   -- 'monthly'|'annual'|NULL for trial
    max_devices         INTEGER NOT NULL DEFAULT 3,
    status              TEXT NOT NULL DEFAULT 'active',  -- 'active'|'suspended'|'expired'
    issued_at           TIMESTAMPTZ DEFAULT now(),
    expires_at          TIMESTAMPTZ NOT NULL
);

CREATE TABLE device_activations (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    license_id          UUID REFERENCES licenses(id),
    device_id           TEXT NOT NULL,
    device_name         TEXT,                   -- Windows hostname
    first_seen_at       TIMESTAMPTZ DEFAULT now(),
    last_seen_at        TIMESTAMPTZ DEFAULT now(),
    UNIQUE (license_id, device_id)
);

CREATE TABLE module_configs (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    module              TEXT NOT NULL,          -- 'graduation'
    version             TEXT NOT NULL,          -- semver
    config_json         JSONB NOT NULL,         -- selectors, URLs, mappings
    min_app_version     TEXT NOT NULL,
    released_at         TIMESTAMPTZ DEFAULT now(),
    UNIQUE (module, version)
);

CREATE TABLE telemetry_events (
    id                  BIGSERIAL PRIMARY KEY,
    license_id          UUID,
    device_id           TEXT,
    event               TEXT NOT NULL,          -- allow-listed only
    app_version         TEXT,
    payload             JSONB NOT NULL,         -- validated against event-specific schema
    created_at          TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE billing_subscriptions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    school_id           UUID REFERENCES schools(id),
    license_id          UUID REFERENCES licenses(id),
    provider            TEXT NOT NULL,          -- 'omise'|'2c2p'|'promptpay_manual'
    billing_interval    TEXT NOT NULL,          -- 'monthly'|'annual'
    provider_sub_id     TEXT,
    status              TEXT NOT NULL,
    current_period_end  TIMESTAMPTZ,
    created_at          TIMESTAMPTZ DEFAULT now()
);
```

## 6. API Contracts (Cloud)

All endpoints use `Authorization: Bearer <license_key>` unless noted. Responses are JSON.

### 6.1 POST `/v1/license/activate`
```json
// req
{
  "license_key": "DMC-XXXX-XXXX-XXXX",
  "device_id": "uuid",
  "device_name": "PC-SOMSRI",
  "app_version": "0.1.0"
}
// resp 200
{
  "license_tier": "school_501_1500",
  "school_size_tier": "501_1500",
  "billing_interval": "monthly",
  "student_count_total": 800,
  "expires_at": "2027-04-22T00:00:00Z",
  "modules_enabled": ["graduation"],
  "max_devices": 3,
  "offline_grace_days": 7
}
// resp 409 — device limit exceeded
// resp 410 — license expired
```

### 6.2 GET `/v1/license/heartbeat`
เรียกวันละ 1 ครั้งตอนเปิดแอปเมื่อ online
```json
// resp 200
{
  "status": "active",
  "license_tier": "school_501_1500",
  "school_size_tier": "501_1500",
  "billing_interval": "monthly",
  "student_count_total": 800,
  "expires_at": "2027-04-22T00:00:00Z",
  "modules_enabled": ["graduation"],
  "max_devices": 3,
  "offline_grace_days": 7
}
// resp 402 — need renewal
```

Client behavior:
- ถ้า heartbeat สำเร็จ ให้เลื่อน `offline_grace_until = now + 7 days`
- ถ้า heartbeat ล้มเหลวเพราะ network และ `now <= offline_grace_until` ให้แอปใช้งานต่อได้
- ถ้าเกิน grace window ให้ block การเริ่ม job ใหม่จนกว่า online check จะสำเร็จ

### 6.3 GET `/v1/config/{module}`
```
?current_version=1.2.3
```
```json
// resp 200 when newer available
{
  "version": "1.3.0",
  "config": {
    "target_url": "...",
    "selectors": { "...": "..." },
    "status_code_map": { "...": "..." }
  },
  "signature": "base64..."
}
// resp 204 — already up to date
```

### 6.4 POST `/v1/telemetry`
Batch endpoint, fire-and-forget. รับเฉพาะ event type ที่ allow-list ไว้และ field ต้องตรง schema ของ event นั้นแบบ exact match

Allowed event types:
- `app_started`
- `license_checked`
- `job_completed`
- `job_failed`
- `config_updated`

```json
{
  "events": [
    {
      "event": "job_completed",
      "ts": "2026-04-22T01:23:45Z",
      "module": "graduation",
      "total": 200,
      "succeeded": 198,
      "failed": 2,
      "duration_sec": 3210
    },
    {
      "event": "config_updated",
      "ts": "2026-04-22T02:10:00Z",
      "module": "graduation",
      "from_version": "1.2.3",
      "to_version": "1.3.0"
    }
  ]
}
```

Validation rules:
- ปฏิเสธ event type ที่ไม่อยู่ใน allow-list
- ปฏิเสธ field ที่นอก schema ของ event นั้น
- ปฏิเสธ payload ที่มี student PII ทุกกรณี

### 6.5 POST `/v1/updates/manifest`
Handled by Tauri updater flow; signed manifest served from object storage.

## 7. Desktop ↔ Sidecar IPC

JSON-RPC 2.0 over stdin/stdout. Tauri spawns the sidecar as a child process at startup.

### Methods
- `ping()` → `"pong"`
- `validate_excel(path, module)` → `{ rows, warnings[], preview }`
- `start_job(job_id, module, excel_path, options)` → streams events back
- `pause_job(job_id)` / `resume_job(job_id)` / `cancel_job(job_id)`
- `get_job_status(job_id)` → snapshot

### Events (sidecar → desktop)
```json
{ "type": "progress", "job_id": "...", "processed": 42, "total": 200 }
{ "type": "record_done", "job_id": "...", "row": 42, "status": "success" }
{ "type": "needs_auth", "job_id": "...", "reason": "qr_timeout" }
{ "type": "job_done", "job_id": "...", "report_path": "..." }
{ "type": "error", "job_id": "...", "code": "...", "message": "..." }
```

## 8. Key Flows

### 8.1 First-time Activation
1. User installs `.msi` → Tauri initializes SQLite and spawns sidecar
2. UI asks for license key → calls `/v1/license/activate` with generated `device_id`
3. On success → cache `license_tier`, `school_size_tier`, `billing_interval`, `student_count_total`, `max_devices`, `expires_at`
4. Encrypt `license_key` at rest via DPAPI
5. Set `offline_grace_until = now + 7 days`
6. Fetch `module_configs` and save to `%APPDATA%/dmc-assistant/configs/`

### 8.2 Running a Job (graduation module)
1. User picks module + Excel file → UI calls `validate_excel`
2. Show preview + warnings → user confirms
3. UI calls `start_job` → sidecar:
   - Creates job row + checkpoint
   - Launches Playwright using a per-license profile under `%APPDATA%/dmc-assistant/profiles/<license_hash>/`
   - Navigates to `TARGET_URL` from signed config
   - If not authenticated → emits `needs_auth` → UI shows "โปรดสแกน QR"
   - Polls until login OK
   - Iterates rows, updates checkpoint every record
   - Emits `progress` + `record_done` events
4. On complete → writes local Excel/CSV reports + emits `job_done`
5. Fire allow-listed telemetry only

### 8.3 Auto-update of Module Config
- On app start + every 6 hours: call `/v1/config/{module}?current_version=X`
- If 200 → verify signature (Ed25519 public key bundled in app) → replace config atomically
- If signature fails → log + keep old config

### 8.4 Handling Session Expiry Mid-job
- Sidecar detects login page redirect → pauses job, saves checkpoint
- Emits `needs_auth` → UI surfaces modal "Session หมด โปรดสแกน QR"
- User completes auth → UI calls `resume_job`
- Sidecar resumes from checkpoint row

### 8.5 Offline Licensing Behavior
- Activation of a new device requires a successful online `/activate`
- Existing activated device calls `/heartbeat` daily when online
- If `/heartbeat` fails because of temporary network issues, app may continue until `offline_grace_until`
- If grace window expires, app blocks starting new jobs and prompts user to reconnect

## 9. Security

### Threat Model (brief)
| Threat | Mitigation |
|---|---|
| License key theft | DPAPI encryption at rest; device binding; rate-limited activation endpoint |
| PII leak via telemetry | Typed allow-list schema validator on client + server |
| Malicious remote config | Ed25519 signed configs, public key embedded in binary |
| Reverse engineering | Accepted risk; value is service + distribution, not client secrecy |
| QR code phishing inside app | Always navigate to signed official DMC URL/config |
| Update tampering | Tauri updater with signed manifest + binary signatures |

### Credential Handling
- DMC username/password is **not stored by default**
- If user opts in to "remember", store in Windows Credential Manager and never sync

### Local Artifacts Policy
- Report files may contain student data and therefore must remain local-only
- Logs, audit logs, telemetry, crash reports, and cloud payloads must contain no student PII
- Sentry scrubbing must run before any event leaves the device

## 10. Packaging & Distribution

### Desktop
- GitHub Actions builds `.msi` on tag push (`v*`)
- Code-signed with EV cert to reduce SmartScreen warnings
- PyInstaller bundles sidecar as single `.exe` and copies into Tauri resources
- Tauri updater manifest published to object storage

### Cloud
- Dockerfile → deploy to Fly.io or Render
- Alembic migrations run in release step
- Secrets via platform secret manager

## 11. Observability

### Client
- Sentry (Rust, TS, Python SDKs) for errors only, with strict PII scrubbing
- Local log file at `%APPDATA%/dmc-assistant/logs/app.log` (rotated 10MB × 5)
- No report file contents, names, student identifiers, or raw form values are sent to Sentry

### Server
- Sentry for exceptions
- Structured logs → BetterStack
- Uptime checks on `/healthz`

## 12. Testing Strategy

### Sidecar (Python)
- Unit tests for Excel parsing + status code mapping ported from existing script
- Unit tests for checkpoint/resume behavior
- Integration tests with Playwright against a local mock portal
- Contract tests against JSON-RPC schema

### Desktop (TS)
- Vitest for UI logic + Zustand stores
- Component tests for license activation, offline grace banner, progress, auth prompt

### Cloud
- pytest + httpx for API
- Telemetry schema tests to assert only allow-listed event types/fields are accepted
- License heartbeat tests covering online success, offline grace, and grace expiry
- Alembic migration round-trip test

### E2E
- Golden path: install MSI in a VM → activate license → run a 10-record graduation job against mock portal → verify local report
- Resume path: interrupt mid-job → re-auth → continue from checkpoint
- Isolation path: two different licenses on one machine use different Playwright profiles

## 13. Development Milestones

### M1 — Skeleton (2 weeks)
- [ ] Monorepo scaffold (Tauri + Python sidecar + FastAPI)
- [ ] IPC contract + ping round-trip
- [ ] License activate + SQLite persistence
- [ ] Persist `offline_grace_until` and heartbeat metadata
- [ ] Empty module loader

### M2 — Graduation Module (3 weeks)
- [ ] Port `fill_obec_portal.py` into `modules/graduation.py`
- [ ] Excel validation + preview UI
- [ ] Progress UI + checkpoint/resume
- [ ] QR auth pause/resume flow
- [ ] Local Excel/CSV report output
- [ ] Per-license Playwright profile isolation

### M3 — Cloud Config + Updates (2 weeks)
- [ ] Signed module configs, Ed25519 verify on client
- [ ] Tauri updater wired
- [ ] Allow-listed telemetry batching + schema validation
- [ ] Daily heartbeat + offline grace behavior

### M4 — Billing Readiness + Polish (3 weeks)
- [ ] School-size tier model in billing/admin flows
- [ ] Billing provider integration (final provider TBD)
- [ ] Landing page + docs site
- [ ] MSI signing + SmartScreen reputation bootstrap

### M5 — Beta with 5 schools (2 weeks)
- [ ] Onboarding and feedback loop
- [ ] Commercial readiness checklist for pilot billing
- [ ] Go/No-Go review while ToS/legal question is still open

## 14. Open Technical Questions

- [ ] รอ OBEC ตอบเรื่อง ToS ก่อนเปิด self-service billing หรือจำกัดเป็น pilot/invoice ไปก่อน
- [ ] Ed25519 key rotation strategy ควรเก็บ 2 public keys (current + next) หรือมากกว่า
- [ ] Billing provider ตัวสุดท้ายจะเป็น Omise, 2C2P หรือ PromptPay manual

## 15. Instructions for Codex CLI

ใช้เอกสารนี้ + [PRD.md](./PRD.md) เป็นแหล่งอ้างอิงหลัก กติกาสำหรับ implement:

1. **เริ่มจาก Milestone M1** — สร้าง scaffold ตามโครงใน §4 ก่อน ห้ามข้าม
2. **Reuse โค้ดเดิม** — `fill_obec_portal.py` ที่ root ให้เอามาเป็นฐานของ `modules/graduation.py` อย่า rewrite จากศูนย์
3. **Strict typing** — TS ทุกไฟล์ strict mode; Python ใช้ `mypy --strict` + Pydantic v2
4. **IPC schema first** — เขียน JSON schema ใน `packages/shared-schemas/` ก่อน implement ทั้งสองฝั่ง
5. **Telemetry must be allow-listed** — ต้องมี unit test ที่ assert ว่า event type และ field shape ตรง schema ที่อนุญาตเท่านั้น
6. **Tests required** — ทุก module + ทุก API endpoint ต้องมี test ก่อน merge
7. **Commit granularity** — 1 commit = 1 logical change, message เป็นภาษาอังกฤษ Conventional Commits
8. **ห้ามเพิ่ม dependency ใหม่โดยไม่ justify** — ถาม user ก่อนถ้าจะเพิ่ม runtime dependency
9. **ห้าม log PII** — log เก็บได้แค่ row index, status code, error code, timing และ metadata ที่ไม่ระบุตัวบุคคล
10. **UI ภาษาไทย** — string ทั้งหมดอยู่ใน `i18n/th.json` ตั้งแต่ต้น
