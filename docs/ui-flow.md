# UI Flow

> UI and interaction flow for the Windows desktop MVP
> Audience: implementers, QA, and product review
> Last updated: 2026-04-22

---

## 1. Product Goal

แอปนี้ต้องทำให้ครูหรือเจ้าหน้าที่ที่รับผิดชอบ DMC ระดับโรงเรียนสามารถ:
- เปิดแอป
- เปิดใช้ license
- เลือกไฟล์ Excel
- ตรวจข้อมูลก่อนรัน
- login / สแกน QR เมื่อจำเป็น
- เห็นความคืบหน้า
- รับมือกับ pause/resume/re-auth/review
- ได้ report local ตอนจบงาน

โดยไม่ต้องเข้าใจ technical internals ของ Tauri, sidecar, หรือ Playwright

## 2. Primary Screens

MVP ใช้ 6 หน้าหลัก:
- `Activation`
- `Home / Job Setup`
- `Validation Preview`
- `Running Job`
- `Auth Required`
- `Run Summary`

ทุกหน้าต้องใช้ข้อความภาษาไทยใน `i18n/th.json`

## 3. Global UI Rules

- แอปต้องบอกชัดเสมอว่าข้อมูลนักเรียนไม่ถูกส่งขึ้น cloud
- ต้องมี license status visible ตลอดใน header หรือ status area
- ต้องแสดง module ปัจจุบันชัดเจนว่าเป็น `ข้อมูลจบการศึกษา`
- ต้องแสดง file path ที่ผู้ใช้เลือก
- ปุ่ม destructive เช่น `ยกเลิกงาน` ต้องมี confirm
- ถ้า app อยู่ใน offline grace mode ต้องมี banner ชัดเจน

## 4. Screen Flows

### 4.1 Activation

#### Purpose
เปิดใช้งานแอปครั้งแรก หรือเมื่อ license หมด/ถูกถอดออก

#### Inputs
- `license_key`

#### UI elements
- ช่องกรอก license key
- ปุ่ม `เปิดใช้งาน`
- ลิงก์ `ติดต่อผู้ดูแล / ต่ออายุ`
- ข้อความ privacy short note

#### States
- `idle`
- `submitting`
- `success`
- `error_invalid_license`
- `error_device_limit`
- `error_expired`
- `error_network`

#### Success behavior
- บันทึก license ลง local store
- พาไปหน้า `Home / Job Setup`

### 4.2 Home / Job Setup

#### Purpose
เป็นหน้าเริ่มต้นหลัง activate สำเร็จ

#### Required information
- โรงเรียน / tier / วันหมดอายุ
- สถานะ online/offline grace
- โมดูลที่เปิดใช้ได้

#### Controls
- selector สำหรับโมดูล
- file picker สำหรับ Excel
- ปุ่ม `ตรวจไฟล์`
- ปุ่ม `เริ่มกรอก`
- ปุ่ม `resume งานล่าสุด` ถ้ามี checkpoint/job ค้าง

#### Default behavior
- MVP มีเพียงโมดูล `ข้อมูลจบการศึกษา`
- ปุ่ม `เริ่มกรอก` disabled จนกว่าจะเลือกไฟล์และ validate ผ่านอย่างน้อย 1 ครั้ง

#### Error states
- ไม่มีไฟล์
- ไฟล์ไม่ถูกต้อง
- license หมดอายุ
- offline grace หมดแล้ว

### 4.3 Validation Preview

#### Purpose
ให้ผู้ใช้เห็นก่อนว่าไฟล์อ่านได้, level ถูกต้อง, และมี warning อะไรบ้าง

#### Show
- `detected_level`
- จำนวน rows ทั้งหมด
- จำนวน rows ที่ยอมรับ
- warning summary
- preview 5 แถวแรก

#### Actions
- `ย้อนกลับ`
- `เริ่มกรอก`
- `เริ่มแบบ dry-run`

#### Warning presentation
- warning เป็น list อ่านง่าย
- ถ้า warning มี review risk สูง เช่น status map ไม่ได้ ให้เน้นสีชัด

#### Blocking rules
- ถ้าไฟล์ invalid ห้ามไปต่อ
- ถ้าเป็นแค่ warnings ให้ไปต่อได้

### 4.4 Running Job

#### Purpose
แสดงสถานะระหว่าง automation run

#### Show
- โมดูล
- ชื่อไฟล์
- progress bar
- `processed / total`
- `succeeded / failed`
- หน้าปัจจุบัน (`current_page`) ถ้ามี
- สถานะล่าสุดของระบบ เช่น `กำลังเลือกข้อมูล`, `กำลังบันทึกหน้า`, `รอสแกน QR`

#### Actions
- `พักงาน`
- `ทำต่อ`
- `ยกเลิกงาน`

#### Optional detail panel
- recent events 5–10 รายการล่าสุดแบบไม่มี PII
- เช่น `กำลังประมวลผลหน้า 3`, `บันทึกหน้า 3 สำเร็จ`, `หยุดเพื่อให้ยืนยันตัวตน`

#### States
- `running`
- `paused`
- `needs_auth`
- `stopped_on_review`
- `failed`
- `done`

### 4.5 Auth Required

#### Trigger
- ยังไม่ได้ login
- session หมด
- QR timeout

