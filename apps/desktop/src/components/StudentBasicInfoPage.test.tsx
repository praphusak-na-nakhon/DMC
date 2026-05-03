import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { StudentBasicInfoPage } from "./StudentBasicInfoPage";

const mockRpc = vi.hoisted(() => ({
  openExcelDialog: vi.fn(),
  exportStudentBasicInfoForm: vi.fn(),
}));

vi.mock("../lib/rpcClient", () => mockRpc);

describe("StudentBasicInfoPage", () => {
  it("uploads a DMC Excel file and exposes the generated workbook", async () => {
    const onRevealPath = vi.fn();
    mockRpc.openExcelDialog.mockResolvedValue("C:\\dmc\\2568-3-student.xlsx");
    mockRpc.exportStudentBasicInfoForm.mockResolvedValue({
      module: "studentBasicInfo",
      source_path: "C:\\dmc\\2568-3-student.xlsx",
      output_path: "C:\\reports\\2568-3-student-basic-info.xlsx",
      school_name: "โรงเรียนตัวอย่าง",
      school_year: "2568",
      term: "3",
      rows_total: 4,
      students_exported: 4,
      classes_exported: 2,
      classes: [
        { level: "ม.1", room: "1", sheet_name: "ม.1-1", students: 2 },
        { level: "ม.1", room: "2", sheet_name: "ม.1-2", students: 2 },
      ],
    });

    render(<StudentBasicInfoPage onBackHome={vi.fn()} onRevealPath={onRevealPath} />);

    fireEvent.click(screen.getByRole("button", { name: "เลือกไฟล์" }));
    await waitFor(() => expect(mockRpc.openExcelDialog).toHaveBeenCalled());

    fireEvent.click(screen.getByRole("button", { name: "สร้างไฟล์ตามฟอร์ม" }));
    await waitFor(() => expect(screen.getByText("ไฟล์ผลลัพธ์")).toBeInTheDocument());

    expect(mockRpc.exportStudentBasicInfoForm).toHaveBeenCalledWith("C:\\dmc\\2568-3-student.xlsx");
    expect(screen.getByText("โรงเรียนตัวอย่าง")).toBeInTheDocument();
    expect(screen.getByText("4/4 แถว")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "ดาวน์โหลดไฟล์" }));

    expect(onRevealPath).toHaveBeenCalledWith("C:\\reports\\2568-3-student-basic-info.xlsx");
  });
});
