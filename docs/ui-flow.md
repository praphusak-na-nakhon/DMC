# UI Flow

> UI and interaction flow for DMC Assistant Desktop
> Audience: implementers, QA, and product review
> Last updated: 2026-05-08

## 1. Product Goal

DMC Assistant ช่วยครูและเจ้าหน้าที่โรงเรียนทำงานกับข้อมูล DMC โดยไม่ต้องเข้าใจรายละเอียดของ Tauri, sidecar, Playwright หรือระบบ credit ภายใน ผู้ใช้ควรทำงานหลักได้จากหน้าเดียวของแต่ละโมดูล:

- ลงชื่อเข้าใช้ด้วย email/password เพื่อใช้โมดูลที่ต้องใช้เครดิต
- เห็นเครดิตพร้อมใช้ เครดิตที่กันไว้ และข้อผิดพลาดของบัญชีอย่างชัดเจน
- เลือกโมดูลงานจากหน้า Home
- เลือกไฟล์ ตรวจข้อมูลก่อนเริ่ม และเห็น preview ที่อ่านง่าย
- เริ่ม dry run หรือเริ่มงานจริงโดยมี confirmation ที่ชัดเจน
- เห็นสถานะงานระหว่างรัน รวมถึง paused, needs_auth, stopped_on_review, failed และ done
- กลับมาทำงานต่อจาก checkpoint ได้
- เปิดรายงานหรือไฟล์ output หลังจบงานได้

## 2. Primary Screens

ระบบปัจจุบันเป็น credit-only และไม่มี license activation แล้ว หน้าหลักมี:

- `Home`: เลือกโมดูล, ลงชื่อเข้าใช้, ดูเครดิต, สำรองข้อมูล, restore และอัปเดตระบบ
- `Graduation Wizard`: ตรวจไฟล์จบการศึกษา, กันเครดิต, รัน automation, pause/resume/cancel, ดูรายงาน
- `Form Converter`: ใช้ OCR แปลงแบบฟอร์ม DMC เป็น JSON และแสดง error ของ provider เป็นภาษาไทย
- `Student Basic Info`: สร้าง workbook ข้อมูลพื้นฐานนักเรียนจากไฟล์ DMC
- `P-SAR Readiness`: ตรวจความพร้อมหลักฐาน P-SAR, แนะนำไฟล์ที่ขาด, สร้างรายงาน
- `Current Students`: ตรวจแบบฟอร์มนักเรียนปัจจุบันก่อนนำเข้า

ทุกหน้าต้องใช้ข้อความภาษาไทยเป็นค่าเริ่มต้น และ error code ต้อง map เป็นข้อความที่ผู้ใช้ทำต่อได้

## 3. Global UI Rules

- ห้ามอ้าง license หรือ activation ใน UX ปัจจุบัน
- โมดูลที่ต้องใช้เครดิตต้องแสดง account/credit status ก่อนเริ่มงานจริง
- destructive action ต้องใช้ styled confirmation dialog ไม่ใช้ `window.confirm`
- งานที่รันนานต้องป้องกันการปิดหน้าต่างโดยไม่ตั้งใจ และต้องแจ้งเตือนเมื่อ done, failed หรือ needs_auth
- needs_auth ต้องมี banner บอกชัดว่าให้ไป login ใน Chromium แล้วกลับมากดทำต่อ
- status จาก API เช่น `stopped_on_review`, `paused`, `done`, `start_failed:*` ต้องแปลเป็นภาษาไทยก่อนแสดง
- loading state ต้องไม่ใช้ progress ปลอม หากยังไม่รู้เปอร์เซ็นต์จริงให้ใช้ spinner หรือ skeleton
- back affordance ควรอยู่ top-left และใช้ copy เดียวกัน เช่น `กลับหน้าหลัก`
- error pattern ควรรวมผ่าน central mapping ก่อน fallback เป็นข้อความ technical

## 4. Module Flows

