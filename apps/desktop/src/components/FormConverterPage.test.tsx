import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { FormConverterPage } from "./FormConverterPage";

const mockRpc = vi.hoisted(() => ({
  exportDmcFormJson: vi.fn(),
  previewDmcFormJson: vi.fn(),
  openExcelDialog: vi.fn(),
  openCsvDialog: vi.fn(),
  openMarkdownDialog: vi.fn(),
}));

vi.mock("../lib/rpcClient", () => mockRpc);

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
  birth_date: "วันเกิด",
  birth_province: "จังหวัดที่เกิด",
  weight_kg: "น้ำหนัก",
  height_cm: "ส่วนสูง",
  religion: "ศาสนา",
  race: "เชื้อชาติ",
  nationality: "สัญชาติ",
  "registered_address.house_id": "รหัสประจำบ้าน",
  "registered_address.house_no": "บ้านเลขที่",
  "registered_address.subdistrict": "ตำบล",
  "registered_address.district": "อำเภอ",
  "registered_address.province": "จังหวัด",
  "registered_address.postal_code": "รหัสไปรษณีย์",
  "father.first_name": "ชื่อบิดา",
  "father.last_name": "นามสกุลบิดา",
  "mother.first_name": "ชื่อมารดา",
  "mother.last_name": "นามสกุลมารดา",
  "guardian.first_name": "ชื่อผู้ปกครอง",
  "guardian.last_name": "นามสกุลผู้ปกครอง",
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
    student_no: "19984",
    citizen_id: "1819900905157",
    grade: 1,
    room: 1,
    seat_no: 4,
    sex: "ชาย",
    prefix: "เด็กชาย",
    first_name: "อนุวัฒน์",
    last_name: "เดชอุดม",
    birth_date: "2556-01-01",
    birth_province: "บุรีรัมย์",
    weight_kg: 45,
    height_cm: 155,
    religion: "พุทธ",
    race: "ไทย",
    nationality: "ไทย",
    "registered_address.house_id": null,
    "registered_address.house_no": null,
    "registered_address.subdistrict": null,
    "registered_address.district": null,
    "registered_address.province": null,
    "registered_address.postal_code": null,
    "father.first_name": null,
    "father.last_name": null,
    "mother.first_name": null,
    "mother.last_name": null,
    "guardian.first_name": null,
    "guardian.last_name": null,
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
      warnings: [],
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
      warnings: [],
      conflicts: [missingMotherConflict],
      records: [previewRecord],
    });

    render(<FormConverterPage onBackHome={vi.fn()} onRevealPath={onRevealPath} />);

    fireEvent.click(screen.getByRole("button", { name: /เลือก Excel/ }));
    fireEvent.click(screen.getByRole("button", { name: /เลือก CSV/ }));
    fireEvent.click(screen.getByRole("button", { name: /เพิ่มไฟล์ OCR/ }));
    fireEvent.click(screen.getByRole("button", { name: /เพิ่มไฟล์ทะเบียนบ้าน/ }));
    await waitFor(() =>
      expect(screen.getByDisplayValue("C:\\dmc\\uploadTest\\studentListM1-M4 2569.xlsx")).toBeInTheDocument(),
    );
    expect(screen.getByDisplayValue("D:\\DMC\\2569\\CivilDoc.md")).toBeInTheDocument();

    expect(screen.queryByText("ประเภทงาน")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /ตรวจและแสดงตัวอย่าง/ }));

    await waitFor(() => expect(mockRpc.previewDmcFormJson).toHaveBeenCalled());
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
    expect(screen.getByRole("columnheader", { name: "ปีการศึกษา" })).toBeInTheDocument();
    expect(screen.getByText("1819900905157")).toBeInTheDocument();
    const previewHeaders = screen.getAllByRole("columnheader").map((header) => header.textContent ?? "");
    expect(previewHeaders.indexOf("เลขประจำตัวนักเรียน*")).toBeLessThan(
      previewHeaders.indexOf("เลขประจำตัวประชาชน*"),
    );
    expect(previewHeaders.indexOf("รหัสประจำบ้าน*")).toBeLessThan(previewHeaders.indexOf("ชื่อบิดา*"));
    expect(previewHeaders.indexOf("ชื่อบิดา*")).toBeLessThan(previewHeaders.indexOf("ชื่อมารดา*"));
    expect(previewHeaders.indexOf("ชื่อมารดา*")).toBeLessThan(previewHeaders.indexOf("ชื่อผู้ปกครอง*"));

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
});
