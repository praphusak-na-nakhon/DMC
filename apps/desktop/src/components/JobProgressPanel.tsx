import messages from "../i18n/th.json";
import { cardStyle } from "../lib/appUi";
import type { JobStatusSnapshot } from "../types/contracts";

type JobProgressPanelProps = {
  currentJob: JobStatusSnapshot | null;
  progressPercent: number;
};

const pathTextStyle = { wordBreak: "break-all" as const, overflowWrap: "anywhere" as const };

export function JobProgressPanel({ currentJob, progressPercent }: JobProgressPanelProps) {
  const processedLabel =
    currentJob?.total !== null && currentJob?.total !== undefined && currentJob.processed > currentJob.total
      ? `${currentJob.processed} แถวบนเว็บ (Excel validate ${currentJob.total} รายการ)`
      : `${currentJob?.processed ?? 0}/${currentJob?.total ?? "-"}`;

  return (
    <section style={{ ...cardStyle, minWidth: 0 }}>
      <h2 style={{ marginTop: 0 }}>{messages.app.progress.title}</h2>
      {currentJob ? (
        <>
          <div
            style={{
              height: "14px",
              borderRadius: "999px",
              backgroundColor: "rgb(226, 232, 240)",
              overflow: "hidden",
              marginBottom: "14px",
            }}
          >
            <div
              style={{
                width: `${progressPercent}%`,
                height: "100%",
                background: "linear-gradient(90deg, rgb(13, 148, 136), rgb(34, 197, 94))",
                transition: "width 200ms ease",
              }}
            />
          </div>
          <div style={{ display: "grid", gap: "8px", lineHeight: 1.6, minWidth: 0 }}>
            <div>
              <strong>{messages.app.progress.status}:</strong> {currentJob.status}
            </div>
            <div>
              <strong>{messages.app.progress.processed}:</strong> {processedLabel}
            </div>
            <div>
              <strong>{messages.app.progress.currentPage}:</strong> {currentJob.current_page ?? "-"}
            </div>
            <div>
              <strong>{messages.app.progress.success}:</strong> {currentJob.succeeded}
            </div>
            <div>
              <strong>{messages.app.progress.failed}:</strong> {currentJob.failed}
            </div>
            <div style={pathTextStyle}>
              <strong>ไฟล์:</strong> {currentJob.source_file}
            </div>
            <div style={pathTextStyle}>
              <strong>Report:</strong> {currentJob.report_path ?? "-"}
            </div>
            {currentJob.needs_auth ? (
              <div
                style={{
                  marginTop: "8px",
                  borderRadius: "12px",
                  backgroundColor: "rgb(255, 247, 237)",
                  border: "1px solid rgb(253, 230, 138)",
                  padding: "12px 14px",
                  color: "rgb(154, 52, 18)",
                }}
              >
                ต้องลงชื่อเข้าใช้ DMC ใหม่ก่อน resume
                <div style={{ marginTop: "6px" }}>reason: {currentJob.auth_reason ?? "auth_required"}</div>
              </div>
            ) : null}
          </div>
        </>
      ) : (
        <p style={{ marginBottom: 0 }}>{messages.app.progress.empty}</p>
      )}
    </section>
  );
}
