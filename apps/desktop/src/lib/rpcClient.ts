import { invoke } from "@tauri-apps/api/core";
import { listen, type UnlistenFn } from "@tauri-apps/api/event";
import type {
  AvailableUpdate,
  AccountStatus,
  AksonOcrDmcFormResponse,
  ArchiveJobsResponse,
  BackupCreateResponse,
  BrowserRuntimeStatus,
  CurrentStudentOperationType,
  ExportDmcFormJsonResponse,
  ExportCurrentStudentsBlankFormResponse,
  ExportCurrentStudentsImportExcelResponse,
  PreviewDmcFormJsonResponse,
  CurrentStudentsReconciliationResponse,
  DatabaseStatus,
  JobStatusSnapshot,
  ListJobsResponse,
  ModuleCatalogResponse,
  ModuleConfigStatus,
  RestoreBackupResponse,
  SidecarEvent,
  UpdaterEvent,
  UpdaterStatus,
  StartJobResponse,
  ExportStudentBasicInfoFormResponse,
  AddPsarEvidenceResponse,
  GeneratePsarReportResponse,
  PsarReadinessResponse,
  ValidateCurrentStudentsImportFormResponse,
  ValidateExcelResponse,
} from "../types/contracts";
import {
  parseAddPsarEvidenceResponse,
  parseAksonOcrDmcFormResponse,
  parseAvailableUpdate,
  parseAccountStatus,
  parseArchiveJobsResponse,
  parseBackupCreateResponse,
  parseBrowserRuntimeStatus,
  parseExportDmcFormJsonResponse,
  parseExportCurrentStudentsBlankFormResponse,
  parseExportCurrentStudentsImportExcelResponse,
  parsePreviewDmcFormJsonResponse,
  parseCurrentStudentsReconciliationResponse,
  parseDatabaseStatus,
  parseExportStudentBasicInfoFormResponse,
  parseGeneratePsarReportResponse,
  parseJobActionResponse,
  parseJobStatusSnapshot,
  parseListJobsResponse,
  parseModuleCatalogResponse,
  parseModuleConfigStatus,
  parsePsarReadinessResponse,
  parseRestoreBackupResponse,
  parseResumeExistingJobResponse,
  parseSidecarEvent,
  parseStartJobResponse,
  parseUpdaterEvent,
  parseUpdaterStatus,
  parseValidateCurrentStudentsImportFormResponse,
  parseValidateExcelResponse,
} from "../types/contracts";

export type JsonRpcRequest = {
  jsonrpc: "2.0";
  id: string;
  method: string;
  params: Record<string, unknown>;
};

export type JsonRpcSuccess<T> = {
  jsonrpc: "2.0";
  id: string;
  result: T;
};

export type JsonRpcFailure = {
  jsonrpc: "2.0";
  id: string | null;
  error: {
    code: string;
    message: string;
    details: Record<string, unknown>;
  };
};

let requestCounter = 0;

type TauriWindow = Window &
  typeof globalThis & {
    __TAURI_INTERNALS__?: unknown;
  };

export function isDesktopRuntimeAvailable(): boolean {
  if (typeof window === "undefined") {
    return false;
  }
  return Boolean((window as TauriWindow).__TAURI_INTERNALS__);
}

function desktopRuntimeUnavailableError(command: string): Error {
  return new Error(
    `DESKTOP_RUNTIME_UNAVAILABLE: Tauri IPC is not available for command "${command}". Open this feature in the DMC Assistant desktop window, not browser preview/localhost.`,
  );
}

async function desktopInvoke<T>(command: string, args?: Record<string, unknown>): Promise<T> {
  if (!isDesktopRuntimeAvailable()) {
    throw desktopRuntimeUnavailableError(command);
  }
  return invoke<T>(command, args);
}

function buildRequest(method: string, params: Record<string, unknown>): JsonRpcRequest {
  requestCounter += 1;
  return {
    jsonrpc: "2.0",
    id: `${method}-${requestCounter}`,
    method,
    params,
  };
}

async function sidecarRequest<T>(
  method: string,
  params: Record<string, unknown>,
): Promise<T> {
  const request = buildRequest(method, params);
  return desktopInvoke<T>("rpc_request", {
    requestJson: JSON.stringify(request),
  });
}

export async function initializeSidecar(): Promise<void> {
  await desktopInvoke("initialize_sidecar");
}

export async function shutdownSidecar(): Promise<void> {
  await desktopInvoke("shutdown_sidecar");
}

export async function openExcelDialog(): Promise<string | null> {
  return desktopInvoke<string | null>("open_excel_dialog");
}

export async function openCurrentStudentImportDialog(): Promise<string | null> {
  return desktopInvoke<string | null>("open_current_student_import_dialog");
}

