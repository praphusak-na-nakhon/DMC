# Graduation Module Spec

> Module spec for the first MVP automation module
> Scope: DMC graduation / post-graduation status workflow at school level
> Source baseline: [`fill_obec_portal.py`](/C:/dmc/fill_obec_portal.py)
> Last updated: 2026-04-22

---

## 1. Purpose

โมดูล `graduation` ใช้สำหรับช่วยกรอกสถานะการศึกษาต่อหรือการทำงานของนักเรียนที่จบการศึกษาในระบบ DMC / OBEC portal จากไฟล์ Excel ที่โรงเรียนเตรียมไว้ โดยรันบนเครื่องผู้ใช้ และข้อมูลนักเรียนกับรายงานคงอยู่ในเครื่อง

ใน MVP โมดูลนี้เป็น automation module แรกและต้อง reuse logic จาก `fill_obec_portal.py` เป็นฐาน ไม่ rewrite business rules จากศูนย์

## 2. Supported Scope

### Included in MVP
- ระดับ `ม.3`
- ระดับ `ม.6`
- อ่านข้อมูลจากไฟล์ Excel ที่มีอย่างน้อย 7 คอลัมน์
- ตรวจข้อมูลเบื้องต้น, preview, warning, run automation, สร้าง report local
- รองรับ dry-run, pause/resume, re-auth ระหว่างงาน, checkpoint resume

### Not included
- การแก้ไขข้อมูลนักเรียนใน DMC นอกฟิลด์สถานะศึกษาต่อ/ทำงาน
- การส่งไฟล์ต้นทางหรือผลลัพธ์ออกจากเครื่องโดยโมดูลนี้
- การรองรับหลายโรงเรียนใน job เดียว
- การรองรับหลายระดับชั้นปนกันใน job เดียว

## 3. Input Contract

### File format
- ประเภทไฟล์: `.xlsx`
- อ่านด้วย `pandas.read_excel(..., dtype=str).fillna("")`
- ต้องมีอย่างน้อย 7 คอลัมน์
- MVP ให้รองรับรูปแบบไฟล์ที่สคริปต์เดิมใช้อยู่เท่านั้น

### Required logical columns
ระบบอ้างตำแหน่งคอลัมน์ตาม index ไม่ใช่ชื่อคอลัมน์

| Index | Meaning | Required | Notes |
|---|---|---|---|
| `0` | `order` | Yes | ลำดับแถวในไฟล์ต้นทาง |
| `1` | `level_label` | Yes | ต้องเป็น `ม.3` หรือ `ม.6` |
| `2` | `room` | Optional | ถ้ามีใช้ช่วย score matching |
| `3` | `student_no` | Optional | normalize เหลือเฉพาะตัวเลข |
| `4` | `first_name` | Yes | ถ้าไม่มีให้ข้ามแถวนั้น |
| `5` | `last_name` | Optional | ใช้ร่วมกับ first name |
| `6` | `status_text` | Optional | ถ้า map ไม่ได้จะเป็น review item หรือ fallback ตาม rule |

### File-level rules
- job หนึ่งต้อง detect ได้ level เดียว
- level แรกที่ตรวจเจอในไฟล์เป็น `detected_level`
- ถ้าไม่พบ `ม.3` หรือ `ม.6` ในคอลัมน์ level ให้ถือว่า invalid file
- แถวที่ไม่มี `first_name` ให้ข้าม

### Validation result shape
`validate_excel(path, module="graduation")` ต้องคืนอย่างน้อย:

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

## 4. Level Rules

### `ม.3`
- `level_code = 12`
- `default_missing_code = 207`
- `ambiguity_floor = 45`
- `require_exact_student_no = true`

Behavior:
- ถ้า portal row มี `student_no` แต่หา exact match ใน source ไม่เจอ ให้เลือก `207` เป็น default
- ถ้า score ต่ำกว่า `min_score` แต่ต่ำกว่า `ambiguity_floor` ด้วย ให้ใช้ default `207`
- ถ้า score อยู่ระหว่าง `ambiguity_floor` กับ `min_score - 1` ให้เป็น review item

