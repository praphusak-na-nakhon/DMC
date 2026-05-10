import { describe, expect, it } from "vitest";
import { describeUserFacingError, getRuntimeConnectionErrorKind } from "./errorMessages";

describe("error message mapping", () => {
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
});