### 4.1 Home

Purpose: เป็น dashboard สำหรับเลือกเครื่องมือและเตรียมบัญชี

Must show:

- สถานะบัญชีและเครดิตพร้อมใช้
- form ลงชื่อเข้าใช้ email/password
- ปุ่ม refresh credits และ sign out เมื่อ signed in
- module cards ทั้ง 5 โมดูล พร้อม badge ว่าใช้เครดิตหรือไม่
- backup, restore, diagnostics และ updater controls

Important states:

- signed out: โมดูลที่ต้องใช้เครดิตยังเปิดดูได้ แต่เริ่มงานจริงไม่ได้
- cloud unavailable: แสดง warning ภาษาไทยและให้ retry
- insufficient credits: บอกให้ติดต่อผู้ดูแลเพื่อเติมเครดิต

### 4.2 Graduation Wizard

Purpose: เป็น workflow หลักสำหรับกรอกข้อมูลจบการศึกษาเข้า DMC

Flow:

1. เลือกไฟล์ Excel
2. กดตรวจไฟล์
3. ดู preview, warning และ credit estimate
4. กด dry run หรือเริ่มงานจริง
5. งานจริงต้องแสดง confirmation ที่มีชื่อไฟล์ จำนวนแถว และเครดิตที่จะกันไว้
6. หลัง start ให้แสดง credit status เช่น `กำลังกันเครดิต`, `กันเครดิตแล้ว`, `เริ่มงานไม่สำเร็จ`
7. ระหว่างรันแสดง progress, processed/total, succeeded/failed, current page และ status ไทย
8. ถ้า needs_auth ให้แสดง banner เหนือ action buttons
9. เมื่อ done หรือ stopped_on_review ให้เปิดรายงานได้

Controls:

- `พักงาน`
- `ทำต่อหลังยืนยันตัวตน`
- `ยกเลิกงาน`
- `รีเฟรชสถานะ`
- `ซิงก์ config`
- `ติดตั้ง Chromium`

### 4.3 Form Converter

Purpose: แปลงเอกสารแบบฟอร์ม DMC เป็น JSON ผ่าน OCR

Must show:

- input เอกสารและ metadata ที่จำเป็น
- สถานะ OCR ที่ไม่ทำให้ผู้ใช้คิดว่างานค้างถ้า provider ตอบช้า
- error provider เป็นภาษาไทย เช่น permission denied, invalid API key, model unavailable, response invalid
- output path และปุ่มเปิดไฟล์เมื่อสำเร็จ

Retry behavior:

- request เดิมต้องไม่เรียก provider ซ้ำโดยไม่จำเป็น
- ถ้า provider เคยถูก charge แล้วแต่ cache หาย ให้แจ้งผู้ใช้ด้วยข้อความที่ retry อย่างปลอดภัย

### 4.4 Student Basic Info

Purpose: สร้าง Excel ข้อมูลพื้นฐานนักเรียนตาม template

Must show:

- path ไฟล์ DMC และ output path
- progress แบบซื่อสัตย์: spinner ระหว่างประมวลผล และ 100% เมื่อเสร็จ
- summary จำนวนแถว/ชีตที่สร้าง
- error ภาษาไทยสำหรับไฟล์ผิดรูปแบบหรือ column ไม่ครบ

### 4.5 P-SAR Readiness

Purpose: ตรวจหลักฐาน P-SAR และแนะนำสิ่งที่ยังขาด

Must show:

- readiness score, complete/partial/missing/needs review
- รายการ requirement แยกตาม section
- หลักฐานที่ขาดและหลักฐานที่พบ
- recommended uploads เรียงตาม priority
- mapped files
- confirmation dialog เมื่อสร้างรายงานทั้งที่ score ต่ำกว่า threshold

Copy must be Thai throughout this page.

### 4.6 Current Students

Purpose: ตรวจแบบฟอร์มนักเรียนปัจจุบันก่อน import