### `ม.6`
- `level_code = 15`
- `default_missing_code = null`
- `ambiguity_floor = null`
- `require_exact_student_no = false`

Behavior:
- ถ้าไม่ match หรือ score ต่ำกว่า threshold ให้เป็น review item
- ไม่มี default fallback code อัตโนมัติ

## 5. Status Mapping Rules

### Mapping source
- ใช้ `STATUS_CODE_MAP` เป็น source of truth ตั้งต้น
- รองรับทั้งข้อความที่มี prefix ระดับ เช่น `(ม.6) ...`
- และรองรับข้อความที่ไม่มี prefix โดยเติม prefix จาก `level_label` ก่อน lookup

### ม.6 status code 301–320 (fixed collision)
ลำดับ `(ม.6)` ใช้รหัส 301–320 ต่อเนื่องกัน:
- `301`–`308` = ศึกษาต่อสถาบันต่าง ๆ
- `309` = `(ม.6) ศึกษาต่อสถาบันอื่น ๆ`
- `310`–`318` = ไม่ศึกษาต่อ + ทำงาน/บวช
- `319` = `(ม.6) ไม่ประกอบอาชีพและไม่ศึกษาต่อ`
- `320` = `(ม.6) ศึกษาต่อต่างประเทศ`

รหัส `319` เคยถูก map ผิดเป็น `309` (ชนกับ `ศึกษาต่อสถาบันอื่น ๆ`) ซึ่งจะเขียน disposition ผิดให้กับนักเรียนจริงใน portal — แก้แล้วในทั้ง `graduation_legacy.STATUS_CODE_MAP` และ `packages/module-configs/graduation/v1.json`

### Mapping resolution
1. trim ข้อความ
2. lookup ตรงด้วย `status_text`
3. ถ้าไม่ขึ้นต้นด้วย `(` ให้ลอง lookup ด้วย `({level_label}) {status_text}`
4. ถ้ายังไม่พบ ให้ถือว่า `status_code = ""`

### `status_code_not_mapped`
กรณีที่ source row ถูก match แล้วแต่ `status_text` map เป็น code ไม่ได้:
- ไม่ submit ค่านั้น
- mark เป็น review item
- ถ้า user เปิด `stop_on_review` ให้หยุด job ที่แถวนั้น

## 6. Portal Extraction Contract

จากแต่ละ `tr[id^='tr-']` ในตาราง ต้องสกัดข้อมูลขั้นต่ำได้ดังนี้:

```json
{
  "row_id": "tr-42",
  "row_index": 42,
  "seq_no": "43",
  "room": 2,
  "student_no": "18588",
  "title": "นางสาว",
  "first_name": "นาซีนีน",
  "last_name": "เด็นมาเส",
  "full_name": "นาซีนีน เด็นมาเส"
}
```

### Required DOM assumptions
- ตารางนักเรียนมี selector `tr[id^='tr-']`
- dropdown สถานะอยู่ที่ `select[name$='.studyTypeCode']`
- ปุ่มบันทึกอยู่ที่ `form.form-horizontal.form-condensed button[name='action'][value='confirm']`
- pagination ใช้ `div.pagination li a` และ active page อยู่ที่ `div.pagination li.active a`

ถ้า selector เหล่านี้พัง ให้ถือว่าเป็น config/runtime error ไม่ใช่ data error

## 7. Matching Algorithm

### Normalization
- `normalize_text`: trim, แทน `\xa0`, ลบ whitespace ซ้ำและช่องว่างทั้งหมด
- `normalize_digits`: เก็บเฉพาะตัวเลข
- `normalize_name`: ใช้ `normalize_text` แล้วลบเครื่องหมาย/วรรณยุกต์ไทยบางชุดตามสคริปต์เดิม

