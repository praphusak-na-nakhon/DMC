import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { App } from "./App";
import messages from "./i18n/th.json";
import { useJobStore } from "./stores/useJobStore";

vi.mock("@tauri-apps/api/core", () => ({ invoke: vi.fn() }));
vi.mock("@tauri-apps/api/event", () => ({ listen: vi.fn() }));
vi.mock("@tauri-apps/api/window", () => ({
  getCurrentWindow: () => ({ onCloseRequested: async () => () => {}, requestUserAttention: async () => {} }),
  UserAttentionType: { Informational: 1 },
}));
const calls: string[] = [];
beforeEach(() => {
  useJobStore.getState().reset();
  calls.length = 0;
  Object.assign(window, { __TAURI_INTERNALS__: {} });
  vi.mocked(listen).mockResolvedValue(() => {});
  vi.mocked(invoke).mockImplementation(async (command, args) => {
    if (command === "initialize_sidecar") { calls.push(command); return; }
    if (command !== "rpc_request") throw new Error("Unexpected native command: " + command);
    const { method } = JSON.parse((args as { requestJson: string }).requestJson);
    calls.push(method);
    switch (method) {
      case "get_ai_settings": return { provider: "gemini", configured: false };
      case "get_database_status": return { path: "local.sqlite3", schema_generation: 2, tables: ["job"], job_columns: ["id"] };
      case "list_jobs": return { items: [] };
      case "get_browser_runtime_status": return { state: "ready", installed: true, install_dir: "browser", executable_path: "browser/chrome.exe", bootstrap_supported: true, bootstrap_performed: false, estimated_download_bytes: null, required_components: [], message: null, guidance: null, last_error: null, log_tail: [] };
      default: throw new Error("Unsupported local RPC: " + method);
    }
  });
});
afterEach(cleanup);

it("starts locally with four visible modules and AI settings using only retained native commands", async () => {
  await act(async () => { render(<App />); });
  await waitFor(() => expect(calls).toContain("get_browser_runtime_status"));
  expect(useJobStore.getState().connectionState).toBe("ready");
  expect(useJobStore.getState().errorMessage).toBeNull();
  for (const id of ["formConverter", "studentBasicInfo", "currentStudents", "graduation"] as const) {
    expect(screen.getByRole("button", { name: messages.app.home.moduleActions[id] })).toBeVisible();
  }
  expect(screen.getByText(messages.app.home.aiSettings.title)).toBeVisible();
  expect(vi.mocked(listen).mock.calls.map(([event]) => event)).toEqual(["sidecar-event"]);
  expect(calls).toEqual(expect.arrayContaining(["initialize_sidecar", "get_database_status", "list_jobs", "get_ai_settings"]));
  expect(calls).not.toEqual(expect.arrayContaining(["get_account_status"]));
  expect(calls.some((method) => /account|catalog|wallet|sign_in|module_config/.test(method))).toBe(false);
  expect(screen.queryByText(/เครดิต|เข้าสู่ระบบ|License/i)).not.toBeInTheDocument();
});
