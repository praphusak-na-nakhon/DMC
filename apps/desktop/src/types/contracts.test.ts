import { describe, expect, it } from "vitest";
import { parseJobStatusSnapshot } from "./contracts";

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
});
