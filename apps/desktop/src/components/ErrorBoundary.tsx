import React from "react";
import { RefreshCw } from "lucide-react";
import { describeUserFacingError } from "../lib/errorMessages";
import { Alert, AlertDescription, AlertTitle } from "./ui/alert";
import { Button } from "./ui/button";

type ErrorBoundaryProps = {
  children: React.ReactNode;
};

type ErrorBoundaryState = {
  error: Error | null;
};

export class ErrorBoundary extends React.Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error("Desktop render error", error, info);
  }

  render() {
    if (!this.state.error) {
      return this.props.children;
    }

    return (
      <main className="min-h-screen bg-background p-4 text-foreground">
        <div className="mx-auto max-w-3xl">
          <Alert variant="destructive">
            <AlertTitle>แอปแสดงผลไม่สำเร็จ</AlertTitle>
            <AlertDescription className="mt-2 break-words">
              {describeUserFacingError(this.state.error)}
            </AlertDescription>
            <Button
              type="button"
              variant="outline"
              className="mt-4"
              onClick={() => this.setState({ error: null })}
            >
              <RefreshCw className="h-4 w-4" />
              ลองแสดงหน้านี้อีกครั้ง
            </Button>
          </Alert>
        </div>
      </main>
    );
  }
}
