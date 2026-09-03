import { fireEvent, render, screen, within } from "@testing-library/react";
import type { ComponentProps } from "react";
import { describe, expect, it, vi } from "vitest";
import messages from "../i18n/th.json";
import { ModuleHome } from "./ModuleHome";

type ModuleHomeProps = ComponentProps<typeof ModuleHome>;

function buildHomeProps(overrides: Partial<ModuleHomeProps> = {}) {
  return {
    onOpenModule: vi.fn(),
    connectionState: "ready" as const,
    accountStatus: null,
    errorMessage: null,
    onOpenSignIn: vi.fn(),
    onOpenTopup: vi.fn(),
    onSignOut: vi.fn(),
    onRetryRuntime: vi.fn(),
    ...overrides,
  };
}

function renderHome(overrides: Partial<ModuleHomeProps> = {}) {
  const props = buildHomeProps(overrides);
  render(<ModuleHome {...props} />);
  return props;
}

function renderHomeWithAccountWarning() {
  renderHome({
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
  });
}

describe("ModuleHome", () => {
  it("renders only retained local modules", () => {
    renderHome();

    const moduleCards = screen
      .getAllByRole("button")
      .filter((element) => element.getAttribute("tabindex") === "0");

    expect(moduleCards).toHaveLength(4);
    expect(moduleCards.map((card) => within(card).getByRole("button").textContent)).toEqual([
      messages.app.home.moduleActions.formConverter,
      messages.app.home.moduleActions.studentBasicInfo,
      messages.app.home.moduleActions.currentStudents,
      messages.app.home.moduleActions.graduation,
    ]);
  });

  it("shows Gemini settings only when the sidecar connection is ready", () => {
    const { rerender } = render(<ModuleHome {...buildHomeProps({ connectionState: "connecting" })} />);

    expect(screen.queryByText(messages.app.home.aiSettings.title)).not.toBeInTheDocument();

    rerender(<ModuleHome {...buildHomeProps({ connectionState: "ready" })} />);

    expect(screen.getByText(messages.app.home.aiSettings.title)).toBeInTheDocument();
  });

  it("opens currentStudents from the ready module list", () => {
    const onOpenModule = vi.fn();
    renderHome({ onOpenModule });

    fireEvent.click(screen.getByRole("button", { name: messages.app.home.moduleActions.formConverter }));

    expect(onOpenModule).toHaveBeenCalledWith("formConverter");

    fireEvent.click(screen.getByRole("button", { name: messages.app.home.moduleActions.currentStudents }));

    expect(onOpenModule).toHaveBeenCalledWith("currentStudents");
  });

  it("shows a friendly cloud unavailable account warning", () => {
    renderHomeWithAccountWarning();

    expect(screen.getByText(messages.app.account.errors.ACCOUNT_CLOUD_UNAVAILABLE)).toBeInTheDocument();
  });

  it("opens the separate credit top-up page from account actions", () => {
    const props = renderHome();

    fireEvent.click(screen.getByRole("button", { name: messages.app.account.topup.expandLabel }));

    expect(props.onOpenTopup).toHaveBeenCalled();
    expect(screen.queryByText(messages.app.account.topup.packages[0].unitRate)).not.toBeInTheDocument();
  });

  it("opens the separate sign-in page from account actions", () => {
    const props = renderHome();

    fireEvent.click(screen.getByRole("button", { name: messages.app.account.signIn }));

    expect(props.onOpenSignIn).toHaveBeenCalled();
  });

  it("shows global login and cloud errors on the home screen", () => {
    const props = buildHomeProps({
      errorMessage: messages.app.account.errors.INVALID_CREDENTIALS,
    });

    render(<ModuleHome {...props} />);

    expect(screen.getByText(messages.app.account.errors.INVALID_CREDENTIALS)).toBeInTheDocument();
  });
});
