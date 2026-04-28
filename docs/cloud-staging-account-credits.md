# Cloud staging: account + credits

เอกสารนี้ใช้สำหรับรัน cloud แบบ staging ในเครื่อง, สร้าง user, เติมเครดิต และทดสอบ live run ที่ต้องใช้เครดิต

## 1. ตั้งค่า environment

PowerShell:

```powershell
cd C:\dmc
$env:DMC_CLOUD_SQLITE_PATH = "C:\dmc\.cloud-staging.sqlite3"
$env:DMC_CLOUD_API_BEARER_TOKEN = "change-this-admin-token"
$env:DMC_CLOUD_BASE_URL = "http://127.0.0.1:8000"
```

`DMC_CLOUD_API_BEARER_TOKEN` ใช้เรียก admin API เท่านั้น อย่าใช้ค่าเดียวกันใน production

## 2. รัน cloud staging

```powershell
corepack pnpm run cloud:dev
```

หรือรันตรงด้วย Python:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir apps/cloud --host 127.0.0.1 --port 8000 --reload
```

ตรวจ health:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

## 3. สร้าง user สำหรับครู

```powershell
.\.venv\Scripts\python.exe apps\cloud\scripts\manage_accounts.py seed-user `
  --email teacher@example.test `
  --password correct-password `
  --display-name "Teacher Demo"
```

`seed-user` รันซ้ำได้ ถ้า user มีอยู่แล้วจะอัปเดตชื่อ/สถานะ แต่จะไม่ reset password เว้นแต่ใส่ `--reset-password`

ดูข้อมูล user และ wallet:

```powershell
.\.venv\Scripts\python.exe apps\cloud\scripts\manage_accounts.py show --email teacher@example.test
```

## 4. เติมเครดิตแบบ manual admin

หลังตรวจการชำระเงินแล้ว ให้เติมเครดิตด้วยคำสั่งนี้:

```powershell
.\.venv\Scripts\python.exe apps\cloud\scripts\manage_accounts.py topup `
  --email teacher@example.test `
  --amount 500 `
  --note "manual payment receipt #001" `
  --idempotency-key "receipt-001"
```

ดู ledger:

```powershell
.\.venv\Scripts\python.exe apps\cloud\scripts\manage_accounts.py ledger --email teacher@example.test
```

ถ้ารันคำสั่ง top-up ด้วย `--idempotency-key` เดิมซ้ำ ระบบจะไม่เติมเครดิตซ้ำ

## 5. ทดสอบกับ desktop/sidecar

1. รัน cloud staging ตามข้อ 2
2. รัน desktop:

```powershell
corepack pnpm --dir apps/desktop exec tauri dev
```

3. เปิดหน้า Home แล้วลงชื่อเข้าใช้ด้วย email/password ที่สร้างไว้
4. ตรวจว่า credit balance แสดงถูกต้อง
5. เข้าโมดูลข้อมูลสิ้นปีการศึกษา
6. ตรวจไฟล์ Excel แล้วกดเริ่มส่งข้อมูลเข้า DMC

Live run จะเริ่มได้ก็ต่อเมื่อ cloud ติดต่อได้, login แล้ว และเครดิตพอ ระบบจะ reserve เครดิตก่อนเปิด browser และ capture/release หลังงานจบตามผลจริง

## 6. Admin API ขั้นต่ำ

ต้องส่ง header:

```text
Authorization: Bearer change-this-admin-token
```

Endpoints:

- `POST /v1/admin/users` สร้าง user
- `GET /v1/admin/users` ดูรายการ user
- `GET /v1/admin/users/{user_id}` ดู user รายเดียว
- `PATCH /v1/admin/users/{user_id}` แก้ display name, password หรือ status
- `GET /v1/admin/users/{user_id}/wallet` ดู wallet
- `POST /v1/admin/users/{user_id}/credits/topup` เติมเครดิต
- `GET /v1/admin/users/{user_id}/ledger` ดู ledger

## 7. ข้อจำกัด staging

- ยังไม่มี payment gateway
- ยังไม่มี self-registration
- admin token เป็น shared bearer token
- production ควรย้ายไปใช้ managed DB, secret manager, audit log และ admin auth แยกต่างหาก