Must show:

- input template และไฟล์ที่กรอกแล้ว
- validation result และ warning
- progress แบบซื่อสัตย์ ไม่ใช้ setInterval เพิ่มเปอร์เซ็นต์ปลอม
- output summary หรือไฟล์ report ถ้ามี

## 5. App-Level States

- `ready`: sidecar พร้อมใช้งาน
- `connecting`: กำลังเชื่อมต่อ sidecar
- `error`: เชื่อมต่อ sidecar หรือ cloud ไม่สำเร็จ
- `signed_out`: ยังไม่ได้ลงชื่อเข้าใช้
- `credit_ready`: ลงชื่อเข้าใช้และมีเครดิตพร้อมใช้
- `credit_blocked`: เครดิตไม่พอหรือบัญชีต้องตรวจสอบ

## 6. Job-Level States

- `idle`
- `validating`
- `ready_to_run`
- `reserving`
- `running`
- `paused`
- `needs_auth`
- `stopped_on_review`
- `failed`
- `done`
- `cancelled`

Credit status ที่ต้อง render:

- `reserving`: กำลังกันเครดิต
- `reserved`: กันเครดิตแล้ว
- `finalized`: สรุปเครดิตแล้ว
- `start_failed:INSUFFICIENT_CREDITS`: เครดิตไม่พอ
- `start_failed:ACCOUNT_CLOUD_UNAVAILABLE`: ติดต่อ cloud ไม่ได้

## 7. Error and Empty States

Empty states ต้องมี next action เมื่อเหมาะสม:

- ยังไม่เลือกไฟล์: ชี้ให้กดเลือกไฟล์
- ยังไม่มี preview: ชี้ให้กดตรวจไฟล์
- ไม่มีงานใน checkpoint: ชี้ให้เริ่มงานใหม่จากไฟล์
- P-SAR ยังไม่มี mapped files: ชี้ให้อัปโหลดหลักฐาน

Blocking errors ต้องมี:

- ข้อความไทยสั้น
- สิ่งที่ผู้ใช้ควรทำต่อ
- technical code สำหรับ support เมื่อจำเป็น

## 8. Long-Running Job UX

งาน Graduation อาจใช้เวลา 10-30 นาที จึงต้องมี:

- close guard เมื่อมีงาน active
- notification หรือ window attention เมื่อ done, failed หรือ needs_auth
- ปุ่ม resume ที่ชัดเจนหลังยืนยันตัวตน
- local checkpoint list สำหรับกลับมาทำงานต่อ

## 9. Minimum QA Scenarios

- sign in สำเร็จและ refresh credits
- sign in ผิดและแสดง error ไทย
- credit ไม่พอก่อนเริ่มงานจริง
- validate Excel ผ่านและเริ่ม dry run
- เริ่มงานจริงแล้วเห็น confirmation และ credit status
- reserve credit ล้มเหลวแล้วเห็น `start_failed:*` เป็นข้อความไทย
- needs_auth ระหว่างงานและ resume หลัง login
- pause/resume/cancel ใช้ dialog และ status ถูกต้อง
- job done แล้ว notification/attention ทำงาน
- ปิดหน้าต่างขณะมีงาน active แล้ว dialog กันไว้
- Form Converter แสดง OCR provider errors เป็นไทย
- P-SAR ทั้งหน้าไม่มี label อังกฤษที่เป็น action/status หลัก

## 10. Acceptance Criteria

- ผู้ใช้ไทยอ่าน flow และทำงานจบได้โดยไม่ต้องตีความคำอังกฤษใน action/status สำคัญ
- QA ใช้เอกสารนี้เทียบกับหน้าจอจริงได้โดยไม่มี license/activation drift
- developer รู้ว่า event ใดต้องเปลี่ยน UI state ใด
- error และ status สำคัญไม่หลุดเป็น raw code เว้นแต่เป็นส่วน support detail
