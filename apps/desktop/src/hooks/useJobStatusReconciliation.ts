import { useEffect } from "react";
import { getJobStatus } from "../lib/rpcClient";
import type { JobStatusSnapshot } from "../types/contracts";

type UseJobStatusReconciliationArgs = {
  activeJobId: string | null;
  currentJobStatus: string | null;
  onStatus: (job: JobStatusSnapshot) => void;
  onError: (message: string) => void;
};

const RECONCILE_INTERVAL_MS = 15000;

export function useJobStatusReconciliation({
  activeJobId,
  currentJobStatus,
  onStatus,
  onError,
}: UseJobStatusReconciliationArgs) {
  useEffect(() => {
    if (!activeJobId) {
      return;
    }

    if (
      currentJobStatus &&
      ["done", "cancelled", "failed", "stopped_on_review"].includes(currentJobStatus)
    ) {
      return;
    }

    const timer = window.setInterval(() => {
      void getJobStatus(activeJobId)
        .then((status) => {
          onStatus(status);
        })
        .catch((error) => {
          onError(error instanceof Error ? error.message : String(error));
        });
    }, RECONCILE_INTERVAL_MS);

    return () => window.clearInterval(timer);
  }, [activeJobId, currentJobStatus, onError, onStatus]);
}
