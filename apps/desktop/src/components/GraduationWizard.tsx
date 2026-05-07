import { useEffect, useMemo, useState } from "react";
import {
  AlertCircle,
  ArrowLeft,
  Award,
  CheckCircle2,
  CloudCog,
  FileCheck2,
  FileDown,
  FileSpreadsheet,
  FolderOpen,
  Grid3X3,
  Loader2,
  LogIn,
  Pause,
  Play,
  RefreshCw,
  SearchCheck,
  Square,
  Trash2,
  UploadCloud,
  UserCircle2,
  UsersRound,
} from "lucide-react";
import messages from "../i18n/th.json";
import {
  describeBrowserRuntimePhase,
  describeCreditStatus,
  describeJobStatus,
  formatBytes,
  formatTimestamp,
} from "../lib/appUi";
import { Alert, AlertDescription, AlertTitle } from "./ui/alert";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { Progress } from "./ui/progress";
import { Separator } from "./ui/separator";
import { Switch } from "./ui/switch";
import { ExistingJobsPanel } from "./ExistingJobsPanel";
import { SidecarLogPanel } from "./SidecarLogPanel";
import type {
  AccountStatus,
  BrowserRuntimeStatus,
  JobStatusSnapshot,
  ModuleConfigStatus,
  ValidateExcelResponse,
} from "../types/contracts";

type BrowserRuntimeProgress = {
  phase: "checking" | "installing" | "verifying" | "ready" | "failed";
  message: string;
  percent: number | null;
  detail: string | null;
} | null;

type ConnectionState = "idle" | "connecting" | "ready" | "error";

type GraduationWizardProps = {
  preview: ValidateExcelResponse | null;
  currentJob: JobStatusSnapshot | null;
  existingJobs: JobStatusSnapshot[];
  sidecarMessages: string[];
  activeJobId: string | null;
  progressPercent: number;
  connectionState: ConnectionState;
  accountStatus: AccountStatus | null;
  moduleConfigStatus: ModuleConfigStatus | null;
  browserRuntimeStatus: BrowserRuntimeStatus | null;
  browserRuntimeProgress: BrowserRuntimeProgress;
  supportMessage: string | null;
  errorMessage: string | null;
  excelPath: string;
  minScore: number;
  stopOnReview: boolean;
  isValidating: boolean;
  isStartingJob: boolean;
  isDownloadingTemplate: boolean;
  isArchivingJobs: boolean;
  isBootstrappingBrowser: boolean;
  accountBlocksStart: boolean;
  browserRuntimeBlocksStart: boolean;
  validationBlocksStart: boolean;
  preflightRowsAccepted: number | null;
  preflightRowsTotal: number | null;
  currentJobNeedsAuth: boolean;
  onBackHome: () => void;
  onExcelPathChange: (value: string) => void;
  onMinScoreChange: (value: number) => void;
  onStopOnReviewChange: (value: boolean) => void;
  onConnect: () => void;
  onRefreshJobs: () => void;
  onRefreshWallet: () => void;
  onSyncConfig: () => void;
  onValidate: () => void;
  onStartDryRun: () => void;
  onStartLive: () => void;
  onRefreshStatus: () => void;
  onPause: () => void;
  onResume: () => void;
  onCancel: () => void;
  onBrowseFile: () => void;
  onDownloadTemplate: () => void;
  onArchiveOldJobs: () => void;
  onBootstrapBrowserRuntime: () => void;
  onReloadBrowserRuntime: () => void;
  onSelectJob: (job: JobStatusSnapshot) => void;
  onResumeExisting: (job: JobStatusSnapshot) => void;
  onRevealPath: (path: string) => void;
};

const gradeOptions = [
  {
    id: "m3",
    title: "จบการศึกษา ม.3",
    subtitle: "จบการศึกษาจบชั้นมัธยมศึกษาปีที่ 3",
    badge: "ม.3",
  },
  {
    id: "m6",
    title: "จบการศึกษา ม.6",
    subtitle: "จบการศึกษาจบชั้นมัธยมศึกษาปีที่ 6",
    badge: "ม.6",
  },
] as const;

function connectionLabel(state: ConnectionState) {
  if (state === "ready") return "เชื่อมต่อแล้ว";
  if (state === "connecting") return "กำลังเชื่อมต่อ";
  if (state === "error") return "เชื่อมต่อมีปัญหา";
  return "ยังไม่เชื่อมต่อ";
}

