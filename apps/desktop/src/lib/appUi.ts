import type { CSSProperties } from "react";
import type {
  AvailableUpdate,
  BrowserRuntimeStatus,
  DatabaseStatus,
  JobStatusSnapshot,
  LicenseStatus,
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
      return "Check installer prerequisites";
    case "installing":
      return "Download and install Chromium runtime";
    case "verifying":
      return "Verify installed browser runtime";
    case "ready":
      return "Browser runtime is ready";
    case "failed":
      return "Browser runtime setup failed";
  }
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
  };
}

type DiagnosticsInput = {
  appVersion: string;
  platform: string;
  connectionState: string;
  databaseStatus: DatabaseStatus | null;
  licenseStatus: LicenseStatus | null;
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
  };
}

function sanitizeLicenseForDiagnostics(status: LicenseStatus | null): Record<string, unknown> | null {
  if (!status) {
    return null;
  }
  return {
    configured: status.configured,
    status: status.status,
    license_tier: status.license_tier,
    school_size_tier: status.school_size_tier,
    billing_interval: status.billing_interval,
    student_count_total: status.student_count_total,
    max_devices: status.max_devices,
    modules_enabled: status.modules_enabled,
    expires_at: status.expires_at,
    last_checked_at: status.last_checked_at,
    offline_grace_until: status.offline_grace_until,
    offline_mode: status.offline_mode,
    within_offline_grace: status.within_offline_grace,
    can_start_jobs: status.can_start_jobs,
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
    license_status: sanitizeLicenseForDiagnostics(input.licenseStatus),
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
