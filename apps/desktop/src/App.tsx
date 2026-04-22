import { useEffect, useMemo, useState, type CSSProperties } from "react";
import messages from "./i18n/th.json";
import {
  cancelJob,
  getJobStatus,
  getModuleConfigStatus,
  initializeSidecar,
  listJobs,
  listenSidecarEvents,
  openExcelDialog,
  pauseJob,
  resumeExistingJob,
  resumeJob,
  startGraduationJob,
  syncModuleConfig,
  validateExcel,
} from "./lib/rpcClient";
import { useJobStore } from "./stores/useJobStore";
import type { JobStatusSnapshot } from "./types/contracts";

function formatSummary(template: string, accepted: number, total: number): string {
  return template.replace("{accepted}", String(accepted)).replace("{total}", String(total));
}

function buildJobId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `job-${Date.now()}`;
}

function formatTimestamp(value: string | null): string {
  if (!value) {
    return "-";
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  return parsed.toLocaleString("th-TH", {
    dateStyle: "short",
    timeStyle: "short",
  });
}

const cardStyle: CSSProperties = {
  border: "1px solid rgb(226, 232, 240)",
  borderRadius: "16px",
  padding: "20px",
  backgroundColor: "rgba(255, 255, 255, 0.92)",
};

const buttonStyle: CSSProperties = {
  border: "none",
  borderRadius: "999px",
  padding: "11px 16px",
  fontSize: "14px",
  fontWeight: 600,
  cursor: "pointer",
  backgroundColor: "rgb(15, 118, 110)",
  color: "white",
};

function buildDraftJob(excelPath: string, previewRowsAccepted: number | null, jobId: string): JobStatusSnapshot {
  return {
    job_id: jobId,
    module: "graduation",
    status: "running",
    source_file: excelPath,
    processed: 0,
    total: previewRowsAccepted,
    succeeded: 0,
    failed: 0,
    current_page: 1,
    needs_auth: false,
    auth_reason: null,
    report_path: null,
    review_report_path: null,
    stopped_item: null,
    started_at: null,
    finished_at: null,
    level_label: null,
  };
}

export function App() {
  const {
    preview,
    currentJob,
    moduleConfigStatus,
    existingJobs,
    excelPath,
    connectionState,
    isValidating,
    isStartingJob,
    errorMessage,
    sidecarMessages,
    activeJobId,
    setExcelPath,
    setPreview,
    setCurrentJob,
    setModuleConfigStatus,
    setExistingJobs,
    upsertExistingJob,
    setConnectionState,
    setIsValidating,
    setIsStartingJob,
    setErrorMessage,
    pushSidecarMessage,
    setActiveJobId,
    applySidecarEvent,
  } = useJobStore();

  const [minScore, setMinScore] = useState(72);
  const [stopOnReview, setStopOnReview] = useState(true);

  async function handleLoadJobs() {
    try {
      const response = await listJobs();
      setExistingJobs(response.items);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : String(error));
    }
  }

  async function handleSyncConfig() {
    try {
      const status = await syncModuleConfig("graduation");
      setModuleConfigStatus(status);
      pushSidecarMessage(
        status.updated
          ? `config graduation อัปเดตเป็น ${status.version} แล้ว`
          : `config graduation ใช้งานเวอร์ชัน ${status.version} (${status.source})`,
      );
      if (status.last_error) {
        pushSidecarMessage(`config fallback: ${status.last_error}`);
      }
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : String(error));
    }
  }

  async function handleConnect() {
    setErrorMessage(null);
    setConnectionState("connecting");
    try {
      await initializeSidecar();
      setConnectionState("ready");
      setModuleConfigStatus(await getModuleConfigStatus("graduation"));
      await handleLoadJobs();
      await handleSyncConfig();
    } catch (error) {
      setConnectionState("error");
      setErrorMessage(error instanceof Error ? error.message : String(error));
    }
  }

  useEffect(() => {
    let disposed = false;
    let unlisten: (() => void) | undefined;

    async function bootstrap() {
      try {
        await handleConnect();
        if (disposed) {
          return;
        }
        unlisten = await listenSidecarEvents((event) => {
          applySidecarEvent(event);
        });
      } catch (error) {
        if (!disposed) {
          const message = error instanceof Error ? error.message : String(error);
          setConnectionState("error");
          setErrorMessage(message);
        }
      }
    }

    void bootstrap();

    return () => {
      disposed = true;
      if (unlisten) {
        void unlisten();
      }
    };
  }, [applySidecarEvent, setConnectionState, setErrorMessage]);

  useEffect(() => {
    if (!activeJobId) {
      return;
    }

    const timer = window.setInterval(() => {
      void getJobStatus(activeJobId)
        .then((status) => {
          setCurrentJob(status);
          upsertExistingJob(status);
        })
        .catch((error) => {
          const message = error instanceof Error ? error.message : String(error);
          setErrorMessage(message);
        });
    }, 2000);

    return () => window.clearInterval(timer);
  }, [activeJobId, setCurrentJob, setErrorMessage, upsertExistingJob]);

  const progressPercent = useMemo(() => {
    if (!currentJob?.total || currentJob.total <= 0) {
      return 0;
    }
    return Math.round((currentJob.processed / currentJob.total) * 100);
  }, [currentJob]);

  async function handleBrowseFile() {
    try {
      const selected = await openExcelDialog();
      if (selected) {
        setExcelPath(selected);
        setErrorMessage(null);
      }
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : String(error));
    }
  }

  async function handleValidate() {
    if (!excelPath.trim()) {
      setErrorMessage("กรุณาระบุพาธไฟล์ Excel ก่อน");
      return;
    }

    setErrorMessage(null);
    setIsValidating(true);
    try {
      const response = await validateExcel(excelPath.trim());
      setPreview(response);
      pushSidecarMessage(`validate_excel สำเร็จ: ${response.rows_accepted}/${response.rows_total}`);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setIsValidating(false);
    }
  }

  async function handleStart(dryRun: boolean) {
    if (!excelPath.trim()) {
      setErrorMessage("กรุณาระบุพาธไฟล์ Excel ก่อน");
      return;
    }

    setErrorMessage(null);
    setIsStartingJob(true);
    try {
      await handleSyncConfig();
      const result = await startGraduationJob({
        jobId: buildJobId(),
        excelPath: excelPath.trim(),
        dryRun,
        stopOnReview,
        minScore,
      });
      const draft = buildDraftJob(excelPath.trim(), preview?.rows_accepted ?? null, result.job_id);
      setActiveJobId(result.job_id);
      setCurrentJob(draft);
      upsertExistingJob(draft);
      pushSidecarMessage(`${dryRun ? "เริ่ม dry run" : "เริ่มงานจริง"} แล้ว: ${result.job_id}`);
      await handleLoadJobs();
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setIsStartingJob(false);
    }
  }

  async function handleResume() {
    if (!activeJobId) {
      return;
    }
    try {
      await resumeJob(activeJobId);
      pushSidecarMessage(`resume_job ส่งแล้ว: ${activeJobId}`);
      const status = await getJobStatus(activeJobId);
      setCurrentJob(status);
      upsertExistingJob(status);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : String(error));
    }
  }

  async function handleResumeExisting(job: JobStatusSnapshot) {
    try {
      setErrorMessage(null);
      setIsStartingJob(true);
      const response = await resumeExistingJob(job.job_id);
      if (response.accepted) {
        setActiveJobId(job.job_id);
        setCurrentJob(job);
        upsertExistingJob({ ...job, status: "running" });
        setExcelPath(job.source_file);
        pushSidecarMessage(`กลับมาทำงาน ${job.job_id} ต่อแล้ว`);
      }
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setIsStartingJob(false);
    }
  }

  async function handlePause() {
    if (!activeJobId) {
      return;
    }
    try {
      await pauseJob(activeJobId);
      const status = await getJobStatus(activeJobId);
      setCurrentJob(status);
      upsertExistingJob(status);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : String(error));
    }
  }

  async function handleCancel() {
    if (!activeJobId) {
      return;
    }
    try {
      await cancelJob(activeJobId);
      const status = await getJobStatus(activeJobId);
      setCurrentJob(status);
      upsertExistingJob(status);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : String(error));
    }
  }

  async function handleRefreshStatus() {
    if (!activeJobId) {
      return;
    }
    try {
      const status = await getJobStatus(activeJobId);
      setCurrentJob(status);
      upsertExistingJob(status);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : String(error));
    }
  }

  return (
    <main
      style={{
        minHeight: "100vh",
        padding: "28px",
        background:
          "radial-gradient(circle at top left, rgb(240, 253, 250), rgb(226, 232, 240) 50%, rgb(248, 250, 252))",
        color: "rgb(15, 23, 42)",
        fontFamily: "\"Segoe UI\", Tahoma, sans-serif",
      }}
    >
      <section
        style={{
          maxWidth: "1280px",
          margin: "0 auto",
          backgroundColor: "rgba(255, 255, 255, 0.9)",
          borderRadius: "24px",
          padding: "28px",
          boxShadow: "0 30px 80px rgba(15, 23, 42, 0.12)",
          backdropFilter: "blur(10px)",
        }}
      >
        <p style={{ margin: 0, fontSize: "13px", letterSpacing: "0.08em", textTransform: "uppercase" }}>
          {messages.app.tagline}
        </p>
        <div
          style={{
            display: "flex",
            gap: "20px",
            alignItems: "flex-start",
            justifyContent: "space-between",
            flexWrap: "wrap",
            marginTop: "10px",
            marginBottom: "24px",
          }}
        >
          <div style={{ maxWidth: "760px" }}>
            <h1 style={{ marginTop: 0, marginBottom: "14px", fontSize: "38px" }}>
              {messages.app.title}
            </h1>
            <p style={{ lineHeight: 1.7, margin: 0 }}>{messages.app.description}</p>
          </div>
          <div
            style={{
              ...cardStyle,
              minWidth: "220px",
              backgroundColor:
                connectionState === "ready" ? "rgb(240, 253, 250)" : "rgba(255, 255, 255, 0.9)",
            }}
          >
            <div style={{ fontSize: "13px", color: "rgb(71, 85, 105)" }}>Sidecar</div>
            <div style={{ fontSize: "20px", fontWeight: 700, marginTop: "6px" }}>
              {connectionState === "ready"
                ? messages.app.connected
                : connectionState === "connecting"
                  ? messages.app.connecting
                  : connectionState}
            </div>
            {moduleConfigStatus ? (
              <div style={{ marginTop: "10px", fontSize: "13px", color: "rgb(51, 65, 85)", lineHeight: 1.5 }}>
                <div>
                  Config {moduleConfigStatus.version} ({moduleConfigStatus.source})
                </div>
                <div>
                  Verify: {moduleConfigStatus.signature_verified ? "signed" : "bundled"}
                </div>
              </div>
            ) : null}
          </div>
        </div>

        <section style={{ ...cardStyle, marginBottom: "20px" }}>
          <div style={{ display: "grid", gap: "12px" }}>
            <label style={{ display: "grid", gap: "8px" }}>
              <span style={{ fontWeight: 600 }}>{messages.app.filePathLabel}</span>
              <div style={{ display: "flex", gap: "10px", flexWrap: "wrap" }}>
                <input
                  value={excelPath}
                  onChange={(event) => setExcelPath(event.target.value)}
                  placeholder={messages.app.filePathPlaceholder}
                  style={{
                    flex: 1,
                    minWidth: "360px",
                    borderRadius: "12px",
                    border: "1px solid rgb(203, 213, 225)",
                    padding: "12px 14px",
                    fontSize: "15px",
                  }}
                />
                <button
                  style={{ ...buttonStyle, backgroundColor: "rgb(3, 105, 161)" }}
                  onClick={() => void handleBrowseFile()}
                >
                  {messages.app.browse}
                </button>
              </div>
            </label>
            <div
              style={{
                display: "flex",
                flexWrap: "wrap",
                gap: "10px",
                alignItems: "center",
              }}
            >
              <button style={buttonStyle} onClick={() => void handleConnect()}>
                {messages.app.connect}
              </button>
              <button
                style={{ ...buttonStyle, backgroundColor: "rgb(8, 145, 178)" }}
                onClick={() => void handleLoadJobs()}
              >
                {messages.app.refreshJobs}
              </button>
              <button
                style={{ ...buttonStyle, backgroundColor: "rgb(2, 132, 199)" }}
                onClick={() => void handleSyncConfig()}
              >
                {messages.app.syncConfig}
              </button>
              <button style={buttonStyle} disabled={isValidating} onClick={() => void handleValidate()}>
                {messages.app.validate}
              </button>
              <button
                style={buttonStyle}
                disabled={isStartingJob}
                onClick={() => void handleStart(true)}
              >
                {messages.app.startDryRun}
              </button>
              <button
                style={{ ...buttonStyle, backgroundColor: "rgb(22, 163, 74)" }}
                disabled={isStartingJob}
                onClick={() => void handleStart(false)}
              >
                {messages.app.startLive}
              </button>
              <button
                style={{ ...buttonStyle, backgroundColor: "rgb(14, 116, 144)" }}
                disabled={!activeJobId}
                onClick={() => void handleRefreshStatus()}
              >
                {messages.app.refreshStatus}
              </button>
              <button
                style={{ ...buttonStyle, backgroundColor: "rgb(100, 116, 139)" }}
                disabled={!activeJobId}
                onClick={() => void handlePause()}
              >
                {messages.app.pause}
              </button>
              <button
                style={{ ...buttonStyle, backgroundColor: "rgb(217, 119, 6)" }}
                disabled={!currentJob?.needs_auth}
                onClick={() => void handleResume()}
              >
                {messages.app.resume}
              </button>
              <button
                style={{ ...buttonStyle, backgroundColor: "rgb(220, 38, 38)" }}
                disabled={!activeJobId}
                onClick={() => void handleCancel()}
              >
                {messages.app.cancel}
              </button>
            </div>
            <div style={{ display: "flex", gap: "20px", alignItems: "center", flexWrap: "wrap" }}>
              <label style={{ display: "flex", gap: "10px", alignItems: "center" }}>
                <span style={{ fontWeight: 600 }}>{messages.app.minScoreLabel}</span>
                <input
                  type="number"
                  min={0}
                  max={100}
                  value={minScore}
                  onChange={(event) => setMinScore(Number(event.target.value))}
                  style={{
                    width: "90px",
                    borderRadius: "10px",
                    border: "1px solid rgb(203, 213, 225)",
                    padding: "8px 10px",
                  }}
                />
              </label>
              <label style={{ display: "flex", gap: "10px", alignItems: "center" }}>
                <input
                  type="checkbox"
                  checked={stopOnReview}
                  onChange={(event) => setStopOnReview(event.target.checked)}
                />
                <span>{messages.app.stopOnReview}</span>
              </label>
            </div>
            <p style={{ margin: 0, color: "rgb(71, 85, 105)" }}>{messages.app.dryRunHint}</p>
            <p style={{ margin: 0, color: "rgb(180, 83, 9)" }}>{messages.app.authHint}</p>
            {moduleConfigStatus ? (
              <div
                style={{
                  borderRadius: "12px",
                  backgroundColor: moduleConfigStatus.last_error ? "rgb(255, 247, 237)" : "rgb(240, 249, 255)",
                  border: moduleConfigStatus.last_error
                    ? "1px solid rgb(253, 186, 116)"
                    : "1px solid rgb(186, 230, 253)",
                  color: moduleConfigStatus.last_error ? "rgb(154, 52, 18)" : "rgb(12, 74, 110)",
                  padding: "12px 14px",
                }}
              >
                <div>
                  {messages.app.configStatus}: {moduleConfigStatus.version} ({moduleConfigStatus.source})
                </div>
                <div>
                  {messages.app.configCheckedAt}: {formatTimestamp(moduleConfigStatus.checked_at)}
                </div>
                <div>
                  {messages.app.configSignature}:{" "}
                  {moduleConfigStatus.signature_verified ? messages.app.configVerified : messages.app.configBundled}
                </div>
                {moduleConfigStatus.last_error ? (
                  <div>
                    {messages.app.configFallback}: {moduleConfigStatus.last_error}
                  </div>
                ) : null}
              </div>
            ) : null}
            {errorMessage ? (
              <div
                style={{
                  borderRadius: "12px",
                  backgroundColor: "rgb(254, 242, 242)",
                  border: "1px solid rgb(254, 202, 202)",
                  color: "rgb(153, 27, 27)",
                  padding: "12px 14px",
                }}
              >
                {errorMessage}
              </div>
            ) : null}
          </div>
        </section>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1.25fr 1fr 1fr",
            gap: "20px",
          }}
        >
          <section style={cardStyle}>
            <h2 style={{ marginTop: 0 }}>{messages.app.preview.title}</h2>
            {preview ? (
              <>
                <p style={{ marginTop: 0, lineHeight: 1.6 }}>
                  {preview.detected_level} •{" "}
                  {formatSummary(
                    messages.app.preview.summaryRows,
                    preview.rows_accepted,
                    preview.rows_total,
                  )}
                </p>
                <div style={{ marginBottom: "16px" }}>
                  <strong>{messages.app.preview.warnings}</strong>
                  <div style={{ marginTop: "8px", color: "rgb(71, 85, 105)" }}>
                    {preview.warnings.length === 0
                      ? "ไม่มี warning"
                      : preview.warnings.map((warning) => (
                          <div key={`${warning.code}-${warning.row_index}`}>
                            {warning.code} • row {warning.row_index} • {warning.message_th}
                          </div>
                        ))}
                  </div>
                </div>
                <strong>{messages.app.preview.tableTitle}</strong>
                <div style={{ overflowX: "auto", marginTop: "10px" }}>
                  <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "14px" }}>
                    <thead>
                      <tr style={{ textAlign: "left", backgroundColor: "rgb(241, 245, 249)" }}>
                        <th style={{ padding: "10px" }}>ลำดับ</th>
                        <th style={{ padding: "10px" }}>ห้อง</th>
                        <th style={{ padding: "10px" }}>เลขนักเรียน</th>
                        <th style={{ padding: "10px" }}>ชื่อ</th>
                        <th style={{ padding: "10px" }}>สถานะ</th>
                        <th style={{ padding: "10px" }}>รหัส</th>
                      </tr>
                    </thead>
                    <tbody>
                      {preview.preview.map((row) => (
                        <tr key={`${row.order}-${row.student_no}`}>
                          <td style={{ padding: "10px", borderTop: "1px solid rgb(226, 232, 240)" }}>
                            {row.order}
                          </td>
                          <td style={{ padding: "10px", borderTop: "1px solid rgb(226, 232, 240)" }}>
                            {row.room ?? "-"}
                          </td>
                          <td style={{ padding: "10px", borderTop: "1px solid rgb(226, 232, 240)" }}>
                            {row.student_no}
                          </td>
                          <td style={{ padding: "10px", borderTop: "1px solid rgb(226, 232, 240)" }}>
                            {row.first_name} {row.last_name}
                          </td>
                          <td style={{ padding: "10px", borderTop: "1px solid rgb(226, 232, 240)" }}>
                            {row.status_text}
                          </td>
                          <td style={{ padding: "10px", borderTop: "1px solid rgb(226, 232, 240)" }}>
                            {row.status_code}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            ) : (
              <p style={{ marginBottom: 0 }}>{messages.app.preview.empty}</p>
            )}
          </section>

          <section style={cardStyle}>
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
                      background:
                        "linear-gradient(90deg, rgb(13, 148, 136), rgb(34, 197, 94))",
                      transition: "width 200ms ease",
                    }}
                  />
                </div>
                <div style={{ display: "grid", gap: "8px", lineHeight: 1.6 }}>
                  <div>
                    <strong>{messages.app.progress.status}:</strong> {currentJob.status}
                  </div>
                  <div>
                    <strong>{messages.app.progress.processed}:</strong> {currentJob.processed}/
                    {currentJob.total ?? "-"}
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
                  <div>
                    <strong>ไฟล์:</strong> {currentJob.source_file}
                  </div>
                  <div>
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
                      ต้องลงชื่อเข้าใช้ใหม่ก่อน resume
                      <div style={{ marginTop: "6px" }}>
                        reason: {currentJob.auth_reason ?? "auth_required"}
                      </div>
                    </div>
                  ) : null}
                </div>
              </>
            ) : (
              <p style={{ marginBottom: 0 }}>{messages.app.progress.empty}</p>
            )}
          </section>

          <div style={{ display: "grid", gap: "20px" }}>
            <section style={cardStyle}>
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
                      <div style={{ fontWeight: 700 }}>{job.job_id}</div>
                      <div style={{ marginTop: "4px", color: "rgb(71, 85, 105)", fontSize: "14px" }}>
                        {job.level_label ?? "-"} • {job.status} • {job.processed}/{job.total ?? "-"}
                      </div>
                      <div style={{ marginTop: "6px", fontSize: "13px", color: "rgb(51, 65, 85)" }}>
                        <strong>{messages.app.existingJobs.sourceFile}:</strong> {job.source_file}
                      </div>
                      <div style={{ marginTop: "4px", fontSize: "13px", color: "rgb(51, 65, 85)" }}>
                        <strong>{messages.app.existingJobs.updatedAt}:</strong>{" "}
                        {formatTimestamp(job.finished_at ?? job.started_at)}
                      </div>
                      <div style={{ display: "flex", gap: "8px", marginTop: "10px", flexWrap: "wrap" }}>
                        <button
                          style={{ ...buttonStyle, padding: "8px 12px", backgroundColor: "rgb(5, 150, 105)" }}
                          onClick={() => {
                            setActiveJobId(job.job_id);
                            setCurrentJob(job);
                            setExcelPath(job.source_file);
                          }}
                        >
                          ใช้งานรายการนี้
                        </button>
                        <button
                          style={{ ...buttonStyle, padding: "8px 12px", backgroundColor: "rgb(59, 130, 246)" }}
                          disabled={isStartingJob || job.status === "done" || job.status === "cancelled"}
                          onClick={() => void handleResumeExisting(job)}
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

            <section style={cardStyle}>
              <h2 style={{ marginTop: 0 }}>{messages.app.sidecarLog.title}</h2>
              {sidecarMessages.length > 0 ? (
                <div style={{ display: "grid", gap: "8px" }}>
                  {sidecarMessages.map((message, index) => (
                    <div
                      key={`${message}-${index}`}
                      style={{
                        borderRadius: "12px",
                        backgroundColor: "rgb(248, 250, 252)",
                        padding: "10px 12px",
                        color: "rgb(51, 65, 85)",
                      }}
                    >
                      {message}
                    </div>
                  ))}
                </div>
              ) : (
                <p style={{ marginBottom: 0 }}>{messages.app.sidecarLog.empty}</p>
              )}
            </section>
          </div>
        </div>
      </section>
    </main>
  );
}
