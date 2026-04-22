import { create } from "zustand";
import type {
  JobStatusSnapshot,
  SidecarEvent,
  ValidateExcelResponse,
} from "../types/contracts";

type JobStoreState = {
  preview: ValidateExcelResponse | null;
  currentJob: JobStatusSnapshot | null;
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
  setConnectionState: (state: JobStoreState["connectionState"]) => void;
  setIsValidating: (value: boolean) => void;
  setIsStartingJob: (value: boolean) => void;
  setErrorMessage: (message: string | null) => void;
  pushSidecarMessage: (message: string) => void;
  setActiveJobId: (jobId: string | null) => void;
  applySidecarEvent: (event: SidecarEvent) => void;
  reset: () => void;
};

function updateFromProgress(
  currentJob: JobStatusSnapshot | null,
  event: Extract<SidecarEvent, { type: "progress" }>,
): JobStatusSnapshot {
  return {
    job_id: event.job_id,
    module: currentJob?.module ?? "graduation",
    status: currentJob?.status ?? "running",
    processed: event.processed,
    total: event.total,
    succeeded: event.succeeded,
    failed: event.failed,
    current_page: event.current_page,
    needs_auth: event.needs_auth,
    auth_reason: event.auth_reason,
    report_path: currentJob?.report_path ?? null,
    stopped_item: currentJob?.stopped_item ?? null,
  };
}

export const useJobStore = create<JobStoreState>((set) => ({
  preview: null,
  currentJob: null,
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
        return {
          currentJob: updateFromProgress(state.currentJob, event),
          activeJobId: event.job_id,
        };
      }

      if (event.type === "needs_auth") {
        return {
          currentJob: state.currentJob
            ? {
                ...state.currentJob,
                status: "paused",
                needs_auth: true,
                auth_reason: event.reason,
              }
            : null,
          activeJobId: event.job_id,
          sidecarMessages: [
            `ต้องลงชื่อเข้าใช้ DMC ใหม่: ${event.reason}`,
            ...state.sidecarMessages,
          ].slice(0, 8),
        };
      }

      if (event.type === "job_done") {
        return {
          currentJob: state.currentJob
            ? {
                ...state.currentJob,
                status: event.status,
                needs_auth: false,
                auth_reason: null,
                report_path: event.report_path,
              }
            : null,
          sidecarMessages: [
            `งาน ${event.job_id} เสร็จสมบูรณ์`,
            ...state.sidecarMessages,
          ].slice(0, 8),
        };
      }

      if (event.type === "job_stopped") {
        return {
          currentJob: state.currentJob
            ? {
                ...state.currentJob,
                status: event.status,
                stopped_item: event.stopped_item,
              }
            : null,
          sidecarMessages: [
            `งาน ${event.job_id} หยุดเพราะต้อง review`,
            ...state.sidecarMessages,
          ].slice(0, 8),
        };
      }

      if (event.type === "error") {
        return {
          errorMessage: `${event.code}: ${event.message}`,
          sidecarMessages: [
            `เกิดข้อผิดพลาดใน sidecar: ${event.message}`,
            ...state.sidecarMessages,
          ].slice(0, 8),
        };
      }

      if (event.type === "sidecar_started") {
        return {
          connectionState: "ready",
          sidecarMessages: [
            `เชื่อมต่อ sidecar แล้ว (PID ${event.pid ?? "-"})`,
            ...state.sidecarMessages,
          ].slice(0, 8),
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

      return state;
    }),
  reset: () =>
    set({
      preview: null,
      currentJob: null,
      excelPath: "",
      connectionState: "idle",
      isValidating: false,
      isStartingJob: false,
      errorMessage: null,
      sidecarMessages: [],
      activeJobId: null,
    }),
}));
