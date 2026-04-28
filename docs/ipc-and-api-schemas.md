# IPC and API Schemas

> Shared contract spec for desktop ↔ sidecar IPC and desktop ↔ cloud API
> Last updated: 2026-04-22
> Related: [TDD.md](./TDD.md)

---

## 1. Purpose

เอกสารนี้เป็น source of truth สำหรับ:
- JSON-RPC ระหว่าง desktop app กับ Python sidecar
- HTTP API ระหว่าง desktop app กับ cloud backend
- typed telemetry events

เป้าหมายคือทำให้ implementer เขียนทั้งสองฝั่งได้โดยไม่เดา field shape, event names, status semantics, หรือ error contract

## 2. General Conventions

### Naming
- JSON fields ใช้ `snake_case`
- enum values ใช้ `snake_case`
- timestamp ใช้ RFC 3339 UTC string
- path เป็น absolute path ฝั่ง local

### Request/response discipline
- ห้ามเพิ่ม field ที่ไม่อยู่ใน schema
- ฝั่งรับต้อง reject unknown required-behavior-changing fields
- ฝั่งส่งต้องไม่ส่ง `null` ถ้า schema ไม่อนุญาต

### Error object
ทุก boundary ใช้ logical error code กลาง

```json
{
  "code": "PORTAL_SESSION_EXPIRED",
  "message": "Session expired. Re-authentication required.",
  "details": {
    "job_id": "uuid"
  }
}
```

### No-PII rule
- ห้ามส่ง student names, student numbers, citizen IDs, raw report rows, หรือ raw form values ผ่าน cloud API หรือ telemetry
- IPC ภายในเครื่องส่ง PII ได้เฉพาะเท่าที่จำเป็นต่อการทำงานของ app และต้องไม่ถูก log แบบ plain text

## 3. Desktop ↔ Sidecar IPC

### Transport
- JSON-RPC 2.0 over `stdin/stdout`
- sidecar start โดย Tauri ตอนเปิดแอป
- desktop เป็น requester หลัก
- sidecar ส่งทั้ง response และ async event stream

### Base envelopes

#### Request
```json
{
  "jsonrpc": "2.0",
  "id": "req-1",
  "method": "validate_excel",
  "params": {
    "path": "C:\\data\\m6-obec-study-form.xlsx",
    "module": "graduation"
  }
}
```

#### Success response
```json
{
  "jsonrpc": "2.0",
  "id": "req-1",
  "result": {}
}
```

#### Error response
```json
{
  "jsonrpc": "2.0",
  "id": "req-1",
  "error": {
    "code": "INPUT_FILE_INVALID_FORMAT",
    "message": "Expected at least 7 columns.",
    "details": {}
  }
}
```

### 3.1 Methods

#### `ping`
Request:
```json
{}
```

Response:
```json
{
  "value": "pong",
  "sidecar_version": "0.1.0"
}
```

#### `validate_excel`
Request:
```json
{
  "path": "C:\\data\\m6-obec-study-form.xlsx",
  "module": "graduation"
}
```

Response:
```json
{
  "module": "graduation",
  "detected_level": "ม.6",
  "rows_total": 200,
  "rows_accepted": 198,
  "warnings": [
    {
      "code": "STATUS_CODE_NOT_MAPPED",
      "row_index": 42,
      "message_th": "ไม่พบ mapping สำหรับสถานะนี้"
    }
  ],
  "preview": [
    {
      "order": 1,
      "level_label": "ม.6",
      "room": 1,
      "student_no": "18539",
      "first_name": "กมลชนก",
      "last_name": "แซ่อิ๋ว",
      "status_text": "(ม.6) ศึกษาต่อมหาวิทยาลัยของรัฐ",
      "status_code": "301"
    }
  ]
}
```

#### `start_job`
Request:
```json
{
  "job_id": "uuid",
  "module": "graduation",
  "excel_path": "C:\\data\\m6-obec-study-form.xlsx",
  "options": {
    "dry_run": false,
    "min_score": 72,
    "resume_current": false,
    "stop_on_review": false
  }
}
```

Immediate response:
```json
{
  "accepted": true,
  "job_id": "uuid"
}
```

#### `pause_job`
Request:
```json
{
  "job_id": "uuid"
}
```

Response:
```json
{
  "job_id": "uuid",
  "status": "paused"
}
```