#### Show
- ข้อความว่าแอปต้องให้ผู้ใช้ยืนยันตัวตนใน browser
- reason เช่น `กรุณาเข้าสู่ระบบ` หรือ `session หมดอายุ`
- ปุ่ม `ทำต่อหลังยืนยันตัวตนแล้ว`

#### Behavior
- browser sidecar ยังคงอยู่
- ผู้ใช้ทำ login/scan QR เอง
- เมื่อกดปุ่ม resume ให้ desktop เรียก `resume_job`

### 4.6 Run Summary

#### Purpose
สรุปผลหลัง run จบหรือหยุดเพราะ review

#### Show
- total rows
- succeeded
- failed / review items
- report path
- review report path
- ปุ่ม `เปิดโฟลเดอร์รายงาน`
- ปุ่ม `เริ่มงานใหม่`

#### If stopped on review
- ต้องแสดง stopped item summary
- บอกชัดว่าหน้าปัจจุบันยังไม่ถูก save
- แนะนำผู้ใช้ให้ตรวจ review report ก่อน

## 5. Main User Journeys

### Journey A: First successful run
1. เปิดแอป
2. กรอก license key
3. เข้า `Home`
4. เลือกไฟล์ Excel
5. กด `ตรวจไฟล์`
6. ดู preview และ warnings
7. กด `เริ่มกรอก`
8. login / scan QR ถ้าจำเป็น
9. ดู progress จนเสร็จ
10. ไปหน้า summary และเปิด report ได้

### Journey B: Session expired mid-job
1. job กำลังรัน
2. sidecar ส่ง `needs_auth`
3. UI เปลี่ยนเป็น auth-required state
4. ผู้ใช้ยืนยันตัวตนใน browser
5. กด `ทำต่อหลังยืนยันตัวตนแล้ว`
6. job resume จาก checkpoint

### Journey C: Stopped on review
1. ผู้ใช้เริ่มงานด้วย `stop_on_review = true`
2. ระบบเจอ low-confidence / unmapped / option missing
3. หน้า `Running Job` เปลี่ยนไป summary แบบ stopped
4. ผู้ใช้เห็นว่าหน้าปัจจุบันยังไม่ถูก save
5. เปิด review report ไปตรวจ

### Journey D: Offline grace mode
1. แอปเคย activate แล้ว
2. heartbeat ล้มเหลวเพราะ network
3. หน้า `Home` แสดง banner ว่าอยู่ใน offline grace mode
4. ผู้ใช้ยังเริ่มงานใหม่ได้จนกว่าจะหมด grace
5. ถ้า grace หมด ให้ disable ปุ่มเริ่มงานและแจ้งว่าต้องเชื่อมต่ออินเทอร์เน็ต

## 6. State Model

### App-level states
- `activation_required`
- `ready`
- `offline_grace`
- `license_blocked`

### Job-level states
- `idle`
- `validating`
- `ready_to_run`
- `running`
- `paused`
- `needs_auth`
- `stopped_on_review`
- `failed`
- `done`

State transition หลัก:
- `idle -> validating -> ready_to_run -> running`
- `running -> paused -> running`
- `running -> needs_auth -> running`
- `running -> stopped_on_review`
- `running -> failed`
- `running -> done`

## 7. Error and Empty States

### Empty states
- ยังไม่มี license
- ยังไม่ได้เลือกไฟล์
- ยังไม่มีงานล่าสุดให้ resume

### Recoverable errors
- network error ตอน activate
- network error ตอน heartbeat
- invalid file format
- unsupported level
- session expired

### Blocking errors
- license expired
- offline grace expired
- config signature invalid
- save button/selectors หาย

ทุก blocking error ต้องมี:
- ข้อความไทยสั้น
- สิ่งที่ผู้ใช้ควรทำต่อ
- technical code แบบย่อเพื่อใช้ support

## 8. Recommended Thai Copy Areas

ขั้นต่ำต้องเตรียม string กลุ่มนี้:
- activation
- file picker
- validation warnings
- run controls
- auth required
- summary
- offline grace
- blocking errors

ตัวอย่าง tone:
- ตรงไปตรงมา
- ไม่ใช้ศัพท์เทคนิคเกินจำเป็น
- บอก action ต่อไปชัด

ตัวอย่าง:
- `กรุณาเลือกไฟล์ Excel ก่อนเริ่มงาน`
- `ไฟล์นี้ไม่ตรงรูปแบบที่ระบบรองรับ`
- `session หมดอายุ กรุณาสแกน QR อีกครั้ง`
- `ยังใช้งานแบบออฟไลน์ได้ชั่วคราว`

## 9. Minimum QA Scenarios

- activate สำเร็จ
- activate ไม่สำเร็จเพราะ device limit
- เปิดแอปใน offline grace mode
- เลือกไฟล์ผิด format
- validate ผ่านแต่มี warnings
- เริ่ม dry-run
- เริ่ม run จริงแล้ว pause/resume
- needs_auth ระหว่างงาน
- stopped_on_review
- job failed เพราะ portal selector พัง
- run สำเร็จและเปิด report folder ได้

## 10. Acceptance Criteria

- คนที่ไม่รู้ implementation ภายในสามารถอ่าน flow แล้ววาด UI ได้ครบ
- developer รู้ว่าหน้าไหนต้องตอบสนองต่อ IPC event อะไร
- QA รู้ expected state ของแต่ละ journey
- ไม่มีหน้าหรือ flow ที่ต้องเดาเองใน MVP รอบแรก