### Candidate selection
1. ตัด source rows ที่ถูกใช้ไปแล้ว (`used_orders`) ออก
2. ถ้า portal row มี `student_no`:
   - หา source rows ที่ `student_no` ตรง exact
   - ถ้าพบ 1 row ให้ score = `100`
   - ถ้าพบหลาย row ให้เลือกตัวที่ได้ name score สูงสุด แต่ score result ยังเป็น `100`
3. ถ้ายังไม่ปิดเคส:
   - ถ้ามี `room` ทั้งสองฝั่ง ให้ preference กับ candidate ในห้องเดียวกัน
   - จากนั้นคำนวณ score ตามชื่อ

### Score calculation
- `first_score = similarity(normalized_first_name)`
- `last_score = similarity(normalized_last_name)`
- `full_score = similarity(normalized_full_name)`
- `joined_score = similarity(normalized_joined_name, source.normalized_full_name)`
- `room_bonus = 8` ถ้าห้องตรงกัน

ถ้ามีนามสกุล:
- `split_score = last*0.45 + first*0.35 + max(full, joined)*0.20`

ถ้าไม่มีนามสกุล:
- ใช้ `max(full, joined) + room_bonus`

score สุดท้าย clamp ที่ `0..100`

### Minimum threshold
- ค่า default `min_score` ใน baseline script คือ `72`
- MVP ต้อง expose ค่า threshold นี้เป็น job option แต่ default ยังคง `72`

## 8. Decision Outcomes Per Row

แต่ละ portal row ต้องจบด้วย outcome เดียวเท่านั้น:

| Outcome | Meaning | Review? | Save page? |
|---|---|---|---|
| `filled` | match ได้และ submit code สำเร็จ | No | Yes |
| `dry_run` | match ได้แต่ไม่ submit เพราะ dry-run | No | No submit |
| `default_missing_filled` | ใช้ default fallback code และ submit | No | Yes |
| `default_missing_dry_run` | ใช้ default fallback code ใน dry-run | No | No submit |
| `low_confidence_below_<N>` | score ต่ำกว่า threshold | Yes | Yes/Stop depending on option |
| `no_match` | หา source match ไม่ได้และไม่มี fallback | Yes | Yes/Stop depending on option |
| `status_code_not_mapped` | match ได้แต่ map status ไม่ได้ | Yes | Yes/Stop depending on option |
| `option_value_not_found` | dropdown ไม่มี value ที่ต้องการ | Yes | Yes/Stop depending on option |

### `stop_on_review`
ถ้าเปิด option นี้:
- หยุดทันทีเมื่อเจอ outcome ที่เป็น review
- หน้าปัจจุบันต้องยังไม่กด save
- คืน `stopped_item` กลับไปที่ UI

## 9. Job Options

`start_job(..., options)` สำหรับ `graduation` ต้องรองรับอย่างน้อย:

```json
{
  "dry_run": false,
  "min_score": 72,
  "resume_current": false,
  "stop_on_review": false
}
```

### Semantics
- `dry_run`: navigate + match + report แต่ไม่ submit dropdown และไม่ save page
- `min_score`: threshold สำหรับ confidence
- `resume_current`: เริ่มจากหน้าที่เปิดอยู่แทนการบังคับไปหน้า 1
- `stop_on_review`: หยุดทันทีเมื่อเจอ review item

## 10. Run Flow

1. validate Excel
2. detect `level_label`
3. build target URL จาก `level_code`
4. เปิด browser profile ในเครื่องตามค่าเริ่มต้น
5. ให้ user ทำ portal authentication ด้วยตนเองถ้าจำเป็น
6. เปิด target page ของ level นั้น
7. ถ้า `resume_current = false` ให้ไปหน้า 1
8. วนทุกหน้า:
   - extract rows
   - match และเลือก outcome
   - select dropdown เมื่อไม่ใช่ dry-run
   - save page เมื่อทั้งหน้าเสร็จและไม่มี stop-on-review
9. สร้าง local reports
10. สรุป job result

