import { create } from "zustand";
import type {
  AccountStatus,
  JobStatusSnapshot,
  ModuleConfigStatus,
  SidecarEvent,
  ValidateExcelResponse,
} from "../types/contracts";

type JobStoreState = {
  preview: ValidateExcelResponse | null;
  currentJob: JobStatusSnapshot | null;
  accountStatus: AccountStatus | null;
  moduleConfigStatus: ModuleConfigStatus | null;
  existingJobs: JobStatusSnapshot[];
  excelPath: string;
  connectionState: "idle" | "connecting" | "ready" | "error";
  isValidating: boolean;
  isStartingJob: boolean;
  errorMessage: string | null;
  sidecarMessages: string[];
  activeJobId: string | null;
  setExcelPath: (excelPath: string) => void;
  setPreview: (preview: ValidateExcelResponse | null) => void;
  setCurrentJob: (job: JobStatusSnapshot | null) => void;
  setAccountStatus: (status: AccountStatus | null) => void;
  setModuleConfigStatus: (status: ModuleConfigStatus | null) => void;
  setExistingJobs: (jobs: JobStatusSnapshot[]) => void;
  upsertExistingJob: (job: JobStatusSnapshot) => void;
  setConnectionState: (state: JobStoreState["connectionState"]) => void;
  setIsValidating: (value: boolean) => void;
  setIsStartingJob: (value: boolean) => void;
  setErrorMessage: (message: string | null) => void;
  pushSidecarMessage: (message: string) => void;
  setActiveJobId: (jobId: string | null) => void;
  applySidecarEvent: (event: SidecarEvent) => void;
  reset: () => void;
};

function mergeJob(
  base: JobStatusSnapshot | null,
  partial: Partial<JobStatusSnapshot> & Pick<JobStatusSnapshot, "job_id">,
): JobStatusSnapshot {
  return {
    job_id: partial.job_id,
    module: partial.module ?? base?.module ?? "graduation",
    status: partial.status ?? base?.status ?? "pending",
    source_file: partial.source_file ?? base?.source_file ?? "",
    processed: partial.processed ?? base?.processed ?? 0,
    total: partial.total ?? base?.total ?? null,
    succeeded: partial.succeeded ?? base?.succeeded ?? 0,
    failed: partial.failed ?? base?.failed ?? 0,
    current_page: partial.current_page ?? base?.current_page ?? null,
    needs_auth: partial.needs_auth ?? base?.needs_auth ?? false,
    auth_reason: partial.auth_reason ?? base?.auth_reason ?? null,
    report_path: partial.report_path ?? base?.report_path ?? null,
    review_report_path: partial.review_report_path ?? base?.review_report_path ?? null,
    stopped_item: partial.stopped_item ?? base?.stopped_item ?? null,
    started_at: partial.started_at ?? base?.started_at ?? null,
    finished_at: partial.finished_at ?? base?.finished_at ?? null,
    level_label: partial.level_label ?? base?.level_label ?? null,
    run_summary: partial.run_summary ?? base?.run_summary ?? null,
    credit_reservation_id: partial.credit_reservation_id ?? base?.credit_reservation_id ?? null,
    credits_reserved: partial.credits_reserved ?? base?.credits_reserved ?? 0,
    credits_captured: partial.credits_captured ?? base?.credits_captured ?? 0,
    credits_refunded: partial.credits_refunded ?? base?.credits_refunded ?? 0,
    credit_status: partial.credit_status ?? base?.credit_status ?? null,
  };
}

function upsertJobList(existingJobs: JobStatusSnapshot[], nextJob: JobStatusSnapshot): JobStatusSnapshot[] {
  return [nextJob, ...existingJobs.filter((item) => item.job_id !== nextJob.job_id)].slice(0, 20);
}

