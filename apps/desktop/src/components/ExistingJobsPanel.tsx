import { useMemo, useState } from "react";
import messages from "../i18n/th.json";
import { buttonStyle, cardStyle, formatTimestamp } from "../lib/appUi";
import type { JobStatusSnapshot } from "../types/contracts";

type ExistingJobsPanelProps = {
  existingJobs: JobStatusSnapshot[];
  activeJobId: string | null;
  isStartingJob: boolean;
  onSelectJob: (job: JobStatusSnapshot) => void;
  onResumeExisting: (job: JobStatusSnapshot) => void;
  onRevealPath: (path: string) => void;
};

export function ExistingJobsPanel({
  existingJobs,
  activeJobId,
  isStartingJob,
  onSelectJob,
  onResumeExisting,
  onRevealPath,
}: ExistingJobsPanelProps) {
  const [statusFilter, setStatusFilter] = useState<"all" | "active" | "done" | "failed">("active");
  const pathTextStyle = { wordBreak: "break-all" as const, overflowWrap: "anywhere" as const };
  const visibleJobs = useMemo(() => {
    if (statusFilter === "all") {
      return existingJobs;
    }
    if (statusFilter === "active") {
      return existingJobs.filter((job) =>
        ["running", "paused", "stopped_on_review", "failed"].includes(job.status),
      );
    }
    if (statusFilter === "done") {
      return existingJobs.filter((job) => job.status === "done");
    }
    return existingJobs.filter((job) => job.status === "failed");
  }, [existingJobs, statusFilter]);

  return (
    <section style={{ ...cardStyle, minWidth: 0 }}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: "12px", flexWrap: "wrap" }}>
        <h2 style={{ marginTop: 0, marginBottom: "12px" }}>{messages.app.existingJobs.title}</h2>
        <select
          value={statusFilter}
          onChange={(event) => setStatusFilter(event.target.value as typeof statusFilter)}
          style={{
            height: "34px",
            borderRadius: "10px",
            border: "1px solid rgb(203, 213, 225)",
            padding: "0 10px",
            backgroundColor: "white",
          }}
        >
          <option value="active">{messages.app.existingJobs.filterActive}</option>
          <option value="done">{messages.app.existingJobs.filterDone}</option>
          <option value="failed">{messages.app.existingJobs.filterFailed}</option>
          <option value="all">{messages.app.existingJobs.filterAll}</option>
        </select>
      </div>
      {existingJobs.length > 0 ? (
        <div style={{ display: "grid", gap: "10px" }}>
          {visibleJobs.length === 0 ? (
            <p style={{ margin: 0, color: "rgb(71, 85, 105)" }}>{messages.app.existingJobs.emptyFiltered}</p>
          ) : null}
          {visibleJobs.map((job) => {
            const reportPath = job.report_path;
            const reviewReportPath = job.review_report_path;
            const reportDirectory = reportPath?.replace(/[\\/][^\\/]+$/, "") ?? reviewReportPath?.replace(/[\\/][^\\/]+$/, "");
            return (
              <div
                key={job.job_id}
                style={{
                  borderRadius: "14px",
                  border: "1px solid rgb(226, 232, 240)",
                  padding: "12px 14px",
                  backgroundColor:
                    activeJobId === job.job_id ? "rgb(236, 253, 245)" : "rgb(248, 250, 252)",
                }}
              >
                <div style={{ fontWeight: 700, ...pathTextStyle }}>{job.job_id}</div>
                <div style={{ marginTop: "4px", color: "rgb(71, 85, 105)", fontSize: "14px" }}>
                  {job.level_label ?? "-"} • {job.status} • {job.processed}/{job.total ?? "-"}
                </div>
                <div style={{ marginTop: "6px", fontSize: "13px", color: "rgb(51, 65, 85)", ...pathTextStyle }}>
                  <strong>{messages.app.existingJobs.sourceFile}:</strong> {job.source_file}
                </div>
                <div style={{ marginTop: "4px", fontSize: "13px", color: "rgb(51, 65, 85)" }}>
                  <strong>{messages.app.existingJobs.updatedAt}:</strong>{" "}
                  {formatTimestamp(job.finished_at ?? job.started_at)}
                </div>
                <div style={{ display: "flex", gap: "8px", marginTop: "10px", flexWrap: "wrap" }}>
                  <button
                    style={{ ...buttonStyle, padding: "8px 12px", backgroundColor: "rgb(5, 150, 105)" }}
                    onClick={() => onSelectJob(job)}
                  >
                    ใช้งานรายการนี้
                  </button>
                  <button
                    style={{ ...buttonStyle, padding: "8px 12px", backgroundColor: "rgb(59, 130, 246)" }}
                    disabled={isStartingJob || job.status === "done" || job.status === "cancelled"}
                    onClick={() => onResumeExisting(job)}
                  >
                    {messages.app.resumeExisting}
                  </button>
                  {reportPath ? (
                    <button
                      style={{ ...buttonStyle, padding: "8px 12px", backgroundColor: "rgb(37, 99, 235)" }}
                      onClick={() => onRevealPath(reportPath)}
                    >
                      {messages.app.progress.openReport}
                    </button>
                  ) : null}
                  {reportDirectory ? (
                    <button
                      style={{ ...buttonStyle, padding: "8px 12px", backgroundColor: "rgb(8, 145, 178)" }}
                      onClick={() => onRevealPath(reportDirectory)}
                    >
                      {messages.app.progress.openReportFolder}
                    </button>
                  ) : null}
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <p style={{ marginBottom: 0 }}>{messages.app.existingJobs.empty}</p>
      )}
    </section>
  );
}
