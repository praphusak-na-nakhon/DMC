import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AiSettingsCard } from "./AiSettingsCard";

const mockRpc = vi.hoisted(() => ({
  getAiSettings: vi.fn(),
  saveAiApiKey: vi.fn(),
  testAiConnection: vi.fn(),
  deleteAiApiKey: vi.fn(),
}));

vi.mock("../lib/rpcClient", () => mockRpc);

const geminiSettings = (configured: boolean) => ({ provider: "gemini" as const, configured });

beforeEach(() => {
  for (const mock of Object.values(mockRpc)) {
    mock.mockReset();
  }
  mockRpc.getAiSettings.mockResolvedValue(geminiSettings(false));
});

describe("AiSettingsCard", () => {
  it("loads and displays the configured Gemini status when the connection is ready", async () => {
    mockRpc.getAiSettings.mockResolvedValue(geminiSettings(true));

    render(<AiSettingsCard connectionReady />);

    expect(await screen.findByText("ตั้งค่า Gemini API key แล้ว")).toBeInTheDocument();
    expect(mockRpc.getAiSettings).toHaveBeenCalledWith("gemini");
  });

  it("saves a Gemini key, clears the input, and does not render the submitted secret", async () => {
    mockRpc.saveAiApiKey.mockResolvedValue(geminiSettings(true));
    render(<AiSettingsCard connectionReady />);
    const apiKey = screen.getByLabelText("Gemini API key");

    fireEvent.change(apiKey, { target: { value: "secret-value" } });
    fireEvent.click(screen.getByRole("button", { name: "บันทึก API key" }));

    await waitFor(() => expect(mockRpc.saveAiApiKey).toHaveBeenCalledWith("gemini", "secret-value"));
    expect(apiKey).toHaveValue("");
    expect(document.body.textContent).not.toContain("secret-value");
  });

  it("shows a successful Gemini connection test result", async () => {
    mockRpc.testAiConnection.mockResolvedValue({
      provider: "gemini",
      ok: true,
      tested_at: "2026-09-04T00:00:00Z",
      message: "connected",
    });
    render(<AiSettingsCard connectionReady />);

    fireEvent.click(screen.getByRole("button", { name: "ทดสอบการเชื่อมต่อ" }));

    expect(await screen.findByText("เชื่อมต่อ Gemini สำเร็จ")).toBeInTheDocument();
  });

  it("shows a safe failure message when the Gemini connection test fails", async () => {
    mockRpc.testAiConnection.mockRejectedValue(new Error("invalid secret-value"));
    render(<AiSettingsCard connectionReady />);

    fireEvent.click(screen.getByRole("button", { name: "ทดสอบการเชื่อมต่อ" }));

    expect(await screen.findByText("ไม่สามารถทดสอบการเชื่อมต่อ Gemini ได้ กรุณาลองใหม่")).toBeInTheDocument();
    expect(document.body.textContent).not.toContain("secret-value");
  });

  it("deletes the configured Gemini key and updates the status", async () => {
    mockRpc.getAiSettings.mockResolvedValue(geminiSettings(true));
    mockRpc.deleteAiApiKey.mockResolvedValue(geminiSettings(false));
    render(<AiSettingsCard connectionReady />);
    await screen.findByText("ตั้งค่า Gemini API key แล้ว");

    fireEvent.click(screen.getByRole("button", { name: "ลบ API key" }));

    await waitFor(() => expect(mockRpc.deleteAiApiKey).toHaveBeenCalledWith("gemini"));
    expect(screen.getByText("ยังไม่ได้ตั้งค่า Gemini API key")).toBeInTheDocument();
  });

  it("keeps AI actions disabled until the sidecar connection is ready", () => {
    render(<AiSettingsCard connectionReady={false} />);

    expect(screen.getByText("กำลังเชื่อมต่อระบบ AI")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "บันทึก API key" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "ทดสอบการเชื่อมต่อ" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "ลบ API key" })).toBeDisabled();
    expect(mockRpc.getAiSettings).not.toHaveBeenCalled();
  });
});
