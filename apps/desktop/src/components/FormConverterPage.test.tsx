import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { FormConverterPage } from "./FormConverterPage";

const mockRpc = vi.hoisted(() => ({
  exportDmcFormJson: vi.fn(),
  previewDmcFormJson: vi.fn(),
  openExcelDialog: vi.fn(),
  openCsvDialog: vi.fn(),
  openMarkdownDialog: vi.fn(),
  openOcrSourceDialog: vi.fn(),
  ocrDmcFormWithGemini: vi.fn(),
  saveOcrMarkdownDialog: vi.fn(),
  copyOcrMarkdownFile: vi.fn(),
}));

vi.mock("../lib/rpcClient", () => mockRpc);

beforeEach(() => {
  for (const mock of Object.values(mockRpc)) {
    mock.mockReset();
  }
});

const summary = {
  roster_records: 4,
  thai_id_scan_records: 6,
  ocr_form_records: 1,
  civil_registration_records: 1,
  records_total: 1,
  auto_matched: 1,
  needs_review: 0,
  duplicate_records: 0,
  duplicate_scan_records: 2,
  invalid_id_records: 0,
  new_or_transfer_candidates: 0,
  roster_without_thai_id: 0,
  ocr_attached_records: 1,
  ocr_unmatched_records: 0,
  review_queue_records: 0,
  warnings_total: 1,
};

const fieldLabels = {
  school_year: "ปีการศึกษา",
  student_no: "เลขประจำตัวนักเรียน",
  citizen_id: "เลขประจำตัวประชาชน",
  grade: "ชั้น",
  room: "ห้อง",
  seat_no: "เลขที่",
  sex: "เพศ",
  prefix: "คำนำหน้าชื่อ",
  first_name: "ชื่อ",
  last_name: "นามสกุล",
  first_name_en: "ชื่ออังกฤษ",
  last_name_en: "นามสกุลอังกฤษ",
  birth_date: "วันเกิด",
  birth_province: "จังหวัดที่เกิด",
  birth_hospital: "สถานพยาบาลเกิด",
  blood_type: "กลุ่มเลือด",
  weight_kg: "น้ำหนัก",
  height_cm: "ส่วนสูง",
  religion: "ศาสนา",
  race: "เชื้อชาติ",
  nationality: "สัญชาติ",
  "registered_address.house_id": "รหัสประจำบ้าน",
  "registered_address.house_no": "บ้านเลขที่",
  "registered_address.moo": "หมู่ที่ตามทะเบียน",
  "registered_address.road": "ถนนตามทะเบียน",
  "registered_address.subdistrict": "ตำบล",
  "registered_address.district": "อำเภอ",
  "registered_address.province": "จังหวัด",
  "registered_address.postal_code": "รหัสไปรษณีย์",
  "current_address.house_id": "รหัสประจำบ้านปัจจุบัน",
  "current_address.house_no": "บ้านเลขที่ปัจจุบัน",
  "current_address.moo": "หมู่ที่ปัจจุบัน",
  "current_address.road": "ถนนปัจจุบัน",
  "current_address.subdistrict": "ตำบลปัจจุบัน",
  "current_address.district": "อำเภอปัจจุบัน",
  "current_address.province": "จังหวัดปัจจุบัน",
  "current_address.postal_code": "รหัสไปรษณีย์ปัจจุบัน",
  commute_method: "การเดินทาง",
  distance_water_km: "ระยะทางทางน้ำ กม.",
  distance_dirt_road_km: "ระยะทางถนนลูกรัง กม.",
  distance_paved_road_km: "ระยะทางถนนลาดยาง กม.",
  commute_minutes: "เวลาเดินทาง นาที",
  parents_marital_status: "สถานภาพบิดามารดา",
  older_brothers: "จำนวนพี่ชาย",
  younger_brothers: "จำนวนน้องชาย",
  older_sisters: "จำนวนพี่สาว",
  younger_sisters: "จำนวนน้องสาว",
  siblings_studying_count: "จำนวนพี่น้องที่ศึกษาอยู่",
  child_order: "นักเรียนเป็นบุตรคนที่",
  "father.citizen_id": "เลขบัตรบิดา",
  "father.first_name": "ชื่อบิดา",
  "father.last_name": "นามสกุลบิดา",
  "father.occupation": "อาชีพบิดา",
  "father.income_text": "รายได้บิดา",
  "father.phone": "โทรศัพท์บิดา",
  "mother.citizen_id": "เลขบัตรมารดา",
  "mother.first_name": "ชื่อมารดา",
  "mother.last_name": "นามสกุลมารดา",
  "mother.occupation": "อาชีพมารดา",
  "mother.income_text": "รายได้มารดา",
  "mother.phone": "โทรศัพท์มารดา",
  "guardian.citizen_id": "เลขบัตรผู้ปกครอง",
  "guardian.first_name": "ชื่อผู้ปกครอง",
  "guardian.last_name": "นามสกุลผู้ปกครอง",
  "guardian.occupation": "อาชีพผู้ปกครอง",
  "guardian.income_text": "รายได้ผู้ปกครอง",
  "guardian.phone": "โทรศัพท์ผู้ปกครอง",
  guardian_relationship: "ความเกี่ยวข้องผู้ปกครอง",
};

