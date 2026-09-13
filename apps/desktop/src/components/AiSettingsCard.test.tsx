import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
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

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((promiseResolve, promiseReject) => {
    resolve = promiseResolve;
    reject = promiseReject;
  });
  return { promise, resolve, reject };
}

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

  it("keeps a successful save status when an older initial settings response resolves later", async () => {
    const initialLoad = deferred<ReturnType<typeof geminiSettings>>();
    mockRpc.getAiSettings.mockReturnValue(initialLoad.promise);
    mockRpc.saveAiApiKey.mockResolvedValue(geminiSettings(true));
    render(<AiSettingsCard connectionReady />);

    fireEvent.change(screen.getByLabelText("Gemini API key"), { target: { value: "secret-value" } });
    fireEvent.click(screen.getByRole("button", { name: "บันทึก API key" }));

    expect(await screen.findByText("ตั้งค่า Gemini API key แล้ว")).toBeInTheDocument();
    await act(async () => {
      initialLoad.resolve(geminiSettings(false));
      await initialLoad.promise;
    });

    expect(screen.getByText("ตั้งค่า Gemini API key แล้ว")).toBeInTheDocument();
    expect(screen.queryByText("ยังไม่ได้ตั้งค่า Gemini API key")).not.toBeInTheDocument();
  });

  it("shows a recoverable settings-load failure instead of remaining in loading", async () => {
    mockRpc.getAiSettings.mockRejectedValueOnce(new Error("settings secret-value failure"));
    mockRpc.getAiSettings.mockResolvedValueOnce(geminiSettings(false));
    render(<AiSettingsCard connectionReady />);

    expect(await screen.findByText("ไม่สามารถตรวจสอบสถานะ Gemini API key ได้ กรุณาลองใหม่")).toBeInTheDocument();
    expect(screen.queryByText("กำลังตรวจสอบสถานะ Gemini API key")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "ลองตรวจสอบใหม่" }));

    expect(await screen.findByText("ยังไม่ได้ตั้งค่า Gemini API key")).toBeInTheDocument();
    expect(mockRpc.getAiSettings).toHaveBeenCalledTimes(2);
    expect(document.body.textContent).not.toContain("secret-value");
  });

  it.each([
    ["AI_API_KEY_REQUIRED", "กรุณาตั้งค่า Gemini API key ที่หน้าหลักก่อนใช้ OCR"],
    ["AI_API_KEY_INVALID", "Gemini API key ไม่ถูกต้องหรือไม่มีสิทธิ์ใช้งาน กรุณาตรวจสอบที่หน้าหลัก"],
  ])("explains %s save errors without rendering the submitted key", async (code, expectedMessage) => {
    mockRpc.saveAiApiKey.mockRejectedValue(new Error(`${code}: secret-value`));
    render(<AiSettingsCard connectionReady />);
    await screen.findByText("ยังไม่ได้ตั้งค่า Gemini API key");

    const apiKey = screen.getByLabelText("Gemini API key");
    fireEvent.change(apiKey, { target: { value: "secret-value" } });
    fireEvent.click(screen.getByRole("button", { name: "บันทึก API key" }));

    expect(await screen.findByText(expectedMessage)).toBeInTheDocument();
    expect(apiKey).toHaveValue("secret-value");
    expect(document.body.textContent).not.toContain("secret-value");
  });

  it("explains a credential-store failure when deleting a configured key", async () => {
    mockRpc.getAiSettings.mockResolvedValue(geminiSettings(true));
    mockRpc.deleteAiApiKey.mockRejectedValue(new Error("AI_CREDENTIAL_STORE_UNAVAILABLE: secret-value"));
    render(<AiSettingsCard connectionReady />);
    await screen.findByText("ตั้งค่า Gemini API key แล้ว");

    fireEvent.click(screen.getByRole("button", { name: "ลบ API key" }));

    expect(await screen.findByText("ไม่สามารถเข้าถึงที่เก็บ API key ที่ปลอดภัยได้ กรุณาตรวจสอบการตั้งค่า AI ที่หน้าหลัก")).toBeInTheDocument();
    expect(document.body.textContent).not.toContain("secret-value");
  });

  it("uses the safe AI fallback for unknown secret-bearing action errors", async () => {
    mockRpc.saveAiApiKey.mockRejectedValue(new Error("provider error: secret-value"));
    render(<AiSettingsCard connectionReady />);
    await screen.findByText("ยังไม่ได้ตั้งค่า Gemini API key");

    fireEvent.change(screen.getByLabelText("Gemini API key"), { target: { value: "secret-value" } });
    fireEvent.click(screen.getByRole("button", { name: "บันทึก API key" }));

    expect(await screen.findByText("AI ประมวลผลเอกสารไม่สำเร็จ กรุณาลองใหม่")).toBeInTheDocument();
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

  it("uses the safe AI fallback when the Gemini connection test returns an unknown error", async () => {
    mockRpc.testAiConnection.mockRejectedValue(new Error("invalid secret-value"));
    render(<AiSettingsCard connectionReady />);

    fireEvent.click(screen.getByRole("button", { name: "ทดสอบการเชื่อมต่อ" }));

    expect(await screen.findByText("AI ประมวลผลเอกสารไม่สำเร็จ กรุณาลองใหม่")).toBeInTheDocument();
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