export const useJobStore = create<JobStoreState>((set) => ({
  preview: null,
  currentJob: null,
  accountStatus: null,
  moduleConfigStatus: null,
  existingJobs: [],
  excelPath: "",
  connectionState: "idle",
  isValidating: false,
  isStartingJob: false,
  errorMessage: null,
  sidecarMessages: [],
  activeJobId: null,
  setExcelPath: (excelPath) => set({ excelPath }),
  setPreview: (preview) => set({ preview }),
  setCurrentJob: (currentJob) => set({ currentJob }),
  setAccountStatus: (accountStatus) => set({ accountStatus }),
  setModuleConfigStatus: (moduleConfigStatus) => set({ moduleConfigStatus }),
  setExistingJobs: (existingJobs) => set({ existingJobs }),
  upsertExistingJob: (job) =>
    set((state) => ({
      existingJobs: upsertJobList(state.existingJobs, job),
    })),
  setConnectionState: (connectionState) => set({ connectionState }),
  setIsValidating: (isValidating) => set({ isValidating }),
  setIsStartingJob: (isStartingJob) => set({ isStartingJob }),
  setErrorMessage: (errorMessage) => set({ errorMessage }),
  pushSidecarMessage: (message) =>
    set((state) => ({
      sidecarMessages: [message, ...state.sidecarMessages].slice(0, 8),
    })),
  setActiveJobId: (activeJobId) => set({ activeJobId }),
  applySidecarEvent: (event) =>
    set((state) => {
      if (event.type === "progress") {
        const nextJob = mergeJob(state.currentJob, {
          job_id: event.job_id,
          status: "running",
          processed: event.processed,
          total: event.total,
          succeeded: event.succeeded,
          failed: event.failed,
          current_page: event.current_page,
          needs_auth: event.needs_auth,
          auth_reason: event.auth_reason,
        });
        return {
          currentJob: nextJob,
          existingJobs: upsertJobList(state.existingJobs, nextJob),
          activeJobId: event.job_id,
        };
      }

      if (event.type === "needs_auth") {
        const nextJob = state.currentJob
          ? mergeJob(state.currentJob, {
              job_id: event.job_id,
              status: "paused",
              needs_auth: true,
              auth_reason: event.reason,
            })
          : null;
        return {
          currentJob: nextJob,
          existingJobs: nextJob ? upsertJobList(state.existingJobs, nextJob) : state.existingJobs,
          activeJobId: event.job_id,
          sidecarMessages: [
            `ต้องลงชื่อเข้าใช้ DMC ใหม่: ${event.reason}`,
            ...state.sidecarMessages,
          ].slice(0, 8),
        };
      }

      if (event.type === "job_done") {
        const nextJob = state.currentJob
          ? mergeJob(state.currentJob, {
              job_id: event.job_id,
              status: event.status,
              processed: event.processed,
              total: event.total,
              succeeded: event.succeeded,
              failed: event.failed,
              current_page: event.current_page,
              needs_auth: false,
              auth_reason: null,
              report_path: event.report_path,
              review_report_path: event.review_report_path,
              run_summary: event.run_summary,
            })
          : null;
        return {
          currentJob: nextJob,
          existingJobs: nextJob ? upsertJobList(state.existingJobs, nextJob) : state.existingJobs,
          sidecarMessages: [`งาน ${event.job_id} เสร็จสมบูรณ์`, ...state.sidecarMessages].slice(0, 8),
        };
      }

      if (event.type === "job_stopped") {
        const nextJob = state.currentJob
          ? mergeJob(state.currentJob, {
              job_id: event.job_id,
              status: event.status,
              stopped_item: event.stopped_item,
            })
          : null;
        return {
          currentJob: nextJob,
          existingJobs: nextJob ? upsertJobList(state.existingJobs, nextJob) : state.existingJobs,
          sidecarMessages: [`งาน ${event.job_id} หยุดเพราะต้อง review`, ...state.sidecarMessages].slice(
            0,
            8,
          ),
        };
      }

      if (event.type === "error") {
        if (event.job_id && state.activeJobId && event.job_id !== state.activeJobId) {
          return state;
        }
        const nextJob =
          event.job_id && state.currentJob
            ? mergeJob(state.currentJob, {
                job_id: event.job_id,
                status: "failed",
                credit_status:
                  state.currentJob.credit_status === "reserving"
                    ? `start_failed:${event.code}`
                    : state.currentJob.credit_status,
              })
            : null;
        return {
          currentJob: nextJob ?? state.currentJob,
          existingJobs: nextJob ? upsertJobList(state.existingJobs, nextJob) : state.existingJobs,
          errorMessage: `${event.code}: ${event.message}`,
          sidecarMessages: [`เกิดข้อผิดพลาดใน sidecar: ${event.message}`, ...state.sidecarMessages].slice(
            0,
            8,
          ),
        };
      }

      if (event.type === "sidecar_started") {
        return {
          connectionState: "ready",
          sidecarMessages: [`เชื่อมต่อ sidecar แล้ว (PID ${event.pid ?? "-"})`, ...state.sidecarMessages].slice(
            0,
            8,
          ),
        };
      }

      if (event.type === "sidecar_exited") {
        return {
          connectionState: "error",
          sidecarMessages: [
            `sidecar ปิดตัวลง (code=${event.code ?? "-"}, signal=${event.signal ?? "-"})`,
            ...state.sidecarMessages,
          ].slice(0, 8),
        };
      }

      if (event.type === "sidecar_stderr") {
        return {
          sidecarMessages: [event.message, ...state.sidecarMessages].slice(0, 8),
        };
      }

      if (event.type === "browser_runtime_progress") {
        return {
          sidecarMessages: [
            `browser runtime: ${event.message}${event.detail ? ` (${event.detail})` : ""}`,
            ...state.sidecarMessages,
          ].slice(0, 8),
        };
      }

      return state;
    }),
  reset: () =>
    set({
      preview: null,
      currentJob: null,
      accountStatus: null,
      moduleConfigStatus: null,
      existingJobs: [],
      excelPath: "",
      connectionState: "idle",
      isValidating: false,
      isStartingJob: false,
      errorMessage: null,
      sidecarMessages: [],
      activeJobId: null,
    }),
}));
