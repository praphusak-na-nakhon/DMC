type UnknownRecord = Record<string, unknown>;

function asRecord(value: unknown, context: string): UnknownRecord {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new Error(`${context} must be an object`);
  }
  return value as UnknownRecord;
}

function readString(record: UnknownRecord, key: string, context: string): string {
  const value = record[key];
  if (typeof value !== "string") {
    throw new Error(`${context}.${key} must be a string`);
  }
  return value;
}

function readOptionalString(record: UnknownRecord, key: string, context: string): string | null {
  const value = record[key];
  if (value === null || value === undefined) {
    return null;
  }
  if (typeof value !== "string") {
    throw new Error(`${context}.${key} must be a string or null`);
  }
  return value;
}

function readNumber(record: UnknownRecord, key: string, context: string): number {
  const value = record[key];
  if (typeof value !== "number" || Number.isNaN(value)) {
    throw new Error(`${context}.${key} must be a number`);
  }
  return value;
}

function readOptionalNumber(record: UnknownRecord, key: string, context: string): number | null {
  const value = record[key];
  if (value === null || value === undefined) {
    return null;
  }
  if (typeof value !== "number" || Number.isNaN(value)) {
    throw new Error(`${context}.${key} must be a number or null`);
  }
  return value;
}

function readBoolean(record: UnknownRecord, key: string, context: string): boolean {
  const value = record[key];
  if (typeof value !== "boolean") {
    throw new Error(`${context}.${key} must be a boolean`);
  }
  return value;
}

function readObjectOrNull(record: UnknownRecord, key: string, context: string): Record<string, unknown> | null {
  const value = record[key];
  if (value === null || value === undefined) {
    return null;
  }
  if (typeof value !== "object" || Array.isArray(value)) {
    throw new Error(`${context}.${key} must be an object or null`);
  }
  return value as Record<string, unknown>;
}

function readArray(record: UnknownRecord, key: string, context: string): unknown[] {
  const value = record[key];
  if (!Array.isArray(value)) {
    throw new Error(`${context}.${key} must be an array`);
  }
  return value;
}

export type ValidationWarning = {
  code: string;
  row_index: number;
  message_th: string;
};

export type PreviewRow = {
  order: number;
  level_label: string;
  room: number | null;
  student_no: string;
  first_name: string;
  last_name: string;
  status_text: string;
  status_code: string;
};

export type ValidateExcelResponse = {
  module: "graduation";
  detected_level: string;
  rows_total: number;
  rows_accepted: number;
  warnings: ValidationWarning[];
  preview: PreviewRow[];
};

export type JobRunSummary = {
  dmc_rows_total: number;
  matched_from_excel: number;
  default_207: number;
  excel_missing: number;
  review_rows: number;
  applied_rows: number;
  dry_run_rows: number;
};

export type JobStatusSnapshot = {
  job_id: string;
  module: string;
  status: string;
  source_file: string;
  processed: number;
  total: number | null;
  succeeded: number;
  failed: number;
  current_page: number | null;
  needs_auth: boolean;
  auth_reason: string | null;
  report_path: string | null;
  review_report_path: string | null;
  stopped_item: Record<string, unknown> | null;
  started_at: string | null;
  finished_at: string | null;
  level_label: string | null;
  run_summary: JobRunSummary | null;
};

export type StartJobResponse = {
  accepted: boolean;
  job_id: string;
};

export type ModuleConfigStatus = {
  module: "graduation";
  version: string;
  source: "bundled" | "cached" | "cloud";
  signature_verified: boolean;
  config_path: string;
  checked_at: string;
  updated: boolean;
  last_error: string | null;
};

export type LicenseStatus = {
  configured: boolean;
  status: string;
  license_tier: string | null;
  school_size_tier: string | null;
  billing_interval: string | null;
  student_count_total: number | null;
  max_devices: number | null;
  modules_enabled: string[];
  expires_at: string | null;
  last_checked_at: string | null;
  offline_grace_until: string | null;
  offline_mode: boolean;
  within_offline_grace: boolean;
  can_start_jobs: boolean;
  needs_attention: boolean;
  message: string | null;
  last_error: string | null;
};

export type BrowserRuntimePackage = {
  name: string;
  install_location: string;
  download_url: string;
  download_bytes: number | null;
};

export type BrowserRuntimeStatus = {
  state: "ready" | "missing" | "installing" | "failed";
  installed: boolean;
  install_dir: string;
  executable_path: string | null;
  bootstrap_supported: boolean;
  bootstrap_performed: boolean;
  estimated_download_bytes: number | null;
  required_components: BrowserRuntimePackage[];
  message: string | null;
  guidance: string | null;
  last_error: string | null;
  log_tail: string[];
};

