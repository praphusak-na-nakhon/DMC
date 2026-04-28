import { FileSpreadsheet, GraduationCap, Loader2, RefreshCw, UploadCloud, UserPlus } from "lucide-react";
import { formatTimestamp } from "../lib/appUi";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./ui/card";
import { SupportToolsPanel } from "./SupportToolsPanel";
import type { AvailableUpdate, DatabaseStatus, LicenseStatus, UpdaterStatus } from "../types/contracts";

type ModuleHomeProps = {
  onOpenGraduation: () => void;
  updaterStatus: UpdaterStatus | null;
  availableUpdate: AvailableUpdate | null;
  updateMessage: string | null;
  updateProgress: { downloaded: number; contentLength: number | null } | null;
  isCheckingUpdate: boolean;
  isInstallingUpdate: boolean;
  connectionState: "idle" | "connecting" | "ready" | "error";
  databaseStatus: DatabaseStatus | null;
  licenseStatus: LicenseStatus | null;
  isCreatingBackup: boolean;
  isRestoringBackup: boolean;
  isExportingDiagnostics: boolean;
  onCheckForUpdates: () => void;
  onInstallUpdate: () => void;
  onRefreshDatabaseStatus: () => void;
  onCreateBackup: () => void;
  onRestoreBackup: () => void;
  onExportDiagnostics: () => void;
};

type ModuleCard = {
  title: string;
  description: string;
  status: "ready" | "planned";
  icon: typeof GraduationCap;
  onClick?: () => void;
};

