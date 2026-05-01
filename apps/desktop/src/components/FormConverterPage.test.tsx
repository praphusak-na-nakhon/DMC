import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import messages from "../i18n/th.json";
import { FormConverterPage } from "./FormConverterPage";
import type { AccountStatus, FormConversionStatusResponse } from "../types/contracts";

const mockRpc = vi.hoisted(() => ({
  openPdfDialog: vi.fn(),
  validateFormPdf: vi.fn(),
  startFormConversion: vi.fn(),
  getConversionStatus: vi.fn(),
  saveReviewEdits: vi.fn(),
  exportConvertedExcel: vi.fn(),
}));

vi.mock("../lib/rpcClient", () => mockRpc);

const accountStatus: AccountStatus = {
  signed_in: true,
  user_id: "user-1",
  email: "teacher@example.test",
  display_name: "Teacher",
  status: "active",
  token_expires_at: "2030-01-01T00:00:00Z",
  last_checked_at: "2026-04-29T00:00:00Z",
  wallet: { user_id: "user-1", balance: 10, reserved: 0, available: 10 },
  can_start_credit_jobs: true,
  needs_attention: false,
  message: null,
  last_error: null,
};

function conversionStatus(status: FormConversionStatusResponse["status"]): FormConversionStatusResponse {
  return {
    job_id: "form-job-1",
    module: "formConverter",
    status,
    pdf_path: "C:\\data\\student-history.pdf",
    template_type: "student_history_v1",
    ocr_provider: "test-provider",
    school_year: "2569",
    page_count: 1,
    processed: 1,
    total: 1,
    summary: {
      records_total: 1,
      ready_records: status === "reviewed" || status === "done" ? 1 : 0,
      needs_review_records: status === "needs_review" ? 1 : 0,
      invalid_records: 0,
      exported_records: status === "done" ? 1 : 0,
    },
    records: [
      {
        record_id: "page-1",
        page_number: 1,
        status: status === "needs_review" ? "needs_review" : "ready",
        fields: [
          {
            field_name: "first_name",
            label_th: "ชื่อ",
            value: "ตัวอย่าง",
            confidence: 0.58,
            status: status === "needs_review" ? "needs_review" : "ready",
            alternatives: [],
            edited: false,
          },
        ],
      },
    ],
    excel_path: status === "done" ? "C:\\reports\\student-history.xlsx" : null,
    report_path: status === "done" ? "C:\\reports\\form-conversion-report.csv" : null,
    review_report_path: status === "done" ? "C:\\reports\\form-conversion-review.csv" : null,
    credit_reservation_id: "reservation-1",
    credits_reserved: 1,
    credits_captured: status === "done" ? 1 : 0,
    credits_refunded: 0,
    credit_status: status === "done" ? "finalized" : "reserved",
    last_error: null,
    review_confirmed: status === "reviewed" || status === "done",
  };
}

describe("FormConverterPage", () => {
  it("requires PDF validation, consent, review, then export", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    mockRpc.openPdfDialog.mockResolvedValue("C:\\data\\student-history.pdf");
    mockRpc.validateFormPdf.mockResolvedValue({
      module: "formConverter",
      path: "C:\\data\\student-history.pdf",
      file_name: "student-history.pdf",
      template_type: "student_history_v1",
      page_count: 1,
      estimated_records: 1,
      credit_estimate: 1,
      supported_template: true,
      requires_ai_consent: true,
      warnings: [],
    });
    mockRpc.startFormConversion.mockResolvedValue({
      accepted: true,
      job_id: "form-job-1",
      credit_reservation_id: "reservation-1",
      credits_reserved: 1,
    });
    mockRpc.getConversionStatus
      .mockResolvedValueOnce(conversionStatus("needs_review"))
      .mockResolvedValueOnce(conversionStatus("done"));
    mockRpc.saveReviewEdits.mockResolvedValue(conversionStatus("reviewed"));
    mockRpc.exportConvertedExcel.mockResolvedValue({
      job_id: "form-job-1",
      excel_path: "C:\\reports\\student-history.xlsx",
      report_path: "C:\\reports\\form-conversion-report.csv",
      review_report_path: "C:\\reports\\form-conversion-review.csv",
      exported_records: 1,
      credit_reservation_id: "reservation-1",
      credits_captured: 1,
      credits_refunded: 0,
    });

    render(
      <FormConverterPage
        accountStatus={accountStatus}
        onBackHome={vi.fn()}
        onRefreshWallet={vi.fn()}
        onRevealPath={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: messages.app.formConverter.browsePdf }));
    await waitFor(() => expect(mockRpc.openPdfDialog).toHaveBeenCalled());

    fireEvent.click(screen.getByRole("button", { name: messages.app.formConverter.validatePdf }));
    await waitFor(() => expect(screen.getByDisplayValue("C:\\data\\student-history.pdf")).toBeInTheDocument());

    fireEvent.click(screen.getByRole("checkbox"));
    fireEvent.click(screen.getByRole("button", { name: messages.app.formConverter.startAiRead }));

    await waitFor(() => expect(screen.getByText(messages.app.formConverter.reviewTitle)).toBeInTheDocument());
    expect(screen.getByText("58%")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: messages.app.formConverter.exportExcel })).toBeDisabled();

    fireEvent.click(screen.getByRole("button", { name: messages.app.formConverter.saveReview }));
    await waitFor(() => expect(mockRpc.saveReviewEdits).toHaveBeenCalled());

    fireEvent.click(screen.getByRole("button", { name: messages.app.formConverter.exportExcel }));
    await waitFor(() => expect(screen.getByText(messages.app.formConverter.outputTitle)).toBeInTheDocument());
  });
});
