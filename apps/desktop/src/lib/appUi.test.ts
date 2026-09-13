import { describe, expect, it } from "vitest";
import { buildDraftJob, buildSupportDiagnostics } from "./appUi";
describe("local job UI", () => {
  it("builds a credit-free draft with local progress and DMC auth fields", () => {
    const draft = buildDraftJob("C:/local/students.xlsx", 2, "job-local");
    expect(draft).toMatchObject({ job_id: "job-local", source_file: "C:/local/students.xlsx", total: 2, processed: 0, needs_auth: false });
    expect(Object.keys(draft).some((key) => key.includes("credit"))).toBe(false);
  });
  it("exports local diagnostics without account data or sensitive job paths", () => {
    const output = buildSupportDiagnostics({
      appVersion: "0.1.0", platform: "Win32", connectionState: "ready",
      databaseStatus: { path: "local.sqlite3", schema_generation: 2, tables: ["job"], job_columns: ["id"] },
      browserRuntimeStatus: null,
      currentJob: buildDraftJob("private-student-path.xlsx", 2, "job-local"), existingJobs: [],
      sidecarMessageCount: 0, hasErrorMessage: false,
    });
    expect(output.database_status).toMatchObject({ schema_generation: 2, tables: ["job"], job_columns: ["id"] });
    expect(output.current_job).toMatchObject({ job_id: "job-local", total: 2 });
    expect(output).not.toHaveProperty("updater_status");
    expect(output).not.toHaveProperty("available_update");
    expect(JSON.stringify(output)).not.toMatch(/account|credit|private-student-path|module_config/);
  });
});