const missingMotherConflict = {
  record_id: "roster:1.1:4:19984",
  full_name: "เด็กชาย อนุวัฒน์ เดชอุดม",
  student_no: "19984",
  citizen_id: "1819900905157",
  field_name: "mother.first_name",
  field_label: "ชื่อมารดา",
  selected_value: null,
  selected_source: null,
  selected_basis:
    "ตรวจจากบัญชีรายชื่อ, CSV เครื่องสแกนบัตร และ OCR แบบฟอร์มแล้วไม่พบข้อมูล ต้องเติมข้อมูลนี้ก่อนนำเข้า DMC",
  reason: "missing_after_all_sources",
  source_values: [],
};

const thaiIdWarning = {
  code: "THAI_ID_INVALID_OR_MASKED",
  message: "Citizen ID from Thai ID scan is missing, masked, or failed checksum validation.",
  source: "thai_id_scan",
  source_path: "C:\\dmc\\uploadTest\\ThaiID M1-2569.CSV",
  row_index: 34,
  sheet_name: null,
};

const ocrCitizenWarning = {
  code: "OCR_CITIZEN_ID_INVALID_OR_MISSING",
  message: "OCR form citizen ID is missing or failed checksum validation.",
  source: "ocr_form",
  source_path: "C:\\dmc\\uploadTest\\1-3ex.md",
  row_index: null,
  sheet_name: null,
};

const missingCitizenConflict = {
  ...missingMotherConflict,
  citizen_id: null,
  field_name: "citizen_id",
  field_label: fieldLabels.citizen_id,
};

const previewRecord = {
  record_id: "roster:1.1:4:19984",
  match_status: "auto_matched",
  student_no: "19984",
  citizen_id: "1819900905157",
  grade: 1,
  room: 1,
  seat_no: 4,
  prefix: "เด็กชาย",
  first_name: "อนุวัฒน์",
  last_name: "เดชอุดม",
  full_name: "เด็กชาย อนุวัฒน์ เดชอุดม",
  match_score: null,
  review_reasons: [],
  suggestions: [],
  sources: [],
  fields: {
    school_year: 2569,
    student_no: "19984",
    citizen_id: "1819900905157",
    grade: 1,
    room: 1,
    seat_no: 4,
    sex: "ชาย",
    prefix: "เด็กชาย",
    first_name: "อนุวัฒน์",
    last_name: "เดชอุดม",
    first_name_en: null,
    last_name_en: null,
    birth_date: "2556-01-01",
    birth_province: "บุรีรัมย์",
    birth_hospital: null,
    blood_type: null,
    weight_kg: 45,
    height_cm: 155,
    religion: "พุทธ",
    race: "ไทย",
    nationality: "ไทย",
    "registered_address.house_id": null,
    "registered_address.house_no": null,
    "registered_address.moo": null,
    "registered_address.road": null,
    "registered_address.subdistrict": null,
    "registered_address.district": null,
    "registered_address.province": null,
    "registered_address.postal_code": null,
    "current_address.house_id": null,
    "current_address.house_no": null,
    "current_address.moo": null,
    "current_address.road": null,
    "current_address.subdistrict": null,
    "current_address.district": null,
    "current_address.province": null,
    "current_address.postal_code": null,
    commute_method: null,
    distance_water_km: null,
    distance_dirt_road_km: null,
    distance_paved_road_km: null,
    commute_minutes: null,
    parents_marital_status: null,
    older_brothers: null,
    younger_brothers: null,
    older_sisters: null,
    younger_sisters: null,
    siblings_studying_count: "1",
    child_order: "2",
    "father.citizen_id": null,
    "father.first_name": null,
    "father.last_name": null,
    "father.occupation": null,
    "father.income_text": null,
    "father.phone": null,
    "mother.citizen_id": null,
    "mother.first_name": null,
    "mother.last_name": null,
    "mother.occupation": null,
    "mother.income_text": null,
    "mother.phone": null,
    "guardian.citizen_id": null,
    "guardian.first_name": null,
    "guardian.last_name": null,
    "guardian.occupation": null,
    "guardian.income_text": null,
    "guardian.phone": null,
    guardian_relationship: null,
  },
  field_details: {},
};

