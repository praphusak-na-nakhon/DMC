import type { CSSProperties } from "react";
import type {
  AccountStatus,
  AvailableUpdate,
  BrowserRuntimeStatus,
  DatabaseStatus,
  JobStatusSnapshot,
  ModuleConfigStatus,
  UpdaterStatus,
} from "../types/contracts";

export function formatSummary(template: string, accepted: number, total: number): string {
  return template.replace("{accepted}", String(accepted)).replace("{total}", String(total));
}

export function buildJobId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `job-${Date.now()}`;
}

export function buildTimestampSlug(): string {
  const now = new Date();
  const pad = (value: number): string => String(value).padStart(2, "0");
  return `${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}-${pad(now.getHours())}${pad(now.getMinutes())}${pad(now.getSeconds())}`;
}

export function formatTimestamp(value: string | null): string {
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

export function formatBytes(value: number | null): string {
  if (value === null || value <= 0) {
    return "-";
  }
  const units = ["B", "KB", "MB", "GB"];
  let current = value;
  let unitIndex = 0;
  while (current >= 1024 && unitIndex < units.length - 1) {
    current /= 1024;
    unitIndex += 1;
  }
  return `${current.toFixed(current >= 100 || unitIndex === 0 ? 0 : 1)} ${units[unitIndex]}`;
}

export function describeBrowserRuntimePhase(
  phase: "checking" | "installing" | "verifying" | "ready" | "failed",
): string {
  switch (phase) {
    case "checking":
      return "กำลังตรวจความพร้อมก่อนติดตั้ง";
    case "installing":
      return "กำลังดาวน์โหลดและติดตั้ง Chromium";
    case "verifying":
      return "กำลังตรวจสอบ Chromium ที่ติดตั้งแล้ว";
    case "ready":
      return "Chromium พร้อมใช้งาน";
    case "failed":
      return "ติดตั้ง Chromium ไม่สำเร็จ";
  }
}

export function describeJobStatus(status: string | null | undefined): string {
  switch (status) {
    case "running":
      return "กำลังทำงาน";
    case "pending":
      return "รอเริ่มงาน";
    case "paused":
      return "พักงาน";
    case "stopped_on_review":
      return "หยุดเพื่อให้ตรวจทาน";
    case "failed":
      return "ล้มเหลว";
    case "done":
      return "เสร็จแล้ว";
    case "cancelled":
      return "ยกเลิกแล้ว";
    default:
      return status ?? "-";
  }
}

export function isActiveJobStatus(status: string | null | undefined): boolean {
  return status === "running" || status === "pending" || status === "paused" || status === "stopped_on_review";
}

export function describeCreditStatus(status: string | null | undefined): {
  tone: "info" | "warning" | "danger" | "success";
  title: string;
  message: string;
} | null {
  if (!status) {
    return null;
  }
  if (status === "reserving") {
    return {
      tone: "info",
      title: "กำลังกันเครดิต",
      message: "ระบบกำลังติดต่อ cloud เพื่อกันเครดิตก่อนเริ่มงานจริง กรุณารอสักครู่",
    };
  }
  if (status === "reserved") {
    return {
      tone: "success",
      title: "กันเครดิตแล้ว",
      message: "ระบบกันเครดิตสำหรับงานนี้เรียบร้อย และจะคืนเครดิตส่วนที่ไม่ได้ใช้หลังจบงาน",
    };
  }
  if (status === "finalized") {
    return {
      tone: "success",
      title: "สรุปเครดิตแล้ว",
      message: "ระบบตัดเครดิตที่ใช้จริงและคืนเครดิตที่เหลือเรียบร้อย",
    };
  }
  if (status.startsWith("start_failed:")) {
    const code = status.slice("start_failed:".length);
    if (code === "INSUFFICIENT_CREDITS") {
      return {
        tone: "danger",
        title: "เครดิตไม่พอ",
        message: "ระบบกันเครดิตไม่สำเร็จเพราะเครดิตไม่พอ กรุณาเติมเครดิตแล้วลองเริ่มงานอีกครั้ง",
      };
    }
    if (code === "ACCOUNT_CLOUD_UNAVAILABLE") {
      return {
        tone: "danger",
        title: "เชื่อมต่อ cloud ไม่ได้",
        message: "ระบบยังกันเครดิตไม่ได้เพราะติดต่อ cloud ไม่สำเร็จ กรุณาตรวจอินเทอร์เน็ตแล้วลองใหม่",
      };
    }
    return {
      tone: "danger",
      title: "เริ่มงานไม่สำเร็จ",
      message: `ระบบกันเครดิตหรือเตรียมงานไม่สำเร็จ (${code}) กรุณาลองใหม่หรือติดต่อผู้ดูแล`,
    };
  }
  return {
    tone: "warning",
    title: "สถานะเครดิต",
    message: status,
  };
}

export const cardStyle: CSSProperties = {
  border: "1px solid rgb(226, 232, 240)",
  borderRadius: "16px",
  padding: "20px",
  backgroundColor: "rgba(255, 255, 255, 0.92)",
  minWidth: 0,
  maxWidth: "100%",
  boxSizing: "border-box",
};

export const buttonStyle: CSSProperties = {
  border: "none",
  borderRadius: "999px",
  padding: "11px 16px",
  fontSize: "14px",
  fontWeight: 600,
  cursor: "pointer",
  backgroundColor: "rgb(15, 118, 110)",
  color: "white",
  maxWidth: "100%",
  overflowWrap: "anywhere",
  textAlign: "center",
};

export function buildDraftJob(
  excelPath: string,
  previewRowsAccepted: number | null,
  jobId: string,
): JobStatusSnapshot {
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
    run_summary: null,
    credit_reservation_id: null,
    credits_reserved: 0,
    credits_captured: 0,
    credits_refunded: 0,
    credit_status: null,
  };
}

