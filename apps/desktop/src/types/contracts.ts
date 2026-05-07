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
  credit_reservation_id: string | null;
  credits_reserved: number;
  credits_captured: number;
  credits_refunded: number;
  credit_status: string | null;
};

export type StartJobResponse = {
  accepted: boolean;
  job_id: string;
  credit_reservation_id: string | null;
  credits_reserved: number;
};

export type WalletSnapshot = {
  user_id: string;
  balance: number;
  reserved: number;
  available: number;
};

export type AccountStatus = {
  signed_in: boolean;
  user_id: string | null;
  email: string | null;
  display_name: string | null;
  status: string;
  token_expires_at: string | null;
  last_checked_at: string | null;
  wallet: WalletSnapshot | null;
  can_start_credit_jobs: boolean;
  needs_attention: boolean;
  message: string | null;
  last_error: string | null;
};

export type ModuleCatalogItem = {
  id: string;
  enabled: boolean;
  requires_credits: boolean;
  pricing_mode: "per_billable_record";
  credit_per_unit: number;
  production_dry_run_enabled: boolean;
};

export type ModuleCatalogResponse = {
  modules: ModuleCatalogItem[];
};

export type StudentBasicInfoClassSummary = {
  level: string;
  room: string;
  sheet_name: string;
  students: number;
};

export type ExportStudentBasicInfoFormResponse = {
  module: "studentBasicInfo";
  source_path: string;
  output_path: string;
  school_name: string | null;
  school_year: string | null;
  term: string | null;
  rows_total: number;
  students_exported: number;
  classes_exported: number;
  classes: StudentBasicInfoClassSummary[];
};

export type CurrentStudentSourceType = "roster" | "thai_id_scan" | "ocr_form" | "manual";
export type CurrentStudentFieldConfidence = "authoritative" | "high" | "review" | "missing";
export type CurrentStudentFieldValue = string | number | boolean | null;
export type CurrentStudentOperationType = "current" | "transfer_in" | "add_new";
export type CurrentStudentMatchStatus =
  | "auto_matched"
  | "needs_review"
  | "duplicate"
  | "invalid_id"
  | "new_or_transfer_candidate";

export type CurrentStudentsWarning = {
  code: string;
  message: string;
  source: CurrentStudentSourceType | null;
  source_path: string | null;
  row_index: number | null;
  sheet_name: string | null;
};

export type CurrentStudentField = {
  value: CurrentStudentFieldValue;
  source: CurrentStudentSourceType;
  confidence: CurrentStudentFieldConfidence;
  raw_value: string | null;
};

export type CurrentStudentsConflictValue = {
  source: CurrentStudentSourceType;
  value: CurrentStudentFieldValue;
  confidence: CurrentStudentFieldConfidence;
  raw_value: string | null;
  source_path: string | null;
  row_index: number | null;
  sheet_name: string | null;
};

export type CurrentStudentsFieldConflict = {
  record_id: string;
  full_name: string | null;
  student_no: string | null;
  citizen_id: string | null;
  field_name: string;
  field_label: string;
  selected_value: CurrentStudentFieldValue;
  selected_source: CurrentStudentSourceType | null;
  selected_basis: string;
  reason: string;
  source_values: CurrentStudentsConflictValue[];
};

export type CurrentStudentSourceReference = {
  source: CurrentStudentSourceType;
  source_path: string;
  row_index: number | null;
  sheet_name: string | null;
};

export type CurrentStudentMatchSuggestion = {
  student_no: string;
  full_name: string;
  grade: number;
  room: number;
  score: number;
  source_path: string;
  sheet_name: string;
  row_index: number;
};

export type CurrentStudentRecord = {
  record_id: string;
  operation_type: CurrentStudentOperationType;
  match_status: CurrentStudentMatchStatus;
  student_no: string | null;
  citizen_id: string | null;
  grade: number | null;
  room: number | null;
  seat_no: number | null;
  prefix: string | null;
  first_name: string | null;
  last_name: string | null;
  full_name: string | null;
  match_score: number | null;
  review_reasons: string[];
  suggestions: CurrentStudentMatchSuggestion[];
  dmc_fields: Record<string, CurrentStudentField>;
  sources: CurrentStudentSourceReference[];
};

export type CurrentStudentsSummary = {
  roster_records: number;
  thai_id_scan_records: number;
  ocr_form_records: number;
  records_total: number;
  auto_matched: number;
  needs_review: number;
  duplicate_records: number;
  duplicate_scan_records: number;
  invalid_id_records: number;
  new_or_transfer_candidates: number;
  roster_without_thai_id: number;
  ocr_attached_records: number;
  ocr_unmatched_records: number;
  review_queue_records: number;
  warnings_total: number;
};

export type CurrentStudentsReconciliationResponse = {
  module: "currentStudents";
  school_year: number;
  grade_levels: number[] | null;
  operation_type: CurrentStudentOperationType;
  roster_excel_path: string;
  thai_id_csv_path: string | null;
  ocr_markdown_paths: string[];
  summary: CurrentStudentsSummary;
  records: CurrentStudentRecord[];
  review_queue: CurrentStudentRecord[];
  warnings: CurrentStudentsWarning[];
};

export type ExportCurrentStudentsBlankFormResponse = {
  module: "currentStudents";
  output_path: string;
  field_count: number;
  required_fields: string[];
};