export type DatabaseStatus = {
  path: string;
  schema_version: number;
  tables: string[];
};

export type BackupCreateResponse = {
  backup_path: string;
};

export type RestoreBackupResponse = {
  restored_from: string;
  safety_backup_path: string;
  database_path: string;
};

export type ListJobsResponse = {
  items: JobStatusSnapshot[];
};

export type UpdaterStatus = {
  configured: boolean;
  endpoint: string | null;
  current_version: string;
  pubkey_configured: boolean;
};

export type AvailableUpdate = {
  version: string;
  current_version: string;
  date: string | null;
  body: string | null;
};

export type UpdaterEvent =
  | {
      type: "started";
      downloaded: number;
      contentLength: number | null;
    }
  | {
      type: "progress";
      downloaded: number;
      contentLength: number | null;
    }
  | {
      type: "finished";
    }
  | {
      type: "installed";
    }
  | {
      type: "error";
      message: string;
    };

export type SidecarEvent =
  | {
      type: "progress";
      job_id: string;
      processed: number;
      total: number | null;
      succeeded: number;
      failed: number;
      current_page: number | null;
      needs_auth: boolean;
      auth_reason: string | null;
    }
  | {
      type: "record_done";
      job_id: string;
      row: number;
      status: string;
    }
  | {
      type: "needs_auth";
      job_id: string;
      reason: string;
    }
  | {
      type: "job_done";
      job_id: string;
      status: string;
      report_path: string;
      review_report_path: string;
      run_summary: JobRunSummary | null;
    }
  | {
      type: "job_stopped";
      job_id: string;
      status: string;
      stopped_item: Record<string, unknown> | null;
    }
  | {
      type: "error";
      job_id: string;
      code: string;
      message: string;
    }
  | {
      type: "sidecar_started";
      pid: number | null;
    }
  | {
      type: "sidecar_exited";
      code: number | null;
      signal: string | null;
      message: string | null;
    }
  | {
      type: "sidecar_stderr";
      message: string;
    }
  | {
      type: "browser_runtime_progress";
      phase: "checking" | "installing" | "verifying" | "ready" | "failed";
      message: string;
      percent: number | null;
      detail: string | null;
    };

function parseValidationWarning(value: unknown, index: number): ValidationWarning {
  const record = asRecord(value, `validation_warning[${index}]`);
  return {
    code: readString(record, "code", "validation_warning"),
    row_index: readNumber(record, "row_index", "validation_warning"),
    message_th: readString(record, "message_th", "validation_warning"),
  };
}

function parsePreviewRow(value: unknown, index: number): PreviewRow {
  const record = asRecord(value, `preview_row[${index}]`);
  return {
    order: readNumber(record, "order", "preview_row"),
    level_label: readString(record, "level_label", "preview_row"),
    room: readOptionalNumber(record, "room", "preview_row"),
    student_no: readString(record, "student_no", "preview_row"),
    first_name: readString(record, "first_name", "preview_row"),
    last_name: readString(record, "last_name", "preview_row"),
    status_text: readString(record, "status_text", "preview_row"),
    status_code: readString(record, "status_code", "preview_row"),
  };
}

export function parseValidateExcelResponse(value: unknown): ValidateExcelResponse {
  const record = asRecord(value, "validate_excel_response");
  const module = readString(record, "module", "validate_excel_response");
  if (module !== "graduation") {
    throw new Error("validate_excel_response.module must be 'graduation'");
  }
  return {
    module,
    detected_level: readString(record, "detected_level", "validate_excel_response"),
    rows_total: readNumber(record, "rows_total", "validate_excel_response"),
    rows_accepted: readNumber(record, "rows_accepted", "validate_excel_response"),
    warnings: readArray(record, "warnings", "validate_excel_response").map(parseValidationWarning),
    preview: readArray(record, "preview", "validate_excel_response").map(parsePreviewRow),
  };
}

function parseJobRunSummary(value: unknown, context = "job_run_summary"): JobRunSummary {
  const record = asRecord(value, context);
  return {
    dmc_rows_total: readNumber(record, "dmc_rows_total", context),
    matched_from_excel: readNumber(record, "matched_from_excel", context),
    default_207: readNumber(record, "default_207", context),
    excel_missing: readNumber(record, "excel_missing", context),
    review_rows: readNumber(record, "review_rows", context),
    applied_rows: readNumber(record, "applied_rows", context),
    dry_run_rows: readNumber(record, "dry_run_rows", context),
  };
}