type DiagnosticsInput = {
  appVersion: string;
  platform: string;
  connectionState: string;
  databaseStatus: DatabaseStatus | null;
  accountStatus: AccountStatus | null;
  moduleConfigStatus: ModuleConfigStatus | null;
  browserRuntimeStatus: BrowserRuntimeStatus | null;
  updaterStatus: UpdaterStatus | null;
  availableUpdate: AvailableUpdate | null;
  currentJob: JobStatusSnapshot | null;
  existingJobs: JobStatusSnapshot[];
  sidecarMessageCount: number;
  hasErrorMessage: boolean;
};

function sanitizeJobForDiagnostics(job: JobStatusSnapshot | null): Record<string, unknown> | null {
  if (!job) {
    return null;
  }
  return {
    job_id: job.job_id,
    module: job.module,
    status: job.status,
    processed: job.processed,
    total: job.total,
    succeeded: job.succeeded,
    failed: job.failed,
    current_page: job.current_page,
    needs_auth: job.needs_auth,
    auth_reason: job.auth_reason,
    started_at: job.started_at,
    finished_at: job.finished_at,
    level_label: job.level_label,
    has_report_path: Boolean(job.report_path),
    has_review_report_path: Boolean(job.review_report_path),
    has_stopped_item: Boolean(job.stopped_item),
    run_summary: job.run_summary,
    credits_reserved: job.credits_reserved,
    credits_captured: job.credits_captured,
    credits_refunded: job.credits_refunded,
    credit_status: job.credit_status,
  };
}

function sanitizeAccountForDiagnostics(status: AccountStatus | null): Record<string, unknown> | null {
  if (!status) {
    return null;
  }
  return {
    signed_in: status.signed_in,
    user_id: status.user_id,
    status: status.status,
    token_expires_at: status.token_expires_at,
    last_checked_at: status.last_checked_at,
    wallet: status.wallet
      ? {
          balance: status.wallet.balance,
          reserved: status.wallet.reserved,
          available: status.wallet.available,
        }
      : null,
    can_start_credit_jobs: status.can_start_credit_jobs,
    needs_attention: status.needs_attention,
    message: status.message,
    last_error: status.last_error,
  };
}

export function buildSupportDiagnostics(input: DiagnosticsInput): Record<string, unknown> {
  return {
    exported_at: new Date().toISOString(),
    app_version: input.appVersion,
    platform: input.platform,
    connection_state: input.connectionState,
    database_status: input.databaseStatus,
    account_status: sanitizeAccountForDiagnostics(input.accountStatus),
    module_config_status: input.moduleConfigStatus,
    browser_runtime_status: input.browserRuntimeStatus,
    updater_status: input.updaterStatus,
    available_update: input.availableUpdate,
    current_job: sanitizeJobForDiagnostics(input.currentJob),
    existing_jobs: input.existingJobs.map(sanitizeJobForDiagnostics),
    sidecar_message_count: input.sidecarMessageCount,
    has_error_message: input.hasErrorMessage,
  };
}