#### `resume_job`
Request:
```json
{
  "job_id": "uuid"
}
```

Response:
```json
{
  "job_id": "uuid",
  "status": "running"
}
```

#### `cancel_job`
Request:
```json
{
  "job_id": "uuid"
}
```

Response:
```json
{
  "job_id": "uuid",
  "status": "cancelled"
}
```

#### `get_job_status`
Request:
```json
{
  "job_id": "uuid"
}
```

Response:
```json
{
  "job_id": "uuid",
  "module": "graduation",
  "status": "running",
  "processed": 42,
  "total": 200,
  "succeeded": 40,
  "failed": 2,
  "current_page": 3,
  "needs_auth": false,
  "report_path": null,
  "stopped_item": null
}
```

### 3.2 Sidecar events

All async events use:
```json
{
  "jsonrpc": "2.0",
  "method": "event",
  "params": {}
}
```

#### `progress`
```json
{
  "type": "progress",
  "job_id": "uuid",
  "processed": 42,
  "total": 200,
  "succeeded": 40,
  "failed": 2,
  "current_page": 3
}
```

#### `record_done`
```json
{
  "type": "record_done",
  "job_id": "uuid",
  "row": 42,
  "status": "success"
}
```

#### `needs_auth`
```json
{
  "type": "needs_auth",
  "job_id": "uuid",
  "reason": "session_expired"
}
```

Allowed reasons:
- `login_required`
- `session_expired`
- `qr_timeout`

#### `job_done`
```json
{
  "type": "job_done",
  "job_id": "uuid",
  "status": "done",
  "report_path": "C:\\Users\\...\\obec-fill-report.csv",
  "review_report_path": "C:\\Users\\...\\obec-fill-review.csv"
}
```

#### `job_stopped`
```json
{
  "type": "job_stopped",
  "job_id": "uuid",
  "status": "stopped_on_review",
  "stopped_item": {
    "page": 2,
    "portal_seq_no": "17",
    "portal_name": "สมชาย ใจดี",
    "note": "low_confidence_below_72",
    "score": 61
  }
}
```

#### `error`
```json
{
  "type": "error",
  "job_id": "uuid",
  "code": "PORTAL_OPTION_VALUE_NOT_FOUND",
  "message": "Dropdown does not contain requested value."
}
```

## 4. Cloud API

### Authentication
- License-bearing client APIs ใช้ `Authorization: Bearer <license_key>`
- Admin APIs อยู่นอก scope เอกสารนี้

### 4.1 `POST /v1/license/activate`

Request:
```json
{
  "license_key": "DMC-XXXX-XXXX-XXXX",
  "device_id": "uuid",
  "device_name": "PC-SOMSRI",
  "app_version": "0.1.0"
}
```

Response `200`:
```json
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
```

Errors:
- `409 DEVICE_LIMIT_EXCEEDED`
- `410 LICENSE_EXPIRED`
- `403 LICENSE_SUSPENDED`

### 4.2 `GET /v1/license/heartbeat`

Response `200`:
```json
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
```

Errors:
- `402 NEED_RENEWAL`
- `403 LICENSE_SUSPENDED`

### 4.3 `GET /v1/config/{module}`

Query:
- `current_version=1.2.3`

Response `200`:
```json
{
  "version": "1.3.0",
  "config": {
    "target_url_template": "https://portal.bopp-obec.info/...",
    "login_url": "https://portal.bopp-obec.info/obec68/auth/login",
    "selectors": {
      "student_rows": "tr[id^='tr-']",
      "status_select": "select[name$='.studyTypeCode']",
      "save_button": "form.form-horizontal.form-condensed button[name='action'][value='confirm']",
      "pagination_active": "div.pagination li.active a",
      "pagination_links": "div.pagination li a"
    },
    "level_rules": {
      "ม.3": {
        "level_code": "12",
        "default_missing_code": "207",
        "ambiguity_floor": 45,
        "require_exact_student_no": true
      },
      "ม.6": {
        "level_code": "15",
        "default_missing_code": null,
        "ambiguity_floor": null,
        "require_exact_student_no": false
      }
    },
    "status_code_map": {
      "(ม.6) ศึกษาต่อมหาวิทยาลัยของรัฐ": "301"
    }
  },
  "signature": "base64..."
}
```

