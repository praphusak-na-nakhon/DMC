import { beforeEach, describe, expect, it } from "vitest";
import { buildDraftJob } from "../lib/appUi";
import { parseSidecarEvent } from "../types/contracts";
import { useJobStore } from "./useJobStore";
beforeEach(() => useJobStore.getState().reset());
describe("credit-free job events", () => {
  it("reconciles progress, DMC authentication and completion into current and retained jobs", () => {
    const store = useJobStore.getState();
    store.setCurrentJob(buildDraftJob("students.xlsx", 2, "job-1"));
    const apply = (event: unknown) => store.applySidecarEvent(parseSidecarEvent(event));
    apply({ type: "progress", job_id: "job-1", processed: 1, total: 2, succeeded: 1, failed: 0, current_page: 1, needs_auth: false, auth_reason: null });
    expect(useJobStore.getState().currentJob).toMatchObject({ status: "running", processed: 1, total: 2 });
    apply({ type: "needs_auth", job_id: "job-1", reason: "dmc_session_expired" });
    expect(useJobStore.getState().currentJob).toMatchObject({ status: "paused", needs_auth: true, auth_reason: "dmc_session_expired" });
    apply({ type: "progress", job_id: "job-1", processed: 2, total: 2, succeeded: 2, failed: 0, current_page: 1, needs_auth: false, auth_reason: null });
    expect(useJobStore.getState().currentJob).toMatchObject({ status: "running", needs_auth: false, auth_reason: null });
    apply({ type: "job_done", job_id: "job-1", status: "done", processed: 2, total: 2, succeeded: 2, failed: 0, current_page: 1, report_path: "report.csv", review_report_path: "review.csv", run_summary: null, summary_report_path: "summary.xlsx", completion_summary: { total: 2, succeeded: 2, failed: 0, success_items: [], failure_items: [] } });
    const state = useJobStore.getState();
    expect(state.currentJob).toMatchObject({ status: "done", processed: 2, needs_auth: false, auth_reason: null, report_path: "report.csv", summary_report_path: "summary.xlsx", completion_summary: { succeeded: 2 } });
    expect(state.existingJobs).toEqual([state.currentJob]);
    expect(JSON.stringify(state.currentJob)).not.toContain("credit");
    expect(state).not.toHaveProperty("accountStatus");
  });
  it("ignores unrelated errors and records local failures", () => {
    const store = useJobStore.getState();
    store.setCurrentJob({ ...buildDraftJob("students.xlsx", 2, "job-1"), needs_auth: true, auth_reason: "dmc_session_expired" });
    store.setActiveJobId("job-1");
    store.applySidecarEvent({ type: "error", job_id: "other", code: "LOCAL_FAILURE", message: "other" });
    expect(useJobStore.getState().currentJob?.status).toBe("running");
    store.applySidecarEvent({ type: "error", job_id: "job-1", code: "LOCAL_FAILURE", message: "failed" });
    expect(useJobStore.getState().currentJob).toMatchObject({ status: "failed", needs_auth: true, auth_reason: "dmc_session_expired" });
    expect(useJobStore.getState().errorMessage).toBe("LOCAL_FAILURE: failed");
    expect(JSON.stringify(useJobStore.getState().currentJob)).not.toContain("credit");
  });
});
