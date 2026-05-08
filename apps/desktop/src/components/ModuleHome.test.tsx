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
    errorMessage: null,
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

function renderHomeWithAccountWarning() {
  const props = {
    onOpenModule: vi.fn(),
    updaterStatus: null,
    availableUpdate: null,
    updateMessage: null,
    updateProgress: null,
    isCheckingUpdate: false,
    isInstallingUpdate: false,
    connectionState: "ready" as const,
    databaseStatus: null,
    accountStatus: {
      signed_in: false,
      user_id: null,
      email: null,
      display_name: null,
      status: "missing",
      token_expires_at: null,
      last_checked_at: null,
      wallet: null,
      can_start_credit_jobs: false,
      needs_attention: true,
      message: null,
      last_error: "ACCOUNT_CLOUD_UNAVAILABLE",
    },
    errorMessage: null,
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
}

function renderHomeWithSignedInAccount() {
  const props = {
    onOpenModule: vi.fn(),
    updaterStatus: null,
    availableUpdate: null,
    updateMessage: null,
    updateProgress: null,
    isCheckingUpdate: false,
    isInstallingUpdate: false,
    connectionState: "ready" as const,
    databaseStatus: null,
    accountStatus: {
      signed_in: true,
      user_id: "user-1",
      email: "teacher@example.test",
      display_name: "Teacher Demo",
      status: "active",
      token_expires_at: "2026-05-09T00:00:00Z",
      last_checked_at: "2026-05-08T00:00:00Z",
      wallet: {
        user_id: "user-1",
        balance: 20,
        reserved: 5,
        available: 15,
      },
      can_start_credit_jobs: true,
      needs_attention: false,
      message: null,
      last_error: null,
    },
    errorMessage: null,
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
}

describe("ModuleHome", () => {
  it("renders all module entry points from i18n copy", () => {
    renderHome();

    expect(screen.getByRole("heading", { name: messages.app.home.title })).toBeInTheDocument();
    expect(screen.getByText("บัญชีและเครดิต")).toBeInTheDocument();
    expect(screen.getByText(messages.app.home.modules.formConverter.title)).toBeInTheDocument();
    expect(screen.getByText(messages.app.home.modules.studentBasicInfo.title)).toBeInTheDocument();
    expect(screen.getByText(messages.app.home.modules.psar.title)).toBeInTheDocument();
    expect(screen.getByText(messages.app.home.modules.currentStudents.title)).toBeInTheDocument();
    expect(screen.getByText(messages.app.home.modules.graduation.title)).toBeInTheDocument();
    expect(screen.getAllByText(/ใช้เครดิต 1\/รายการ/)).toHaveLength(2);
    expect(screen.getByText(messages.app.account.topup.title)).toBeInTheDocument();
    for (const packageOption of messages.app.account.topup.packages) {
      expect(screen.getByText(packageOption.name)).toBeInTheDocument();
      expect(screen.getByText(packageOption.unitRate)).toBeInTheDocument();
    }
    expect(screen.queryByText("License Activation")).not.toBeInTheDocument();
  });

  it("opens currentStudents from the ready module list", () => {
    const onOpenModule = vi.fn();
    renderHome(onOpenModule);

    fireEvent.click(screen.getAllByRole("button", { name: messages.app.home.openModule })[0]);

    expect(onOpenModule).toHaveBeenCalledWith("formConverter");

    fireEvent.click(screen.getAllByRole("button", { name: messages.app.home.openModule })[3]);

    expect(onOpenModule).toHaveBeenCalledWith("currentStudents");
  });

  it("shows a friendly cloud unavailable account warning", () => {
    renderHomeWithAccountWarning();

    expect(screen.getByText(messages.app.account.errors.ACCOUNT_CLOUD_UNAVAILABLE)).toBeInTheDocument();
  });

  it("shows feedback after selecting a credit top-up package", () => {
    renderHomeWithSignedInAccount();

    const packageOption = messages.app.account.topup.packages[1];
    fireEvent.click(
      screen.getByRole("button", {
        name: `${messages.app.account.topup.cta} ${packageOption.name}`,
      }),
    );

    expect(
      screen.getByText(messages.app.account.topup.selectedMessage.replace("{name}", packageOption.name)),
    ).toBeInTheDocument();
  });

  it("shows global login and cloud errors on the home screen", () => {
    const props = renderHome();

    render(<ModuleHome {...props} errorMessage={messages.app.account.errors.INVALID_CREDENTIALS} />);

    expect(screen.getByText(messages.app.account.errors.INVALID_CREDENTIALS)).toBeInTheDocument();
  });
});
