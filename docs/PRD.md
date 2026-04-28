# PRD — DMC Assistant (Desktop App + Cloud Licensing)

> Product Requirements Document
> Version: 0.2 (MVP baseline)
> Last updated: 2026-04-22

---

## 1. Vision

เครื่องมือ desktop สำหรับครู/เจ้าหน้าที่ธุรการ ใช้กรอกข้อมูลในระบบ DMC / OBEC portal แบบกึ่งอัตโนมัติจากไฟล์ Excel โดยข้อมูลนักเรียนยังอยู่ในโรงเรียน ขายเป็น SaaS ผ่านระบบ license key และ billing รายเดือน/รายปี

## 2. Problem Statement

- โรงเรียนในสังกัด สพฐ. ต้องกรอกข้อมูลจำนวนมากเข้าระบบ DMC ทุกปี (ข้อมูลนักเรียน, จบการศึกษา, ครุภัณฑ์ ฯลฯ)
- ปัจจุบันต้องกรอกมือทีละคน ใช้เวลาหลายวัน ผิดพลาดง่าย
- ระบบ DMC บังคับ 2FA แบบสแกน QR (ThaID) จึงไม่สามารถทำ full automation บน cloud ได้
- ข้อมูลนักเรียนอยู่ภายใต้ PDPA จึงไม่ควรส่งออกนอกโรงเรียน

## 3. Target Users

### Primary
- **ครูงานทะเบียน / งานวิชาการ** — ผู้กรอกข้อมูลหลัก อายุ 30–55 ปี ใช้ Windows, Excel คล่อง, เทคนิคพอใช้
- **เจ้าหน้าที่ธุรการ** — รับผิดชอบงานเอกสาร DMC โดยตรง

### Secondary
- **ผู้อำนวยการโรงเรียน** — ผู้อนุมัติจ่ายเงิน สนใจเรื่อง compliance และการประหยัดเวลาครู

## 4. User Persona

**ครูสมศรี** (อายุ 45, ร.ร.ขนาดกลาง 800 คน)
- ต้องกรอกข้อมูลจบ ม.6 จำนวน 200 คน เข้าระบบ DMC ภายใน 30 มิ.ย.
- ใช้เวลา 3 วันทำงาน กรอกมือทีละคน ตาลาย
- กลัวกรอกผิด แล้วถูกเขตตำหนิ
- Pain: "อยากได้เครื่องมือกรอกให้อัตโนมัติ แต่ไม่อยากเอาข้อมูลนักเรียนไปไว้บน cloud"

## 5. Current Prototype vs MVP Direction

### Current Prototype (สิ่งที่มีอยู่จริงตอนนี้)
- มีสคริปต์ CLI `fill_obec_portal.py` สำหรับโมดูลจบการศึกษา
- ใช้ Playwright เปิด Chromium บนเครื่องผู้ใช้เอง
- ผู้ใช้ login และเตรียมหน้า browser แบบ manual ก่อนเริ่มรัน
- ใช้ fuzzy match ชื่อ/ห้องเรียนจากไฟล์ Excel เพื่อเลือก status code
- สร้างผลลัพธ์เป็นไฟล์ `json`, `csv`, และ `review csv` ในเครื่อง
- ยังไม่มี desktop UI, license system, cloud config, checkpoint, telemetry, หรือ packaging แบบ product

### MVP Direction (สิ่งที่เอกสารนี้กำหนด)
- สร้าง desktop app แบบ Windows-first และใช้ automation บนเครื่องผู้ใช้
- โฟกัส workflow ระดับโรงเรียน สำหรับครู/เจ้าหน้าที่ที่รับผิดชอบ DMC โดยตรง
- เริ่มจากโมดูล **ข้อมูลจบการศึกษา** โดย reuse logic จาก `fill_obec_portal.py`
- เพิ่ม license activation, device binding, remote config, progress UI, report export, app update
- ส่งขึ้น cloud ได้เฉพาะข้อมูลด้าน licensing/config/allow-listed telemetry ที่ไม่มี PII

## 6. User Stories (MVP)

### Epic 1: License & Onboarding
- US-01: ครูดาวน์โหลดแอปจากเว็บของเรา ติดตั้งบน Windows ได้ใน < 3 นาที
- US-02: ครูกรอก license key แล้วแอปตรวจกับ cloud และเปิดใช้งานได้
- US-03: ถ้า license หมดอายุ แอปแจ้งเตือนล่วงหน้า 7 วัน และพาไปขั้นตอนต่ออายุ
- US-04: 1 license = 1 โรงเรียน, ผูกกับ device สูงสุด 3 เครื่อง
- US-05: tier ของ license สำหรับโรงเรียนแบบ paid ถูกกำหนดจาก `จำนวนนักเรียนทั้งหมดของโรงเรียน` ณ เวลาที่ activate หรือ renew
- US-06: ถ้าเครื่องเคย activate แล้วและเน็ตมีปัญหา แอปยังใช้งานต่อได้ใน grace window 7 วันโดยไม่ต้อง activate ใหม่