export type ExportCurrentStudentsImportExcelResponse = {
  module: "formConverter";
  output_path: string;
  school_year: number;
  operation_type: CurrentStudentOperationType;
  rows_exported: number;
  summary: CurrentStudentsSummary;
  warnings: CurrentStudentsWarning[];
  conflicts: CurrentStudentsFieldConflict[];
};

export type DmcFormJsonRecord = {
  record_id: string;
  match_status: CurrentStudentMatchStatus;
  student_no: string | null;
  citizen_id: string | null;
  grade: number | null;
  room: number | null;
  seat_no: number | null;
  prefix: string | null;
  first_name: string | null;
  last_name: string | null;
  full_name: string | null;
  match_score: number | null;
  review_reasons: string[];
  suggestions: CurrentStudentMatchSuggestion[];
  sources: CurrentStudentSourceReference[];
  fields: Record<string, CurrentStudentFieldValue>;
  field_details: Record<string, CurrentStudentField>;
};

export type PreviewDmcFormJsonResponse = {
  module: "formConverter";
  schema_version: "dmc_form_json.v1";
  generated_at: string;
  school_year: number;
  grade_levels: number[] | null;
  records_previewed: number;
  field_labels: Record<string, string>;
  summary: CurrentStudentsSummary;
  warnings: CurrentStudentsWarning[];
  conflicts: CurrentStudentsFieldConflict[];
  records: DmcFormJsonRecord[];
};

export type ExportDmcFormJsonResponse = {
  module: "formConverter";
  schema_version: "dmc_form_json.v1";
  generated_at: string;
  output_path: string;
  school_year: number;
  grade_levels: number[] | null;
  records_exported: number;
  field_labels: Record<string, string>;
  summary: CurrentStudentsSummary;
  warnings: CurrentStudentsWarning[];
  conflicts: CurrentStudentsFieldConflict[];
  records: DmcFormJsonRecord[];
};

export type CurrentStudentsImportRowStatus = "ready" | "needs_review" | "invalid";

export type CurrentStudentsImportRowPreview = {
  row_index: number;
  status: CurrentStudentsImportRowStatus;
  operation_type: string | null;
  student_no: string | null;
  citizen_id: string | null;
  full_name: string;
  issues: string[];
};

export type CurrentStudentsImportSummary = {
  rows_total: number;
  ready_rows: number;
  needs_review_rows: number;
  invalid_rows: number;
  duplicate_citizen_ids: number;
  warnings_total: number;
};

export type ValidateCurrentStudentsImportFormResponse = {
  module: "currentStudents";
  excel_path: string;
  summary: CurrentStudentsImportSummary;
  preview: CurrentStudentsImportRowPreview[];
  warnings: CurrentStudentsWarning[];
};

export type EvidenceMappingStatus = "accepted" | "suggested" | "rejected" | "needs_review";
export type ReadinessRequirementStatus = "complete" | "partial" | "missing" | "needs_review";
export type ReadinessPriority = "high" | "medium" | "low";

export type PsarRequirement = {
  requirement_id: string;
  section_id: string;
  section_title: string;
  section_order: number;
  title: string;
  category: string;
  required_evidence: string[];
  optional_evidence: string[];
  weight: number;
  minimum_required_items: number;
  description: string;
};

export type PsarUploadedFile = {
  file_id: string;
  file_name: string;
  file_path: string;
  file_type: string;
  extracted_summary: string;
  created_at: string;
  updated_at: string;
};

export type PsarEvidenceMapping = {
  requirement_id: string;
  evidence_type: string;
  source_file_id: string;
  source_file_name: string;
  extracted_summary: string;
  confidence_score: number;
  page_number: number | null;
  location: string | null;
  status: EvidenceMappingStatus;
  created_at: string;
  updated_at: string;
};

export type PsarReadinessRequirement = {
  requirement_id: string;
  requirement_title: string;
  category: string;
  description: string;
  required_evidence: string[];
  optional_evidence: string[];
  weight: number;
  minimum_required_items: number;
  status: ReadinessRequirementStatus;
  completion_score: number;
  missing_evidence: string[];
  found_evidence: PsarEvidenceMapping[];
  recommendation: string;
  priority: ReadinessPriority;
};

export type PsarReadinessSection = {
  section_id: string;
  section_title: string;
  completion_score: number;
  complete_count: number;
  partial_count: number;
  missing_count: number;
  needs_review_count: number;
  requirements: PsarReadinessRequirement[];
};

export type PsarMissingEvidenceRecommendation = {
  evidence_name: string;
  requirement_id: string;
  requirement_title: string;
  section_id: string;
  section_title: string;
  why_needed: string;
  priority: ReadinessPriority;
  suggested_file_types: string[];
};

export type PsarReadinessResponse = {
  project_id: string;
  overall_completion_score: number;
  warning_threshold: number;
  confidence_threshold: number;
  total_requirements: number;
  complete_count: number;
  partial_count: number;
  missing_count: number;
  needs_review_count: number;
  sections: PsarReadinessSection[];
  missing_evidence_recommendations: PsarMissingEvidenceRecommendation[];
  mapped_files: PsarEvidenceMapping[];
  uploaded_files: PsarUploadedFile[];
};

export type AddPsarEvidenceResponse = {
  project_id: string;
  file: PsarUploadedFile;
  mappings: PsarEvidenceMapping[];
  readiness: PsarReadinessResponse;
};

