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
  processed: number;
  total: number | null;
  succeeded: number;
  failed: number;
  current_page: number | null;
  needs_auth: boolean;
  auth_reason: string | null;
  report_path: string | null;
  stopped_item: Record<string, unknown> | null;
};

export type StartJobResponse = {
  accepted: boolean;
  job_id: string;
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
      type: "sidecar_started" | "sidecar_exited";
      pid?: number;
      code?: number | null;
      signal?: string | null;
      message?: string;
    }
  | {
      type: "sidecar_stderr";
      message: string;
    };
