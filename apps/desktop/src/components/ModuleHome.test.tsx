import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import messages from "../i18n/th.json";
import { ModuleHome } from "./ModuleHome";

describe("ModuleHome", () => {
  it("opens all four local modules without commercial controls", () => {
    const onOpenModule = vi.fn();
    render(<ModuleHome onOpenModule={onOpenModule} connectionState="idle" errorMessage={null} onRetryRuntime={vi.fn()} />);
    for (const id of ["formConverter", "studentBasicInfo", "currentStudents", "graduation"] as const) {
      fireEvent.click(screen.getByRole("button", { name: messages.app.home.moduleActions[id] }));
      expect(onOpenModule).toHaveBeenLastCalledWith(id);
    }
    expect(screen.queryByText(/เครดิต|เข้าสู่ระบบ|License/i)).not.toBeInTheDocument();
  });
  it("shows local errors and offers runtime recovery", () => {
    const retry = vi.fn();
    render(<ModuleHome onOpenModule={vi.fn()} connectionState="error" errorMessage="Runtime disconnected" onRetryRuntime={retry} />);
    expect(screen.getByText("Runtime disconnected")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: messages.app.home.retryConnection }));
    expect(retry).toHaveBeenCalledOnce();
    expect(screen.queryByText(messages.app.home.aiSettings.title)).not.toBeInTheDocument();
  });
});
