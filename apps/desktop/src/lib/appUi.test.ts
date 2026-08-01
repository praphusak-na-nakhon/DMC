import { describe, expect, it } from "vitest";
import { describeCreditStatus } from "./appUi";

describe("describeCreditStatus", () => {
  it("describes cloud-unavailable start failure as a blocking error", () => {
    const status = describeCreditStatus("start_failed:ACCOUNT_CLOUD_UNAVAILABLE");

    expect(status?.tone).toBe("danger");
    expect(status?.message).toContain("cloud");
  });

  it("describes cloud-unavailable finalize failure as a retryable warning", () => {
    const status = describeCreditStatus("finalize_failed:ACCOUNT_CLOUD_UNAVAILABLE");

    expect(status?.tone).toBe("warning");
    expect(status?.message).toContain("ลอง");
  });
});