function compactPath(path: string) {
  return path.split(/[\\/]/).filter(Boolean).pop() ?? path;
}

function StepBadge({ step }: { step: number }) {
  return (
    <div className="absolute -left-5 -top-5 flex h-11 w-11 items-center justify-center rounded-full bg-blue-600 text-lg font-bold text-white shadow-lg shadow-blue-600/30 ring-4 ring-white">
      {step}
    </div>
  );
}

function WizardStep({
  number,
  label,
  active,
}: {
  number: number;
  label: string;
  active: boolean;
}) {
  return (
    <div
      data-wizard-step={number}
      className={`relative flex min-h-16 min-w-[210px] flex-1 items-center justify-center px-5 text-center text-lg font-semibold transition ${
        active
          ? "bg-blue-600 text-white shadow-lg shadow-blue-600/20"
          : "bg-blue-50 text-slate-900"
      }`}
      style={{
        clipPath:
          number === 1
            ? "polygon(0 0, calc(100% - 28px) 0, 100% 50%, calc(100% - 28px) 100%, 0 100%)"
            : "polygon(0 0, calc(100% - 28px) 0, 100% 50%, calc(100% - 28px) 100%, 0 100%, 28px 50%)",
      }}
    >
      <span>ขั้นที่ {number}: {label}</span>
    </div>
  );
}

function SystemPill({
  label,
  value,
  tone = "muted",
}: {
  label: string;
  value: string;
  tone?: "success" | "warning" | "danger" | "muted";
}) {
  const toneClass = {
    success: "border-primary/20 bg-primary/10 text-primary",
    warning: "border-amber-500/30 bg-amber-500/10 text-amber-700",
    danger: "border-destructive/30 bg-destructive/10 text-destructive",
    muted: "border-border bg-background text-muted-foreground",
  }[tone];
  return (
    <div className={`rounded-full border px-3 py-1.5 text-xs font-semibold ${toneClass}`}>
      {label}: {value}
    </div>
  );
}