export type GeneratePsarReportResponse = {
  project_id: string;
  report_path: string;
  readiness: PsarReadinessResponse;
  generated_at: string;
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

export type ArchiveJobsResponse = {
  archived: number;
  kept: number;
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
    credit_reservation_id: readOptionalString(record, "credit_reservation_id", "job_status_snapshot"),
    credits_reserved: readNumber(record, "credits_reserved", "job_status_snapshot"),
    credits_captured: readNumber(record, "credits_captured", "job_status_snapshot"),
    credits_refunded: readNumber(record, "credits_refunded", "job_status_snapshot"),
    credit_status: readOptionalString(record, "credit_status", "job_status_snapshot"),
  };
}

export function parseStartJobResponse(value: unknown): StartJobResponse {
  const record = asRecord(value, "start_job_response");
  return {
    accepted: readBoolean(record, "accepted", "start_job_response"),
    job_id: readString(record, "job_id", "start_job_response"),
    credit_reservation_id: readOptionalString(record, "credit_reservation_id", "start_job_response"),
    credits_reserved: readNumber(record, "credits_reserved", "start_job_response"),
  };
}

function parseWalletSnapshot(value: unknown, context = "wallet_snapshot"): WalletSnapshot {
  const record = asRecord(value, context);
  return {
    user_id: readString(record, "user_id", context),
    balance: readNumber(record, "balance", context),
    reserved: readNumber(record, "reserved", context),
    available: readNumber(record, "available", context),
  };
}

function parseOptionalWalletSnapshot(record: UnknownRecord, key: string, context: string): WalletSnapshot | null {
  const value = record[key];
  if (value === null || value === undefined) {
    return null;
  }
  return parseWalletSnapshot(value, `${context}.${key}`);
}

export function parseAccountStatus(value: unknown): AccountStatus {
  const record = asRecord(value, "account_status");
  return {
    signed_in: readBoolean(record, "signed_in", "account_status"),
    user_id: readOptionalString(record, "user_id", "account_status"),
    email: readOptionalString(record, "email", "account_status"),
    display_name: readOptionalString(record, "display_name", "account_status"),
    status: readString(record, "status", "account_status"),
    token_expires_at: readOptionalString(record, "token_expires_at", "account_status"),
    last_checked_at: readOptionalString(record, "last_checked_at", "account_status"),
    wallet: parseOptionalWalletSnapshot(record, "wallet", "account_status"),
    can_start_credit_jobs: readBoolean(record, "can_start_credit_jobs", "account_status"),
    needs_attention: readBoolean(record, "needs_attention", "account_status"),
    message: readOptionalString(record, "message", "account_status"),
    last_error: readOptionalString(record, "last_error", "account_status"),
  };
}

function parseModuleCatalogItem(value: unknown, index: number): ModuleCatalogItem {
  const record = asRecord(value, `module_catalog_item[${index}]`);
  const pricingMode = readString(record, "pricing_mode", "module_catalog_item");
  if (pricingMode !== "per_billable_record") {
    throw new Error("module_catalog_item.pricing_mode must be per_billable_record");
  }
  return {
    id: readString(record, "id", "module_catalog_item"),
    enabled: readBoolean(record, "enabled", "module_catalog_item"),
    requires_credits: readBoolean(record, "requires_credits", "module_catalog_item"),
    pricing_mode: pricingMode,
    credit_per_unit: readNumber(record, "credit_per_unit", "module_catalog_item"),
    production_dry_run_enabled: readBoolean(record, "production_dry_run_enabled", "module_catalog_item"),
  };
}

export function parseModuleCatalogResponse(value: unknown): ModuleCatalogResponse {
  const record = asRecord(value, "module_catalog_response");
  return {
    modules: readArray(record, "modules", "module_catalog_response").map(parseModuleCatalogItem),
  };
}

function parseStudentBasicInfoClassSummary(value: unknown, index: number): StudentBasicInfoClassSummary {
  const record = asRecord(value, `student_basic_info_class[${index}]`);
  return {
    level: readString(record, "level", "student_basic_info_class"),
    room: readString(record, "room", "student_basic_info_class"),
    sheet_name: readString(record, "sheet_name", "student_basic_info_class"),
    students: readNumber(record, "students", "student_basic_info_class"),
  };
}

export function parseExportStudentBasicInfoFormResponse(value: unknown): ExportStudentBasicInfoFormResponse {
  const record = asRecord(value, "export_student_basic_info_form_response");
  const module = readString(record, "module", "export_student_basic_info_form_response");
  if (module !== "studentBasicInfo") {
    throw new Error("export_student_basic_info_form_response.module must be studentBasicInfo");
  }
  return {
    module,
    source_path: readString(record, "source_path", "export_student_basic_info_form_response"),
    output_path: readString(record, "output_path", "export_student_basic_info_form_response"),
    school_name: readOptionalString(record, "school_name", "export_student_basic_info_form_response"),
    school_year: readOptionalString(record, "school_year", "export_student_basic_info_form_response"),
    term: readOptionalString(record, "term", "export_student_basic_info_form_response"),
    rows_total: readNumber(record, "rows_total", "export_student_basic_info_form_response"),
    students_exported: readNumber(record, "students_exported", "export_student_basic_info_form_response"),
    classes_exported: readNumber(record, "classes_exported", "export_student_basic_info_form_response"),
    classes: readArray(record, "classes", "export_student_basic_info_form_response").map(
      parseStudentBasicInfoClassSummary,
    ),
  };
}

function parseCurrentStudentSourceType(value: string, context: string): CurrentStudentSourceType {
  if (value !== "roster" && value !== "thai_id_scan" && value !== "ocr_form" && value !== "manual") {
    throw new Error(`${context}.source is invalid`);
  }
  return value;
}