function parseOptionalJobRunSummary(record: UnknownRecord, key: string, context: string): JobRunSummary | null {
  const value = readObjectOrNull(record, key, context);
  return value ? parseJobRunSummary(value, `${context}.${key}`) : null;
}

export function parseJobStatusSnapshot(value: unknown): JobStatusSnapshot {
  const record = asRecord(value, "job_status_snapshot");
  return {
    job_id: readString(record, "job_id", "job_status_snapshot"),
    module: readString(record, "module", "job_status_snapshot"),
    status: readString(record, "status", "job_status_snapshot"),
    source_file: readString(record, "source_file", "job_status_snapshot"),
    processed: readNumber(record, "processed", "job_status_snapshot"),
    total: readOptionalNumber(record, "total", "job_status_snapshot"),
    succeeded: readNumber(record, "succeeded", "job_status_snapshot"),
    failed: readNumber(record, "failed", "job_status_snapshot"),
    current_page: readOptionalNumber(record, "current_page", "job_status_snapshot"),
    needs_auth: readBoolean(record, "needs_auth", "job_status_snapshot"),
    auth_reason: readOptionalString(record, "auth_reason", "job_status_snapshot"),
    report_path: readOptionalString(record, "report_path", "job_status_snapshot"),
    review_report_path: readOptionalString(record, "review_report_path", "job_status_snapshot"),
    stopped_item: readObjectOrNull(record, "stopped_item", "job_status_snapshot"),
    started_at: readOptionalString(record, "started_at", "job_status_snapshot"),
    finished_at: readOptionalString(record, "finished_at", "job_status_snapshot"),
    level_label: readOptionalString(record, "level_label", "job_status_snapshot"),
    run_summary: parseOptionalJobRunSummary(record, "run_summary", "job_status_snapshot"),
  };
}

export function parseStartJobResponse(value: unknown): StartJobResponse {
  const record = asRecord(value, "start_job_response");
  return {
    accepted: readBoolean(record, "accepted", "start_job_response"),
    job_id: readString(record, "job_id", "start_job_response"),
  };
}

export function parseModuleConfigStatus(value: unknown): ModuleConfigStatus {
  const record = asRecord(value, "module_config_status");
  const module = readString(record, "module", "module_config_status");
  if (module !== "graduation") {
    throw new Error("module_config_status.module must be 'graduation'");
  }

  const source = readString(record, "source", "module_config_status");
  if (source !== "bundled" && source !== "cached" && source !== "cloud") {
    throw new Error("module_config_status.source must be bundled, cached, or cloud");
  }

  return {
    module,
    version: readString(record, "version", "module_config_status"),
    source,
    signature_verified: readBoolean(record, "signature_verified", "module_config_status"),
    config_path: readString(record, "config_path", "module_config_status"),
    checked_at: readString(record, "checked_at", "module_config_status"),
    updated: readBoolean(record, "updated", "module_config_status"),
    last_error: readOptionalString(record, "last_error", "module_config_status"),
  };
}

export function parseLicenseStatus(value: unknown): LicenseStatus {
  const record = asRecord(value, "license_status");
  return {
    configured: readBoolean(record, "configured", "license_status"),
    status: readString(record, "status", "license_status"),
    license_tier: readOptionalString(record, "license_tier", "license_status"),
    school_size_tier: readOptionalString(record, "school_size_tier", "license_status"),
    billing_interval: readOptionalString(record, "billing_interval", "license_status"),
    student_count_total: readOptionalNumber(record, "student_count_total", "license_status"),
    max_devices: readOptionalNumber(record, "max_devices", "license_status"),
    modules_enabled: readArray(record, "modules_enabled", "license_status").map((item, index) => {
      if (typeof item !== "string") {
        throw new Error(`license_status.modules_enabled[${index}] must be a string`);
      }
      return item;
    }),
    expires_at: readOptionalString(record, "expires_at", "license_status"),
    last_checked_at: readOptionalString(record, "last_checked_at", "license_status"),
    offline_grace_until: readOptionalString(record, "offline_grace_until", "license_status"),
    offline_mode: readBoolean(record, "offline_mode", "license_status"),
    within_offline_grace: readBoolean(record, "within_offline_grace", "license_status"),
    can_start_jobs: readBoolean(record, "can_start_jobs", "license_status"),
    needs_attention: readBoolean(record, "needs_attention", "license_status"),
    message: readOptionalString(record, "message", "license_status"),
    last_error: readOptionalString(record, "last_error", "license_status"),
  };
}

