import { describe, expect, it } from "vitest";
import { parseJobStatusSnapshot, parseGeminiOcrDmcFormResponse } from "./contracts";

const baseJob = {
  job_id: "job-empty-summary",
  module: "graduation",
  status: "done",
  source_file: "C:\\dmc\\m3-obec-study-form.xlsx",
  processed: 0,
  total: 0,
  succeeded: 0,
  failed: 0,
  current_page: null,
  needs_auth: false,
  auth_reason: null,
  report_path: null,
  review_report_path: null,
  stopped_item: null,
  started_at: null,
  finished_at: null,
  level_label: null,
  summary_report_path: null,
  completion_summary: null,
  credit_reservation_id: null,
  credits_reserved: 0,
  credits_captured: 0,
  credits_refunded: 0,
  credit_status: null,
};

describe("job status contracts", () => {
  it("treats an empty legacy run summary as absent", () => {
    const parsed = parseJobStatusSnapshot({
      ...baseJob,
      run_summary: {},
    });

    expect(parsed.run_summary).toBeNull();
  });

  it("accepts older run summaries with missing optional counters", () => {
    const parsed = parseJobStatusSnapshot({
      ...baseJob,
      run_summary: {
        dmc_rows_total: 12,
      },
    });

    expect(parsed.run_summary).toEqual({
      dmc_rows_total: 12,
      matched_from_excel: 0,
      default_207: 0,
      excel_missing: 0,
      review_rows: 0,
      applied_rows: 0,
      dry_run_rows: 0,
    });
  });

  it("parses completion summary items and report path", () => {
    const parsed = parseJobStatusSnapshot({
      ...baseJob,
      summary_report_path: "C:\\dmc\\.dmc-assistant-data\\reports\\job-1\\job-completion-summary.xlsx",
      completion_summary: {
        total: 2,
        succeeded: 1,
        failed: 1,
        success_items: [
          {
            row_index: 1,
            record_id: "record-1",
            student_no: "1001",
            citizen_id: null,
            full_name: "Student One",
            classroom: "1",
            status: "success",
            note: "dry_run",
            message: null,
            applied: false,
          },
        ],
        failure_items: [
          {
            row_index: 2,
            record_id: "record-2",
            student_no: "1002",
            citizen_id: null,
            full_name: "Student Two",
            classroom: "1",
            status: "review",
            note: "dmc_validation_error",
            message: "Needs review",
            applied: false,
          },
        ],
      },
    });

    expect(parsed.summary_report_path).toContain("job-completion-summary.xlsx");
    expect(parsed.completion_summary?.succeeded).toBe(1);
    expect(parsed.completion_summary?.failure_items[0].full_name).toBe("Student Two");
  });
});

describe("Gemini contracts", () => {
  it("parses the generated structured OCR response with usage metadata", () => {
    const parsed = parseGeminiOcrDmcFormResponse({
      module: "formConverter",
      engine: "gemini",
      model: "gemini-3.5-flash",
      processing_mode: "batch",
      source_path: "C:\\dmc\\uploadTest\\dmc-form.pdf",
      markdown_path: "C:\\dmc\\.dmc-assistant-data\\ocr\\gemini\\dmc-form.json",
      structured_json_path: "C:\\dmc\\.dmc-assistant-data\\ocr\\gemini\\dmc-form.json",
      output_format: "structured_json",
      cached: false,
      pages_processed: 2,
      pages_estimated: 2,
      credits_per_page: 3,
      credits_charged: 6,
      charged: true,
      credit_reservation_id: "reservation-1",
      average_confidence: null,
      usage_metadata: {
        prompt_token_count: 1300,
        candidates_token_count: 700,
        total_token_count: 2000,
        input_tokens_per_page: 650,
        output_tokens_per_page: 350,
        total_tokens_per_page: 1000,
      },
      batch_job_name: "batches/test",
      batch_state: "JOB_STATE_SUCCEEDED",
      file_sha256: "abc123",
      created_at: "2026-05-11T00:00:00+00:00",
    });

    expect(parsed).toMatchObject({
      engine: "gemini",
      model: "gemini-3.5-flash",
      processing_mode: "batch",
      pages_processed: 2,
      structured_json_path: "C:\\dmc\\.dmc-assistant-data\\ocr\\gemini\\dmc-form.json",
      credits_charged: 6,
      charged: true,
      average_confidence: null,
      batch_job_name: "batches/test",
      batch_state: "JOB_STATE_SUCCEEDED",
    });
    expect(parsed.usage_metadata?.total_token_count).toBe(2000);
    expect(parsed.usage_metadata?.total_tokens_per_page).toBe(1000);
  });
});