function parseCurrentStudentFieldConfidence(value: string, context: string): CurrentStudentFieldConfidence {
  if (value !== "authoritative" && value !== "high" && value !== "review" && value !== "missing") {
    throw new Error(`${context}.confidence is invalid`);
  }
  return value;
}

function parseCurrentStudentOperationType(value: string, context: string): CurrentStudentOperationType {
  if (value !== "current" && value !== "transfer_in" && value !== "add_new") {
    throw new Error(`${context}.operation_type is invalid`);
  }
  return value;
}

function parseCurrentStudentMatchStatus(value: string, context: string): CurrentStudentMatchStatus {
  if (
    value !== "auto_matched" &&
    value !== "needs_review" &&
    value !== "duplicate" &&
    value !== "invalid_id" &&
    value !== "new_or_transfer_candidate"
  ) {
    throw new Error(`${context}.match_status is invalid`);
  }
  return value;
}

function parseCurrentStudentFieldValue(value: unknown, context: string): string | number | boolean | null {
  if (value === null || typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return value;
  }
  throw new Error(`${context}.value must be a string, number, boolean, or null`);
}

function parseCurrentStudentsWarning(value: unknown, index: number): CurrentStudentsWarning {
  const context = `current_students_warning[${index}]`;
  const record = asRecord(value, context);
  const source = readOptionalString(record, "source", context);
  return {
    code: readString(record, "code", context),
    message: readString(record, "message", context),
    source: source ? parseCurrentStudentSourceType(source, context) : null,
    source_path: readOptionalString(record, "source_path", context),
    row_index: readOptionalNumber(record, "row_index", context),
    sheet_name: readOptionalString(record, "sheet_name", context),
  };
}

function parseCurrentStudentField(value: unknown, context = "current_student_field"): CurrentStudentField {
  const record = asRecord(value, context);
  return {
    value: parseCurrentStudentFieldValue(record.value, context),
    source: parseCurrentStudentSourceType(readString(record, "source", context), context),
    confidence: parseCurrentStudentFieldConfidence(readString(record, "confidence", context), context),
    raw_value: readOptionalString(record, "raw_value", context),
  };
}

function parseCurrentStudentsConflictValue(value: unknown, index: number): CurrentStudentsConflictValue {
  const context = `current_students_conflict_value[${index}]`;
  const record = asRecord(value, context);
  return {
    source: parseCurrentStudentSourceType(readString(record, "source", context), context),
    value: parseCurrentStudentFieldValue(record.value, context),
    confidence: parseCurrentStudentFieldConfidence(readString(record, "confidence", context), context),
    raw_value: readOptionalString(record, "raw_value", context),
    source_path: readOptionalString(record, "source_path", context),
    row_index: readOptionalNumber(record, "row_index", context),
    sheet_name: readOptionalString(record, "sheet_name", context),
  };
}

function parseCurrentStudentsFieldConflict(value: unknown, index: number): CurrentStudentsFieldConflict {
  const context = `current_students_field_conflict[${index}]`;
  const record = asRecord(value, context);
  const selectedSource = readOptionalString(record, "selected_source", context);
  return {
    record_id: readString(record, "record_id", context),
    full_name: readOptionalString(record, "full_name", context),
    student_no: readOptionalString(record, "student_no", context),
    citizen_id: readOptionalString(record, "citizen_id", context),
    field_name: readString(record, "field_name", context),
    field_label: readString(record, "field_label", context),
    selected_value: parseCurrentStudentFieldValue(record.selected_value, context),
    selected_source: selectedSource ? parseCurrentStudentSourceType(selectedSource, context) : null,
    selected_basis: readString(record, "selected_basis", context),
    reason: readString(record, "reason", context),
    source_values: readArray(record, "source_values", context).map(parseCurrentStudentsConflictValue),
  };
}

function parseCurrentStudentDmcFields(value: unknown, context: string): Record<string, CurrentStudentField> {
  const record = asRecord(value, context);
  return Object.fromEntries(
    Object.entries(record).map(([key, fieldValue]) => [key, parseCurrentStudentField(fieldValue, `${context}.${key}`)]),
  );
}

function parseCurrentStudentFieldValueMap(value: unknown, context: string): Record<string, CurrentStudentFieldValue> {
  const record = asRecord(value, context);
  return Object.fromEntries(
    Object.entries(record).map(([key, fieldValue]) => [
      key,
      parseCurrentStudentFieldValue(fieldValue, `${context}.${key}`),
    ]),
  );
}

function parseStringMap(value: unknown, context: string): Record<string, string> {
  const record = asRecord(value, context);
  return Object.fromEntries(
    Object.entries(record).map(([key, fieldValue]) => {
      if (typeof fieldValue !== "string") {
        throw new Error(`${context}.${key} must be a string`);
      }
      return [key, fieldValue];
    }),
  );
}

function parseCurrentStudentSourceReference(value: unknown, index: number): CurrentStudentSourceReference {
  const context = `current_student_source[${index}]`;
  const record = asRecord(value, context);
  return {
    source: parseCurrentStudentSourceType(readString(record, "source", context), context),
    source_path: readString(record, "source_path", context),
    row_index: readOptionalNumber(record, "row_index", context),
    sheet_name: readOptionalString(record, "sheet_name", context),
  };
}

