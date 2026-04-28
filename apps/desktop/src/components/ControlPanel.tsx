import {
  AlertCircle,
  CheckCircle2,
  CloudCog,
  DatabaseZap,
  FileCheck2,
  FileSpreadsheet,
  FolderOpen,
  KeyRound,
  Loader2,
  LogIn,
  Pause,
  Play,
  RefreshCw,
  SearchCheck,
  ShieldCheck,
  Square,
  UploadCloud,
} from "lucide-react";
import messages from "../i18n/th.json";
import {
  describeBrowserRuntimePhase,
  formatBytes,
  formatTimestamp,
} from "../lib/appUi";
import { Alert, AlertDescription, AlertTitle } from "./ui/alert";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./ui/card";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { Progress } from "./ui/progress";
import { Separator } from "./ui/separator";
import { Switch } from "./ui/switch";
import type {
  BrowserRuntimeStatus,
  LicenseStatus,
  ModuleConfigStatus,
} from "../types/contracts";

type BrowserRuntimeProgress = {
  phase: "checking" | "installing" | "verifying" | "ready" | "failed";
  message: string;
  percent: number | null;
  detail: string | null;
} | null;

type ConnectionState = "idle" | "connecting" | "ready" | "error";

type ControlPanelProps = {
  connectionState: ConnectionState;
  licenseStatus: LicenseStatus | null;
  moduleConfigStatus: ModuleConfigStatus | null;
  browserRuntimeStatus: BrowserRuntimeStatus | null;
  browserRuntimeProgress: BrowserRuntimeProgress;
  supportMessage: string | null;
  errorMessage: string | null;
  licenseKey: string;
  deviceName: string;
  excelPath: string;
  minScore: number;
  stopOnReview: boolean;
  isValidating: boolean;
  isStartingJob: boolean;
  isActivatingLicense: boolean;
  isBootstrappingBrowser: boolean;
  licenseBlocksStart: boolean;
  browserRuntimeBlocksStart: boolean;
  validationBlocksStart: boolean;
  preflightRowsAccepted: number | null;
  preflightRowsTotal: number | null;
  onLicenseKeyChange: (value: string) => void;
  onDeviceNameChange: (value: string) => void;
  onExcelPathChange: (value: string) => void;
  onMinScoreChange: (value: number) => void;
  onStopOnReviewChange: (value: boolean) => void;
  onConnect: () => void;
  onRefreshJobs: () => void;
  onRefreshLicense: () => void;
  onSyncConfig: () => void;
  onValidate: () => void;
  onStartDryRun: () => void;
  onStartLive: () => void;
  onRefreshStatus: () => void;
  onPause: () => void;
  onResume: () => void;
  onCancel: () => void;
  onActivateLicense: () => void;
  onBrowseFile: () => void;
  onBootstrapBrowserRuntime: () => void;
  onReloadBrowserRuntime: () => void;
  describeLicenseStatus: (status: LicenseStatus) => string;
  activeJobId: string | null;
  currentJobNeedsAuth: boolean;
};

function connectionLabel(state: ConnectionState) {
  if (state === "ready") return messages.app.connected;
  if (state === "connecting") return messages.app.connecting;
  if (state === "error") return "Sidecar error";
  return "ยังไม่ได้เชื่อมต่อ";
}

function statusBadgeClass(state: ConnectionState) {
  if (state === "error") return "border-destructive/50 text-destructive";
  return "border-border bg-secondary text-secondary-foreground";
}

function DetailRow({ label, value }: { label: string; value: string | number | null | undefined }) {
  return (
    <div className="grid gap-0.5 text-sm">
      <span className="text-muted-foreground">{label}</span>
      <span className="min-w-0 break-words font-medium text-foreground">{value ?? "-"}</span>
    </div>
  );
}

