import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { FormConverterPage } from "./FormConverterPage";

const mockRpc = vi.hoisted(() => ({
  exportDmcFormJson: vi.fn(),
  openExcelDialog: vi.fn(),
  openCsvDialog: vi.fn(),
  openMarkdownDialog: vi.fn(),
}));

vi.mock("../lib/rpcClient", () => mockRpc);

describe("FormConverterPage", () => {
  it("exports DMC form JSON from roster, Thai ID CSV, and OCR markdown without operation type", async () => {
    const onRevealPath = vi.fn();
    mockRpc.openExcelDialog.mockResolvedValue("C:\\dmc\\uploadTest\\studentListM1-M4 2569.xlsx");
    mockRpc.openCsvDialog.mockResolvedValue("C:\\dmc\\uploadTest\\ThaiID M1-2569.CSV");
    mockRpc.openMarkdownDialog.mockResolvedValue("C:\\dmc\\uploadTest\\1-3ex.md");
    mockRpc.exportDmcFormJson.mockResolvedValue({
      module: "formConverter",
      schema_version: "dmc_form_json.v1",
      generated_at: "2026-05-07T00:00:00+00:00",
      output_path: "C:\\dmc\\reports\\dmc-form-data-2569.json",
      school_year: 2569,
      grade_levels: [1],
      records_exported: 1,
      field_labels: {},
      summary: {
        roster_records: 4,
        thai_id_scan_records: 6,
        ocr_form_records: 1,
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
      },
      warnings: [],
      conflicts: [
        {
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
        },
      ],
      records: [],
    });

    render(<FormConverterPage onBackHome={vi.fn()} onRevealPath={onRevealPath} />);

    fireEvent.click(screen.getByRole("button", { name: /เลือก Excel/ }));
    fireEvent.click(screen.getByRole("button", { name: /เลือก CSV/ }));
    fireEvent.click(screen.getByRole("button", { name: /เพิ่มไฟล์ OCR/ }));
    await waitFor(() =>
      expect(screen.getByDisplayValue("C:\\dmc\\uploadTest\\studentListM1-M4 2569.xlsx")).toBeInTheDocument(),
    );

    expect(screen.queryByText("ประเภทงาน")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /สร้าง JSON/ }));

    await waitFor(() => expect(mockRpc.exportDmcFormJson).toHaveBeenCalled());
    expect(await screen.findByText("ข้อมูลจำเป็นที่ยังไม่พบ")).toBeInTheDocument();
    expect(screen.getByText("ชื่อมารดา")).toBeInTheDocument();
    expect(screen.getByText("ไม่มีข้อมูล ต้องเติมก่อนนำเข้า")).toBeInTheDocument();
    expect(screen.queryByText("ยึดหลัก")).not.toBeInTheDocument();
    expect(screen.queryByText("ตรวจครบทั้ง 3 แหล่งแล้วไม่พบข้อมูลสำหรับช่องนี้")).not.toBeInTheDocument();
    expect(mockRpc.exportDmcFormJson).toHaveBeenCalledWith({
      rosterExcelPath: "C:\\dmc\\uploadTest\\studentListM1-M4 2569.xlsx",
      thaiIdCsvPath: "C:\\dmc\\uploadTest\\ThaiID M1-2569.CSV",
      ocrMarkdownPaths: ["C:\\dmc\\uploadTest\\1-3ex.md"],
      schoolYear: 2569,
      gradeLevels: [1],
      outputPath: null,
    });

    fireEvent.click(screen.getByRole("button", { name: /เปิดไฟล์ JSON/ }));
    expect(onRevealPath).toHaveBeenCalledWith("C:\\dmc\\reports\\dmc-form-data-2569.json");
  });
});