function parseCurrentStudentMatchSuggestion(value: unknown, index: number): CurrentStudentMatchSuggestion {
  const context = `current_student_suggestion[${index}]`;
  const record = asRecord(value, context);
  return {
    student_no: readString(record, "student_no", context),
    full_name: readString(record, "full_name", context),
    grade: readNumber(record, "grade", context),
    room: readNumber(record, "room", context),
    score: readNumber(record, "score", context),
    source_path: readString(record, "source_path", context),
    sheet_name: readString(record, "sheet_name", context),
    row_index: readNumber(record, "row_index", context),
  };
}

function parseCurrentStudentRecord(value: unknown, index: number): CurrentStudentRecord {
  const context = `current_student_record[${index}]`;
  const record = asRecord(value, context);
  const operationType = parseCurrentStudentOperationType(readString(record, "operation_type", context), context);
  const matchStatus = parseCurrentStudentMatchStatus(readString(record, "match_status", context), context);
  return {
    record_id: readString(record, "record_id", context),
    operation_type: operationType,
    match_status: matchStatus,
    student_no: readOptionalString(record, "student_no", context),
    citizen_id: readOptionalString(record, "citizen_id", context),
    grade: readOptionalNumber(record, "grade", context),
    room: readOptionalNumber(record, "room", context),
    seat_no: readOptionalNumber(record, "seat_no", context),
    prefix: readOptionalString(record, "prefix", context),
    first_name: readOptionalString(record, "first_name", context),
    last_name: readOptionalString(record, "last_name", context),
    full_name: readOptionalString(record, "full_name", context),
    match_score: readOptionalNumber(record, "match_score", context),
    review_reasons: readStringArray(record, "review_reasons", context),
    suggestions: readArray(record, "suggestions", context).map(parseCurrentStudentMatchSuggestion),
    dmc_fields: parseCurrentStudentDmcFields(record.dmc_fields, `${context}.dmc_fields`),
    sources: readArray(record, "sources", context).map(parseCurrentStudentSourceReference),
  };
}

function parseDmcFormJsonRecord(value: unknown, index: number): DmcFormJsonRecord {
  const context = `dmc_form_json_record[${index}]`;
  const record = asRecord(value, context);
  return {
    record_id: readString(record, "record_id", context),
    match_status: parseCurrentStudentMatchStatus(readString(record, "match_status", context), context),
    student_no: readOptionalString(record, "student_no", context),
    citizen_id: readOptionalString(record, "citizen_id", context),
    grade: readOptionalNumber(record, "grade", context),
    room: readOptionalNumber(record, "room", context),
    seat_no: readOptionalNumber(record, "seat_no", context),
    prefix: readOptionalString(record, "prefix", context),
    first_name: readOptionalString(record, "first_name", context),
    last_name: readOptionalString(record, "last_name", context),
    full_name: readOptionalString(record, "full_name", context),
    match_score: readOptionalNumber(record, "match_score", context),
    review_reasons: readStringArray(record, "review_reasons", context),
    suggestions: readArray(record, "suggestions", context).map(parseCurrentStudentMatchSuggestion),
    sources: readArray(record, "sources", context).map(parseCurrentStudentSourceReference),
    fields: parseCurrentStudentFieldValueMap(record.fields, `${context}.fields`),
    field_details: parseCurrentStudentDmcFields(record.field_details, `${context}.field_details`),
  };
}

function parseCurrentStudentsSummary(value: unknown): CurrentStudentsSummary {
  const record = asRecord(value, "current_students_summary");
  return {
    roster_records: readNumber(record, "roster_records", "current_students_summary"),
    thai_id_scan_records: readNumber(record, "thai_id_scan_records", "current_students_summary"),
    ocr_form_records: readNumber(record, "ocr_form_records", "current_students_summary"),
    records_total: readNumber(record, "records_total", "current_students_summary"),
    auto_matched: readNumber(record, "auto_matched", "current_students_summary"),
    needs_review: readNumber(record, "needs_review", "current_students_summary"),
    duplicate_records: readNumber(record, "duplicate_records", "current_students_summary"),
    duplicate_scan_records: readNumber(record, "duplicate_scan_records", "current_students_summary"),
    invalid_id_records: readNumber(record, "invalid_id_records", "current_students_summary"),
    new_or_transfer_candidates: readNumber(record, "new_or_transfer_candidates", "current_students_summary"),
    roster_without_thai_id: readNumber(record, "roster_without_thai_id", "current_students_summary"),
    ocr_attached_records: readNumber(record, "ocr_attached_records", "current_students_summary"),
    ocr_unmatched_records: readNumber(record, "ocr_unmatched_records", "current_students_summary"),
    review_queue_records: readNumber(record, "review_queue_records", "current_students_summary"),
    warnings_total: readNumber(record, "warnings_total", "current_students_summary"),
  };
}

export function parseCurrentStudentsReconciliationResponse(value: unknown): CurrentStudentsReconciliationResponse {
  const record = asRecord(value, "current_students_reconciliation_response");
  const module = readString(record, "module", "current_students_reconciliation_response");
  if (module !== "currentStudents") {
    throw new Error("current_students_reconciliation_response.module must be currentStudents");
  }
  const gradeLevelsValue = record.grade_levels;
  const gradeLevels =
    gradeLevelsValue === null || gradeLevelsValue === undefined
      ? null
      : readArray(record, "grade_levels", "current_students_reconciliation_response").map((item, index) => {
          if (typeof item !== "number" || Number.isNaN(item)) {
            throw new Error(`current_students_reconciliation_response.grade_levels[${index}] must be a number`);
          }
          return item;
        });
  return {
    module,
    school_year: readNumber(record, "school_year", "current_students_reconciliation_response"),
    grade_levels: gradeLevels,
    operation_type: parseCurrentStudentOperationType(
      readString(record, "operation_type", "current_students_reconciliation_response"),
      "current_students_reconciliation_response",
    ),
    roster_excel_path: readString(record, "roster_excel_path", "current_students_reconciliation_response"),
    thai_id_csv_path: readOptionalString(record, "thai_id_csv_path", "current_students_reconciliation_response"),
    ocr_markdown_paths: readStringArray(record, "ocr_markdown_paths", "current_students_reconciliation_response"),
    summary: parseCurrentStudentsSummary(record.summary),
    records: readArray(record, "records", "current_students_reconciliation_response").map(parseCurrentStudentRecord),
    review_queue: readArray(record, "review_queue", "current_students_reconciliation_response").map(
      parseCurrentStudentRecord,
    ),
    warnings: readArray(record, "warnings", "current_students_reconciliation_response").map(
      parseCurrentStudentsWarning,
    ),
  };
}