function parseBrowserRuntimePackage(value: unknown, index: number): BrowserRuntimePackage {
  const record = asRecord(value, `browser_runtime_package[${index}]`);
  return {
    name: readString(record, "name", "browser_runtime_package"),
    install_location: readString(record, "install_location", "browser_runtime_package"),
    download_url: readString(record, "download_url", "browser_runtime_package"),
    download_bytes: readOptionalNumber(record, "download_bytes", "browser_runtime_package"),
  };
}

export function parseBrowserRuntimeStatus(value: unknown): BrowserRuntimeStatus {
  const record = asRecord(value, "browser_runtime_status");
  const state = readString(record, "state", "browser_runtime_status");
  if (state !== "ready" && state !== "missing" && state !== "installing" && state !== "failed") {
    throw new Error("browser_runtime_status.state must be ready, missing, installing, or failed");
  }
  return {
    state,
    installed: readBoolean(record, "installed", "browser_runtime_status"),
    install_dir: readString(record, "install_dir", "browser_runtime_status"),
    executable_path: readOptionalString(record, "executable_path", "browser_runtime_status"),
    bootstrap_supported: readBoolean(record, "bootstrap_supported", "browser_runtime_status"),
    bootstrap_performed: readBoolean(record, "bootstrap_performed", "browser_runtime_status"),
    estimated_download_bytes: readOptionalNumber(record, "estimated_download_bytes", "browser_runtime_status"),
    required_components: readArray(record, "required_components", "browser_runtime_status").map(parseBrowserRuntimePackage),
    message: readOptionalString(record, "message", "browser_runtime_status"),
    guidance: readOptionalString(record, "guidance", "browser_runtime_status"),
    last_error: readOptionalString(record, "last_error", "browser_runtime_status"),
    log_tail: readArray(record, "log_tail", "browser_runtime_status").map((item, index) => {
      if (typeof item !== "string") {
        throw new Error(`browser_runtime_status.log_tail[${index}] must be a string`);
      }
      return item;
    }),
  };
}

export function parseDatabaseStatus(value: unknown): DatabaseStatus {
  const record = asRecord(value, "database_status");
  return {
    path: readString(record, "path", "database_status"),
    schema_version: readNumber(record, "schema_version", "database_status"),
    tables: readArray(record, "tables", "database_status").map((item, index) => {
      if (typeof item !== "string") {
        throw new Error(`database_status.tables[${index}] must be a string`);
      }
      return item;
    }),
  };
}

export function parseBackupCreateResponse(value: unknown): BackupCreateResponse {
  const record = asRecord(value, "backup_create_response");
  return {
    backup_path: readString(record, "backup_path", "backup_create_response"),
  };
}

export function parseRestoreBackupResponse(value: unknown): RestoreBackupResponse {
  const record = asRecord(value, "restore_backup_response");
  return {
    restored_from: readString(record, "restored_from", "restore_backup_response"),
    safety_backup_path: readString(record, "safety_backup_path", "restore_backup_response"),
    database_path: readString(record, "database_path", "restore_backup_response"),
  };
}

export function parseListJobsResponse(value: unknown): ListJobsResponse {
  const record = asRecord(value, "list_jobs_response");
  return {
    items: readArray(record, "items", "list_jobs_response").map(parseJobStatusSnapshot),
  };
}

export function parseUpdaterStatus(value: unknown): UpdaterStatus {
  const record = asRecord(value, "updater_status");
  return {
    configured: readBoolean(record, "configured", "updater_status"),
    endpoint: readOptionalString(record, "endpoint", "updater_status"),
    current_version: readString(record, "current_version", "updater_status"),
    pubkey_configured: readBoolean(record, "pubkey_configured", "updater_status"),
  };
}

export function parseAvailableUpdate(value: unknown): AvailableUpdate | null {
  if (value === null) {
    return null;
  }
  const record = asRecord(value, "available_update");
  return {
    version: readString(record, "version", "available_update"),
    current_version: readString(record, "current_version", "available_update"),
    date: readOptionalString(record, "date", "available_update"),
    body: readOptionalString(record, "body", "available_update"),
  };
}

export function parseJobActionResponse(value: unknown): {
  accepted?: boolean;
  job_id: string;
  status: string;
} {
  const record = asRecord(value, "job_action_response");
  const acceptedValue = record.accepted;
  return {
    accepted: acceptedValue === undefined ? undefined : readBoolean(record, "accepted", "job_action_response"),
    job_id: readString(record, "job_id", "job_action_response"),
    status: readString(record, "status", "job_action_response"),
  };
}