export async function openCsvDialog(): Promise<string | null> {
  return desktopInvoke<string | null>("open_csv_dialog");
}

export async function openMarkdownDialog(): Promise<string | null> {
  return desktopInvoke<string | null>("open_markdown_dialog");
}

export async function openOcrSourceDialog(): Promise<string | null> {
  return desktopInvoke<string | null>("open_ocr_source_dialog");
}

export async function openEvidenceDialog(): Promise<string | null> {
  return desktopInvoke<string | null>("open_evidence_dialog");
}

export async function openBackupArchiveDialog(): Promise<string | null> {
  return desktopInvoke<string | null>("open_backup_archive_dialog");
}

export async function saveBackupDialog(defaultName?: string): Promise<string | null> {
  return desktopInvoke<string | null>("save_backup_dialog", { defaultName });
}

export async function saveDiagnosticsDialog(defaultName?: string): Promise<string | null> {
  return desktopInvoke<string | null>("save_diagnostics_dialog", { defaultName });
}

export async function saveTemplateDialog(defaultName?: string): Promise<string | null> {
  return desktopInvoke<string | null>("save_template_dialog", { defaultName });
}

export async function copyTemplateFile(destinationPath: string): Promise<string> {
  return desktopInvoke<string>("copy_template_file", { destinationPath });
}

export async function writeTextFile(path: string, contents: string): Promise<void> {
  await desktopInvoke("write_text_file", { path, contents });
}

export async function revealPath(path: string): Promise<void> {
  await desktopInvoke("reveal_path", { path });
}

export async function getUpdaterStatus(): Promise<UpdaterStatus> {
  const result = await desktopInvoke<unknown>("get_updater_status");
  return parseUpdaterStatus(result);
}

export async function checkForAppUpdate(): Promise<AvailableUpdate | null> {
  const result = await desktopInvoke<unknown>("check_for_app_update");
  return parseAvailableUpdate(result);
}

export async function installAppUpdate(): Promise<void> {
  await desktopInvoke("install_app_update");
}

export async function validateExcel(
  path: string,
  module: "graduation" = "graduation",
): Promise<ValidateExcelResponse> {
  const result = await sidecarRequest<unknown>("validate_excel", { path, module });
  return parseValidateExcelResponse(result);
}

export async function exportStudentBasicInfoForm(
  excelPath: string,
): Promise<ExportStudentBasicInfoFormResponse> {
  const result = await sidecarRequest<unknown>("export_student_basic_info_form", {
    excel_path: excelPath,
  });
  return parseExportStudentBasicInfoFormResponse(result);
}

export async function validateCurrentStudentSources(input: {
  rosterExcelPath: string;
  thaiIdCsvPath: string | null;
  ocrMarkdownPaths: string[];
  civilRegistrationMarkdownPaths?: string[];
  schoolYear: number;
  gradeLevels: number[] | null;
  operationType: CurrentStudentOperationType;
}): Promise<CurrentStudentsReconciliationResponse> {
  const result = await sidecarRequest<unknown>("validate_current_student_sources", {
    roster_excel_path: input.rosterExcelPath,
    thai_id_csv_path: input.thaiIdCsvPath,
    ocr_markdown_paths: input.ocrMarkdownPaths,
    civil_registration_markdown_paths: input.civilRegistrationMarkdownPaths ?? [],
    school_year: input.schoolYear,
    grade_levels: input.gradeLevels,
    operation_type: input.operationType,
  });
  return parseCurrentStudentsReconciliationResponse(result);
}

export async function exportCurrentStudentImportExcel(input: {
  rosterExcelPath: string;
  thaiIdCsvPath: string | null;
  ocrMarkdownPaths: string[];
  civilRegistrationMarkdownPaths?: string[];
  schoolYear: number;
  gradeLevels: number[] | null;
  operationType: CurrentStudentOperationType;
  outputPath: string | null;
}): Promise<ExportCurrentStudentsImportExcelResponse> {
  const result = await sidecarRequest<unknown>("export_current_student_import_excel", {
    roster_excel_path: input.rosterExcelPath,
    thai_id_csv_path: input.thaiIdCsvPath,
    ocr_markdown_paths: input.ocrMarkdownPaths,
    civil_registration_markdown_paths: input.civilRegistrationMarkdownPaths ?? [],
    school_year: input.schoolYear,
    grade_levels: input.gradeLevels,
    operation_type: input.operationType,
    output_path: input.outputPath,
  });
  return parseExportCurrentStudentsImportExcelResponse(result);
}

