import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import messages from "../i18n/th.json";
import { ModuleHome } from "./ModuleHome";

function renderHome(onOpenModule = vi.fn()) {
  const props = {
    onOpenModule,
    updaterStatus: {
      configured: false,
      endpoint: null,
      current_version: "0.1.0",
      pubkey_configured: false,
    },
    availableUpdate: null,
    updateMessage: null,
    updateProgress: null,
    isCheckingUpdate: false,
    isInstallingUpdate: false,
    connectionState: "ready" as const,
    databaseStatus: null,
    accountStatus: null,
    accountEmail: "",
    accountPassword: "",
    isSigningIn: false,
    isCreatingBackup: false,
    isRestoringBackup: false,
    isExportingDiagnostics: false,
    onAccountEmailChange: vi.fn(),
    onAccountPasswordChange: vi.fn(),
    onSignIn: vi.fn(),
    onSignOut: vi.fn(),
    onRefreshWallet: vi.fn(),
    onCheckForUpdates: vi.fn(),
    onInstallUpdate: vi.fn(),
    onRefreshDatabaseStatus: vi.fn(),
    onCreateBackup: vi.fn(),
    onRestoreBackup: vi.fn(),
    onExportDiagnostics: vi.fn(),
  };
  render(<ModuleHome {...props} />);
  return props;
}

describe("ModuleHome", () => {
  it("renders all module entry points from i18n copy", () => {
    renderHome();

    expect(screen.getByRole("heading", { name: messages.app.home.title })).toBeInTheDocument();
    expect(screen.getByText("บัญชีและเครดิต")).toBeInTheDocument();
    expect(screen.getByText(messages.app.home.modules.formConverter.title)).toBeInTheDocument();
    expect(screen.getByText(messages.app.home.modules.currentStudents.title)).toBeInTheDocument();
    expect(screen.getByText(messages.app.home.modules.graduation.title)).toBeInTheDocument();
    expect(screen.getAllByText(/ใช้เครดิต 1\/รายการ/)).toHaveLength(3);
    expect(screen.queryByText("License Activation")).not.toBeInTheDocument();
  });

  it("opens skeleton modules instead of disabling them", () => {
    const onOpenModule = vi.fn();
    renderHome(onOpenModule);

    fireEvent.click(screen.getAllByRole("button", { name: messages.app.home.openSkeleton })[0]);

    expect(onOpenModule).toHaveBeenCalledWith("formConverter");
  });
});
