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

export type ListJobsResponse = {
  items: JobStatusSnapshot[];
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

export function parseListJobsResponse(value: unknown): ListJobsResponse {
  const record = asRecord(value, "list_jobs_response");
  return {
    items: readArray(record, "items", "list_jobs_response").map(parseJobStatusSnapshot),
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
    default:
      throw new Error(`Unsupported sidecar event type: ${eventType}`);
  }
}
