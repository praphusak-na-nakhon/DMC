import { useEffect, useMemo, useState } from "react";
import {
  AlertCircle,
  Award,
  CheckCircle2,
  CloudCog,
  FileCheck2,
  FileDown,
  FileSpreadsheet,
  FolderOpen,
  Loader2,
  LogIn,
  Pause,
  Play,
  RefreshCw,
  SearchCheck,
  Square,
  Trash2,
  UploadCloud,
  UsersRound,
} from "lucide-react";
import messages from "../i18n/th.json";
import { describeUserFacingError } from "../lib/errorMessages";
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
import { PageHeader } from "./PageHeader";
import { SystemErrorAlert } from "./SystemErrorAlert";
import type {
  AccountStatus,
  BrowserRuntimeStatus,
  JobCompletionItem,
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

function completionItemLabel(item: JobCompletionItem) {
  return item.full_name ?? item.student_no ?? item.citizen_id ?? item.record_id ?? `row ${item.row_index ?? "-"}`;
}

function completionItemMeta(item: JobCompletionItem) {
  return [
    item.student_no ? `เลขประจำตัว ${item.student_no}` : null,
    item.classroom ? `ห้อง ${item.classroom}` : null,
    item.note ?? item.status,
  ]
    .filter(Boolean)
    .join(" / ");
}

function CompletionList({
  title,
  items,
  emptyText,
}: {
  title: string;
  items: JobCompletionItem[];
  emptyText: string;
}) {
  const visibleItems = items.slice(0, 8);
  return (
    <div className="rounded-md border bg-muted/30 p-3">
      <div className="font-semibold">{title}</div>
      {visibleItems.length > 0 ? (
        <ul className="mt-2 space-y-2">
          {visibleItems.map((item, index) => (
            <li key={`${item.record_id ?? item.student_no ?? item.row_index ?? index}-${index}`} className="min-w-0">
              <div className="truncate font-medium">{completionItemLabel(item)}</div>
              <div className="truncate text-xs text-muted-foreground">{completionItemMeta(item)}</div>
            </li>
          ))}
        </ul>
      ) : (
        <div className="mt-2 text-sm text-muted-foreground">{emptyText}</div>
      )}
      {items.length > visibleItems.length ? (
        <div className="mt-2 text-xs text-muted-foreground">และอีก {items.length - visibleItems.length} คนในไฟล์ Excel</div>
      ) : null}
    </div>
  );
}

function StepBadge({ step }: { step: number }) {
  return (
    <div className="absolute -left-3 -top-3 flex h-8 w-8 items-center justify-center rounded-full border bg-background text-sm font-bold shadow-sm">
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
      className={`relative flex min-h-12 min-w-0 items-center justify-center rounded-md border px-3 text-center text-sm font-semibold transition ${
        active
          ? "border-primary bg-primary text-primary-foreground"
          : "bg-background text-muted-foreground"
      }`}
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
  const summaryReportPath = currentJob?.summary_report_path ?? null;
  const reportDirectory =
    reportPath?.replace(/[\\/][^\\/]+$/, "") ??
    reviewReportPath?.replace(/[\\/][^\\/]+$/, "") ??
    summaryReportPath?.replace(/[\\/][^\\/]+$/, "");
  const latestReportJob = useMemo(
    () => existingJobs.find((job) => job.report_path || job.review_report_path) ?? null,
    [existingJobs],
  );
  const latestSummaryReportJob = useMemo(
    () => existingJobs.find((job) => job.summary_report_path) ?? null,
    [existingJobs],
  );
  const latestCsvPath = reportPath ?? latestReportJob?.report_path ?? reviewReportPath ?? latestReportJob?.review_report_path ?? null;
  const latestSummaryReportPath = summaryReportPath ?? latestSummaryReportJob?.summary_report_path ?? null;
  const latestReportDirectory =
    reportDirectory ||
    latestSummaryReportPath?.replace(/[\\/][^\\/]+$/, "") ||
    latestCsvPath?.replace(/[\\/][^\\/]+$/, "") ||
    null;
  const runSummary = currentJob?.run_summary ?? null;
  const completionSummary = currentJob?.completion_summary ?? null;
  const canResumeCurrentJob = Boolean(activeJobId && (currentJobNeedsAuth || currentJob?.status === "paused"));
  const resumeLabel = currentJobNeedsAuth ? "ทำต่อหลังยืนยันตัวตน" : "ปิด dry run และเขียน report";
  const processedLabel =
    currentJob?.total !== null && currentJob?.total !== undefined && currentJob.processed > currentJob.total
      ? `${currentJob.processed} แถวบนเว็บ`
      : `${currentJob?.processed ?? 0}/${currentJob?.total ?? "-"}`;

  const rowsForPreview = useMemo(() => preview?.preview.slice(0, 5) ?? [], [preview]);
  const visibleErrorMessage = errorMessage ? describeUserFacingError(errorMessage) : null;
  const reportTools = messages.app.reportTools;
  const accountCopy = messages.app.account;
  const creditStatus = describeCreditStatus(currentJob?.credit_status);
  const creditStatusClass = {
    info: "border-blue-200 bg-blue-50 text-blue-950",
    warning: "border-amber-200 bg-amber-50 text-amber-950",
    danger: "border-destructive/30 bg-destructive/10 text-destructive",
    success: "border-emerald-200 bg-emerald-50 text-emerald-950",
  } as const;
  const browseFileHint = !selectedGrade ? "เลือกชั้นปีก่อนเลือกไฟล์ Excel" : null;
  const validateHint = !selectedGrade
    ? "เลือกชั้นปีก่อนตรวจสอบข้อมูล"
    : !excelPath.trim()
      ? "เลือกไฟล์ Excel ก่อนตรวจสอบข้อมูล"
      : null;
  const startHint = !selectedGrade
    ? "เลือกชั้นปีก่อนเริ่มส่งข้อมูล"
    : validationBlocksStart
      ? "ตรวจสอบไฟล์ Excel ให้ผ่านก่อนเริ่มส่งข้อมูล"
      : browserRuntimeBlocksStart
        ? "ติดตั้งหรือตรวจ Chromium runtime ให้พร้อมก่อนเริ่มงาน"
        : accountBlocksStart
          ? "ลงชื่อเข้าใช้และตรวจเครดิตก่อนเริ่มงานจริง"
          : null;

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
    <div className="space-y-6">
      <PageHeader
        onBackHome={onBackHome}
        badge="ใช้เครดิต"
        title="ข้อมูลสิ้นปีการศึกษา (สอบได้ เรียนจบ)"
        description="ตรวจไฟล์ Excel, ทดสอบก่อนส่งจริง, กรอกข้อมูลจบการศึกษาใน DMC และสรุปรายงานหลังจบงาน"
        icon={<Award className="h-5 w-5 text-primary" />}
        status={
          <>
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
          </>
        }
      />

      <div className="grid min-w-0 gap-2 sm:grid-cols-4">
        <WizardStep number={1} label="เลือกชั้นปี" active={activeStep === 1} />
        <WizardStep number={2} label="อัปโหลดไฟล์" active={activeStep === 2} />
        <WizardStep number={3} label="ตรวจสอบข้อมูล" active={activeStep === 3} />
        <WizardStep number={4} label="ส่งข้อมูลเข้า DMC" active={activeStep === 4} />
      </div>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)]">
        <Card className="relative overflow-visible">
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
                      ? "border-primary bg-muted shadow-[0_0_0_2px_hsl(var(--primary)/0.12)]"
                      : "border-border bg-background hover:border-primary/40"
                  }`}
                >
                  <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-lg border bg-muted text-primary">
                    <UsersRound className="h-9 w-9" />
                  </div>
                  <div className="text-xl font-bold">{option.title}</div>
                  <div className="mt-2 text-base leading-7 text-muted-foreground">{option.subtitle}</div>
                  <Badge className="mt-4">{option.badge}</Badge>
                </button>
              );
            })}
          </CardContent>
        </Card>

        <Card className="relative overflow-visible">
          <div id="wizard-step-2" className="absolute -top-6" />
          <StepBadge step={2} />
          <CardHeader className="pb-3">
            <CardTitle className="text-2xl">ดาวน์โหลดฟอร์ม & อัปโหลดไฟล์</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-4 lg:grid-cols-2">
            <div className="flex min-h-[210px] flex-col items-center justify-center rounded-lg border bg-muted/40 p-5 text-center">
              <div className="mb-4 flex h-14 w-16 items-center justify-center rounded-lg border bg-background text-primary">
                <FileDown className="h-9 w-9" />
              </div>
              <div className="text-xl font-bold">ดาวน์โหลดไฟล์ต้นแบบ (.xlsx)</div>
              <div className="mt-2 text-muted-foreground">เตรียมไฟล์ต้นแบบสำหรับกรอกข้อมูลนักเรียน</div>
              <Button className="mt-5" variant="outline" onClick={onDownloadTemplate} disabled={isDownloadingTemplate}>
                {isDownloadingTemplate ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <FileSpreadsheet className="h-4 w-4" />
                )}
                ดาวน์โหลดไฟล์ต้นแบบ
              </Button>
            </div>

            <div className="flex min-h-[210px] flex-col items-center justify-center rounded-lg border bg-background p-5 text-center">
              <UploadCloud className="mb-4 h-16 w-16 text-emerald-600" />
              <div className="text-xl font-bold">เลือกไฟล์ Excel</div>
              <div className="mt-2 max-w-full break-words text-muted-foreground">
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
              {browseFileHint ? <div className="mt-3 text-sm text-muted-foreground">{browseFileHint}</div> : null}
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.25fr)_minmax(360px,0.65fr)]">
        <Card className="relative overflow-visible">
          <div id="wizard-step-3" className="absolute -top-6" />
          <StepBadge step={3} />
          <CardHeader className="pb-3">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
              <div>
                <CardTitle className="text-2xl">ตรวจสอบข้อมูล</CardTitle>
                <div className="mt-2 text-sm text-muted-foreground">
                  {preview
                    ? `${detectedLevel} · รับข้อมูลได้ ${preview.rows_accepted} จากทั้งหมด ${preview.rows_total} แถว`
                    : "เลือกไฟล์แล้วกดตรวจสอบ เพื่อดูตัวอย่างก่อนส่งข้อมูลเข้า DMC"}
                </div>
              </div>
              <Button onClick={onValidate} disabled={isValidating || !selectedGrade || !excelPath.trim()}>
                {isValidating ? <Loader2 className="h-4 w-4 animate-spin" /> : <SearchCheck className="h-4 w-4" />}
                ตรวจสอบข้อมูล
              </Button>
              {validateHint ? <div className="text-sm text-muted-foreground lg:text-right">{validateHint}</div> : null}
            </div>
          </CardHeader>
          <CardContent>
            {preview ? (
              <div className="overflow-auto rounded-lg border">
                <table className="w-full min-w-[760px] border-collapse text-base">
                  <thead className="bg-muted/50 text-left">
                    <tr>
                      <th className="px-5 py-4 font-semibold">เลขประจำตัว</th>
                      <th className="px-5 py-4 font-semibold">ชื่อ-นามสกุล</th>
                      <th className="px-5 py-4 font-semibold">ศึกษาต่อหรือไม่</th>
                      <th className="px-5 py-4 font-semibold text-right">สถานะ</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rowsForPreview.map((row) => (
                      <tr key={`${row.order}-${row.student_no}`} className="border-t">
                        <td className="px-5 py-4 font-medium">{row.student_no}</td>
                        <td className="px-5 py-4">
                          {row.first_name} {row.last_name}
                        </td>
                        <td className="px-5 py-4 text-muted-foreground">{row.status_text}</td>
                        <td className="px-5 py-4 text-right">
                          <Badge variant="outline">{row.status_code}</Badge>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="rounded-lg border border-dashed bg-muted/40 p-8 text-center text-muted-foreground">
                ยังไม่มีข้อมูลตัวอย่าง เลือกชั้นปีและไฟล์ Excel แล้วกดตรวจสอบข้อมูล
              </div>
            )}

            {preview?.warnings.length ? (
              <Alert className="mt-4 border-amber-200 bg-amber-50 text-amber-900">
                <AlertCircle className="h-4 w-4" />
                <AlertTitle>มีรายการที่ควรตรวจทาน {preview.warnings.length} รายการ</AlertTitle>
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
                <AlertTitle>ไม่พบคำเตือนจากไฟล์นี้</AlertTitle>
              </Alert>
            ) : null}
          </CardContent>
        </Card>

        <Card className="relative overflow-visible">
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
              <div className="text-sm text-muted-foreground">ระดับชั้น: {detectedLevel}</div>
              <div className="rounded-lg border bg-muted/40 px-3 py-2 text-sm text-foreground">
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

            <div className="grid gap-3 rounded-lg border bg-muted/40 p-4">
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
                className="h-11"
                disabled={!canStart}
                onClick={onStartLive}
              >
                <RefreshCw className="h-4 w-4" />
                เริ่มส่งข้อมูลเข้า DMC
              </Button>
              {startHint ? <div className="text-sm text-muted-foreground">{startHint}</div> : null}
              {showDryRun ? (
                <Button variant="outline" disabled={!canDryRun} onClick={onStartDryRun}>
                  <FileCheck2 className="h-4 w-4" />
                  ทดสอบก่อนส่งจริง
                </Button>
              ) : null}
            </div>

            <div className="space-y-2">
              <Progress value={progressPercent} className="h-2" />
              <div className="text-center text-sm text-muted-foreground">
                {currentJob ? `อัปโหลดข้อมูลคนที่ ${processedLabel}` : "ยังไม่มีงานที่กำลังทำ"}
              </div>
            </div>

            {currentJob ? (
              <div className="grid gap-2 rounded-lg border bg-background p-4 text-sm">
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
                    <div>แถวใน DMC ทั้งหมด: {runSummary.dmc_rows_total}</div>
                    <div>จับคู่จาก Excel: {runSummary.matched_from_excel}</div>
                    <div>default 207: {runSummary.default_207}</div>
                    <div>Excel ไม่พบใน DMC: {runSummary.excel_missing}</div>
                  </>
                ) : null}
                {completionSummary ? (
                  <>
                    <Separator />
                    <div className="grid gap-2 sm:grid-cols-2">
                      <div className="rounded-md border bg-muted/30 p-3">
                        <div className="text-xs text-muted-foreground">สำเร็จ</div>
                        <div className="mt-1 text-xl font-semibold">{completionSummary.succeeded}</div>
                      </div>
                      <div className="rounded-md border bg-muted/30 p-3">
                        <div className="text-xs text-muted-foreground">ล้มเหลว/ต้องตรวจ</div>
                        <div className="mt-1 text-xl font-semibold">{completionSummary.failed}</div>
                      </div>
                    </div>
                    <div className="grid gap-3 lg:grid-cols-2">
                      <CompletionList
                        title="รายชื่อที่สำเร็จ"
                        items={completionSummary.success_items}
                        emptyText="ยังไม่มีรายการสำเร็จ"
                      />
                      <CompletionList
                        title="รายชื่อที่ล้มเหลว/ต้องตรวจ"
                        items={completionSummary.failure_items}
                        emptyText="ไม่มีรายการล้มเหลว"
                      />
                    </div>
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
              <Button size="sm" variant="secondary" disabled={!canResumeCurrentJob} onClick={onResume}>
                <LogIn className="h-4 w-4" />
                {resumeLabel}
              </Button>
              <Button variant="destructive" size="sm" disabled={!activeJobId} onClick={onCancel}>
                <Square className="h-4 w-4" />
                ยกเลิกงาน
              </Button>
            </div>

            <div className="rounded-lg border bg-background p-4">
              <div className="font-semibold">{reportTools.title}</div>
              <div className="mt-1 text-sm text-muted-foreground">
                {reportTools.description}
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                <Button size="sm" disabled={!latestCsvPath} onClick={() => latestCsvPath && onRevealPath(latestCsvPath)}>
                  <FileSpreadsheet className="h-4 w-4" />
                  {reportTools.openLatestCsv}
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  disabled={!latestSummaryReportPath}
                  onClick={() => latestSummaryReportPath && onRevealPath(latestSummaryReportPath)}
                >
                  <FileSpreadsheet className="h-4 w-4" />
                  เปิดสรุป Excel
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
        <SystemErrorAlert message={visibleErrorMessage} onRetry={onConnect} />
      ) : null}
      {supportMessage ? (
        <Alert>
          <AlertDescription className="break-words">{supportMessage}</AlertDescription>
        </Alert>
      ) : null}

      <Card>
        <CardHeader className="pb-3">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <CardTitle>เครื่องมือเพิ่มเติม</CardTitle>
              <div className="mt-1 text-sm text-muted-foreground">
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
                <div className="space-y-3 rounded-lg border bg-muted/40 p-4">
                  <div className="font-semibold">เชื่อมต่อตัวเชื่อมระบบ</div>
                  <div className="text-sm text-muted-foreground">{connectionLabel(connectionState)}</div>
                  <Button className="w-full" variant="outline" onClick={onConnect} disabled={connectionState === "connecting"}>
                    {connectionState === "connecting" ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
                    เชื่อมต่อระบบ
                  </Button>
                </div>

                <div className="space-y-3 rounded-lg border bg-muted/40 p-4">
                  <div className="font-semibold">บัญชีและเครดิต</div>
                  <div className="text-sm text-muted-foreground">
                    {accountStatus?.signed_in ? accountStatus.email : accountCopy.signInRequired}
                  </div>
                  <div className="grid grid-cols-3 gap-2 text-sm">
                    <div className="rounded-lg border bg-background p-2">
                      <div className="text-xs text-muted-foreground">เครดิตรวม</div>
                      <div className="font-semibold">{accountStatus?.wallet?.balance ?? "-"}</div>
                    </div>
                    <div className="rounded-lg border bg-background p-2">
                      <div className="text-xs text-muted-foreground">กันไว้</div>
                      <div className="font-semibold">{accountStatus?.wallet?.reserved ?? "-"}</div>
                    </div>
                    <div className="rounded-lg border bg-background p-2">
                      <div className="text-xs text-muted-foreground">พร้อมใช้</div>
                      <div className="font-semibold">{accountStatus?.wallet?.available ?? "-"}</div>
                    </div>
                  </div>
                  <Button variant="outline" onClick={onRefreshWallet} disabled={!accountStatus?.signed_in}>
                    <RefreshCw className="h-4 w-4" />
                    {accountCopy.refreshCredits}
                  </Button>
                </div>

                <div className="space-y-3 rounded-lg border bg-muted/40 p-4">
                  <div className="font-semibold">Config และ Chromium</div>
                  <div className="text-sm text-muted-foreground">
                    สถานะ config: {moduleConfigStatus ? `${moduleConfigStatus.version} (${moduleConfigStatus.source})` : "-"}
                  </div>
                  <div className="text-sm text-muted-foreground">
                    สถานะ runtime: {browserRuntimeStatus?.message ?? browserRuntimeStatus?.state ?? "-"}
                  </div>
                  {browserRuntimeProgress ? (
                    <div className="rounded-lg border bg-background p-3 text-sm">
                      <div className="font-semibold">{describeBrowserRuntimePhase(browserRuntimeProgress.phase)}</div>
                      <div className="mt-1 text-muted-foreground">{browserRuntimeProgress.message}</div>
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
                    <div className="text-xs text-muted-foreground">
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

      <Card className="px-4 py-3 text-xs text-muted-foreground">
        สถานะล่าสุด: บัญชีตรวจเมื่อ {formatTimestamp(accountStatus?.last_checked_at ?? null)} · config ตรวจเมื่อ{" "}
        {formatTimestamp(moduleConfigStatus?.checked_at ?? null)}
      </Card>
    </div>
  );
}