export async function previewDmcFormJson(input: {
  rosterExcelPath: string;
  thaiIdCsvPath: string | null;
  ocrMarkdownPaths: string[];
  civilRegistrationMarkdownPaths?: string[];
  schoolYear: number;
  gradeLevels: number[] | null;
}): Promise<PreviewDmcFormJsonResponse> {
  const result = await sidecarRequest<unknown>("preview_dmc_form_json", {
    roster_excel_path: input.rosterExcelPath,
    thai_id_csv_path: input.thaiIdCsvPath,
    ocr_markdown_paths: input.ocrMarkdownPaths,
    civil_registration_markdown_paths: input.civilRegistrationMarkdownPaths ?? [],
    school_year: input.schoolYear,
    grade_levels: input.gradeLevels,
  });
  return parsePreviewDmcFormJsonResponse(result);
}

export async function exportDmcFormJson(input: {
  rosterExcelPath: string;
  thaiIdCsvPath: string | null;
  ocrMarkdownPaths: string[];
  civilRegistrationMarkdownPaths?: string[];
  schoolYear: number;
  gradeLevels: number[] | null;
  outputPath: string | null;
}): Promise<ExportDmcFormJsonResponse> {
  const result = await sidecarRequest<unknown>("export_dmc_form_json", {
    roster_excel_path: input.rosterExcelPath,
    thai_id_csv_path: input.thaiIdCsvPath,
    ocr_markdown_paths: input.ocrMarkdownPaths,
    civil_registration_markdown_paths: input.civilRegistrationMarkdownPaths ?? [],
    school_year: input.schoolYear,
    grade_levels: input.gradeLevels,
    output_path: input.outputPath,
  });
  return parseExportDmcFormJsonResponse(result);
}

export async function ocrDmcFormWithAkson(input: {
  sourcePath: string;
  apiKey: string | null;
  model?: "AksonOCR-1.0";
  forceRefresh?: boolean;
}): Promise<AksonOcrDmcFormResponse> {
  const result = await sidecarRequest<unknown>("ocr_dmc_form_with_akson", {
    source_path: input.sourcePath,
    api_key: input.apiKey,
    model: input.model ?? "AksonOCR-1.0",
    force_refresh: input.forceRefresh ?? false,
  });
  return parseAksonOcrDmcFormResponse(result);
}

export async function exportCurrentStudentBlankForm(
  outputPath: string,
): Promise<ExportCurrentStudentsBlankFormResponse> {
  const result = await sidecarRequest<unknown>("export_current_student_blank_form", {
    output_path: outputPath,
  });
  return parseExportCurrentStudentsBlankFormResponse(result);
}

export async function validateCurrentStudentImportForm(
  excelPath: string,
): Promise<ValidateCurrentStudentsImportFormResponse> {
  const result = await sidecarRequest<unknown>("validate_current_student_import_form", {
    excel_path: excelPath,
  });
  return parseValidateCurrentStudentsImportFormResponse(result);
}

export async function getPsarReadiness(projectId = "default"): Promise<PsarReadinessResponse> {
  const result = await sidecarRequest<unknown>("get_psar_readiness", {
    project_id: projectId,
  });
  return parsePsarReadinessResponse(result);
}

export async function addPsarEvidence(
  projectId: string,
  filePath: string,
): Promise<AddPsarEvidenceResponse> {
  const result = await sidecarRequest<unknown>("add_psar_evidence", {
    project_id: projectId,
    file_path: filePath,
  });
  return parseAddPsarEvidenceResponse(result);
}

export async function generatePsarReport(projectId: string): Promise<GeneratePsarReportResponse> {
  const result = await sidecarRequest<unknown>("generate_psar_report", {
    project_id: projectId,
  });
  return parseGeneratePsarReportResponse(result);
}

export async function getModuleConfigStatus(
  module: "graduation" = "graduation",
): Promise<ModuleConfigStatus> {
  const result = await sidecarRequest<unknown>("get_module_config_status", { module });
  return parseModuleConfigStatus(result);
}

export async function syncModuleConfig(
  module: "graduation" = "graduation",
): Promise<ModuleConfigStatus> {
  const result = await sidecarRequest<unknown>("sync_module_config", { module });
  return parseModuleConfigStatus(result);
}

export async function signIn(input: {
  email: string;
  password: string;
  deviceName: string;
  appVersion: string;
}): Promise<AccountStatus> {
  const result = await sidecarRequest<unknown>("sign_in", {
    email: input.email,
    password: input.password,
    device_name: input.deviceName,
    app_version: input.appVersion,
  });
  return parseAccountStatus(result);
}

export async function signOut(): Promise<AccountStatus> {
  const result = await sidecarRequest<unknown>("sign_out", {});
  return parseAccountStatus(result);
}

export async function getAccountStatus(): Promise<AccountStatus> {
  const result = await sidecarRequest<unknown>("get_account_status", {});
  return parseAccountStatus(result);
}