describe("FormConverterPage", () => {
  it("previews DMC form JSON, shows read-only missing data, and exports without operation type", async () => {
    const onRevealPath = vi.fn();
    mockRpc.openExcelDialog.mockResolvedValue("C:\\dmc\\uploadTest\\studentListM1-M4 2569.xlsx");
    mockRpc.openCsvDialog.mockResolvedValue("C:\\dmc\\uploadTest\\ThaiID M1-2569.CSV");
    mockRpc.openMarkdownDialog
      .mockResolvedValueOnce("C:\\dmc\\uploadTest\\1-3ex.md")
      .mockResolvedValueOnce("D:\\DMC\\2569\\CivilDoc.md");
    mockRpc.previewDmcFormJson.mockResolvedValue({
      module: "formConverter",
      schema_version: "dmc_form_json.v1",
      generated_at: "2026-05-07T00:00:00+00:00",
      school_year: 2569,
      grade_levels: [1],
      records_previewed: 1,
      field_labels: fieldLabels,
      summary,
      warnings: [thaiIdWarning],
      conflicts: [missingMotherConflict],
      records: [previewRecord],
    });
    mockRpc.exportDmcFormJson.mockResolvedValue({
      module: "formConverter",
      schema_version: "dmc_form_json.v1",
      generated_at: "2026-05-07T00:00:00+00:00",
      output_path: "C:\\dmc\\reports\\dmc-form-data-2569.json",
      school_year: 2569,
      grade_levels: [1],
      records_exported: 1,
      field_labels: fieldLabels,
      summary,
      warnings: [thaiIdWarning],
      conflicts: [missingMotherConflict],
      records: [previewRecord],
    });

    render(<FormConverterPage onBackHome={vi.fn()} onRevealPath={onRevealPath} />);

    fireEvent.click(screen.getByRole("button", { name: /เลือกไฟล์ Excel/ }));
    fireEvent.click(screen.getByRole("button", { name: /เลือกไฟล์ CSV/ }));
    fireEvent.click(screen.getByRole("button", { name: /เลือกไฟล์ OCR จากแบบฟอร์ม DMC/ }));
    fireEvent.click(screen.getByRole("button", { name: /เลือกไฟล์ OCR จากสำเนาทะเบียนบ้านนักเรียน/ }));
    await waitFor(() =>
      expect(screen.getByDisplayValue("C:\\dmc\\uploadTest\\studentListM1-M4 2569.xlsx")).toBeInTheDocument(),
    );
    expect(screen.getByDisplayValue("D:\\DMC\\2569\\CivilDoc.md")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("วันที่มอบตัว"), { target: { value: "2026-05-16" } });

    expect(screen.queryByText("ประเภทงาน")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /ตรวจและแสดงตัวอย่าง/ }));

    await waitFor(() => expect(mockRpc.previewDmcFormJson).toHaveBeenCalled());
    await screen.findByText("ข้อมูลจำเป็นที่ยังไม่พบ");
    expect(screen.queryByText("คำเตือนจากไฟล์ที่เลือก")).not.toBeInTheDocument();
    expect(screen.queryByText("THAI_ID_INVALID_OR_MASKED")).not.toBeInTheDocument();
    expect(screen.getByText("ข้อมูลจำเป็นที่ยังไม่พบ")).toBeInTheDocument();
    expect(screen.getByText("ชื่อมารดา")).toBeInTheDocument();
    expect(screen.getByText("ผลลัพธ์หลังตรวจครบ")).toBeInTheDocument();
    expect(screen.getByText("ไม่มีข้อมูล ต้องเติมก่อนนำเข้า")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /บันทึก/ })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /แสดงตัวอย่างข้อมูล/ }));
    expect(screen.getByRole("columnheader", { name: "ข้อมูลนักเรียน" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "ที่อยู่ตามทะเบียนบ้าน" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "ข้อมูลบิดา" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "ข้อมูลมารดา" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "ข้อมูลผู้ปกครอง" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "เลขประจำตัวประชาชน*" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "รหัสประจำบ้าน*" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "จำนวนพี่น้องที่ศึกษาอยู่" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "นักเรียนเป็นบุตรคนที่" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "ปีการศึกษา" })).toBeInTheDocument();
    expect(screen.getByText("1819900905157")).toBeInTheDocument();
    const previewTable = screen.getByRole("table");
    const previewHeaderRows = within(previewTable).getAllByRole("row").slice(0, 2);
    expect(within(previewHeaderRows[1]).getAllByRole("columnheader").map((header) => header.textContent)).toEqual(
      expect.arrayContaining(["ปีการศึกษา", "ชั้น*", "ห้อง*", "เลขที่*"]),
    );
    expect(within(previewHeaderRows[1]).getAllByRole("columnheader").slice(0, 4).map((header) => header.textContent)).toEqual([
      "ปีการศึกษา",
      "ชั้น*",
      "ห้อง*",
      "เลขที่*",
    ]);
    const topHeaderNames = within(previewHeaderRows[0]).getAllByRole("columnheader").map((header) => header.textContent);
    expect(topHeaderNames[topHeaderNames.length - 1]).toBe("สถานะ");
    const previewHeaders = screen.getAllByRole("columnheader").map((header) => header.textContent ?? "");
    const expectedFieldHeaders = [
      "ปีการศึกษา",
      "ชั้น*",
      "ห้อง*",
      "เลขที่*",
      "เลขประจำตัวประชาชน*",
      "เลขประจำตัวนักเรียน*",
      "คำนำหน้าชื่อ*",
      "เพศ*",
      "ชื่อ*",
      "นามสกุล*",
      "ชื่ออังกฤษ",
      "นามสกุลอังกฤษ",
      "วันเกิด*",
      "จังหวัดที่เกิด*",
      "สถานพยาบาลเกิด",
      "กลุ่มเลือด",
      "เชื้อชาติ*",
      "สัญชาติ*",
      "ศาสนา*",
      "รหัสประจำบ้าน*",
      "บ้านเลขที่*",
      "หมู่ที่ตามทะเบียน",
      "ถนนตามทะเบียน",
      "จังหวัด*",
      "อำเภอ*",
      "ตำบล*",
      "รหัสไปรษณีย์*",
      "รหัสประจำบ้านปัจจุบัน",
      "บ้านเลขที่ปัจจุบัน",
      "หมู่ที่ปัจจุบัน",
      "ถนนปัจจุบัน",
      "จังหวัดปัจจุบัน",
      "อำเภอปัจจุบัน",
      "ตำบลปัจจุบัน",
      "รหัสไปรษณีย์ปัจจุบัน",
      "การเดินทาง",
      "ระยะทางถนนลาดยาง กม.",
      "เวลาเดินทาง นาที",
      "น้ำหนัก*",
      "ส่วนสูง*",
      "สถานภาพบิดามารดา",
      "จำนวนพี่ชาย",
      "จำนวนน้องชาย",
      "จำนวนพี่สาว",
      "จำนวนน้องสาว",
      "จำนวนพี่น้องที่ศึกษาอยู่",
      "นักเรียนเป็นบุตรคนที่",
      "เลขบัตรบิดา",
      "ชื่อบิดา*",
      "นามสกุลบิดา*",
      "อาชีพบิดา",
      "รายได้บิดา",
      "โทรศัพท์บิดา",
      "เลขบัตรมารดา",
      "ชื่อมารดา*",
      "นามสกุลมารดา*",
      "อาชีพมารดา",
      "รายได้มารดา",
      "โทรศัพท์มารดา",
      "เลขบัตรผู้ปกครอง",
      "ชื่อผู้ปกครอง*",
      "นามสกุลผู้ปกครอง*",
      "อาชีพผู้ปกครอง",
      "รายได้ผู้ปกครอง",
      "โทรศัพท์ผู้ปกครอง",
      "ความเกี่ยวข้องผู้ปกครอง",
    ];
    expect(previewHeaders.filter((header) => expectedFieldHeaders.includes(header))).toEqual(expectedFieldHeaders);

    fireEvent.click(screen.getByRole("button", { name: /^สร้าง JSON$/ }));
    await waitFor(() => expect(mockRpc.exportDmcFormJson).toHaveBeenCalled());
    expect(mockRpc.previewDmcFormJson).toHaveBeenCalledWith({
      rosterExcelPath: "C:\\dmc\\uploadTest\\studentListM1-M4 2569.xlsx",
      thaiIdCsvPath: "C:\\dmc\\uploadTest\\ThaiID M1-2569.CSV",
      ocrMarkdownPaths: ["C:\\dmc\\uploadTest\\1-3ex.md"],
      civilRegistrationMarkdownPaths: ["D:\\DMC\\2569\\CivilDoc.md"],
      schoolYear: 2569,
      gradeLevels: null,
      admissionDate: "2026-05-16",
      confirmedMatches: [],
    });
    expect(mockRpc.exportDmcFormJson).toHaveBeenCalledWith({
      rosterExcelPath: "C:\\dmc\\uploadTest\\studentListM1-M4 2569.xlsx",
      thaiIdCsvPath: "C:\\dmc\\uploadTest\\ThaiID M1-2569.CSV",
      ocrMarkdownPaths: ["C:\\dmc\\uploadTest\\1-3ex.md"],
      civilRegistrationMarkdownPaths: ["D:\\DMC\\2569\\CivilDoc.md"],
      schoolYear: 2569,
      gradeLevels: null,
      admissionDate: "2026-05-16",
      confirmedMatches: [],
      excludedRecordIds: [],
      outputPath: null,
    });

    fireEvent.click(screen.getByRole("button", { name: /เปิดไฟล์ JSON/ }));
    expect(onRevealPath).toHaveBeenCalledWith("C:\\dmc\\reports\\dmc-form-data-2569.json");
  });

  it("shows selected-file warnings only when they affect missing fields without fallback", async () => {
    mockRpc.openExcelDialog.mockResolvedValue("C:\\dmc\\uploadTest\\studentListM1-M4 2569.xlsx");
    mockRpc.openMarkdownDialog.mockResolvedValue("C:\\dmc\\uploadTest\\1-3ex.md");
    mockRpc.previewDmcFormJson.mockResolvedValue({
      module: "formConverter",
      schema_version: "dmc_form_json.v1",
      generated_at: "2026-05-07T00:00:00+00:00",
      school_year: 2569,
      grade_levels: [1],
      records_previewed: 1,
      field_labels: fieldLabels,
      summary: { ...summary, warnings_total: 2 },
      warnings: [thaiIdWarning, ocrCitizenWarning],
      conflicts: [missingCitizenConflict],
      records: [
        {
          ...previewRecord,
          citizen_id: null,
          fields: { ...previewRecord.fields, citizen_id: null },
        },
      ],
    });

    render(<FormConverterPage onBackHome={vi.fn()} onRevealPath={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: /เลือกไฟล์ Excel/ }));
    fireEvent.click(screen.getByRole("button", { name: /เลือกไฟล์ OCR จากแบบฟอร์ม DMC/ }));
    await waitFor(() =>
      expect(screen.getByDisplayValue("C:\\dmc\\uploadTest\\studentListM1-M4 2569.xlsx")).toBeInTheDocument(),
    );

    fireEvent.click(screen.getByRole("button", { name: /ตรวจและแสดงตัวอย่าง/ }));

    expect(await screen.findByText("คำเตือนจากไฟล์ที่เลือก")).toBeInTheDocument();
    expect(screen.getByText("OCR_CITIZEN_ID_INVALID_OR_MISSING")).toBeInTheDocument();
    expect(screen.queryByText("THAI_ID_INVALID_OR_MASKED")).not.toBeInTheDocument();
  });

  it("confirms a fuzzy OCR roster candidate and re-previews with the confirmed match", async () => {
    const suggestedRecord = {
      ...previewRecord,
      record_id: "ocr:structured-ocr.json:ocr-1",
      match_status: "needs_review",
      student_no: null,
      citizen_id: "1819900405150",
      grade: null,
      room: null,
      full_name: "Mr Jirawat Wongwuthikorn",
      match_score: 0.96,
      review_reasons: ["ocr_fuzzy_roster_match_candidate", "invalid_or_missing_ocr_citizen_id"],
      suggestions: [
        {
          student_no: "19988",
          full_name: "Mr Jirawat Wongwutikorn",
          grade: 1,
          room: 3,
          score: 0.96,
          source_path: "C:\\dmc\\uploadTest\\NEW-studentlist-M1.xlsx",
          sheet_name: "Worksheet",
          row_index: 49,
        },
      ],
      sources: [
        {
          source: "ocr_form",
          source_path: "D:\\DMC\\2569\\dmc m1\\m1 DMCform\\dmc103.json",
          row_index: null,
          sheet_name: null,
        },
      ],
      fields: {
        ...previewRecord.fields,
        student_no: null,
        citizen_id: "1819900405150",
        grade: null,
        room: null,
      },
    };
    const confirmedRecord = {
      ...previewRecord,
      record_id: "roster:Worksheet:49:19988",
      student_no: "19988",
      citizen_id: "1819900965150",
      grade: 1,
      room: 3,
      full_name: "Mr Jirawat Wongwutikorn",
      sources: [
        {
          source: "roster",
          source_path: "C:\\dmc\\uploadTest\\NEW-studentlist-M1.xlsx",
          row_index: 49,
          sheet_name: "Worksheet",
        },
        {
          source: "ocr_form",
          source_path: "D:\\DMC\\2569\\dmc m1\\m1 DMCform\\dmc103.json",
          row_index: null,
          sheet_name: null,
        },
      ],
      fields: {
        ...previewRecord.fields,
        student_no: "19988",
        citizen_id: "1819900965150",
        grade: 1,
        room: 3,
      },
    };

    mockRpc.openExcelDialog.mockResolvedValue("C:\\dmc\\uploadTest\\NEW-studentlist-M1.xlsx");
    mockRpc.openMarkdownDialog.mockResolvedValue("D:\\DMC\\2569\\dmc m1\\m1 DMCform\\dmc103.json");
    mockRpc.previewDmcFormJson
      .mockResolvedValueOnce({
        module: "formConverter",
        schema_version: "dmc_form_json.v1",
        generated_at: "2026-05-07T00:00:00+00:00",
        school_year: 2569,
        grade_levels: [1],
        records_previewed: 1,
        field_labels: fieldLabels,
        summary: { ...summary, auto_matched: 0, needs_review: 1, ocr_attached_records: 0, ocr_unmatched_records: 1, review_queue_records: 1 },
        warnings: [],
        conflicts: [],
        records: [suggestedRecord],
      })
      .mockResolvedValueOnce({
        module: "formConverter",
        schema_version: "dmc_form_json.v1",
        generated_at: "2026-05-07T00:00:00+00:00",
        school_year: 2569,
        grade_levels: [1],
        records_previewed: 1,
        field_labels: fieldLabels,
        summary: { ...summary, auto_matched: 0, needs_review: 1, ocr_attached_records: 1, ocr_unmatched_records: 0, review_queue_records: 1 },
        warnings: [],
        conflicts: [],
        records: [confirmedRecord],
      });

    render(<FormConverterPage onBackHome={vi.fn()} onRevealPath={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: /เลือกไฟล์ Excel/ }));
    fireEvent.click(screen.getByRole("button", { name: /เลือกไฟล์ OCR จากแบบฟอร์ม DMC/ }));
    await waitFor(() => expect(screen.getByDisplayValue("C:\\dmc\\uploadTest\\NEW-studentlist-M1.xlsx")).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: /ตรวจและแสดงตัวอย่าง/ }));
    expect(await screen.findByText("ตรวจรายการ OCR ที่ยังจับคู่กับบัญชีรายชื่อไม่ได้")).toBeInTheDocument();
    expect(screen.getByText(/ต้องตัดสินใจให้ครบทุกรายการก่อนสร้าง JSON/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /ยืนยันว่าเป็นคนเดียวกัน/ }));

    await waitFor(() => expect(mockRpc.previewDmcFormJson).toHaveBeenCalledTimes(2));
    expect(mockRpc.previewDmcFormJson).toHaveBeenLastCalledWith({
      rosterExcelPath: "C:\\dmc\\uploadTest\\NEW-studentlist-M1.xlsx",
      thaiIdCsvPath: null,
      ocrMarkdownPaths: ["D:\\DMC\\2569\\dmc m1\\m1 DMCform\\dmc103.json"],
      civilRegistrationMarkdownPaths: [],
      schoolYear: 2569,
      gradeLevels: null,
      admissionDate: null,
      confirmedMatches: [{ record_id: "ocr:structured-ocr.json:ocr-1", student_no: "19988" }],
    });
    expect(await screen.findByText(/ยืนยันรายการแล้ว 1 รายการ/)).toBeInTheDocument();
  });

  it("allows an unmatched OCR record to be excluded from the exported JSON", async () => {
    const unmatchedRecord = {
      ...previewRecord,
      record_id: "ocr:dmc108.json:ocr-14",
      match_status: "invalid_id",
      student_no: null,
      citizen_id: null,
      grade: null,
      room: null,
      full_name: "ด.ช. สงกรานต์ มุนชี้",
      match_score: 0.6,
      review_reasons: ["ocr_form_not_linked_to_roster_or_thai_id_scan", "invalid_or_missing_ocr_citizen_id"],
      suggestions: [
        {
          student_no: "20223",
          full_name: "เด็กชาย สงกรานต์ ปานเนียม",
          grade: 1,
          room: 8,
          score: 0.6,
          source_path: "C:\\dmc\\upload\\NEW-studentlist-M1.xlsx",
          sheet_name: "Worksheet",
          row_index: 289,
        },
      ],
      sources: [
        {
          source: "ocr_form",
          source_path: "C:\\dmc\\upload\\form\\dmc108.json",
          row_index: null,
          sheet_name: null,
        },
      ],
      fields: {
        ...previewRecord.fields,
        student_no: null,
        citizen_id: null,
        grade: null,
        room: null,
        first_name: "สงกรานต์",
        last_name: "มุนชี้",
      },
    };

    mockRpc.openExcelDialog.mockResolvedValue("C:\\dmc\\upload\\NEW-studentlist-M1.xlsx");
    mockRpc.openMarkdownDialog.mockResolvedValue("C:\\dmc\\upload\\form\\dmc108.json");
    mockRpc.previewDmcFormJson.mockResolvedValue({
      module: "formConverter",
      schema_version: "dmc_form_json.v1",
      generated_at: "2026-06-04T15:18:44+00:00",
      school_year: 2569,
      grade_levels: [1],
      records_previewed: 1,
      field_labels: fieldLabels,
      summary: { ...summary, auto_matched: 0, invalid_id_records: 1, ocr_attached_records: 0, ocr_unmatched_records: 1 },
      warnings: [],
      conflicts: [],
      records: [unmatchedRecord],
    });
    mockRpc.exportDmcFormJson.mockResolvedValue({
      module: "formConverter",
      schema_version: "dmc_form_json.v1",
      generated_at: "2026-06-04T15:20:00+00:00",
      output_path: "C:\\dmc\\reports\\dmc-form-data-2569.json",
      school_year: 2569,
      grade_levels: [1],
      records_exported: 0,
      field_labels: fieldLabels,
      summary: { ...summary, records_total: 0, auto_matched: 0, invalid_id_records: 0, ocr_attached_records: 0, ocr_unmatched_records: 1 },
      warnings: [],
      conflicts: [],
      records: [],
    });

    render(<FormConverterPage onBackHome={vi.fn()} onRevealPath={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: /เลือกไฟล์ Excel/ }));
    fireEvent.click(screen.getByRole("button", { name: /เลือกไฟล์ OCR จากแบบฟอร์ม DMC/ }));
    await waitFor(() => expect(screen.getByDisplayValue("C:\\dmc\\upload\\NEW-studentlist-M1.xlsx")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: /ตรวจและแสดงตัวอย่าง/ }));

    expect(await screen.findByText("ตรวจรายการ OCR ที่ยังจับคู่กับบัญชีรายชื่อไม่ได้")).toBeInTheDocument();
    expect(screen.getByText("ด.ช. สงกรานต์ มุนชี้")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "ยืนยันว่าเป็นคนเดียวกัน" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^สร้าง JSON$/ })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "ข้าม ไม่นำเข้า JSON" }));
    expect(screen.getByText("ข้ามจาก JSON")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^สร้าง JSON$/ })).toBeEnabled();
    fireEvent.click(screen.getByRole("button", { name: /^สร้าง JSON$/ }));

    await waitFor(() => expect(mockRpc.exportDmcFormJson).toHaveBeenCalled());
    expect(mockRpc.exportDmcFormJson).toHaveBeenCalledWith(
      expect.objectContaining({
        excludedRecordIds: ["ocr:dmc108.json:ocr-14"],
      }),
    );
  });

  it("shows a retryable desktop runtime error when a file dialog is opened from browser preview", async () => {
    const onRetryRuntime = vi.fn();
    mockRpc.openExcelDialog.mockRejectedValue(
      new Error(
        'DESKTOP_RUNTIME_UNAVAILABLE: Tauri IPC is not available for command "open_excel_dialog". Open this feature in the DMC Assistant desktop window, not browser preview/localhost.',
      ),
    );

    render(<FormConverterPage onBackHome={vi.fn()} onRevealPath={vi.fn()} onRetryRuntime={onRetryRuntime} />);

    fireEvent.click(screen.getByRole("button", { name: /เลือกไฟล์ Excel/ }));

    expect((await screen.findAllByText(/Desktop runtime/)).length).toBeGreaterThan(0);
    expect(screen.getByText(/browser preview\/localhost/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "ลองเชื่อมต่อใหม่" }));
    expect(onRetryRuntime).toHaveBeenCalled();
  });

  it("creates Gemini structured JSON and adds it to the DMC OCR file list", async () => {
    const onRevealPath = vi.fn();
    mockRpc.openOcrSourceDialog.mockResolvedValue("C:\\dmc\\uploadTest\\dmc-form.pdf");
    mockRpc.ocrDmcFormWithGemini.mockResolvedValue({
      module: "formConverter",
      engine: "gemini",
      model: "gemini-3.5-flash",
      processing_mode: "batch",
      source_path: "C:\\dmc\\uploadTest\\dmc-form.pdf",
      markdown_path: "C:\\dmc\\.dmc-assistant-data\\ocr\\gemini\\dmc-form-gemini-3-5-flash-batch.json",
      structured_json_path: "C:\\dmc\\.dmc-assistant-data\\ocr\\gemini\\dmc-form-gemini-3-5-flash-batch.json",
      output_format: "structured_json",
      cached: false,
      pages_processed: 2,
      pages_estimated: 2,
      credits_per_page: 3,
      credits_charged: 6,
      charged: true,
      credit_reservation_id: "reservation-dmc",
      average_confidence: 91.5,
      usage_metadata: {
        prompt_token_count: 1400,
        candidates_token_count: 500,
        total_token_count: 1900,
        cached_content_token_count: null,
        thoughts_token_count: null,
        input_tokens_per_page: 700,
        output_tokens_per_page: 250,
        total_tokens_per_page: 950,
      },
      batch_job_name: "batches/dmc",
      batch_state: "JOB_STATE_SUCCEEDED",
      file_sha256: "abc123",
      created_at: "2026-05-11T00:00:00+00:00",
    });

    render(<FormConverterPage onBackHome={vi.fn()} onRevealPath={onRevealPath} />);

    const dmcOcrCard = screen.getByText("ไฟล์ OCR จากแบบฟอร์ม DMC").closest("section") as HTMLElement;
    fireEvent.click(within(dmcOcrCard).getByRole("tab", { name: "มีไฟล์สแกน PDF/รูปภาพ" }));
    expect(within(dmcOcrCard).queryByRole("button", { name: /เลือกไฟล์ OCR จากแบบฟอร์ม DMC/ })).not.toBeInTheDocument();
    fireEvent.click(within(dmcOcrCard).getByRole("button", { name: /เลือกไฟล์ PDF หรือรูปภาพสำหรับ Gemini/ }));
    await waitFor(() => {
      expect(screen.getByDisplayValue("C:\\dmc\\uploadTest\\dmc-form.pdf")).toBeInTheDocument();
    });
    fireEvent.click(within(dmcOcrCard).getByRole("button", { name: /สร้างไฟล์ OCR/ }));

    await waitFor(() => expect(mockRpc.ocrDmcFormWithGemini).toHaveBeenCalled());
    expect(mockRpc.ocrDmcFormWithGemini).toHaveBeenCalledWith({
      sourcePath: "C:\\dmc\\uploadTest\\dmc-form.pdf",
      apiKey: null,
      model: "gemini-3.5-flash",
      processingMode: "batch",
      forceRefresh: false,
    });
    expect(within(dmcOcrCard).getByText("สร้างไฟล์ OCR แล้ว")).toBeInTheDocument();
    expect(
      within(dmcOcrCard).getByText(
        "2 หน้า · Gemini 3.5 Flash Batch · confidence 91.5 · 1,900 tokens (950/หน้า) · ใช้ 6 เครดิต (3 เครดิต/หน้า)",
      ),
    ).toBeInTheDocument();

    fireEvent.click(within(dmcOcrCard).getByRole("button", { name: "เปิดไฟล์" }));
    expect(onRevealPath).toHaveBeenCalledWith("C:\\dmc\\.dmc-assistant-data\\ocr\\gemini\\dmc-form-gemini-3-5-flash-batch.json");

    mockRpc.saveOcrMarkdownDialog.mockResolvedValue("D:\\DMC\\OCR\\dmc-form-ocr.json");
    mockRpc.copyOcrMarkdownFile.mockResolvedValue("D:\\DMC\\OCR\\dmc-form-ocr.json");
    fireEvent.click(within(dmcOcrCard).getByRole("button", { name: /บันทึกเป็น/ }));
    await waitFor(() => expect(mockRpc.copyOcrMarkdownFile).toHaveBeenCalled());
    expect(mockRpc.saveOcrMarkdownDialog).toHaveBeenCalledWith("dmc-form-gemini-3-5-flash-batch.json");
    expect(mockRpc.copyOcrMarkdownFile).toHaveBeenCalledWith(
      "C:\\dmc\\.dmc-assistant-data\\ocr\\gemini\\dmc-form-gemini-3-5-flash-batch.json",
      "D:\\DMC\\OCR\\dmc-form-ocr.json",
    );

    fireEvent.click(within(dmcOcrCard).getByRole("tab", { name: "มีไฟล์ OCR แล้ว" }));
    expect(within(dmcOcrCard).getByDisplayValue("D:\\DMC\\OCR\\dmc-form-ocr.json")).toBeInTheDocument();
  });

  it("creates Gemini structured JSON and adds it to the civil registration OCR file list", async () => {
    mockRpc.openOcrSourceDialog.mockResolvedValue("C:\\dmc\\uploadTest\\civil-registration.pdf");
    mockRpc.ocrDmcFormWithGemini.mockResolvedValue({
      module: "formConverter",
      engine: "gemini",
      model: "gemini-3.5-flash",
      processing_mode: "batch",
      source_path: "C:\\dmc\\uploadTest\\civil-registration.pdf",
      markdown_path: "C:\\dmc\\.dmc-assistant-data\\ocr\\gemini\\civil-registration-gemini-3-5-flash-batch.json",
      structured_json_path: "C:\\dmc\\.dmc-assistant-data\\ocr\\gemini\\civil-registration-gemini-3-5-flash-batch.json",
      output_format: "structured_json",
      cached: false,
      pages_processed: 1,
      pages_estimated: 1,
      credits_per_page: 3,
      credits_charged: 3,
      charged: true,
      credit_reservation_id: "reservation-civil",
      average_confidence: 94,
      usage_metadata: {
        prompt_token_count: 800,
        candidates_token_count: 300,
        total_token_count: 1100,
        cached_content_token_count: null,
        thoughts_token_count: null,
        input_tokens_per_page: 800,
        output_tokens_per_page: 300,
        total_tokens_per_page: 1100,
      },
      batch_job_name: "batches/civil",
      batch_state: "JOB_STATE_SUCCEEDED",
      file_sha256: "civil123",
      created_at: "2026-05-12T00:00:00+00:00",
    });

    render(<FormConverterPage onBackHome={vi.fn()} onRevealPath={vi.fn()} />);

    const civilCard = screen.getByText("ไฟล์ OCR จากสำเนาทะเบียนบ้านนักเรียน").closest("section") as HTMLElement;
    fireEvent.click(within(civilCard).getByRole("tab", { name: "มีไฟล์สแกน PDF/รูปภาพ" }));
    expect(
      within(civilCard).queryByRole("button", { name: /เลือกไฟล์ OCR จากสำเนาทะเบียนบ้านนักเรียน/ }),
    ).not.toBeInTheDocument();
    fireEvent.click(within(civilCard).getByRole("button", { name: /เลือกไฟล์ PDF หรือรูปภาพสำหรับ Gemini/ }));
    await waitFor(() => {
      expect(screen.getByDisplayValue("C:\\dmc\\uploadTest\\civil-registration.pdf")).toBeInTheDocument();
    });
    fireEvent.click(within(civilCard).getByRole("button", { name: /สร้างไฟล์ OCR/ }));

    await waitFor(() => expect(mockRpc.ocrDmcFormWithGemini).toHaveBeenCalled());
    expect(mockRpc.ocrDmcFormWithGemini).toHaveBeenCalledWith({
      sourcePath: "C:\\dmc\\uploadTest\\civil-registration.pdf",
      apiKey: null,
      model: "gemini-3.5-flash",
      processingMode: "batch",
      forceRefresh: false,
    });
    expect(within(civilCard).getByText("สร้างไฟล์ OCR แล้ว")).toBeInTheDocument();
    expect(
      within(civilCard).getByText(
        "1 หน้า · Gemini 3.5 Flash Batch · confidence 94 · 1,100 tokens (1,100/หน้า) · ใช้ 3 เครดิต (3 เครดิต/หน้า)",
      ),
    ).toBeInTheDocument();

    mockRpc.saveOcrMarkdownDialog.mockResolvedValue("D:\\DMC\\OCR\\civil-registration-ocr.json");
    mockRpc.copyOcrMarkdownFile.mockResolvedValue("D:\\DMC\\OCR\\civil-registration-ocr.json");
    fireEvent.click(within(civilCard).getByRole("button", { name: /บันทึกเป็น/ }));
    await waitFor(() => expect(mockRpc.copyOcrMarkdownFile).toHaveBeenCalled());
    expect(mockRpc.saveOcrMarkdownDialog).toHaveBeenCalledWith("civil-registration-gemini-3-5-flash-batch.json");
    expect(mockRpc.copyOcrMarkdownFile).toHaveBeenCalledWith(
      "C:\\dmc\\.dmc-assistant-data\\ocr\\gemini\\civil-registration-gemini-3-5-flash-batch.json",
      "D:\\DMC\\OCR\\civil-registration-ocr.json",
    );

    fireEvent.click(within(civilCard).getByRole("tab", { name: "มีไฟล์ OCR แล้ว" }));
    expect(within(civilCard).getByDisplayValue("D:\\DMC\\OCR\\civil-registration-ocr.json")).toBeInTheDocument();
  });
});