export function ModuleHome({
  onOpenGraduation,
  updaterStatus,
  availableUpdate,
  updateMessage,
  updateProgress,
  isCheckingUpdate,
  isInstallingUpdate,
  connectionState,
  databaseStatus,
  licenseStatus,
  isCreatingBackup,
  isRestoringBackup,
  isExportingDiagnostics,
  onCheckForUpdates,
  onInstallUpdate,
  onRefreshDatabaseStatus,
  onCreateBackup,
  onRestoreBackup,
  onExportDiagnostics,
}: ModuleHomeProps) {
  const modules: ModuleCard[] = [
    {
      title: "แปลงเอกสารแบบฟอร์ม DMC เป็น Excel",
      description: "เตรียมข้อมูลจากเอกสารแบบฟอร์มให้เป็นไฟล์ Excel สำหรับนำไปใช้ต่อในงาน DMC",
      status: "planned",
      icon: FileSpreadsheet,
    },
    {
      title: "นักเรียนปัจจุบัน (ย้ายเข้า/เพิ่มนักเรียน)",
      description: "จัดการรายการนักเรียนปัจจุบัน งานย้ายเข้า และการเพิ่มนักเรียนใหม่",
      status: "planned",
      icon: UserPlus,
    },
    {
      title: "ข้อมูลสิ้นปีการศึกษา (สอบได้ เรียนจบ)",
      description: "ตรวจไฟล์ Excel, dry run, กรอกข้อมูลจบการศึกษาใน DMC และสรุปรายงานหลังจบงาน",
      status: "ready",
      icon: GraduationCap,
      onClick: onOpenGraduation,
    },
  ];

  return (
    <div className="space-y-6">
      <header className="flex min-w-0 flex-col gap-4 border-b pb-6 lg:flex-row lg:items-end lg:justify-between">
        <div className="min-w-0">
          <Badge variant="secondary" className="mb-3 uppercase tracking-normal">
            DMC Assistant
          </Badge>
          <h1 className="text-3xl font-bold tracking-normal text-foreground sm:text-4xl">
            DMC Assistant
          </h1>
          <p className="mt-3 max-w-2xl text-sm leading-7 text-muted-foreground sm:text-base">
            เลือกเครื่องมือที่ต้องการใช้งาน ระบบจะแยก workflow แต่ละงานให้ชัดเจน เพื่อลดการกดผิดและทำงานซ้ำได้ง่าย
          </p>
        </div>
      </header>

      <section className="grid gap-4 lg:grid-cols-3">
        {modules.map((module) => {
          const Icon = module.icon;
          const isReady = module.status === "ready";
          return (
            <Card
              key={module.title}
              className={`flex min-h-[260px] min-w-0 flex-col transition-colors ${
                isReady ? "hover:border-primary/40 hover:bg-muted/30" : "opacity-75"
              }`}
            >
              <CardHeader>
                <div className="mb-4 flex items-center justify-between gap-3">
                  <div className="flex h-11 w-11 items-center justify-center rounded-lg border bg-background">
                    <Icon className="h-5 w-5 text-muted-foreground" />
                  </div>
                  <Badge variant={isReady ? "default" : "secondary"}>
                    {isReady ? "พร้อมใช้งาน" : "เตรียมเปิดใช้งาน"}
                  </Badge>
                </div>
                <CardTitle className="leading-7">{module.title}</CardTitle>
                <CardDescription className="leading-6">{module.description}</CardDescription>
              </CardHeader>
              <CardContent className="mt-auto">
                <Button
                  className="w-full"
                  variant={isReady ? "default" : "secondary"}
                  disabled={!isReady}
                  onClick={module.onClick}
                >
                  {isReady ? "เปิดใช้งาน" : "ยังไม่เปิดใช้งาน"}
                </Button>
              </CardContent>
            </Card>
          );
        })}
      </section>

      <section className="grid gap-4 xl:grid-cols-[minmax(0,1.1fr)_minmax(360px,0.9fr)]">
        <Card>
          <CardHeader className="pb-3">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
              <div>
                <CardTitle>App Updates</CardTitle>
                <CardDescription>
                  เช็กและติดตั้งอัปเดตของ DMC Assistant ทั้งระบบ ไม่ผูกกับโมดูลใดโมดูลหนึ่ง
                </CardDescription>
              </div>
              <Badge variant={updaterStatus?.configured ? "default" : "secondary"}>
                {updaterStatus?.configured ? "พร้อมใช้งาน" : "ยังไม่ตั้งค่า"}
              </Badge>
            </div>
          </CardHeader>
          <CardContent className="grid gap-4">
            <div className="grid gap-3 lg:grid-cols-3">
              <div className="rounded-lg border bg-muted/40 p-3">
                <div className="text-xs text-muted-foreground">เวอร์ชันปัจจุบัน</div>
                <div className="mt-1 font-semibold">{updaterStatus?.current_version ?? "-"}</div>
              </div>
              <div className="rounded-lg border bg-muted/40 p-3 lg:col-span-2">
                <div className="text-xs text-muted-foreground">Endpoint</div>
                <div className="mt-1 break-words text-sm font-medium">{updaterStatus?.endpoint ?? "-"}</div>
              </div>
            </div>

            <div className="flex flex-wrap gap-2">
              <Button variant="outline" disabled={isCheckingUpdate} onClick={onCheckForUpdates}>
                {isCheckingUpdate ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
                เช็กอัปเดตทั้งระบบ
              </Button>
              <Button disabled={!availableUpdate || isInstallingUpdate} onClick={onInstallUpdate}>
                {isInstallingUpdate ? <Loader2 className="h-4 w-4 animate-spin" /> : <UploadCloud className="h-4 w-4" />}
                ติดตั้งอัปเดต
              </Button>
            </div>

            {availableUpdate ? (
              <div className="grid gap-1 rounded-lg border bg-muted/40 p-3 text-sm text-muted-foreground">
                <div className="font-medium text-foreground">พบเวอร์ชันใหม่: {availableUpdate.version}</div>
                <div>เผยแพร่เมื่อ: {formatTimestamp(availableUpdate.date)}</div>
                <div className="break-words">รายละเอียด: {availableUpdate.body ?? "-"}</div>
              </div>
            ) : null}

            {updateProgress ? (
              <div className="text-sm text-muted-foreground">
                ดาวน์โหลดแล้ว {updateProgress.downloaded}
                {updateProgress.contentLength ? ` / ${updateProgress.contentLength}` : ""} bytes
              </div>
            ) : null}

            {updateMessage ? <div className="break-words text-sm text-muted-foreground">{updateMessage}</div> : null}
          </CardContent>
        </Card>

        <SupportToolsPanel
          connectionState={connectionState}
          databaseStatus={databaseStatus}
          licenseStatus={licenseStatus}
          isCreatingBackup={isCreatingBackup}
          isRestoringBackup={isRestoringBackup}
          isExportingDiagnostics={isExportingDiagnostics}
          onRefreshDatabaseStatus={onRefreshDatabaseStatus}
          onCreateBackup={onCreateBackup}
          onRestoreBackup={onRestoreBackup}
          onExportDiagnostics={onExportDiagnostics}
        />
      </section>
    </div>
  );
}
