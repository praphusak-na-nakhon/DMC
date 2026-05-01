# Form Converter Production Readiness

โมดูล `formConverter` คือ workflow `PDF แบบฟอร์มลายมือ -> AI OCR -> review -> Excel`.
สถานะปัจจุบันตั้งใจให้เป็น implementation ที่ทดสอบ end-to-end ได้ใน staging แต่ยังไม่ควรขายกว้างก่อนผ่าน field test กับเอกสารจริง
10-20 ชุดขึ้นไป

## Phase Checklist

1. Provider abstraction
   - `DMC_OCR_PROVIDER=mock` สำหรับ dev/test
   - `DMC_OCR_PROVIDER=openai` สำหรับ cloud AI จริง
   - `DMC_OCR_OPENAI_API_KEY`, `DMC_OCR_OPENAI_MODEL`, `DMC_OCR_OPENAI_BASE_URL` ใช้กำหนด OpenAI Responses endpoint
   - `DMC_OCR_PROVIDER=gemini` สำหรับ Gemini API ผ่าน Google AI Studio key
   - `DMC_OCR_GEMINI_API_KEY`, `DMC_OCR_GEMINI_MODEL`, `DMC_OCR_GEMINI_BASE_URL` ใช้กำหนด Gemini Files + generateContent endpoint

2. Template mapping
   - v1 รองรับ `student_history_v1` เท่านั้น
   - ฟอร์มหนึ่งหน้าเท่ากับนักเรียนหนึ่งคน
   - field export คงที่: `student_id`, `first_name`, `last_name`, `birth_date`, `phone`, `address`

3. Validation/export
   - field required: `student_id`, `first_name`, `last_name`
   - `birth_date` และ `phone` มี pattern validation เบื้องต้น
   - export Excel ได้เฉพาะหลัง review แล้วเท่านั้น

4. Review UX
   - แสดง confidence/status ต่อ field
   - alternatives จาก AI กดเลือกได้
   - low-confidence และ invalid field ต้องผ่าน review ก่อน export

5. Credit controls
   - reserve credit ตามจำนวนหน้า PDF ก่อนส่ง OCR
   - capture credit ตามจำนวน record ที่ export จริง
   - release credit เมื่อ OCR ล้มเหลว หรือมีส่วนที่ไม่ได้ export

6. Privacy controls
   - Cloud OCR ต้องมี account session และ active reservation
   - Cloud ไม่ persist PDF ต้นฉบับหรือ field ที่อ่านได้
   - telemetry/admin audit/ledger ต้องไม่มีชื่อ/เลขนักเรียน

7. Synthetic performance
   - unit test ตรวจ PDF synthetic 100 และ 1,000 หน้า
   - production sizing ยังต้องทดสอบกับ PDF scan จริง เพราะขนาดภาพและคุณภาพสแกนมีผลโดยตรง

8. Field-test gate
   - ต้องมี blank form จริง 1 ชุด
   - ต้องมี PDF ที่นักเรียนกรอกจริงอย่างน้อย 10-20 ชุด
   - ก่อน release กว้างควรทดสอบ batch 100, 1,000, 5,000 หน้า จากเครื่องสแกนจริง

## Provider Notes

OpenAI provider ใช้ Responses API และส่ง PDF เป็น `input_file` แบบ base64 data URL.
ตั้งค่า staging ตัวอย่าง:

```powershell
$env:DMC_OCR_PROVIDER = "openai"
$env:DMC_OCR_OPENAI_API_KEY = "..."
$env:DMC_OCR_OPENAI_MODEL = "gpt-5.5"
corepack pnpm run cloud:dev
```

Gemini provider ใช้ Files API เพื่อ upload PDF ชั่วคราว แล้วเรียก `generateContent` ด้วย `responseMimeType=application/json`.
ตั้งค่า staging ตัวอย่าง:

```powershell
$env:DMC_OCR_PROVIDER = "gemini"
$env:DMC_OCR_GEMINI_API_KEY = "..."
$env:DMC_OCR_GEMINI_MODEL = "gemini-2.5-flash-lite"
corepack pnpm run cloud:dev
```

ถ้าไม่ได้ตั้งค่า provider หรือ key ระบบควรใช้ `mock` ใน dev/test และ block OCR จริงด้วย error ที่ผู้ใช้เข้าใจได้
เช่น `OCR_OPENAI_API_KEY_MISSING` หรือ `OCR_GEMINI_API_KEY_MISSING`.

## Manual Field Tests Still Required

- ตรวจความแม่นยำลายมือไทยจาก PDF scan จริง
- ปรับ mapping/field list ให้ตรงกับ blank form จริง
- วัดค่าใช้จ่ายและเวลา OCR ต่อ 100/1,000/5,000 หน้า
- ยืนยัน wording การยินยอมส่งข้อมูลนักเรียนขึ้น cloud AI ก่อนใช้จริง

Automation runbook: `docs/form-converter-field-test.md`