## 11. Report Contract

### Local outputs
- `obec-fill-report.json`
- `obec-fill-report.csv`
- `obec-fill-review.csv`

MVP อาจเปลี่ยนชื่อ path ได้ แต่ต้องคง logical schema เดิม

### Report row shape

```json
{
  "page": 1,
  "level": "ม.6",
  "portal_row_index": 42,
  "portal_seq_no": "43",
  "portal_student_no": "18588",
  "portal_room": 2,
  "portal_name": "นาซีนีน เด็นมาเส",
  "matched_order": 114,
  "matched_room": 2,
  "matched_student_no": "18588",
  "matched_name": "นาซีนีน เด็นมาเส",
  "matched_status_text": "(ม.6) ศึกษาต่อมหาวิทยาลัยของรัฐ",
  "matched_status_code": "301",
  "score": 100,
  "applied": true,
  "note": "filled"
}
```

### Review CSV
- filter จาก `needs_review(note)`
- ต้องมีเฉพาะ notes:
  - `low_confidence_*`
  - `no_match`
  - `status_code_not_mapped`
  - `option_value_not_found`

## 12. Error Handling

### Data/validation errors
- `INPUT_FILE_NOT_FOUND`
- `INPUT_FILE_INVALID_FORMAT`
- `INPUT_FILE_UNSUPPORTED_LEVEL`
- `INPUT_STATUS_NOT_MAPPED`

### Portal/runtime errors
- `PORTAL_LOGIN_REQUIRED`
- `PORTAL_TABLE_NOT_FOUND`
- `PORTAL_SAVE_BUTTON_NOT_FOUND`
- `PORTAL_OPTION_VALUE_NOT_FOUND`
- `PORTAL_NAVIGATION_FAILED`
- `PORTAL_SESSION_EXPIRED`

### Job control errors
- `JOB_CANCELLED`
- `JOB_STOPPED_ON_REVIEW`
- `JOB_CHECKPOINT_INVALID`

## 13. Privacy Rules

- Source Excel อาจมี student PII
- Portal DOM มี student PII
- Report files local อาจมี student PII
- ห้ามส่ง source row, portal row, report row, หรือ raw student name/number ออกจากเครื่องโดยโมดูลนี้
- เก็บเฉพาะสถานะและรายงานที่จำเป็นในเครื่อง โดยหลีกเลี่ยงการเขียน PII ลง diagnostic output

## 14. Test Scenarios

ขั้นต่ำต้องมี:
- อ่านไฟล์ที่ถูกต้องและ detect `ม.3`
- อ่านไฟล์ที่ถูกต้องและ detect `ม.6`
- reject ไฟล์ที่คอลัมน์ไม่ครบ
- exact `student_no` match แล้วได้ score 100
- room bonus ส่งผลต่อการเลือก candidate
- `ม.3` default fallback เมื่อหา exact student_no ไม่เจอ
- `ม.3` fallback เมื่อ score ต่ำกว่า ambiguity floor
- `ม.6` ไม่มี fallback แล้วได้ `no_match`
- status map ไม่ได้แล้วได้ `status_code_not_mapped`
- dropdown ไม่มี value ที่ต้องการแล้วได้ `option_value_not_found`
- `stop_on_review` หยุดงานและไม่ save current page
- dry-run ไม่ submit และไม่ save page
- session หมดระหว่าง run แล้ว resume ได้จาก checkpoint

## 15. Acceptance Criteria

- Implementer สามารถย้าย logic จาก `fill_obec_portal.py` ไป `modules/graduation.py` โดยไม่ต้องเดา rule หลัก
- UI สามารถแสดง preview, warnings, progress, review list, stopped item ได้จาก contract นี้
- เอกสารนี้ระบุขอบเขต PII และการทดสอบโดยไม่ต้องส่งข้อมูลนักเรียนออกจากเครื่อง
- Test writer สามารถสร้าง mock portal และ fixture Excel ได้จาก spec นี้
