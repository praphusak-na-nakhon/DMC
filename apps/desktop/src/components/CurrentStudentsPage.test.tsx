import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { CurrentStudentsPage } from "./CurrentStudentsPage";

const mockRpc = vi.hoisted(() => ({
  exportCurrentStudentBlankForm: vi.fn(),
  openCurrentStudentImportDialog: vi.fn(),
  saveTemplateDialog: vi.fn(),
  validateCurrentStudentImportForm: vi.fn(),
}));

vi.mock("../lib/rpcClient", () => mockRpc);

describe("CurrentStudentsPage", () => {
  it("downloads a blank import form", async () => {
    const onRevealPath = vi.fn();
    mockRpc.saveTemplateDialog.mockResolvedValue("C:\\dmc\\reports\\current-students-template.xlsx");
    mockRpc.exportCurrentStudentBlankForm.mockResolvedValue({
      module: "currentStudents",
      output_path: "C:\\dmc\\reports\\current-students-template.xlsx",
      field_count: 65,
      required_fields: ["operation_type", "school_year", "citizen_id", "prefix", "first_name", "last_name"],
    });

    render(<CurrentStudentsPage onBackHome={vi.fn()} onRevealPath={onRevealPath} />);

    fireEvent.click(screen.getByRole("button", { name: /ฟอร์มเปล่า/ }));

    await waitFor(() => expect(mockRpc.exportCurrentStudentBlankForm).toHaveBeenCalled());
    expect(mockRpc.saveTemplateDialog).toHaveBeenCalledWith("current-students-import-template.xlsx");
    expect(mockRpc.exportCurrentStudentBlankForm).toHaveBeenCalledWith("C:\\dmc\\reports\\current-students-template.xlsx");
    expect(onRevealPath).toHaveBeenCalledWith("C:\\dmc\\reports\\current-students-template.xlsx");
  });

  it("validates a completed import Excel and renders the preview", async () => {
    mockRpc.openCurrentStudentImportDialog.mockResolvedValue("C:\\dmc\\reports\\current-students-import.xlsx");
    mockRpc.validateCurrentStudentImportForm.mockResolvedValue({
      module: "currentStudents",
      excel_path: "C:\\dmc\\reports\\current-students-import.xlsx",
      summary: {
        rows_total: 2,
        ready_rows: 1,
        needs_review_rows: 1,
        invalid_rows: 0,
        duplicate_citizen_ids: 1,
        warnings_total: 1,
      },
      preview: [
        {
          row_index: 3,
          status: "ready",
          operation_type: "current",
          student_no: "19984",
          citizen_id: "1819900905157",
          full_name: "ด.ญ. กัญญาณัฐ กุลดี",
          issues: [],
        },
        {
          row_index: 4,
          status: "needs_review",
          operation_type: "current",
          student_no: "19985",
          citizen_id: "1819900905157",
          full_name: "ด.ช. ภูริณัฐ หาเหม",
          issues: ["DUPLICATE_CITIZEN_ID"],
        },
      ],
      warnings: [
        {
          code: "DUPLICATE_CITIZEN_ID",
          message: "Citizen ID is duplicated in this import form.",
          source: "manual",
          source_path: "C:\\dmc\\reports\\current-students-import.xlsx",
          row_index: 4,
          sheet_name: null,
        },
      ],
    });

    render(<CurrentStudentsPage onBackHome={vi.fn()} onRevealPath={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: /เลือกไฟล์/ }));
    await waitFor(() =>
      expect(screen.getByDisplayValue("C:\\dmc\\reports\\current-students-import.xlsx")).toBeInTheDocument(),
    );

    fireEvent.click(screen.getByRole("button", { name: /ตรวจไฟล์นำเข้า/ }));

    await waitFor(() => expect(mockRpc.validateCurrentStudentImportForm).toHaveBeenCalled());
    expect(mockRpc.validateCurrentStudentImportForm).toHaveBeenCalledWith("C:\\dmc\\reports\\current-students-import.xlsx");
    expect(screen.getByText("ด.ญ. กัญญาณัฐ กุลดี")).toBeInTheDocument();
    expect(screen.getByText("ด.ช. ภูริณัฐ หาเหม")).toBeInTheDocument();
    expect(screen.getByText(/19984/)).toBeInTheDocument();
    expect(screen.getByText("เลขบัตรซ้ำ")).toBeInTheDocument();
  });
});
