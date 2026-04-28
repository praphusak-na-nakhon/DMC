import { invoke } from "@tauri-apps/api/core";
import { listen, type UnlistenFn } from "@tauri-apps/api/event";
import type {
  AvailableUpdate,
  ArchiveJobsResponse,
  BackupCreateResponse,
  BrowserRuntimeStatus,
  DatabaseStatus,
  JobStatusSnapshot,
  LicenseStatus,
  ListJobsResponse,
  ModuleConfigStatus,
  RestoreBackupResponse,
  SidecarEvent,
  UpdaterEvent,
  UpdaterStatus,
  StartJobResponse,
  ValidateExcelResponse,
} from "../types/contracts";
import {
  parseAvailableUpdate,
  parseArchiveJobsResponse,
  parseBackupCreateResponse,
  parseBrowserRuntimeStatus,
  parseDatabaseStatus,
  parseJobActionResponse,
  parseJobStatusSnapshot,
  parseLicenseStatus,
  parseListJobsResponse,
  parseModuleConfigStatus,
  parseRestoreBackupResponse,
  parseResumeExistingJobResponse,
  parseSidecarEvent,
  parseStartJobResponse,
  parseUpdaterEvent,
  parseUpdaterStatus,
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
  return invoke<T>("rpc_request", {
    requestJson: JSON.stringify(request),
  });
}

export async function initializeSidecar(): Promise<void> {
  await invoke("initialize_sidecar");
}

export async function shutdownSidecar(): Promise<void> {
  await invoke("shutdown_sidecar");
}

export async function openExcelDialog(): Promise<string | null> {
  return invoke<string | null>("open_excel_dialog");
}

export async function openBackupArchiveDialog(): Promise<string | null> {
  return invoke<string | null>("open_backup_archive_dialog");
}

export async function saveBackupDialog(defaultName?: string): Promise<string | null> {
  return invoke<string | null>("save_backup_dialog", { defaultName });
}

export async function saveDiagnosticsDialog(defaultName?: string): Promise<string | null> {
  return invoke<string | null>("save_diagnostics_dialog", { defaultName });
}

export async function saveTemplateDialog(defaultName?: string): Promise<string | null> {
  return invoke<string | null>("save_template_dialog", { defaultName });
}

export async function copyTemplateFile(destinationPath: string): Promise<string> {
  return invoke<string>("copy_template_file", { destinationPath });
}

export async function writeTextFile(path: string, contents: string): Promise<void> {
  await invoke("write_text_file", { path, contents });
}

export async function revealPath(path: string): Promise<void> {
  await invoke("reveal_path", { path });
}

export async function getUpdaterStatus(): Promise<UpdaterStatus> {
  const result = await invoke<unknown>("get_updater_status");
  return parseUpdaterStatus(result);
}

export async function checkForAppUpdate(): Promise<AvailableUpdate | null> {
  const result = await invoke<unknown>("check_for_app_update");
  return parseAvailableUpdate(result);
}

export async function installAppUpdate(): Promise<void> {
  await invoke("install_app_update");
}

export async function validateExcel(
  path: string,
  module: "graduation" = "graduation",
): Promise<ValidateExcelResponse> {
  const result = await sidecarRequest<unknown>("validate_excel", { path, module });
  return parseValidateExcelResponse(result);
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

export async function getLicenseStatus(): Promise<LicenseStatus> {
  const result = await sidecarRequest<unknown>("get_license_status", {});
  return parseLicenseStatus(result);
}

export async function activateLicense(input: {
  licenseKey: string;
  deviceName: string;
  appVersion: string;
}): Promise<LicenseStatus> {
  const result = await sidecarRequest<unknown>("activate_license", {
    license_key: input.licenseKey,
    device_name: input.deviceName,
    app_version: input.appVersion,
  });
  return parseLicenseStatus(result);
}

export async function refreshLicenseStatus(): Promise<LicenseStatus> {
  const result = await sidecarRequest<unknown>("refresh_license_status", {});
  return parseLicenseStatus(result);
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
}): Promise<StartJobResponse> {
  const result = await sidecarRequest<unknown>("start_job", {
    job_id: input.jobId,
    module: "graduation",
    excel_path: input.excelPath,
    options: {
      dry_run: input.dryRun,
      stop_on_review: input.stopOnReview,
      min_score: input.minScore,
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