export function parseExportCurrentStudentsBlankFormResponse(value: unknown): ExportCurrentStudentsBlankFormResponse {
  const record = asRecord(value, "export_current_students_blank_form_response");
  const module = readString(record, "module", "export_current_students_blank_form_response");
  if (module !== "currentStudents") {
    throw new Error("export_current_students_blank_form_response.module must be currentStudents");
  }
  return {
    module,
    output_path: readString(record, "output_path", "export_current_students_blank_form_response"),
    field_count: readNumber(record, "field_count", "export_current_students_blank_form_response"),
    required_fields: readStringArray(record, "required_fields", "export_current_students_blank_form_response"),
  };
}

export function parsePreviewDmcFormJsonResponse(value: unknown): PreviewDmcFormJsonResponse {
  const record = asRecord(value, "preview_dmc_form_json_response");
  const module = readString(record, "module", "preview_dmc_form_json_response");
  if (module !== "formConverter") {
    throw new Error("preview_dmc_form_json_response.module must be formConverter");
  }
  const schemaVersion = readString(record, "schema_version", "preview_dmc_form_json_response");
  if (schemaVersion !== "dmc_form_json.v1") {
    throw new Error("preview_dmc_form_json_response.schema_version must be dmc_form_json.v1");
  }
  const gradeLevelsValue = record.grade_levels;
  const gradeLevels =
    gradeLevelsValue === null || gradeLevelsValue === undefined
      ? null
      : readArray(record, "grade_levels", "preview_dmc_form_json_response").map((item, index) => {
          if (typeof item !== "number" || Number.isNaN(item)) {
            throw new Error(`preview_dmc_form_json_response.grade_levels[${index}] must be a number`);
          }
          return item;
        });
  return {
    module,
    schema_version: schemaVersion,
    generated_at: readString(record, "generated_at", "preview_dmc_form_json_response"),
    school_year: readNumber(record, "school_year", "preview_dmc_form_json_response"),
    grade_levels: gradeLevels,
    records_previewed: readNumber(record, "records_previewed", "preview_dmc_form_json_response"),
    field_labels: parseStringMap(record.field_labels, "preview_dmc_form_json_response.field_labels"),
    summary: parseCurrentStudentsSummary(record.summary),
    warnings: readArray(record, "warnings", "preview_dmc_form_json_response").map(parseCurrentStudentsWarning),
    conflicts: readArray(record, "conflicts", "preview_dmc_form_json_response").map(parseCurrentStudentsFieldConflict),
    records: readArray(record, "records", "preview_dmc_form_json_response").map(parseDmcFormJsonRecord),
  };
}

export function parseExportDmcFormJsonResponse(value: unknown): ExportDmcFormJsonResponse {
  const record = asRecord(value, "export_dmc_form_json_response");
  const module = readString(record, "module", "export_dmc_form_json_response");
  if (module !== "formConverter") {
    throw new Error("export_dmc_form_json_response.module must be formConverter");
  }
  const schemaVersion = readString(record, "schema_version", "export_dmc_form_json_response");
  if (schemaVersion !== "dmc_form_json.v1") {
    throw new Error("export_dmc_form_json_response.schema_version must be dmc_form_json.v1");
  }
  const gradeLevelsValue = record.grade_levels;
  const gradeLevels =
    gradeLevelsValue === null || gradeLevelsValue === undefined
      ? null
      : readArray(record, "grade_levels", "export_dmc_form_json_response").map((item, index) => {
          if (typeof item !== "number" || Number.isNaN(item)) {
            throw new Error(`export_dmc_form_json_response.grade_levels[${index}] must be a number`);
          }
          return item;
        });
  return {
    module,
    schema_version: schemaVersion,
    generated_at: readString(record, "generated_at", "export_dmc_form_json_response"),
    output_path: readString(record, "output_path", "export_dmc_form_json_response"),
    school_year: readNumber(record, "school_year", "export_dmc_form_json_response"),
    grade_levels: gradeLevels,
    records_exported: readNumber(record, "records_exported", "export_dmc_form_json_response"),
    field_labels: parseStringMap(record.field_labels, "export_dmc_form_json_response.field_labels"),
    summary: parseCurrentStudentsSummary(record.summary),
    warnings: readArray(record, "warnings", "export_dmc_form_json_response").map(parseCurrentStudentsWarning),
    conflicts: readArray(record, "conflicts", "export_dmc_form_json_response").map(parseCurrentStudentsFieldConflict),
    records: readArray(record, "records", "export_dmc_form_json_response").map(parseDmcFormJsonRecord),
  };
}