Response `204`: no update

### 4.4 `POST /v1/telemetry`

Request:
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
    }
  ]
}
```

Response `202`:
```json
{
  "accepted": 1,
  "rejected": 0
}
```

### 4.5 `POST /v1/updates/manifest`
- ใช้โดย Tauri updater
- exact manifest shape ตาม Tauri runtime ไม่ redefine ซ้ำในเอกสารนี้

## 5. Telemetry Event Schemas

### Rules
- allow only listed event names
- exact field matching
- reject extra fields
- reject PII fields and PII-like values

### `app_started`
```json
{
  "event": "app_started",
  "ts": "2026-04-22T01:23:45Z",
  "app_version": "0.1.0",
  "platform": "windows"
}
```

### `license_checked`
```json
{
  "event": "license_checked",
  "ts": "2026-04-22T01:23:45Z",
  "result": "ok",
  "offline_mode": false
}
```

Allowed `result`:
- `ok`
- `need_renewal`
- `network_error`
- `suspended`

### `job_completed`
```json
{
  "event": "job_completed",
  "ts": "2026-04-22T01:23:45Z",
  "module": "graduation",
  "total": 200,
  "succeeded": 198,
  "failed": 2,
  "duration_sec": 3210
}
```

### `job_failed`
```json
{
  "event": "job_failed",
  "ts": "2026-04-22T01:23:45Z",
  "module": "graduation",
  "error_code": "PORTAL_SESSION_EXPIRED",
  "processed": 42
}
```

### `config_updated`
```json
{
  "event": "config_updated",
  "ts": "2026-04-22T01:23:45Z",
  "module": "graduation",
  "from_version": "1.2.3",
  "to_version": "1.3.0"
}
```

## 6. Shared Enums

### Job status
- `pending`
- `running`
- `paused`
- `done`
- `failed`
- `cancelled`
- `stopped_on_review`

### Module
- `graduation`

### Record status
- `success`
- `not_found`
- `review`
- `error`

## 7. Error Code Catalog

### Input / validation
- `INPUT_FILE_NOT_FOUND`
- `INPUT_FILE_INVALID_FORMAT`
- `INPUT_FILE_UNSUPPORTED_LEVEL`
- `INPUT_STATUS_NOT_MAPPED`

### Licensing / cloud
- `LICENSE_EXPIRED`
- `LICENSE_SUSPENDED`
- `DEVICE_LIMIT_EXCEEDED`
- `HEARTBEAT_FAILED`
- `OFFLINE_GRACE_EXPIRED`
- `CONFIG_SIGNATURE_INVALID`

### Portal / automation
- `PORTAL_LOGIN_REQUIRED`
- `PORTAL_SESSION_EXPIRED`
- `PORTAL_TABLE_NOT_FOUND`
- `PORTAL_SAVE_BUTTON_NOT_FOUND`
- `PORTAL_OPTION_VALUE_NOT_FOUND`
- `PORTAL_NAVIGATION_FAILED`

### Job control
- `JOB_NOT_FOUND`
- `JOB_ALREADY_RUNNING`
- `JOB_NOT_PAUSED`
- `JOB_CANCELLED`
- `JOB_STOPPED_ON_REVIEW`
- `JOB_CHECKPOINT_INVALID`

### RPC / internal
- `RPC_INVALID_REQUEST`
- `RPC_METHOD_NOT_FOUND`
- `METHOD_NOT_IMPLEMENTED`
- `UNEXPECTED_ERROR`

## 8. Compatibility Rules

- Cloud response changes ต้อง additive เท่านั้นใน MVP
- IPC method names เปลี่ยนไม่ได้โดยไม่ bump desktop + sidecar พร้อมกัน
- `module="graduation"` เป็น required string constant สำหรับ module แรก
- ถ้าเพิ่ม module ใหม่ในอนาคต ต้องเพิ่ม enum, config schema, telemetry semantics, และ validation contract ให้ครบ

## 9. Minimum Tests

- Desktop และ sidecar ใช้ fixture schema เดียวกัน
- contract test สำหรับทุก IPC method
- contract test สำหรับทุก event type
- API response validation สำหรับ `activate`, `heartbeat`, `config`
- telemetry reject unknown event
- telemetry reject extra field
- telemetry reject PII-like field name/value