export function GraduationWizard({
  preview,
  currentJob,
  existingJobs,
  sidecarMessages,
  activeJobId,
  progressPercent,
  connectionState,
  accountStatus,
  moduleConfigStatus,
  browserRuntimeStatus,
  browserRuntimeProgress,
  supportMessage,
  errorMessage,
  excelPath,
  minScore,
  stopOnReview,
  isValidating,
  isStartingJob,
  isDownloadingTemplate,
  isArchivingJobs,
  isBootstrappingBrowser,
  accountBlocksStart,
  browserRuntimeBlocksStart,
  validationBlocksStart,
  preflightRowsAccepted,
  preflightRowsTotal,
  currentJobNeedsAuth,
  onBackHome,
  onExcelPathChange,
  onMinScoreChange,
  onStopOnReviewChange,
  onConnect,
  onRefreshJobs,
  onRefreshWallet,
  onSyncConfig,
  onValidate,
  onStartDryRun,
  onStartLive,
  onRefreshStatus,
  onPause,
  onResume,
  onCancel,
  onBrowseFile,
  onDownloadTemplate,
  onArchiveOldJobs,
  onBootstrapBrowserRuntime,
  onReloadBrowserRuntime,
  onSelectJob,
  onResumeExisting,
  onRevealPath,
}: GraduationWizardProps) {
  const [selectedGrade, setSelectedGrade] = useState<"m3" | "m6" | null>(null);
  const [activeStep, setActiveStep] = useState(1);
  const [showSupportDrawer, setShowSupportDrawer] = useState(false);
  const [supportSection, setSupportSection] = useState<"settings" | "history" | "messages">("settings");
  const runtimeReady = browserRuntimeStatus?.installed ?? false;
  const accountReady = accountStatus?.can_start_credit_jobs ?? false;
  const showDryRun = Boolean((import.meta as unknown as { env?: { DEV?: boolean } }).env?.DEV);
  const canDryRun =
    Boolean(selectedGrade) &&
    !isStartingJob &&
    !isBootstrappingBrowser &&
    !browserRuntimeBlocksStart &&
    !validationBlocksStart;
  const canStart = canDryRun && !accountBlocksStart;
  const acceptedRows = preview?.rows_accepted ?? preflightRowsAccepted ?? 0;
  const totalRows = preview?.rows_total ?? preflightRowsTotal ?? null;
  const detectedLevel =
    preview?.detected_level ?? (selectedGrade === "m3" ? "ม.3" : selectedGrade === "m6" ? "ม.6" : "ยังไม่ได้เลือก");
  const fileName = excelPath.trim() ? compactPath(excelPath.trim()) : "ยังไม่ได้เลือกไฟล์";
  const reportPath = currentJob?.report_path ?? null;
  const reviewReportPath = currentJob?.review_report_path ?? null;
  const reportDirectory = reportPath?.replace(/[\\/][^\\/]+$/, "") ?? reviewReportPath?.replace(/[\\/][^\\/]+$/, "");
  const latestReportJob = useMemo(
    () => existingJobs.find((job) => job.report_path || job.review_report_path) ?? null,
    [existingJobs],
  );
  const latestCsvPath = reportPath ?? latestReportJob?.report_path ?? reviewReportPath ?? latestReportJob?.review_report_path ?? null;
  const latestReportDirectory =
    reportDirectory ||
    latestCsvPath?.replace(/[\\/][^\\/]+$/, "") ||
    null;
  const runSummary = currentJob?.run_summary ?? null;
  const processedLabel =
    currentJob?.total !== null && currentJob?.total !== undefined && currentJob.processed > currentJob.total
      ? `${currentJob.processed} แถวบนเว็บ`
      : `${currentJob?.processed ?? 0}/${currentJob?.total ?? "-"}`;

  const rowsForPreview = useMemo(() => preview?.preview.slice(0, 5) ?? [], [preview]);
  const visibleErrorMessage = errorMessage?.includes("transformCallback") ? null : errorMessage;
  const reportTools = messages.app.reportTools;
  const accountCopy = messages.app.account;
  const creditStatus = describeCreditStatus(currentJob?.credit_status);
  const creditStatusClass = {
    info: "border-blue-200 bg-blue-50 text-blue-950",
    warning: "border-amber-200 bg-amber-50 text-amber-950",
    danger: "border-destructive/30 bg-destructive/10 text-destructive",
    success: "border-emerald-200 bg-emerald-50 text-emerald-950",
  } as const;

  useEffect(() => {
    if (currentJob || preview) {
      setActiveStep(4);
      return;
    }
    if (selectedGrade && excelPath.trim()) {
      setActiveStep(3);
      return;
    }
    if (selectedGrade) {
      setActiveStep(2);
      return;
    }
    setActiveStep(1);
  }, [currentJob, excelPath, preview, selectedGrade]);

  useEffect(() => {
    if (activeStep <= 1 || typeof document === "undefined") {
      return;
    }
    document.getElementById(`wizard-step-${activeStep}`)?.scrollIntoView({
      behavior: "smooth",
      block: "nearest",
    });
  }, [activeStep]);

  return (
    <div className="min-h-screen space-y-6 rounded-[28px] bg-gradient-to-br from-sky-50 via-white to-slate-100 p-3 text-slate-950 sm:p-5">
      <header className="flex min-w-0 items-center justify-between gap-4 rounded-2xl border border-white/80 bg-white/90 px-4 py-3 shadow-sm backdrop-blur">
        <div className="flex min-w-0 items-center gap-4">
          <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-blue-600 text-white shadow-lg shadow-blue-600/25">
            <Award className="h-8 w-8" />
          </div>
          <div className="min-w-0">
            <div className="truncate text-2xl font-bold tracking-normal">
              แอปกรอกข้อมูลนักเรียนจบการศึกษา (DMC)
            </div>
            <div className="mt-1 flex flex-wrap gap-2">
              <SystemPill
                label="ตัวเชื่อมระบบ"
                value={connectionLabel(connectionState)}
                tone={connectionState === "ready" ? "success" : connectionState === "error" ? "danger" : "warning"}
              />
              <SystemPill
                label="บัญชี"
                value={accountStatus?.signed_in ? accountStatus.email ?? "signed in" : accountCopy.signInRequired}
                tone={accountReady ? "success" : "warning"}
              />
              <SystemPill
                label="เครดิต"
                value={accountStatus?.wallet ? `${accountStatus.wallet.available} พร้อมใช้` : "-"}
                tone={accountStatus?.wallet && accountStatus.wallet.available > 0 ? "success" : "warning"}
              />
              <SystemPill
                label="เบราว์เซอร์"
                value={runtimeReady ? "พร้อม" : browserRuntimeStatus?.state ?? "ยังไม่ตรวจ"}
                tone={runtimeReady ? "success" : "warning"}
              />
            </div>
          </div>
        </div>

        <div className="flex shrink-0 items-center gap-2">
          <Button variant="outline" size="icon" onClick={onBackHome} title="กลับหน้าหลัก">
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <Button variant="ghost" size="icon" title="เมนูระบบ">
            <Grid3X3 className="h-5 w-5" />
          </Button>
          <div className="flex h-12 w-12 items-center justify-center rounded-full bg-slate-100 text-slate-400">
            <UserCircle2 className="h-8 w-8" />
          </div>
        </div>
      </header>

      <div className="flex min-w-0 gap-1 overflow-x-auto px-1 pb-1">
        <WizardStep number={1} label="เลือกชั้นปี" active={activeStep === 1} />
        <WizardStep number={2} label="อัปโหลดไฟล์" active={activeStep === 2} />
        <WizardStep number={3} label="ตรวจสอบข้อมูล" active={activeStep === 3} />
        <WizardStep number={4} label="ส่งข้อมูลเข้า DMC" active={activeStep === 4} />
      </div>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)]">
        <Card className="relative overflow-visible rounded-2xl border-slate-200 bg-white/95 shadow-md shadow-slate-200/60">
          <div id="wizard-step-1" className="absolute -top-6" />
          <StepBadge step={1} />
          <CardHeader className="pb-3">
            <CardTitle className="text-2xl">เลือกชั้นปี</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-4 sm:grid-cols-2">
            {gradeOptions.map((option) => {
              const selected = selectedGrade === option.id;
              return (
                <button
                  key={option.id}
                  data-grade-option={option.id}
                  type="button"
                  onClick={() => {
                    setSelectedGrade(option.id);
                    setActiveStep(2);
                  }}
                  className={`min-h-[190px] rounded-xl border p-5 text-center transition ${
                    selected
                      ? "border-blue-500 bg-blue-50 shadow-[0_0_0_2px_rgba(37,99,235,0.12)]"
                      : "border-slate-200 bg-white hover:border-blue-300"
                  }`}
                >
                  <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-blue-100 text-blue-700">
                    <UsersRound className="h-9 w-9" />
                  </div>
                  <div className="text-xl font-bold">{option.title}</div>
                  <div className="mt-2 text-base leading-7 text-slate-600">{option.subtitle}</div>
                  <Badge className="mt-4 bg-blue-600">{option.badge}</Badge>
                </button>
              );
            })}
          </CardContent>
        </Card>

        <Card className="relative overflow-visible rounded-2xl border-slate-200 bg-white/95 shadow-md shadow-slate-200/60">
          <div id="wizard-step-2" className="absolute -top-6" />
          <StepBadge step={2} />
          <CardHeader className="pb-3">
            <CardTitle className="text-2xl">ดาวน์โหลดฟอร์ม & อัปโหลดไฟล์</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-4 lg:grid-cols-2">
            <div className="flex min-h-[210px] flex-col items-center justify-center rounded-xl bg-blue-50 p-5 text-center">
              <div className="mb-4 flex h-16 w-20 items-center justify-center rounded-full bg-blue-600 text-white shadow-lg shadow-blue-600/25">
                <FileDown className="h-9 w-9" />
              </div>
              <div className="text-xl font-bold">ดาวน์โหลดไฟล์ Template (.xlsx)</div>
              <div className="mt-2 text-slate-600">เตรียมไฟล์ต้นแบบสำหรับกรอกข้อมูลนักเรียน</div>
              <Button className="mt-5" variant="outline" onClick={onDownloadTemplate} disabled={isDownloadingTemplate}>
                {isDownloadingTemplate ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <FileSpreadsheet className="h-4 w-4" />
                )}
                ดาวน์โหลด Template
              </Button>
            </div>

            <div className="flex min-h-[210px] flex-col items-center justify-center rounded-xl border border-slate-200 bg-white p-5 text-center">
              <UploadCloud className="mb-4 h-16 w-16 text-emerald-600" />
              <div className="text-xl font-bold">เลือกไฟล์ Excel</div>
              <div className="mt-2 max-w-full break-words text-slate-600">
                {fileName}
                {preview ? ` (${preview.rows_accepted}/${preview.rows_total} คน)` : ""}
              </div>
              <div className="mt-4 flex w-full min-w-0 gap-2">
                <Input
                  value={excelPath}
                  onChange={(event) => {
                    onExcelPathChange(event.target.value);
                    if (event.target.value.trim()) {
                      setActiveStep(3);
                    }
                  }}
                  placeholder="C:\\path\\student_data.xlsx"
                  className="min-w-0"
                />
                <Button type="button" disabled={!selectedGrade} onClick={onBrowseFile}>
                  <FolderOpen className="h-4 w-4" />
                  เลือกไฟล์
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.25fr)_minmax(360px,0.65fr)]">
        <Card className="relative overflow-visible rounded-2xl border-slate-200 bg-white/95 shadow-md shadow-slate-200/60">
          <div id="wizard-step-3" className="absolute -top-6" />
          <StepBadge step={3} />
          <CardHeader className="pb-3">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
              <div>
                <CardTitle className="text-2xl">ตรวจสอบข้อมูล</CardTitle>
                <div className="mt-2 text-sm text-slate-600">
                  {preview
                    ? `${detectedLevel} · รับข้อมูลได้ ${preview.rows_accepted} จากทั้งหมด ${preview.rows_total} แถว`
                    : "เลือกไฟล์แล้วกดตรวจสอบ เพื่อดูตัวอย่างก่อนส่งข้อมูลเข้า DMC"}
                </div>
              </div>
              <Button onClick={onValidate} disabled={isValidating || !selectedGrade || !excelPath.trim()}>
                {isValidating ? <Loader2 className="h-4 w-4 animate-spin" /> : <SearchCheck className="h-4 w-4" />}
                ตรวจสอบข้อมูล
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            {preview ? (
              <div className="overflow-hidden rounded-xl border border-slate-200">
                <table className="w-full min-w-[760px] border-collapse text-base">
                  <thead className="bg-slate-50 text-left">
                    <tr>
                      <th className="px-5 py-4 font-semibold">เลขประจำตัว</th>
                      <th className="px-5 py-4 font-semibold">ชื่อ-นามสกุล</th>
                      <th className="px-5 py-4 font-semibold">ศึกษาต่อหรือไม่</th>
                      <th className="px-5 py-4 font-semibold text-right">สถานะ</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rowsForPreview.map((row) => (
                      <tr key={`${row.order}-${row.student_no}`} className="border-t border-slate-100">
                        <td className="px-5 py-4 font-medium">{row.student_no}</td>
                        <td className="px-5 py-4">
                          {row.first_name} {row.last_name}
                        </td>
                        <td className="px-5 py-4 text-slate-600">{row.status_text}</td>
                        <td className="px-5 py-4 text-right">
                          <Badge variant="outline">{row.status_code}</Badge>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 p-8 text-center text-slate-500">
                ยังไม่มีข้อมูลตัวอย่าง
              </div>
            )}

            {preview?.warnings.length ? (
              <Alert className="mt-4 border-amber-200 bg-amber-50 text-amber-900">
                <AlertCircle className="h-4 w-4" />
                <AlertTitle>มีรายการที่ควรตรวจสอบ {preview.warnings.length} รายการ</AlertTitle>
                <AlertDescription className="mt-2 grid gap-1">
                  {preview.warnings.slice(0, 4).map((warning) => (
                    <div key={`${warning.code}-${warning.row_index}`}>
                      row {warning.row_index}: {warning.message_th}
                    </div>
                  ))}
                </AlertDescription>
              </Alert>
            ) : preview ? (
              <Alert className="mt-4 border-emerald-200 bg-emerald-50 text-emerald-900">
                <CheckCircle2 className="h-4 w-4" />
                <AlertTitle>ไม่พบ warning จากไฟล์นี้</AlertTitle>
              </Alert>
            ) : null}
          </CardContent>
        </Card>

        <Card className="relative overflow-visible rounded-2xl border-slate-200 bg-white/95 shadow-md shadow-slate-200/60">
          <div id="wizard-step-4" className="absolute -top-6" />
          <StepBadge step={4} />
          <CardHeader className="pb-3">
            <CardTitle className="text-2xl">สรุปผลและเริ่มกรอก</CardTitle>
          </CardHeader>
          <CardContent className="space-y-5">
            <div className="space-y-2">
              <div className="text-lg">
                พบข้อมูลนักเรียนจบทั้งหมด:{" "}
                <span className="font-bold">{acceptedRows}</span>{" "}
                คน
                {totalRows !== null ? ` จาก ${totalRows} แถว` : ""}
              </div>
              <div className="text-sm text-slate-600">ระดับชั้น: {detectedLevel}</div>
              <div className="rounded-lg border bg-blue-50 px-3 py-2 text-sm text-blue-900">
                งานจริงนี้จะกันเครดิตไว้ประมาณ {acceptedRows} เครดิต
                {accountStatus?.wallet ? ` · ${accountCopy.availableCredits} ${accountStatus.wallet.available}` : ` · ${accountCopy.signInBeforeLive}`}
              </div>
              {accountStatus?.wallet && accountStatus.wallet.available < acceptedRows ? (
                <Alert variant="destructive">
                  <AlertCircle className="h-4 w-4" />
                  <AlertTitle>{accountCopy.insufficientCreditsTitle}</AlertTitle>
                  <AlertDescription>{accountCopy.insufficientCredits}</AlertDescription>
                </Alert>
              ) : null}
              <Progress value={currentJob ? progressPercent : 0} className="h-3" />
            </div>

            <div className="grid gap-3 rounded-xl border bg-slate-50 p-4">
              <div className="grid grid-cols-[1fr_auto] items-center gap-3">
                <Label htmlFor="wizard-min-score">คะแนนจับคู่ขั้นต่ำ</Label>
                <Input
                  id="wizard-min-score"
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
                <Label htmlFor="wizard-stop-review" className="leading-5">
                  หยุดทันทีเมื่อเจอแถวที่ต้อง review
                </Label>
                <Switch id="wizard-stop-review" checked={stopOnReview} onCheckedChange={onStopOnReviewChange} />
              </div>
            </div>

            <div className="grid gap-3">
              {creditStatus ? (
                <Alert className={creditStatusClass[creditStatus.tone]}>
                  <AlertCircle className="h-4 w-4" />
                  <AlertTitle>{creditStatus.title}</AlertTitle>
                  <AlertDescription>{creditStatus.message}</AlertDescription>
                </Alert>
              ) : null}
              {currentJobNeedsAuth ? (
                <Alert className="border-amber-200 bg-amber-50 text-amber-950">
                  <LogIn className="h-4 w-4" />
                  <AlertTitle>ระบบกำลังรอให้ยืนยันตัวตนใน DMC</AlertTitle>
                  <AlertDescription>
                    ระบบเปิด Chromium สำหรับ DMC ไว้แล้ว กรุณา login ให้เสร็จในหน้าต่างนั้น แล้วกลับมากด “ทำต่อหลังยืนยันตัวตน”
                  </AlertDescription>
                </Alert>
              ) : null}
              <Button
                className="h-16 bg-blue-600 text-lg hover:bg-blue-700"
                disabled={!canStart}
                onClick={onStartLive}
              >
                <RefreshCw className="h-7 w-7" />
                เริ่มส่งข้อมูลเข้า DMC
              </Button>
              {showDryRun ? (
                <Button variant="outline" disabled={!canDryRun} onClick={onStartDryRun}>
                  <FileCheck2 className="h-4 w-4" />
                  เริ่ม Dry Run ก่อนส่งจริง
                </Button>
              ) : null}
            </div>

            <div className="space-y-2">
              <Progress value={progressPercent} className="h-2" />
              <div className="text-center text-sm text-slate-600">
                {currentJob ? `อัปโหลดข้อมูลคนที่ ${processedLabel}` : "ยังไม่มีงานที่กำลังทำ"}
              </div>
            </div>

            {currentJob ? (
              <div className="grid gap-2 rounded-xl border bg-white p-4 text-sm">
                <div className="flex items-center justify-between gap-3">
                  <span className="font-semibold">สถานะ</span>
                  <Badge variant="outline">{describeJobStatus(currentJob.status)}</Badge>
                </div>
                <div>สำเร็จ: {currentJob.succeeded}</div>
                <div>ต้องตรวจเพิ่ม/ผิดพลาด: {currentJob.failed}</div>
                {currentJob.credits_reserved > 0 ? (
                  <>
                    <Separator />
                    <div>เครดิตที่กันไว้: {currentJob.credits_reserved}</div>
                    <div>เครดิตที่ใช้จริง: {currentJob.credits_captured}</div>
                    <div>เครดิตที่คืน: {currentJob.credits_refunded}</div>
                  </>
                ) : null}
                {runSummary ? (
                  <>
                    <Separator />
                    <div>DMC rows ทั้งหมด: {runSummary.dmc_rows_total}</div>
                    <div>matched จาก Excel: {runSummary.matched_from_excel}</div>
                    <div>default 207: {runSummary.default_207}</div>
                    <div>Excel ไม่พบใน DMC: {runSummary.excel_missing}</div>
                  </>
                ) : null}
              </div>
            ) : null}

            <div className="flex flex-wrap gap-2">
              <Button variant="outline" size="sm" disabled={!activeJobId} onClick={onRefreshStatus}>
                <RefreshCw className="h-4 w-4" />
                รีเฟรช
              </Button>
              <Button variant="outline" size="sm" disabled={!activeJobId} onClick={onPause}>
                <Pause className="h-4 w-4" />
                พักงาน
              </Button>
              <Button size="sm" variant="secondary" disabled={!currentJobNeedsAuth} onClick={onResume}>
                <LogIn className="h-4 w-4" />
                ทำต่อหลังยืนยันตัวตน
              </Button>
              <Button variant="destructive" size="sm" disabled={!activeJobId} onClick={onCancel}>
                <Square className="h-4 w-4" />
                ยกเลิกงาน
              </Button>
            </div>

            <div className="rounded-xl border bg-white p-4">
              <div className="font-semibold">{reportTools.title}</div>
              <div className="mt-1 text-sm text-slate-600">
                {reportTools.description}
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                <Button size="sm" disabled={!latestCsvPath} onClick={() => latestCsvPath && onRevealPath(latestCsvPath)}>
                  <FileSpreadsheet className="h-4 w-4" />
                  {reportTools.openLatestCsv}
                </Button>
                {reviewReportPath ? (
                  <Button size="sm" variant="outline" onClick={() => onRevealPath(reviewReportPath)}>
                    <SearchCheck className="h-4 w-4" />
                    {reportTools.openReview}
                  </Button>
                ) : null}
                <Button
                  size="sm"
                  variant="outline"
                  disabled={!latestReportDirectory}
                  onClick={() => latestReportDirectory && onRevealPath(latestReportDirectory)}
                >
                  <FolderOpen className="h-4 w-4" />
                  {reportTools.openFolder}
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {visibleErrorMessage ? (
        <Alert variant="destructive">
          <AlertDescription className="break-words">{visibleErrorMessage}</AlertDescription>
        </Alert>
      ) : null}
      {supportMessage ? (
        <Alert>
          <AlertDescription className="break-words">{supportMessage}</AlertDescription>
        </Alert>
      ) : null}

      <Card className="rounded-2xl border-slate-200 bg-white/95 shadow-sm">
        <CardHeader className="pb-3">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <CardTitle>เครื่องมือเพิ่มเติม</CardTitle>
              <div className="mt-1 text-sm text-slate-600">
                การตั้งค่า, ประวัติการใช้งาน และข้อความจากตัวเชื่อมระบบ
              </div>
            </div>
            <Button variant="outline" onClick={() => setShowSupportDrawer((value) => !value)}>
              {showSupportDrawer ? "ซ่อนเครื่องมือ" : "แสดงเครื่องมือเพิ่มเติม"}
            </Button>
          </div>
        </CardHeader>
        {showSupportDrawer ? (
          <CardContent className="space-y-4">
            <div className="flex flex-wrap gap-2">
              <Button
                variant={supportSection === "settings" ? "default" : "outline"}
                onClick={() => setSupportSection("settings")}
              >
                การตั้งค่า
              </Button>
              <Button
                variant={supportSection === "history" ? "default" : "outline"}
                onClick={() => setSupportSection("history")}
              >
                ประวัติการใช้งาน ({existingJobs.length})
              </Button>
              <Button
                variant={supportSection === "messages" ? "default" : "outline"}
                onClick={() => setSupportSection("messages")}
              >
                ข้อความจากตัวเชื่อมระบบ ({sidecarMessages.length})
              </Button>
            </div>

            {supportSection === "settings" ? (
              <div className="grid gap-4 lg:grid-cols-3">
                <div className="space-y-3 rounded-xl border bg-slate-50 p-4">
                  <div className="font-semibold">เชื่อมต่อตัวเชื่อมระบบ</div>
                  <div className="text-sm text-slate-600">{connectionLabel(connectionState)}</div>
                  <Button className="w-full" variant="outline" onClick={onConnect} disabled={connectionState === "connecting"}>
                    {connectionState === "connecting" ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
                    เชื่อมต่อระบบ
                  </Button>
                </div>

                <div className="space-y-3 rounded-xl border bg-slate-50 p-4">
                  <div className="font-semibold">บัญชีและเครดิต</div>
                  <div className="text-sm text-slate-600">
                    {accountStatus?.signed_in ? accountStatus.email : accountCopy.signInRequired}
                  </div>
                  <div className="grid grid-cols-3 gap-2 text-sm">
                    <div className="rounded-lg border bg-white p-2">
                      <div className="text-xs text-slate-500">เครดิตรวม</div>
                      <div className="font-semibold">{accountStatus?.wallet?.balance ?? "-"}</div>
                    </div>
                    <div className="rounded-lg border bg-white p-2">
                      <div className="text-xs text-slate-500">กันไว้</div>
                      <div className="font-semibold">{accountStatus?.wallet?.reserved ?? "-"}</div>
                    </div>
                    <div className="rounded-lg border bg-white p-2">
                      <div className="text-xs text-slate-500">พร้อมใช้</div>
                      <div className="font-semibold">{accountStatus?.wallet?.available ?? "-"}</div>
                    </div>
                  </div>
                  <Button variant="outline" onClick={onRefreshWallet} disabled={!accountStatus?.signed_in}>
                    <RefreshCw className="h-4 w-4" />
                    {accountCopy.refreshCredits}
                  </Button>
                </div>

                <div className="space-y-3 rounded-xl border bg-slate-50 p-4">
                  <div className="font-semibold">Config และ Chromium</div>
                  <div className="text-sm text-slate-600">
                    สถานะ config: {moduleConfigStatus ? `${moduleConfigStatus.version} (${moduleConfigStatus.source})` : "-"}
                  </div>
                  <div className="text-sm text-slate-600">
                    สถานะ runtime: {browserRuntimeStatus?.message ?? browserRuntimeStatus?.state ?? "-"}
                  </div>
                  {browserRuntimeProgress ? (
                    <div className="rounded-lg border bg-white p-3 text-sm">
                      <div className="font-semibold">{describeBrowserRuntimePhase(browserRuntimeProgress.phase)}</div>
                      <div className="mt-1 text-slate-600">{browserRuntimeProgress.message}</div>
                      {browserRuntimeProgress.percent !== null ? (
                        <Progress className="mt-2" value={browserRuntimeProgress.percent} />
                      ) : null}
                    </div>
                  ) : null}
                  <div className="flex flex-wrap gap-2">
                    <Button variant="outline" onClick={onSyncConfig}>
                      <CloudCog className="h-4 w-4" />
                      ซิงก์ config
                    </Button>
                    {browserRuntimeStatus && !browserRuntimeStatus.installed ? (
                      <Button
                        disabled={connectionState !== "ready" || isBootstrappingBrowser || !browserRuntimeStatus.bootstrap_supported}
                        onClick={onBootstrapBrowserRuntime}
                      >
                        {isBootstrappingBrowser ? <Loader2 className="h-4 w-4 animate-spin" /> : <UploadCloud className="h-4 w-4" />}
                        ติดตั้ง Chromium
                      </Button>
                    ) : (
                      <Button variant="outline" onClick={onReloadBrowserRuntime}>
                        <RefreshCw className="h-4 w-4" />
                        ตรวจ runtime อีกครั้ง
                      </Button>
                    )}
                  </div>
                  {browserRuntimeStatus?.estimated_download_bytes ? (
                    <div className="text-xs text-slate-500">
                      ขนาดดาวน์โหลด: {formatBytes(browserRuntimeStatus.estimated_download_bytes)}
                    </div>
                  ) : null}
                </div>
              </div>
            ) : null}

            {supportSection === "history" ? (
              <ExistingJobsPanel
                existingJobs={existingJobs}
                activeJobId={activeJobId}
                isStartingJob={isStartingJob}
                isArchivingJobs={isArchivingJobs}
                onSelectJob={onSelectJob}
                onResumeExisting={onResumeExisting}
                onRevealPath={onRevealPath}
                onArchiveOldJobs={onArchiveOldJobs}
              />
            ) : null}

            {supportSection === "messages" ? <SidecarLogPanel sidecarMessages={sidecarMessages} /> : null}
          </CardContent>
        ) : null}
      </Card>

      <Card className="rounded-2xl border-slate-200 bg-white/80 px-4 py-3 text-xs text-slate-500">
        สถานะล่าสุด: account checked {formatTimestamp(accountStatus?.last_checked_at ?? null)} · config checked{" "}
        {formatTimestamp(moduleConfigStatus?.checked_at ?? null)}
      </Card>
    </div>
  );
}