export function parseResumeExistingJobResponse(value: unknown): {
  accepted: boolean;
  job_id: string;
  status: string;
} {
  const parsed = parseJobActionResponse(value);
  if (parsed.accepted !== true && parsed.accepted !== false) {
    throw new Error("resume_existing_job response must include accepted");
  }
  return {
    accepted: parsed.accepted,
    job_id: parsed.job_id,
    status: parsed.status,
  };
}

export function parseUpdaterEvent(value: unknown): UpdaterEvent {
  const record = asRecord(value, "updater_event");
  const eventType = readString(record, "type", "updater_event");

  switch (eventType) {
    case "started":
      return {
        type: "started",
        downloaded: readNumber(record, "downloaded", "updater_event"),
        contentLength: readOptionalNumber(record, "contentLength", "updater_event"),
      };
    case "progress":
      return {
        type: "progress",
        downloaded: readNumber(record, "downloaded", "updater_event"),
        contentLength: readOptionalNumber(record, "contentLength", "updater_event"),
      };
    case "finished":
      return { type: "finished" };
    case "installed":
      return { type: "installed" };
    case "error":
      return {
        type: "error",
        message: readString(record, "message", "updater_event"),
      };
    default:
      throw new Error(`Unsupported updater event type: ${eventType}`);
  }
}

export function parseSidecarEvent(value: unknown): SidecarEvent {
  const record = asRecord(value, "sidecar_event");
  const eventType = readString(record, "type", "sidecar_event");

  switch (eventType) {
    case "progress":
      return {
        type: "progress",
        job_id: readString(record, "job_id", "sidecar_event"),
        processed: readNumber(record, "processed", "sidecar_event"),
        total: readOptionalNumber(record, "total", "sidecar_event"),
        succeeded: readNumber(record, "succeeded", "sidecar_event"),
        failed: readNumber(record, "failed", "sidecar_event"),
        current_page: readOptionalNumber(record, "current_page", "sidecar_event"),
        needs_auth: readBoolean(record, "needs_auth", "sidecar_event"),
        auth_reason: readOptionalString(record, "auth_reason", "sidecar_event"),
      };
    case "record_done":
      return {
        type: "record_done",
        job_id: readString(record, "job_id", "sidecar_event"),
        row: readNumber(record, "row", "sidecar_event"),
        status: readString(record, "status", "sidecar_event"),
      };
    case "needs_auth":
      return {
        type: "needs_auth",
        job_id: readString(record, "job_id", "sidecar_event"),
        reason: readString(record, "reason", "sidecar_event"),
      };
    case "job_done":
      return {
        type: "job_done",
        job_id: readString(record, "job_id", "sidecar_event"),
        status: readString(record, "status", "sidecar_event"),
        report_path: readString(record, "report_path", "sidecar_event"),
        review_report_path: readString(record, "review_report_path", "sidecar_event"),
        run_summary: parseOptionalJobRunSummary(record, "run_summary", "sidecar_event"),
      };
    case "job_stopped":
      return {
        type: "job_stopped",
        job_id: readString(record, "job_id", "sidecar_event"),
        status: readString(record, "status", "sidecar_event"),
        stopped_item: readObjectOrNull(record, "stopped_item", "sidecar_event"),
      };
    case "error":
      return {
        type: "error",
        job_id: readString(record, "job_id", "sidecar_event"),
        code: readString(record, "code", "sidecar_event"),
        message: readString(record, "message", "sidecar_event"),
      };
    case "sidecar_started":
      return {
        type: "sidecar_started",
        pid: readOptionalNumber(record, "pid", "sidecar_event"),
      };
    case "sidecar_exited":
      return {
        type: "sidecar_exited",
        code: readOptionalNumber(record, "code", "sidecar_event"),
        signal: readOptionalString(record, "signal", "sidecar_event"),
        message: readOptionalString(record, "message", "sidecar_event"),
      };
    case "sidecar_stderr":
      return {
        type: "sidecar_stderr",
        message: readString(record, "message", "sidecar_event"),
      };
    case "browser_runtime_progress":
      return {
        type: "browser_runtime_progress",
        phase: (() => {
          const phase = readString(record, "phase", "sidecar_event");
          if (
            phase !== "checking" &&
            phase !== "installing" &&
            phase !== "verifying" &&
            phase !== "ready" &&
            phase !== "failed"
          ) {
            throw new Error(`Unsupported browser runtime phase: ${phase}`);
          }
          return phase;
        })(),
        message: readString(record, "message", "sidecar_event"),
        percent: readOptionalNumber(record, "percent", "sidecar_event"),
        detail: readOptionalString(record, "detail", "sidecar_event"),
      };
    default:
      throw new Error(`Unsupported sidecar event type: ${eventType}`);
  }
}
