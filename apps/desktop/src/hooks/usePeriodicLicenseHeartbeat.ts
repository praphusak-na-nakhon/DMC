import { useEffect, useRef } from "react";

type ConnectionState = "idle" | "connecting" | "ready" | "error";

type UsePeriodicLicenseHeartbeatArgs = {
  connectionState: ConnectionState;
  onHeartbeat: () => Promise<unknown>;
};

export function usePeriodicLicenseHeartbeat({
  connectionState,
  onHeartbeat,
}: UsePeriodicLicenseHeartbeatArgs) {
  const inFlightRef = useRef(false);

  useEffect(() => {
    if (connectionState !== "ready") {
      return;
    }

    const timer = window.setInterval(() => {
      if (inFlightRef.current) {
        return;
      }
      inFlightRef.current = true;
      void onHeartbeat().finally(() => {
        inFlightRef.current = false;
      });
    }, 5 * 60 * 1000);

    return () => {
      inFlightRef.current = false;
      window.clearInterval(timer);
    };
  }, [connectionState, onHeartbeat]);
}
