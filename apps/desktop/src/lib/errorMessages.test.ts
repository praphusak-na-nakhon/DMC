import { describe, expect, it } from "vitest";
import { describeAiError, describeUserFacingError, getRuntimeConnectionErrorKind } from "./errorMessages";

describe("error message mapping", () => {
  it("directs users to reinstall a damaged bundled config without leaking details", () => {
    const message = describeUserFacingError("CONFIG_BUNDLED_INVALID: private-path");
    expect(message).toContain("ติดตั้ง");
    expect(message).not.toContain("private-path");
    expect(message).not.toContain("cloud");
  });
  it("classifies missing Tauri IPC as a desktop runtime error", () => {
    const raw = "Cannot read properties of undefined (reading 'transformCallback')";

    expect(getRuntimeConnectionErrorKind(raw)).toBe("desktop");
    expect(describeUserFacingError(raw)).toContain("หน้าต่าง DMC Assistant desktop");
  });

  it("classifies explicit browser-preview runtime errors as desktop runtime errors", () => {
    const raw =
      'DESKTOP_RUNTIME_UNAVAILABLE: Tauri IPC is not available for command "rpc_request". Open this feature in the DMC Assistant desktop window, not browser preview/localhost.';

    expect(getRuntimeConnectionErrorKind(raw)).toBe("desktop");
    expect(describeUserFacingError(raw)).toContain("browser preview/localhost");
  });

  it("does not let sidecar command names override desktop runtime errors", () => {
    const raw =
      'DESKTOP_RUNTIME_UNAVAILABLE: Tauri IPC is not available for command "initialize_sidecar". Open this feature in the DMC Assistant desktop window, not browser preview/localhost.';

    expect(getRuntimeConnectionErrorKind(raw)).toBe("desktop");
    expect(describeUserFacingError(raw)).toContain("browser preview/localhost");
  });

  it("does not mistake unrelated TypeErrors for desktop runtime errors", () => {
    const raw = "Cannot read properties of undefined (reading 'summary')";

    expect(getRuntimeConnectionErrorKind(raw)).toBeNull();
    expect(describeUserFacingError(raw)).toBe("ระบบทำรายการไม่สำเร็จ กรุณาลองอีกครั้ง หากยังเกิดซ้ำให้ส่ง diagnostics ให้ผู้ดูแล");
  });

  it("classifies sidecar failures separately from desktop runtime errors", () => {
    const raw = "Sidecar stdout closed before a response was received.";

    expect(getRuntimeConnectionErrorKind(raw)).toBe("sidecar");
    expect(describeUserFacingError(raw)).toContain("ตัวเชื่อมระบบ");
    expect(describeUserFacingError(raw)).not.toContain("browser preview");
  });

  it("does not classify domain messages that mention sidecar as runtime failures", () => {
    const raw =
      "AI_API_KEY_REQUIRED: secret-key";

    expect(getRuntimeConnectionErrorKind(raw)).toBeNull();
    expect(describeUserFacingError(raw)).toContain("หน้าหลัก");
    expect(describeUserFacingError(raw)).not.toContain("secret-key");
  });
});

it.each(["AI_API_KEY_REQUIRED", "AI_API_KEY_INVALID", "AI_CREDENTIAL_STORE_UNAVAILABLE", "AI_PROVIDER_UNAVAILABLE", "AI_RATE_LIMITED", "AI_REQUEST_TIMEOUT", "AI_RESPONSE_INVALID", "AI_INPUT_UNSUPPORTED", "AI_JOB_FAILED"])("safely translates %s into Thai", (code) => {
  const message = describeUserFacingError(new Error(code + ": secret-key"));
  expect(message).toMatch(/[ก-๙]/);
  expect(message).not.toContain("secret-key");
  expect(describeAiError(new Error(code + ": secret-key"))).toBe(message);
  if (code === "AI_RATE_LIMITED" || code === "AI_REQUEST_TIMEOUT") expect(message).toContain("ลองใหม่");
});
