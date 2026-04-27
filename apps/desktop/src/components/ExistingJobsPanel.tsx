import messages from "../i18n/th.json";
import { buttonStyle, cardStyle, formatTimestamp } from "../lib/appUi";
import type { JobStatusSnapshot } from "../types/contracts";

type ExistingJobsPanelProps = {
  existingJobs: JobStatusSnapshot[];
  activeJobId: string | null;
  isStartingJob: boolean;
  onSelectJob: (job: JobStatusSnapshot) => void;
  onResumeExisting: (job: JobStatusSnapshot) => void;
};

export function ExistingJobsPanel({
  existingJobs,
  activeJobId,
  isStartingJob,
  onSelectJob,
  onResumeExisting,
}: ExistingJobsPanelProps) {
  const pathTextStyle = { wordBreak: "break-all" as const, overflowWrap: "anywhere" as const };

  return (
    <section style={{ ...cardStyle, minWidth: 0 }}>
      <h2 style={{ marginTop: 0 }}>{messages.app.existingJobs.title}</h2>
      {existingJobs.length > 0 ? (
        <div style={{ display: "grid", gap: "10px" }}>
          {existingJobs.map((job) => (
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
              </div>
            </div>
          ))}
        </div>
      ) : (
        <p style={{ marginBottom: 0 }}>{messages.app.existingJobs.empty}</p>
      )}
    </section>
  );
}