export function parseExportCurrentStudentsImportExcelResponse(
  value: unknown,
): ExportCurrentStudentsImportExcelResponse {
  const record = asRecord(value, "export_current_students_import_excel_response");
  const module = readString(record, "module", "export_current_students_import_excel_response");
  if (module !== "formConverter") {
    throw new Error("export_current_students_import_excel_response.module must be formConverter");
  }
  return {
    module,
    output_path: readString(record, "output_path", "export_current_students_import_excel_response"),
    school_year: readNumber(record, "school_year", "export_current_students_import_excel_response"),
    operation_type: parseCurrentStudentOperationType(
      readString(record, "operation_type", "export_current_students_import_excel_response"),
      "export_current_students_import_excel_response",
    ),
    rows_exported: readNumber(record, "rows_exported", "export_current_students_import_excel_response"),
    summary: parseCurrentStudentsSummary(record.summary),
    warnings: readArray(record, "warnings", "export_current_students_import_excel_response").map(
      parseCurrentStudentsWarning,
    ),
    conflicts: readArray(record, "conflicts", "export_current_students_import_excel_response").map(
      parseCurrentStudentsFieldConflict,
    ),
  };
}

function parseCurrentStudentsImportRowStatus(value: string, context: string): CurrentStudentsImportRowStatus {
  if (value !== "ready" && value !== "needs_review" && value !== "invalid") {
    throw new Error(`${context}.status is invalid`);
  }
  return value;
}

function parseCurrentStudentsImportRowPreview(value: unknown, index: number): CurrentStudentsImportRowPreview {
  const context = `current_students_import_row[${index}]`;
  const record = asRecord(value, context);
  return {
    row_index: readNumber(record, "row_index", context),
    status: parseCurrentStudentsImportRowStatus(readString(record, "status", context), context),
    operation_type: readOptionalString(record, "operation_type", context),
    student_no: readOptionalString(record, "student_no", context),
    citizen_id: readOptionalString(record, "citizen_id", context),
    full_name: readString(record, "full_name", context),
    issues: readStringArray(record, "issues", context),
  };
}

function parseCurrentStudentsImportSummary(value: unknown): CurrentStudentsImportSummary {
  const record = asRecord(value, "current_students_import_summary");
  return {
    rows_total: readNumber(record, "rows_total", "current_students_import_summary"),
    ready_rows: readNumber(record, "ready_rows", "current_students_import_summary"),
    needs_review_rows: readNumber(record, "needs_review_rows", "current_students_import_summary"),
    invalid_rows: readNumber(record, "invalid_rows", "current_students_import_summary"),
    duplicate_citizen_ids: readNumber(record, "duplicate_citizen_ids", "current_students_import_summary"),
    warnings_total: readNumber(record, "warnings_total", "current_students_import_summary"),
  };
}

export function parseValidateCurrentStudentsImportFormResponse(
  value: unknown,
): ValidateCurrentStudentsImportFormResponse {
  const record = asRecord(value, "validate_current_students_import_form_response");
  const module = readString(record, "module", "validate_current_students_import_form_response");
  if (module !== "currentStudents") {
    throw new Error("validate_current_students_import_form_response.module must be currentStudents");
  }
  return {
    module,
    excel_path: readString(record, "excel_path", "validate_current_students_import_form_response"),
    summary: parseCurrentStudentsImportSummary(record.summary),
    preview: readArray(record, "preview", "validate_current_students_import_form_response").map(
      parseCurrentStudentsImportRowPreview,
    ),
    warnings: readArray(record, "warnings", "validate_current_students_import_form_response").map(
      parseCurrentStudentsWarning,
    ),
  };
}

function readStringArray(record: UnknownRecord, key: string, context: string): string[] {
  return readArray(record, key, context).map((item, index) => {
    if (typeof item !== "string") {
      throw new Error(`${context}.${key}[${index}] must be a string`);
    }
    return item;
  });
}

function parseEvidenceMappingStatus(value: string, context: string): EvidenceMappingStatus {
  if (value !== "accepted" && value !== "suggested" && value !== "rejected" && value !== "needs_review") {
    throw new Error(`${context}.status is invalid`);
  }
  return value;
}

function parseReadinessRequirementStatus(value: string, context: string): ReadinessRequirementStatus {
  if (value !== "complete" && value !== "partial" && value !== "missing" && value !== "needs_review") {
    throw new Error(`${context}.status is invalid`);
  }
  return value;
}

function parseReadinessPriority(value: string, context: string): ReadinessPriority {
  if (value !== "high" && value !== "medium" && value !== "low") {
    throw new Error(`${context}.priority is invalid`);
  }
  return value;
}

function parsePsarUploadedFile(value: unknown, index: number): PsarUploadedFile {
  const context = `psar_uploaded_file[${index}]`;
  const record = asRecord(value, context);
  return {
    file_id: readString(record, "file_id", context),
    file_name: readString(record, "file_name", context),
    file_path: readString(record, "file_path", context),
    file_type: readString(record, "file_type", context),
    extracted_summary: readString(record, "extracted_summary", context),
    created_at: readString(record, "created_at", context),
    updated_at: readString(record, "updated_at", context),
  };
}

