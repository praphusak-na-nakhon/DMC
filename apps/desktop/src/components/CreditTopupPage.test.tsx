import { fireEvent, render, screen } from "@testing-library/react";
import type { ComponentProps } from "react";
import { describe, expect, it, vi } from "vitest";
import messages from "../i18n/th.json";
import { CreditTopupPage } from "./CreditTopupPage";

type CreditTopupPageProps = ComponentProps<typeof CreditTopupPage>;

function buildProps(overrides: Partial<CreditTopupPageProps> = {}) {
  return {
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
    onBackHome: vi.fn(),
    onOpenSignIn: vi.fn(),
    ...overrides,
  };
}

describe("CreditTopupPage", () => {
  it("renders all credit packages on a separate page", () => {
    render(<CreditTopupPage {...buildProps()} />);

    expect(screen.getByText(messages.app.account.topup.title)).toBeInTheDocument();
    for (const packageOption of messages.app.account.topup.packages) {
      expect(screen.getByText(packageOption.name)).toBeInTheDocument();
      expect(screen.getByText(packageOption.unitRate)).toBeInTheDocument();
    }
  });

  it("shows feedback after selecting a package while signed in", () => {
    render(<CreditTopupPage {...buildProps()} />);

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

  it("opens sign-in instead of selecting a package while signed out", () => {
    const props = buildProps({ accountStatus: null });
    render(<CreditTopupPage {...props} />);

    fireEvent.click(
      screen.getByRole("button", {
        name: `${messages.app.account.topup.cta} ${messages.app.account.topup.packages[0].name}`,
      }),
    );

    expect(props.onOpenSignIn).toHaveBeenCalled();
  });
});
