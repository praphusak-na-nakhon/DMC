import { AlertCircle, RefreshCw } from "lucide-react";
import {
  describeUserFacingError,
  getRuntimeConnectionErrorKind,
  isRuntimeConnectionError,
} from "../lib/errorMessages";
import { Alert, AlertDescription, AlertTitle } from "./ui/alert";
import { Button } from "./ui/button";

type SystemErrorAlertProps = {
  message: string;
  onRetry?: () => void;
  retryLabel?: string;
  retryWhen?: "always" | "runtime";
};

export function SystemErrorAlert({
  message,
  onRetry,
  retryLabel = "ลองเชื่อมต่อใหม่",
  retryWhen = "always",
}: SystemErrorAlertProps) {
  const description = describeUserFacingError(message);
  const isRuntimeError = isRuntimeConnectionError(message);
  const runtimeKind = getRuntimeConnectionErrorKind(message);
  const title =
    runtimeKind === "desktop"
      ? "Desktop runtime ยังไม่พร้อม"
      : runtimeKind === "sidecar"
        ? "ตัวเชื่อมระบบยังไม่พร้อม"
        : "ทำรายการไม่สำเร็จ";
  const shouldShowRetry = Boolean(onRetry) && (retryWhen === "always" || isRuntimeError);

  return (
    <Alert variant="destructive">
      <AlertCircle className="h-4 w-4" />
      <div className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center">
        <div className="min-w-0">
          <AlertTitle>{title}</AlertTitle>
          <AlertDescription className="mt-1 break-words">{description}</AlertDescription>
        </div>
        {shouldShowRetry ? (
          <Button type="button" variant="outline" size="sm" onClick={onRetry}>
            <RefreshCw className="h-4 w-4" />
            {retryLabel}
          </Button>
        ) : null}
      </div>
    </Alert>
  );
}