function parsePsarEvidenceMapping(value: unknown, index: number): PsarEvidenceMapping {
  const context = `psar_evidence_mapping[${index}]`;
  const record = asRecord(value, context);
  return {
    requirement_id: readString(record, "requirement_id", context),
    evidence_type: readString(record, "evidence_type", context),
    source_file_id: readString(record, "source_file_id", context),
    source_file_name: readString(record, "source_file_name", context),
    extracted_summary: readString(record, "extracted_summary", context),
    confidence_score: readNumber(record, "confidence_score", context),
    page_number: readOptionalNumber(record, "page_number", context),
    location: readOptionalString(record, "location", context),
    status: parseEvidenceMappingStatus(readString(record, "status", context), context),
    created_at: readString(record, "created_at", context),
    updated_at: readString(record, "updated_at", context),
  };
}

function parsePsarReadinessRequirement(value: unknown, index: number): PsarReadinessRequirement {
  const context = `psar_readiness_requirement[${index}]`;
  const record = asRecord(value, context);
  return {
    requirement_id: readString(record, "requirement_id", context),
    requirement_title: readString(record, "requirement_title", context),
    category: readString(record, "category", context),
    description: readString(record, "description", context),
    required_evidence: readStringArray(record, "required_evidence", context),
    optional_evidence: readStringArray(record, "optional_evidence", context),
    weight: readNumber(record, "weight", context),
    minimum_required_items: readNumber(record, "minimum_required_items", context),
    status: parseReadinessRequirementStatus(readString(record, "status", context), context),
    completion_score: readNumber(record, "completion_score", context),
    missing_evidence: readStringArray(record, "missing_evidence", context),
    found_evidence: readArray(record, "found_evidence", context).map(parsePsarEvidenceMapping),
    recommendation: readString(record, "recommendation", context),
    priority: parseReadinessPriority(readString(record, "priority", context), context),
  };
}

function parsePsarReadinessSection(value: unknown, index: number): PsarReadinessSection {
  const context = `psar_readiness_section[${index}]`;
  const record = asRecord(value, context);
  return {
    section_id: readString(record, "section_id", context),
    section_title: readString(record, "section_title", context),
    completion_score: readNumber(record, "completion_score", context),
    complete_count: readNumber(record, "complete_count", context),
    partial_count: readNumber(record, "partial_count", context),
    missing_count: readNumber(record, "missing_count", context),
    needs_review_count: readNumber(record, "needs_review_count", context),
    requirements: readArray(record, "requirements", context).map(parsePsarReadinessRequirement),
  };
}

function parsePsarMissingEvidenceRecommendation(
  value: unknown,
  index: number,
): PsarMissingEvidenceRecommendation {
  const context = `psar_missing_evidence_recommendation[${index}]`;
  const record = asRecord(value, context);
  return {
    evidence_name: readString(record, "evidence_name", context),
    requirement_id: readString(record, "requirement_id", context),
    requirement_title: readString(record, "requirement_title", context),
    section_id: readString(record, "section_id", context),
    section_title: readString(record, "section_title", context),
    why_needed: readString(record, "why_needed", context),
    priority: parseReadinessPriority(readString(record, "priority", context), context),
    suggested_file_types: readStringArray(record, "suggested_file_types", context),
  };
}

export function parsePsarReadinessResponse(value: unknown): PsarReadinessResponse {
  const record = asRecord(value, "psar_readiness_response");
  return {
    project_id: readString(record, "project_id", "psar_readiness_response"),
    overall_completion_score: readNumber(record, "overall_completion_score", "psar_readiness_response"),
    warning_threshold: readNumber(record, "warning_threshold", "psar_readiness_response"),
    confidence_threshold: readNumber(record, "confidence_threshold", "psar_readiness_response"),
    total_requirements: readNumber(record, "total_requirements", "psar_readiness_response"),
    complete_count: readNumber(record, "complete_count", "psar_readiness_response"),
    partial_count: readNumber(record, "partial_count", "psar_readiness_response"),
    missing_count: readNumber(record, "missing_count", "psar_readiness_response"),
    needs_review_count: readNumber(record, "needs_review_count", "psar_readiness_response"),
    sections: readArray(record, "sections", "psar_readiness_response").map(parsePsarReadinessSection),
    missing_evidence_recommendations: readArray(
      record,
      "missing_evidence_recommendations",
      "psar_readiness_response",
    ).map(parsePsarMissingEvidenceRecommendation),
    mapped_files: readArray(record, "mapped_files", "psar_readiness_response").map(parsePsarEvidenceMapping),
    uploaded_files: readArray(record, "uploaded_files", "psar_readiness_response").map(parsePsarUploadedFile),
  };
}

export function parseAddPsarEvidenceResponse(value: unknown): AddPsarEvidenceResponse {
  const record = asRecord(value, "add_psar_evidence_response");
  return {
    project_id: readString(record, "project_id", "add_psar_evidence_response"),
    file: parsePsarUploadedFile(record.file, 0),
    mappings: readArray(record, "mappings", "add_psar_evidence_response").map(parsePsarEvidenceMapping),
    readiness: parsePsarReadinessResponse(record.readiness),
  };
}

export function parseGeneratePsarReportResponse(value: unknown): GeneratePsarReportResponse {
  const record = asRecord(value, "generate_psar_report_response");
  return {
    project_id: readString(record, "project_id", "generate_psar_report_response"),
    report_path: readString(record, "report_path", "generate_psar_report_response"),
    readiness: parsePsarReadinessResponse(record.readiness),
    generated_at: readString(record, "generated_at", "generate_psar_report_response"),
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

export function parseArchiveJobsResponse(value: unknown): ArchiveJobsResponse {
  const record = asRecord(value, "archive_jobs_response");
  return {
    archived: readNumber(record, "archived", "archive_jobs_response"),
    kept: readNumber(record, "kept", "archive_jobs_response"),
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
