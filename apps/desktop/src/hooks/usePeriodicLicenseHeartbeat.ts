import { useEffect } from "react";

type ConnectionState = "idle" | "connecting" | "ready" | "error";

type UsePeriodicLicenseHeartbeatArgs = {
  connectionState: ConnectionState;
  onHeartbeat: () => Promise<unknown>;
};

export function usePeriodicLicenseHeartbeat({
  connectionState,
  onHeartbeat,
}: UsePeriodicLicenseHeartbeatArgs) {
  useEffect(() => {
    if (connectionState !== "ready") {
      return;
    }

    const timer = window.setInterval(() => {
      void onHeartbeat();
    }, 5 * 60 * 1000);

    return () => window.clearInterval(timer);
  }, [connectionState, onHeartbeat]);
}