function StatusTile({
  title,
  description,
  tone = "muted",
  icon: Icon,
}: {
  title: string;
  description: string;
  tone?: "success" | "warning" | "destructive" | "muted" | "info";
  icon: typeof CheckCircle2;
}) {
  const toneClass = {
    success: "border-border bg-card text-foreground",
    warning: "border-border bg-card text-foreground",
    destructive: "border-destructive/50 bg-card text-destructive",
    muted: "border-border bg-card text-muted-foreground",
    info: "border-border bg-card text-foreground",
  }[tone];

  return (
    <div className={`min-w-0 rounded-lg border p-3 ${toneClass}`}>
      <div className="flex min-w-0 items-center gap-2">
        <Icon className="h-4 w-4 shrink-0" />
        <div className="min-w-0 truncate text-sm font-semibold">{title}</div>
      </div>
      <div className="mt-1 min-w-0 break-words text-xs leading-relaxed text-foreground/70">{description}</div>
    </div>
  );
}

export function ControlPanel({
  connectionState,
  licenseStatus,
  moduleConfigStatus,
  browserRuntimeStatus,
  browserRuntimeProgress,
  supportMessage,
  errorMessage,
  licenseKey,
  deviceName,
  excelPath,
  minScore,
  stopOnReview,
  isValidating,
  isStartingJob,
  isActivatingLicense,
  isBootstrappingBrowser,
  licenseBlocksStart,
  browserRuntimeBlocksStart,
  validationBlocksStart,
  preflightRowsAccepted,
  preflightRowsTotal,
  onLicenseKeyChange,
  onDeviceNameChange,
  onExcelPathChange,
  onMinScoreChange,
  onStopOnReviewChange,
  onConnect,
  onRefreshJobs,
  onRefreshLicense,
  onSyncConfig,
  onValidate,
  onStartDryRun,
  onStartLive,
  onRefreshStatus,
  onPause,
  onResume,
  onCancel,
  onActivateLicense,
  onBrowseFile,
  onBootstrapBrowserRuntime,
  onReloadBrowserRuntime,
  describeLicenseStatus,
  activeJobId,
  currentJobNeedsAuth,
}: ControlPanelProps) {
  const runtimeReady = browserRuntimeStatus?.installed ?? false;
  const canStart = !isStartingJob && !isBootstrappingBrowser && !licenseBlocksStart && !browserRuntimeBlocksStart && !validationBlocksStart;

  return (
    <div className="space-y-4">
      <div className="flex min-w-0 flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0 max-w-3xl">
          <Badge variant="secondary" className="mb-3 uppercase tracking-normal">
            {messages.app.tagline}
          </Badge>
          <h1 className="text-3xl font-bold tracking-normal text-foreground sm:text-4xl">
            {messages.app.title}
          </h1>
          <p className="mt-3 max-w-2xl text-sm leading-7 text-muted-foreground sm:text-base">
            {messages.app.description}
          </p>
        </div>

        <Card className="w-full shrink-0 shadow-none lg:w-[320px]">
          <CardHeader className="p-4 pb-2">
            <div className="flex items-center justify-between gap-3">
              <CardDescription>Sidecar</CardDescription>
              <Badge variant="outline" className={statusBadgeClass(connectionState)}>
                {connectionLabel(connectionState)}
              </Badge>
            </div>
          </CardHeader>
          <CardContent className="grid gap-2 p-4 pt-0 text-sm">
            <DetailRow label={messages.app.license.title} value={licenseStatus ? describeLicenseStatus(licenseStatus) : "-"} />
            <DetailRow label={messages.app.license.lastChecked} value={formatTimestamp(licenseStatus?.last_checked_at ?? null)} />
            <DetailRow
              label="Config"
              value={moduleConfigStatus ? `${moduleConfigStatus.version} (${moduleConfigStatus.source})` : "-"}
            />
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader className="pb-3">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <CardTitle>เริ่มงาน DMC</CardTitle>
              <CardDescription>เลือกไฟล์ ตรวจข้อมูล แล้วค่อยเริ่ม dry run หรือกรอกจริง</CardDescription>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button variant="outline" size="sm" onClick={onConnect} disabled={connectionState === "connecting"}>
                {connectionState === "connecting" ? <Loader2 className="h-4 w-4 animate-spin" /> : <DatabaseZap className="h-4 w-4" />}
                {messages.app.connect}
              </Button>
              <Button variant="outline" size="sm" onClick={onRefreshJobs}>
                <RefreshCw className="h-4 w-4" />
                {messages.app.refreshJobs}
              </Button>
            </div>
          </div>
        </CardHeader>

        <CardContent className="space-y-4">
          <div className="grid gap-3 rounded-lg border bg-muted/40 p-3 lg:grid-cols-[1fr_auto] lg:items-end">
            <div className="grid min-w-0 gap-2">
              <Label htmlFor="excel-path">{messages.app.filePathLabel}</Label>
              <div className="flex min-w-0 gap-2">
                <Input
                  id="excel-path"
                  value={excelPath}
                  onChange={(event) => onExcelPathChange(event.target.value)}
                  placeholder={messages.app.filePathPlaceholder}
                  className="min-w-0"
                />
                <Button type="button" variant="outline" onClick={onBrowseFile}>
                  <FolderOpen className="h-4 w-4" />
                  {messages.app.browse}
                </Button>
              </div>
            </div>

            <div className="flex flex-wrap gap-2">
              <Button type="button" variant="outline" onClick={onValidate} disabled={isValidating}>
                {isValidating ? <Loader2 className="h-4 w-4 animate-spin" /> : <SearchCheck className="h-4 w-4" />}
                {messages.app.validate}
              </Button>
              <Button type="button" variant="secondary" disabled={!canStart} onClick={onStartDryRun}>
                <FileCheck2 className="h-4 w-4" />
                {messages.app.startDryRun}
              </Button>
              <Button type="button" disabled={!canStart} onClick={onStartLive}>
                <Play className="h-4 w-4" />
                {messages.app.startLive}
              </Button>
            </div>
          </div>

          <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_minmax(260px,0.45fr)]">
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              <StatusTile
                icon={connectionState === "ready" ? CheckCircle2 : AlertCircle}
                title="Sidecar"
                description={connectionLabel(connectionState)}
                tone={connectionState === "ready" ? "success" : connectionState === "error" ? "destructive" : "warning"}
              />
              <StatusTile
                icon={licenseStatus?.can_start_jobs ? ShieldCheck : KeyRound}
                title="License"
                description={licenseStatus ? describeLicenseStatus(licenseStatus) : "ยังไม่ได้โหลดสถานะ"}
                tone={licenseStatus?.can_start_jobs ? "success" : licenseStatus ? "warning" : "muted"}
              />
              <StatusTile
                icon={runtimeReady ? CheckCircle2 : UploadCloud}
                title="Chromium"
                description={browserRuntimeStatus?.message ?? "ยังไม่ได้ตรวจ runtime"}
                tone={runtimeReady ? "success" : browserRuntimeStatus ? "warning" : "muted"}
              />
              <StatusTile
                icon={validationBlocksStart ? FileSpreadsheet : CheckCircle2}
                title="Preflight"
                description={
                  validationBlocksStart
                    ? "ยังไม่ได้ตรวจไฟล์ล่าสุด"
                    : `ผ่านแล้ว ${preflightRowsAccepted ?? 0}/${preflightRowsTotal ?? "-"} รายการ`
                }
                tone={validationBlocksStart ? "warning" : "success"}
              />
            </div>

            <div className="grid gap-3 rounded-lg border bg-card p-3">
              <div className="grid grid-cols-[1fr_auto] items-center gap-3">
                <Label htmlFor="min-score">{messages.app.minScoreLabel}</Label>
                <Input
                  id="min-score"
                  type="number"
                  min={0}
                  max={100}
                  value={minScore}
                  onChange={(event) => onMinScoreChange(Number(event.target.value))}
                  className="h-9 w-20 text-right"
                />
              </div>
              <Separator />
              <div className="flex items-center justify-between gap-3">
                <Label htmlFor="stop-on-review" className="leading-5">
                  {messages.app.stopOnReview}
                </Label>
                <Switch id="stop-on-review" checked={stopOnReview} onCheckedChange={onStopOnReviewChange} />
              </div>
            </div>
          </div>

          <div className="flex flex-wrap gap-2">
            <Button variant="outline" size="sm" disabled={!activeJobId} onClick={onRefreshStatus}>
              <RefreshCw className="h-4 w-4" />
              {messages.app.refreshStatus}
            </Button>
            <Button variant="outline" size="sm" disabled={!activeJobId} onClick={onPause}>
              <Pause className="h-4 w-4" />
              {messages.app.pause}
            </Button>
            <Button size="sm" variant="secondary" disabled={!currentJobNeedsAuth} onClick={onResume}>
              <LogIn className="h-4 w-4" />
              {messages.app.resume}
            </Button>
            <Button variant="destructive" size="sm" disabled={!activeJobId} onClick={onCancel}>
              <Square className="h-4 w-4" />
              {messages.app.cancel}
            </Button>
            <Button variant="outline" size="sm" onClick={onRefreshLicense}>
              <ShieldCheck className="h-4 w-4" />
              {messages.app.license.refresh}
            </Button>
            <Button variant="outline" size="sm" onClick={onSyncConfig}>
              <CloudCog className="h-4 w-4" />
              {messages.app.syncConfig}
            </Button>
          </div>

          {validationBlocksStart ? (
            <Alert className="bg-muted/40">
              <AlertTitle>ต้องตรวจไฟล์ก่อนเริ่มงาน</AlertTitle>
              <AlertDescription>
                กรุณากดตรวจไฟล์ Excel ให้ผ่านก่อน และตรวจใหม่ทุกครั้งหลังเปลี่ยนไฟล์
              </AlertDescription>
            </Alert>
          ) : (
            <Alert className="bg-muted/40">
              <AlertTitle>Preflight ผ่านแล้ว</AlertTitle>
              <AlertDescription>
                งานจริงจะเขียนข้อมูล {preflightRowsAccepted ?? 0}
                {preflightRowsTotal !== null ? ` จาก ${preflightRowsTotal}` : ""} รายการลง DMC และจะถามยืนยันอีกครั้งก่อนเริ่ม
              </AlertDescription>
            </Alert>
          )}

          <p className="text-sm leading-6 text-muted-foreground">{messages.app.dryRunHint}</p>
          <p className="text-sm leading-6 text-muted-foreground">{messages.app.authHint}</p>

          <div className="grid gap-3 lg:grid-cols-2">
            <Alert
              className={
                licenseStatus?.needs_attention
                  ? "bg-muted/40"
                  : "bg-muted/40"
              }
            >
              <AlertTitle>{messages.app.license.title}</AlertTitle>
              <AlertDescription className="grid gap-1">
                <div>{licenseStatus ? describeLicenseStatus(licenseStatus) : "-"}</div>
                <div>{messages.app.license.expiresAt}: {formatTimestamp(licenseStatus?.expires_at ?? null)}</div>
                <div>{messages.app.license.offlineGraceUntil}: {formatTimestamp(licenseStatus?.offline_grace_until ?? null)}</div>
                {licenseStatus?.last_error ? <div>{messages.app.license.lastError}: {licenseStatus.last_error}</div> : null}
              </AlertDescription>
            </Alert>

            <Alert
              className={
                moduleConfigStatus?.last_error
                  ? "bg-muted/40"
                  : "bg-muted/40"
              }
            >
              <AlertTitle>{messages.app.configStatus}</AlertTitle>
              <AlertDescription className="grid gap-1">
                <div>{moduleConfigStatus ? `${moduleConfigStatus.version} (${moduleConfigStatus.source})` : "-"}</div>
                <div>{messages.app.configCheckedAt}: {formatTimestamp(moduleConfigStatus?.checked_at ?? null)}</div>
                <div>
                  {messages.app.configSignature}:{" "}
                  {moduleConfigStatus?.signature_verified ? messages.app.configVerified : messages.app.configBundled}
                </div>
                {moduleConfigStatus?.last_error ? <div>{messages.app.configFallback}: {moduleConfigStatus.last_error}</div> : null}
              </AlertDescription>
            </Alert>
          </div>

          <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_minmax(300px,0.55fr)]">
            <Alert
              className={
                browserRuntimeStatus?.installed
                  ? "bg-muted/40"
                  : "bg-muted/40"
              }
            >
              <AlertTitle>Browser Runtime Setup</AlertTitle>
              <AlertDescription className="grid min-w-0 gap-2">
                <DetailRow label="State" value={browserRuntimeStatus?.state ?? "-"} />
                <DetailRow label="Install dir" value={browserRuntimeStatus?.install_dir ?? "-"} />
                <DetailRow label="Executable" value={browserRuntimeStatus?.executable_path ?? "-"} />
                <DetailRow label="Estimated download" value={formatBytes(browserRuntimeStatus?.estimated_download_bytes ?? null)} />
                {browserRuntimeProgress ? (
                  <div className="rounded-lg border bg-background/75 p-3">
                    <div className="mb-1 font-semibold">{describeBrowserRuntimePhase(browserRuntimeProgress.phase)}</div>
                    <div>{browserRuntimeProgress.message}</div>
                    {browserRuntimeProgress.percent !== null ? (
                      <Progress className="mt-3" value={browserRuntimeProgress.percent} />
                    ) : null}
                    {browserRuntimeProgress.detail ? (
                      <div className="mt-2 break-words text-xs text-muted-foreground">{browserRuntimeProgress.detail}</div>
                    ) : null}
                  </div>
                ) : null}
                {browserRuntimeStatus?.required_components.length ? (
                  <div className="grid gap-1">
                    <div className="font-semibold">Installer plan</div>
                    {browserRuntimeStatus.required_components.map((component) => (
                      <div key={`${component.name}-${component.install_location}`}>
                        {component.name} - {formatBytes(component.download_bytes)}
                      </div>
                    ))}
                  </div>
                ) : null}
                {browserRuntimeStatus?.guidance ? <div>Guidance: {browserRuntimeStatus.guidance}</div> : null}
                {browserRuntimeStatus?.last_error ? <div>Last error: {browserRuntimeStatus.last_error}</div> : null}
                {browserRuntimeStatus && !browserRuntimeStatus.installed ? (
                  <div className="flex flex-wrap gap-2 pt-1">
                    <Button
                      type="button"
                      disabled={connectionState !== "ready" || isBootstrappingBrowser || !browserRuntimeStatus.bootstrap_supported}
                      onClick={onBootstrapBrowserRuntime}
                    >
                      {isBootstrappingBrowser ? <Loader2 className="h-4 w-4 animate-spin" /> : <UploadCloud className="h-4 w-4" />}
                      {isBootstrappingBrowser ? "Installing Chromium..." : "Install Chromium Runtime"}
                    </Button>
                    <Button type="button" variant="outline" disabled={connectionState !== "ready" || isBootstrappingBrowser} onClick={onReloadBrowserRuntime}>
                      <RefreshCw className="h-4 w-4" />
                      Re-check Runtime
                    </Button>
                  </div>
                ) : null}
              </AlertDescription>
            </Alert>

            <Card className="shadow-none">
              <CardHeader className="pb-3">
                <CardTitle className="text-base">License Activation</CardTitle>
                <CardDescription>ถ้ามี cloud แล้ว ยังไม่ activate จะเริ่ม job ใหม่ไม่ได้</CardDescription>
              </CardHeader>
              <CardContent className="grid gap-3">
                <Input
                  value={licenseKey}
                  onChange={(event) => onLicenseKeyChange(event.target.value)}
                  placeholder="DMC-XXXX-XXXX"
                />
                <Input
                  value={deviceName}
                  onChange={(event) => onDeviceNameChange(event.target.value)}
                  placeholder="desktop-01"
                />
                <Button disabled={connectionState !== "ready" || isActivatingLicense} onClick={onActivateLicense}>
                  {isActivatingLicense ? <Loader2 className="h-4 w-4 animate-spin" /> : <KeyRound className="h-4 w-4" />}
                  Activate License
                </Button>
              </CardContent>
            </Card>
          </div>

          {supportMessage ? (
            <Alert>
              <AlertDescription className="break-words">{supportMessage}</AlertDescription>
            </Alert>
          ) : null}

          {errorMessage ? (
            <Alert variant="destructive">
              <AlertDescription className="break-words">{errorMessage}</AlertDescription>
            </Alert>
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}