### Epic 2: Data Preparation
- US-07: ครูเลือก "โมดูล" (เช่น "ข้อมูลจบการศึกษา ปี 2568")
- US-08: ครูอัปโหลดไฟล์ Excel template แล้วแอปตรวจคอลัมน์และแสดงตัวอย่าง 5 แถว
- US-09: แอปตรวจความถูกต้อง (ชื่อซ้ำ, รหัสสถานะไม่รู้จัก) และแสดง warning ก่อนรัน
- US-10: ครูแก้ไข mapping สถานะได้ (เช่น "ทำงานรับจ้าง" → code 317)

### Epic 3: Automation Run
- US-11: ครูกด "เริ่มกรอก" แล้วแอปเปิด Chromium และนำทางไปหน้า DMC
- US-12: QR code โผล่ แล้วครูสแกนด้วย ThaID จากนั้นแอปดำเนินการต่อ
- US-13: แอปแสดง progress real-time (เช่น กรอกคนที่ 42/200, สำเร็จ 40, รอตรวจ 2)
- US-14: ครู pause/resume/cancel ได้ระหว่างรัน
- US-15: ถ้า session หมด แอปหยุดและแจ้งครูสแกน QR ใหม่ แล้วทำต่อจาก checkpoint ล่าสุด

### Epic 4: Review & Report
- US-16: หลังเสร็จ แอปสร้างรายงาน Excel แยก สำเร็จ / ไม่พบในระบบ / ต้องตรวจสอบ
- US-17: ครู export รายงานได้ และ report files ทั้งหมดเก็บไว้ในเครื่อง
- US-18: log และ audit trail ในเครื่องต้องไม่มีข้อมูลนักเรียนที่ระบุตัวตนได้
- US-19: แอปส่ง metadata กลับ cloud เพื่อปรับปรุงได้ แต่ต้องเป็น allow-listed telemetry เท่านั้นและไม่มี PII

### Epic 5: Cloud Admin (ทีมเรา)
- US-20: Admin สร้าง license และดู device activation ของแต่ละโรงเรียน
- US-21: Admin บันทึก `student_count_total` และผูกโรงเรียนเข้ากับ school-size tier ได้
- US-22: Admin push อัปเดต selector/config ใหม่ไปยังทุก client ได้เมื่อ portal เปลี่ยน UI
- US-23: Admin ดู aggregate usage โดยไม่เห็น PII

## 7. Functional Requirements

### MVP (Phase 1) — 3 เดือน
1. **โมดูล "ข้อมูลจบการศึกษา"** — เอา `fill_obec_portal.py` เดิมมาห่อเป็นพื้นฐาน
2. License activation + device binding (`1 school = 3 devices`)
3. School-size tier สำหรับ paid license โดยใช้ `student_count_total` เป็นฐาน
4. Trial 14 วัน, 50 records, โมดูลจบการศึกษา, privacy/device policy เดียวกับ paid license
5. Auto-update config (selectors) จาก cloud
6. Excel import + validation
7. Progress UI + pause/resume/cancel
8. รายงาน Excel output ที่เก็บในเครื่องเท่านั้น
9. Allow-listed telemetry only; ไม่มี student PII ทุกกรณี
10. Auto-update ตัวแอป

### Phase 2 — เดือนที่ 4–6
- โมดูล "ข้อมูลนักเรียนรายบุคคล" (สิ้นปี/ต้นปี)
- Billing self-service (Omise / 2C2P / PromptPay; final choice TBD)

### Phase 3 — เดือนที่ 7–12
- ยังไม่วาง scope เพิ่มเติมนอกเหนือจากงาน DMC ระดับโรงเรียน จนกว่าจะได้ feedback จาก MVP และ pilot schools

## 8. Non-Functional Requirements

### Performance
- เริ่มต้นแอป < 3 วินาที
- กรอก 1 record ≤ 8 วินาทีเฉลี่ย (รวม network)
- รองรับไฟล์ Excel ≤ 5,000 แถว/ครั้ง

### Security / Privacy
- **ข้อมูลนักเรียนต้องไม่ถูกส่งขึ้น cloud ไม่ว่ากรณีใด** (hard rule)
- Cloud sync อนุญาตเฉพาะ `license key`, `device ID`, remote config request/response, และ allow-listed telemetry ที่ไม่มี PII
- Credential DMC (ถ้ามี) เก็บใน Windows Credential Manager (DPAPI)
- Report files อาจมีข้อมูลนักเรียนได้ แต่ต้องเก็บในเครื่องเท่านั้น
- Log, audit trail, telemetry, และ cloud payload ทุกชนิดต้องไม่มี student PII
- ผู้ใช้ต้องสามารถลบ log/report files ในเครื่องได้ตลอดเวลา
- เป็นไปตาม PDPA (มีหนังสือแจ้งการประมวลผลข้อมูลให้โรงเรียน)

