import { invoke } from "@tauri-apps/api/core";
import { listen, type UnlistenFn } from "@tauri-apps/api/event";
import type {
  JobStatusSnapshot,
  ListJobsResponse,
  SidecarEvent,
  StartJobResponse,
  ValidateExcelResponse,
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

export async function validateExcel(
  path: string,
  module: "graduation" = "graduation",
): Promise<ValidateExcelResponse> {
  return sidecarRequest<ValidateExcelResponse>("validate_excel", { path, module });
}

export async function startGraduationJob(input: {
  jobId: string;
  excelPath: string;
  dryRun: boolean;
  stopOnReview: boolean;
  minScore: number;
}): Promise<StartJobResponse> {
  return sidecarRequest<StartJobResponse>("start_job", {
    job_id: input.jobId,
    module: "graduation",
    excel_path: input.excelPath,
    options: {
      dry_run: input.dryRun,
      stop_on_review: input.stopOnReview,
      min_score: input.minScore,
    },
  });
}

export async function getJobStatus(jobId: string): Promise<JobStatusSnapshot> {
  return sidecarRequest<JobStatusSnapshot>("get_job_status", { job_id: jobId });
}

export async function listJobs(limit = 20): Promise<ListJobsResponse> {
  return sidecarRequest<ListJobsResponse>("list_jobs", { limit });
}

export async function pauseJob(jobId: string): Promise<{ job_id: string; status: string }> {
  return sidecarRequest<{ job_id: string; status: string }>("pause_job", { job_id: jobId });
}

export async function resumeJob(jobId: string): Promise<{ job_id: string; status: string }> {
  return sidecarRequest<{ job_id: string; status: string }>("resume_job", { job_id: jobId });
}

export async function resumeExistingJob(
  jobId: string,
): Promise<{ job_id: string; status: string; accepted: boolean }> {
  return sidecarRequest<{ job_id: string; status: string; accepted: boolean }>(
    "resume_existing_job",
    { job_id: jobId },
  );
}

export async function cancelJob(jobId: string): Promise<{ job_id: string; status: string }> {
  return sidecarRequest<{ job_id: string; status: string }>("cancel_job", { job_id: jobId });
}

export async function listenSidecarEvents(
  callback: (event: SidecarEvent) => void,
): Promise<UnlistenFn> {
  return listen<SidecarEvent>("sidecar-event", (event) => {
    callback(event.payload);
  });
}
