import { ArchiveRestore, Database, Download, FileDown, RefreshCw } from "lucide-react";
import { formatTimestamp } from "../lib/appUi";
import { Button } from "./ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./ui/card";
import type { DatabaseStatus, LicenseStatus } from "../types/contracts";

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

function Detail({ label, value }: { label: string; value: string | number | null | undefined }) {
  return (
    <div className="grid gap-0.5 text-sm">
      <span className="text-muted-foreground">{label}</span>
      <span className="min-w-0 break-words font-medium">{value ?? "-"}</span>
    </div>
  );
}

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
  const disabled = connectionState !== "ready";

  return (
    <Card className="min-w-0">
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-3">
          <div>
            <CardTitle>Support Tools</CardTitle>
            <CardDescription>เครื่องมือสำหรับ backup, restore และส่ง diagnostics</CardDescription>
          </div>
          <Database className="h-5 w-5 shrink-0 text-primary" />
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-3">
          <Detail label="Database" value={databaseStatus?.path ?? "-"} />
          <div className="grid gap-3 sm:grid-cols-2">
            <Detail label="Schema version" value={databaseStatus?.schema_version ?? "-"} />
            <Detail label="License tier" value={licenseStatus?.license_tier ?? "-"} />
            <Detail label="Expires" value={formatTimestamp(licenseStatus?.expires_at ?? null)} />
            <Detail label="Offline grace" value={formatTimestamp(licenseStatus?.offline_grace_until ?? null)} />
          </div>
          <Detail label="Tables" value={databaseStatus?.tables.join(", ") ?? "-"} />
        </div>

        <div className="flex flex-wrap gap-2">
          <Button size="sm" variant="outline" disabled={disabled} onClick={onRefreshDatabaseStatus}>
            <RefreshCw className="h-4 w-4" />
            Refresh DB
          </Button>
          <Button size="sm" variant="outline" disabled={disabled || isCreatingBackup} onClick={onCreateBackup}>
            <Download className="h-4 w-4" />
            {isCreatingBackup ? "Creating..." : "Export Backup"}
          </Button>
          <Button size="sm" variant="secondary" disabled={disabled || isRestoringBackup} onClick={onRestoreBackup}>
            <ArchiveRestore className="h-4 w-4" />
            {isRestoringBackup ? "Restoring..." : "Restore Backup"}
          </Button>
          <Button size="sm" disabled={disabled || isExportingDiagnostics} onClick={onExportDiagnostics}>
            <FileDown className="h-4 w-4" />
            {isExportingDiagnostics ? "Exporting..." : "Diagnostics"}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
