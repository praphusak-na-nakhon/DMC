import { ArchiveRestore, Database, Download, FileDown, RefreshCw } from "lucide-react";
import { formatTimestamp } from "../lib/appUi";
import { Button } from "./ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./ui/card";
import type { AccountStatus, DatabaseStatus } from "../types/contracts";

type SupportToolsPanelProps = {
  connectionState: "idle" | "connecting" | "ready" | "error";
  databaseStatus: DatabaseStatus | null;
  accountStatus: AccountStatus | null;
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
  accountStatus,
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
            <CardTitle>เครื่องมือช่วยเหลือ</CardTitle>
            <CardDescription>สำรองข้อมูล กู้คืนข้อมูล และสร้างไฟล์วินิจฉัยเมื่อทีมซัพพอร์ตขอ</CardDescription>
          </div>
          <Database className="h-5 w-5 shrink-0 text-primary" />
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-3">
          <Detail label="Database" value={databaseStatus?.path ?? "-"} />
          <div className="grid gap-3 sm:grid-cols-2">
            <Detail label="Schema version" value={databaseStatus?.schema_version ?? "-"} />
            <Detail label="Account" value={accountStatus?.email ?? accountStatus?.user_id ?? "-"} />
            <Detail label="Session expires" value={formatTimestamp(accountStatus?.token_expires_at ?? null)} />
            <Detail label="Available credits" value={accountStatus?.wallet?.available ?? "-"} />
          </div>
          <Detail label="Tables" value={databaseStatus?.tables.join(", ") ?? "-"} />
        </div>

        <div className="flex flex-wrap gap-2">
          <Button size="sm" variant="outline" disabled={disabled} onClick={onRefreshDatabaseStatus}>
            <RefreshCw className="h-4 w-4" />
            ตรวจสถานะฐานข้อมูล
          </Button>
          <Button size="sm" variant="outline" disabled={disabled || isCreatingBackup} onClick={onCreateBackup}>
            <Download className="h-4 w-4" />
            {isCreatingBackup ? "กำลังสำรอง..." : "สำรองข้อมูล"}
          </Button>
          <Button size="sm" variant="secondary" disabled={disabled || isRestoringBackup} onClick={onRestoreBackup}>
            <ArchiveRestore className="h-4 w-4" />
            {isRestoringBackup ? "กำลังกู้คืน..." : "กู้คืนข้อมูล"}
          </Button>
          <Button size="sm" disabled={disabled || isExportingDiagnostics} onClick={onExportDiagnostics}>
            <FileDown className="h-4 w-4" />
            {isExportingDiagnostics ? "กำลังสร้าง..." : "สร้างไฟล์วินิจฉัย"}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
