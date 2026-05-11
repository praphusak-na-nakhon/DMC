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
  ocrDmcFormWithAkson: vi.fn(),
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

    expect(screen.queryByText("ประเภทงาน")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /ตรวจและแสดงตัวอย่าง/ }));

    await waitFor(() => expect(mockRpc.previewDmcFormJson).toHaveBeenCalled());
    expect(await screen.findByText("คำเตือนจากไฟล์ที่เลือก")).toBeInTheDocument();
    expect(screen.getByText("เลขประจำตัวประชาชนจาก CSV เครื่องสแกนบัตรหาย ถูกปิดบัง หรือ checksum ไม่ผ่าน")).toBeInTheDocument();
    expect(screen.getByText("CSV เครื่องสแกนบัตร · ThaiID M1-2569.CSV · แถว 34")).toBeInTheDocument();
    expect(await screen.findByText("ข้อมูลจำเป็นที่ยังไม่พบ")).toBeInTheDocument();
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
      gradeLevels: [1],
    });
    expect(mockRpc.exportDmcFormJson).toHaveBeenCalledWith({
      rosterExcelPath: "C:\\dmc\\uploadTest\\studentListM1-M4 2569.xlsx",
      thaiIdCsvPath: "C:\\dmc\\uploadTest\\ThaiID M1-2569.CSV",
      ocrMarkdownPaths: ["C:\\dmc\\uploadTest\\1-3ex.md"],
      civilRegistrationMarkdownPaths: ["D:\\DMC\\2569\\CivilDoc.md"],
      schoolYear: 2569,
      gradeLevels: [1],
      outputPath: null,
    });

    fireEvent.click(screen.getByRole("button", { name: /เปิดไฟล์ JSON/ }));
    expect(onRevealPath).toHaveBeenCalledWith("C:\\dmc\\reports\\dmc-form-data-2569.json");
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

    expect(await screen.findByText("Desktop runtime ยังไม่พร้อม")).toBeInTheDocument();
    expect(screen.getByText(/browser preview\/localhost/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /ลองเชื่อมต่อใหม่/ }));
    expect(onRetryRuntime).toHaveBeenCalled();
  });

  it("creates AksonOCR markdown and adds it to the DMC OCR file list", async () => {
    const onRevealPath = vi.fn();
    mockRpc.openOcrSourceDialog.mockResolvedValue("C:\\dmc\\uploadTest\\dmc-form.pdf");
    mockRpc.ocrDmcFormWithAkson.mockResolvedValue({
      module: "formConverter",
      engine: "aksonocr",
      model: "AksonOCR-1.0",
      source_path: "C:\\dmc\\uploadTest\\dmc-form.pdf",
      markdown_path: "C:\\dmc\\.dmc-assistant-data\\ocr\\aksonocr\\dmc-form-aksonocr-1-0.md",
      cached: false,
      pages_processed: 2,
      average_confidence: 91.5,
      file_sha256: "abc123",
      created_at: "2026-05-11T00:00:00+00:00",
    });

    render(<FormConverterPage onBackHome={vi.fn()} onRevealPath={onRevealPath} />);

    fireEvent.click(screen.getByRole("tab", { name: "มีไฟล์สแกน PDF/รูปภาพ" }));
    expect(screen.queryByRole("button", { name: /เลือกไฟล์ OCR จากแบบฟอร์ม DMC/ })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /เลือกไฟล์ PDF หรือรูปภาพสำหรับ AksonOCR/ }));
    await waitFor(() => {
      expect(screen.getByDisplayValue("C:\\dmc\\uploadTest\\dmc-form.pdf")).toBeInTheDocument();
    });
    fireEvent.change(screen.getByLabelText("AksonOCR API key"), { target: { value: "secret-key" } });
    fireEvent.click(screen.getByRole("button", { name: /สร้างไฟล์ OCR/ }));

    await waitFor(() => expect(mockRpc.ocrDmcFormWithAkson).toHaveBeenCalled());
    expect(mockRpc.ocrDmcFormWithAkson).toHaveBeenCalledWith({
      sourcePath: "C:\\dmc\\uploadTest\\dmc-form.pdf",
      apiKey: "secret-key",
      model: "AksonOCR-1.0",
      forceRefresh: false,
    });
    expect(screen.getByText("สร้างไฟล์ OCR แล้ว")).toBeInTheDocument();
    expect(screen.getByText("2 หน้า · confidence 91.5")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "เปิดไฟล์" }));
    expect(onRevealPath).toHaveBeenCalledWith("C:\\dmc\\.dmc-assistant-data\\ocr\\aksonocr\\dmc-form-aksonocr-1-0.md");

    fireEvent.click(screen.getByRole("tab", { name: "มีไฟล์ OCR แล้ว" }));
    expect(
      screen.getByDisplayValue("C:\\dmc\\.dmc-assistant-data\\ocr\\aksonocr\\dmc-form-aksonocr-1-0.md"),
    ).toBeInTheDocument();
  });
});
