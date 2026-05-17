import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import messages from "../i18n/th.json";
import { ExistingJobsPanel } from "./ExistingJobsPanel";
import type { JobStatusSnapshot } from "../types/contracts";

function buildJob(index: number): JobStatusSnapshot {
  return {
    job_id: `job-${index}`,
    module: "graduation",
    status: "done",
    source_file: `C:\\data\\m3-${index}.xlsx`,
    processed: 300,
    total: 300,
    succeeded: 300,
    failed: 0,
    current_page: 5,
    needs_auth: false,
    auth_reason: null,
    report_path: `C:\\reports\\job-${index}\\obec-fill-report.csv`,
    review_report_path: null,
    stopped_item: null,
    started_at: `2026-04-22T00:${String(index).padStart(2, "0")}:00Z`,
    finished_at: `2026-04-22T00:${String(index).padStart(2, "0")}:30Z`,
    level_label: "ม.3",
    run_summary: null,
    summary_report_path: null,
    completion_summary: null,
    credit_reservation_id: null,
    credits_reserved: 0,
    credits_captured: 0,
    credits_refunded: 0,
    credit_status: null,
  };
}

describe("ExistingJobsPanel", () => {
  it("shows an empty state when history is empty", () => {
    render(
      <ExistingJobsPanel
        existingJobs={[]}
        activeJobId={null}
        isStartingJob={false}
        onSelectJob={vi.fn()}
        onResumeExisting={vi.fn()}
        onRevealPath={vi.fn()}
      />,
    );

    expect(screen.getByText(messages.app.existingJobs.empty)).toBeInTheDocument();
  });

  it("can trigger old history cleanup", () => {
    const onArchiveOldJobs = vi.fn();
    render(
      <ExistingJobsPanel
        existingJobs={Array.from({ length: 21 }, (_, index) => buildJob(index))}
        activeJobId={null}
        isStartingJob={false}
        onSelectJob={vi.fn()}
        onResumeExisting={vi.fn()}
        onRevealPath={vi.fn()}
        onArchiveOldJobs={onArchiveOldJobs}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: messages.app.existingJobs.archiveOld }));

    expect(onArchiveOldJobs).toHaveBeenCalledOnce();
  });
});
