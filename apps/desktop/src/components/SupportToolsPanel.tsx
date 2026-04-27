import { buttonStyle, cardStyle, formatTimestamp } from "../lib/appUi";
import type { DatabaseStatus, LicenseStatus } from "../types/contracts";

const pathTextStyle = {
  minWidth: 0,
  overflowWrap: "anywhere",
  wordBreak: "break-word",
} as const;

type SupportToolsPanelProps = {
  connectionState: "idle" | "connecting" | "ready" | "error";
  databaseStatus: DatabaseStatus | null;
  licenseStatus: LicenseStatus | null;
  isCreatingBackup: boolean;
  isRestoringBackup: boolean;
  isExportingDiagnostics: boolean;
  onRefreshDatabaseStatus: () => void;
  onCreateBackup: () => void;
  onRestoreBackup: () => void;
  onExportDiagnostics: () => void;
};

export function SupportToolsPanel({
  connectionState,
  databaseStatus,
  licenseStatus,
  isCreatingBackup,
  isRestoringBackup,
  isExportingDiagnostics,
  onRefreshDatabaseStatus,
  onCreateBackup,
  onRestoreBackup,
  onExportDiagnostics,
}: SupportToolsPanelProps) {
  return (
    <section style={{ ...cardStyle, minWidth: 0 }}>
      <h2 style={{ marginTop: 0 }}>Support Tools</h2>
      <div style={{ display: "grid", gap: "10px", color: "rgb(51, 65, 85)", lineHeight: 1.6 }}>
        <div style={pathTextStyle}>
          <strong>Database:</strong> {databaseStatus?.path ?? "-"}
        </div>
        <div>
          <strong>Schema version:</strong> {databaseStatus?.schema_version ?? "-"}
        </div>
        <div style={pathTextStyle}>
          <strong>Tables:</strong> {databaseStatus?.tables.join(", ") ?? "-"}
        </div>
        <div>
          <strong>License tier:</strong> {licenseStatus?.license_tier ?? "-"}
        </div>
        <div>
          <strong>Expires:</strong> {formatTimestamp(licenseStatus?.expires_at ?? null)}
        </div>
        <div>
          <strong>Offline grace:</strong> {formatTimestamp(licenseStatus?.offline_grace_until ?? null)}
        </div>
      </div>
      <div style={{ display: "flex", gap: "8px", marginTop: "14px", flexWrap: "wrap" }}>
        <button
          style={{ ...buttonStyle, padding: "8px 12px", backgroundColor: "rgb(8, 145, 178)" }}
          disabled={connectionState !== "ready"}
          onClick={onRefreshDatabaseStatus}
        >
          Refresh DB Status
        </button>
        <button
          style={{ ...buttonStyle, padding: "8px 12px", backgroundColor: "rgb(37, 99, 235)" }}
          disabled={connectionState !== "ready" || isCreatingBackup}
          onClick={onCreateBackup}
        >
          {isCreatingBackup ? "Creating Backup..." : "Export Backup"}
        </button>
        <button
          style={{ ...buttonStyle, padding: "8px 12px", backgroundColor: "rgb(202, 138, 4)" }}
          disabled={connectionState !== "ready" || isRestoringBackup}
          onClick={onRestoreBackup}
        >
          {isRestoringBackup ? "Restoring..." : "Restore Backup"}
        </button>
        <button
          style={{ ...buttonStyle, padding: "8px 12px", backgroundColor: "rgb(99, 102, 241)" }}
          disabled={connectionState !== "ready" || isExportingDiagnostics}
          onClick={onExportDiagnostics}
        >
          {isExportingDiagnostics ? "Exporting..." : "Export Diagnostics"}
        </button>
      </div>
    </section>
  );
}