export async function refreshWallet(): Promise<AccountStatus> {
  const result = await sidecarRequest<unknown>("refresh_wallet", {});
  return parseAccountStatus(result);
}

export async function getModuleCatalog(): Promise<ModuleCatalogResponse> {
  const result = await sidecarRequest<unknown>("get_module_catalog", {});
  return parseModuleCatalogResponse(result);
}

export async function getBrowserRuntimeStatus(): Promise<BrowserRuntimeStatus> {
  const result = await sidecarRequest<unknown>("get_browser_runtime_status", {});
  return parseBrowserRuntimeStatus(result);
}

export async function getDatabaseStatus(): Promise<DatabaseStatus> {
  const result = await sidecarRequest<unknown>("get_database_status", {});
  return parseDatabaseStatus(result);
}

export async function createBackup(path?: string): Promise<BackupCreateResponse> {
  const result = await sidecarRequest<unknown>("create_backup", path ? { path } : {});
  return parseBackupCreateResponse(result);
}

export async function restoreBackup(path: string): Promise<RestoreBackupResponse> {
  const result = await sidecarRequest<unknown>("restore_backup", { path });
  return parseRestoreBackupResponse(result);
}

export async function bootstrapBrowserRuntime(): Promise<BrowserRuntimeStatus> {
  const result = await sidecarRequest<unknown>("bootstrap_browser_runtime", {});
  return parseBrowserRuntimeStatus(result);
}

export async function startGraduationJob(input: {
  jobId: string;
  excelPath: string;
  dryRun: boolean;
  stopOnReview: boolean;
  minScore: number;
  estimatedCredits: number;
}): Promise<StartJobResponse> {
  const result = await sidecarRequest<unknown>("start_job", {
    job_id: input.jobId,
    module: "graduation",
    excel_path: input.excelPath,
    options: {
      dry_run: input.dryRun,
      stop_on_review: input.stopOnReview,
      min_score: input.minScore,
      estimated_credits: input.estimatedCredits,
    },
  });
  return parseStartJobResponse(result);
}

export async function startCurrentStudentsImportJob(input: {
  jobId: string;
  jsonPath: string;
  dryRun: boolean;
  estimatedCredits: number;
}): Promise<StartJobResponse> {
  const result = await sidecarRequest<unknown>("start_job", {
    job_id: input.jobId,
    module: "currentStudents",
    excel_path: input.jsonPath,
    options: {
      dry_run: input.dryRun,
      estimated_credits: input.estimatedCredits,
    },
  });
  return parseStartJobResponse(result);
}

export async function getJobStatus(jobId: string): Promise<JobStatusSnapshot> {
  const result = await sidecarRequest<unknown>("get_job_status", { job_id: jobId });
  return parseJobStatusSnapshot(result);
}

export async function listJobs(limit = 20): Promise<ListJobsResponse> {
  const result = await sidecarRequest<unknown>("list_jobs", { limit });
  return parseListJobsResponse(result);
}

export async function archiveOldJobs(keepLatest = 20): Promise<ArchiveJobsResponse> {
  const result = await sidecarRequest<unknown>("archive_old_jobs", { keep_latest: keepLatest });
  return parseArchiveJobsResponse(result);
}

export async function pauseJob(jobId: string): Promise<{ job_id: string; status: string }> {
  const result = await sidecarRequest<unknown>("pause_job", { job_id: jobId });
  return parseJobActionResponse(result);
}

export async function resumeJob(jobId: string): Promise<{ job_id: string; status: string }> {
  const result = await sidecarRequest<unknown>("resume_job", { job_id: jobId });
  return parseJobActionResponse(result);
}

export async function resumeExistingJob(
  jobId: string,
): Promise<{ job_id: string; status: string; accepted: boolean }> {
  const result = await sidecarRequest<unknown>(
    "resume_existing_job",
    { job_id: jobId },
  );
  return parseResumeExistingJobResponse(result);
}

export async function cancelJob(jobId: string): Promise<{ job_id: string; status: string }> {
  const result = await sidecarRequest<unknown>("cancel_job", { job_id: jobId });
  return parseJobActionResponse(result);
}

export async function listenSidecarEvents(
  callback: (event: SidecarEvent) => void,
): Promise<UnlistenFn> {
  return listen<unknown>("sidecar-event", (event) => {
    try {
      callback(parseSidecarEvent(event.payload));
    } catch (error) {
      callback({
        type: "sidecar_stderr",
        message: error instanceof Error ? error.message : String(error),
      });
    }
  });
}

export async function listenUpdaterEvents(
  callback: (event: UpdaterEvent) => void,
): Promise<UnlistenFn> {
  return listen<unknown>("updater-event", (event) => {
    callback(parseUpdaterEvent(event.payload));
  });
}
