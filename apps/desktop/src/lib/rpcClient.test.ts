import { invoke } from "@tauri-apps/api/core";
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  deleteAiApiKey,
  getAiSettings,
  ocrDocument,
  saveAiApiKey,
  testAiConnection,
} from "./rpcClient";

vi.mock("@tauri-apps/api/core", () => ({ invoke: vi.fn() }));
vi.mock("@tauri-apps/api/event", () => ({ listen: vi.fn() }));

const invokeMock = vi.mocked(invoke);

beforeEach(() => {
  Object.assign(window, { __TAURI_INTERNALS__: {} });
  invokeMock.mockReset();
  invokeMock.mockImplementation(async (_command, args) => {
    const request = JSON.parse((args as { requestJson: string }).requestJson) as {
      method: string;
    };
    if (request.method === "test_ai_connection") {
      return {
        provider: "gemini",
        ok: true,
        tested_at: "2026-09-04T00:00:00+00:00",
        message: "Connection succeeded.",
      };
    }
    if (request.method === "ocr_document") {
      return {
        module: "formConverter",
        provider: "gemini",
        model: "gemini-3.5-flash",
        processing_mode: "batch",
        source_path: "C:\\dmc\\source.pdf",
        markdown_path: "C:\\dmc\\output.md",
        structured_json_path: null,
        output_format: "structured_json",
        cached: false,
        pages_processed: 1,
        pages_estimated: 1,
        average_confidence: null,
        usage_metadata: null,
        provider_job_id: null,
        provider_job_state: null,
        file_sha256: "abc123",
        created_at: "2026-09-04T00:00:00+00:00",
      };
    }
    return { provider: "gemini", configured: request.method === "save_ai_api_key" };
  });
});

describe("AI RPC client", () => {
  it("serializes provider-neutral AI requests with snake_case parameters", async () => {
    await expect(getAiSettings("gemini")).resolves.toEqual({ provider: "gemini", configured: false });
    await expect(saveAiApiKey("gemini", "test-api-key")).resolves.toEqual({ provider: "gemini", configured: true });
    await expect(testAiConnection("gemini")).resolves.toMatchObject({ ok: true });
    await expect(deleteAiApiKey("gemini")).resolves.toEqual({ provider: "gemini", configured: false });
    await expect(
      ocrDocument({
        provider: "gemini",
        sourcePath: "C:\\dmc\\source.pdf",
        model: "gemini-3.5-flash",
        processingMode: "batch",
        forceRefresh: true,
      }),
    ).resolves.toMatchObject({ pages_processed: 1, provider_job_id: null });

    const requests = invokeMock.mock.calls.map(([, args]) =>
      JSON.parse((args as { requestJson: string }).requestJson),
    );
    expect(requests.map((request) => request.method)).toEqual([
      "get_ai_settings",
      "save_ai_api_key",
      "test_ai_connection",
      "delete_ai_api_key",
      "ocr_document",
    ]);
    expect(requests[1].params).toEqual({ provider: "gemini", api_key: "test-api-key" });
    expect(requests[4].params).toEqual({
      provider: "gemini",
      source_path: "C:\\dmc\\source.pdf",
      model: "gemini-3.5-flash",
      processing_mode: "batch",
      force_refresh: true,
    });
  });
});