### Reliability
- ถ้า portal เปลี่ยน UI ทีมต้องปรับ selector ได้ใน < 48 ชม.
- แอปต้อง recover จาก crash ได้ (resume จาก checkpoint)
- Uptime ของ cloud licensing ≥ 99%
- แอปต้องตรวจ heartbeat อย่างน้อยวันละ 1 ครั้งเมื่อ online
- เครื่องที่เคย activate แล้วต้องใช้งานต่อแบบ offline ได้ใน grace window 7 วัน ถ้า heartbeat ล้มเหลว
- การ activate เครื่องใหม่ต้อง online เสมอ

### Compatibility
- Windows 10 / 11 (x64)
- (อนาคต) macOS 12+

## 9. Success Metrics

### Business
- 3 เดือนแรก: ทดสอบกับ 5 โรงเรียน (ฟรี) และเก็บ feedback
- 6 เดือน: 50 โรงเรียนจ่ายเงิน
- 12 เดือน: 300 โรงเรียน, MRR ≥ 100,000 บาท

### Product
- Activation rate: ติดตั้ง → ใช้งานจริงครั้งแรก ≥ 70%
- Retention: ต่ออายุเดือนที่ 2 ≥ 80%
- NPS ≥ 40
- เวลากรอก 200 records ลดจาก 3 วัน → < 2 ชม.

## 10. Licensing & Pricing (tentative)

### Pricing Model
- Paid license ทุกโรงเรียนได้โมดูล `graduation` เหมือนกันใน MVP
- ความต่างของ tier ใน MVP อยู่ที่ราคาเชิงพาณิชย์ตามขนาดโรงเรียน ไม่ใช่การเปิดปิดฟีเจอร์
- `Monthly` และ `Annual` เป็น billing interval ไม่ใช่ product plan
- ขนาดโรงเรียนวัดจาก `student_count_total` ณ เวลาที่ activate หรือ renew

| License Type | เกณฑ์โรงเรียน | Billing Interval | ราคา | ฟีเจอร์ |
|---|---|---|---|---|
| Free trial | ทุกโรงเรียน | 14 วัน | 0 ฿ | โมดูลจบการศึกษา, 50 records, 3 devices |
| Paid tier S | `student_count_total <= 500` | Monthly / Annual | TBD | โมดูลจบการศึกษา, 3 devices |
| Paid tier M | `student_count_total 501–1500` | Monthly / Annual | TBD | โมดูลจบการศึกษา, 3 devices |
| Paid tier L | `student_count_total > 1500` | Monthly / Annual | TBD | โมดูลจบการศึกษา, 3 devices |

## 11. Out of Scope (MVP)

- ❌ macOS / Linux
- ❌ Mobile app
- ❌ การเก็บข้อมูลนักเรียนบน cloud
- ❌ การ integrate กับระบบโรงเรียนภายใน (SIS ต่าง ๆ)
- ❌ การรันแบบ server-side automation
- ❌ Web dashboard สำหรับผู้บริหาร
- ❌ โมดูลข้อมูลครูและบุคลากร
- ❌ โมดูล EMIS, B-OBEC, Q-INFO
- ❌ รายงาน 10 มิ.ย. / 10 พ.ย.
- ❌ Multi-school mode
- ❌ Scheduled run
- ❌ Multi-language (ไทยอย่างเดียวก่อน)

## 12. Risks & Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| OBEC ห้าม automation ใน ToS | สูง | ปรึกษานักกฎหมาย, ออกแบบให้เป็น local-assisted automation ไม่ใช่ server-side scrape |
| Portal เปลี่ยน UI กะทันหัน | กลาง | Remote config, unit test selectors, hotfix ภายใน 48 ชม. |
| ครูไม่ไว้ใจ (กลัวข้อมูลรั่ว) | สูง | Open source client บางส่วน, audit report, demo ให้ดูว่าไม่มี upload PII |
| ThaID QR login เปลี่ยน flow | กลาง | Decouple login step, ให้ครู manual login ได้ถ้าจำเป็น |
| โรงเรียนแจ้งขนาดนักเรียนไม่ตรง tier | กลาง | ผูก tier กับ `student_count_total` ตอน activate/renew และให้ admin ตรวจทานได้ |
| ผู้เล่นรายใหญ่ลอก | กลาง | เน้น distribution, service, และความเร็วในการตาม portal change |

## 13. Open Questions

- [ ] ToS ของ DMC portal อนุญาต automation หรือไม่
- [ ] ต้องจดทะเบียนนิติบุคคลก่อนขายหรือไม่
- [ ] PG สำหรับเก็บเงินจะเลือก Omise, 2C2P หรือ PromptPay manual
- [ ] จะ open-source client ส่วนใดบ้างเพื่อสร้างความไว้วางใจ
