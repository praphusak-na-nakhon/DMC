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
  UserCircle2,
  UsersRound,
} from "lucide-react";
import { describeBrowserRuntimePhase, formatBytes, formatTimestamp } from "../lib/appUi";
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
  BrowserRuntimeStatus,
  JobStatusSnapshot,
  LicenseStatus,
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
  isDownloadingTemplate: boolean;
  isBootstrappingBrowser: boolean;
  licenseBlocksStart: boolean;
  browserRuntimeBlocksStart: boolean;
  validationBlocksStart: boolean;
  preflightRowsAccepted: number | null;
  preflightRowsTotal: number | null;
  currentJobNeedsAuth: boolean;
  onBackHome: () => void;
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
  onDownloadTemplate: () => void;
  onBootstrapBrowserRuntime: () => void;
  onReloadBrowserRuntime: () => void;
  onSelectJob: (job: JobStatusSnapshot) => void;
  onResumeExisting: (job: JobStatusSnapshot) => void;
  onRevealPath: (path: string) => void;
  describeLicenseStatus: (status: LicenseStatus) => string;
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
    success: "border-emerald-200 bg-emerald-50 text-emerald-800",
    warning: "border-amber-200 bg-amber-50 text-amber-800",
    danger: "border-red-200 bg-red-50 text-red-700",
    muted: "border-slate-200 bg-white text-slate-600",
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
  isDownloadingTemplate,
  isBootstrappingBrowser,
  licenseBlocksStart,
  browserRuntimeBlocksStart,
  validationBlocksStart,
  preflightRowsAccepted,
  preflightRowsTotal,
  currentJobNeedsAuth,
  onBackHome,
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
  onDownloadTemplate,
  onBootstrapBrowserRuntime,
  onReloadBrowserRuntime,
  onSelectJob,
  onResumeExisting,
  onRevealPath,
  describeLicenseStatus,
}: GraduationWizardProps) {
  const [selectedGrade, setSelectedGrade] = useState<"m3" | "m6" | null>(null);
  const [activeStep, setActiveStep] = useState(1);
  const [showSupportDrawer, setShowSupportDrawer] = useState(false);
  const [supportSection, setSupportSection] = useState<"settings" | "history" | "messages">("settings");
  const runtimeReady = browserRuntimeStatus?.installed ?? false;
  const licenseReady = licenseStatus?.can_start_jobs ?? false;
  const canStart =
    Boolean(selectedGrade) &&
    !isStartingJob &&
    !isBootstrappingBrowser &&
    !licenseBlocksStart &&
    !browserRuntimeBlocksStart &&
    !validationBlocksStart;
  const acceptedRows = preview?.rows_accepted ?? preflightRowsAccepted ?? 0;
  const totalRows = preview?.rows_total ?? preflightRowsTotal ?? null;
  const detectedLevel =
    preview?.detected_level ?? (selectedGrade === "m3" ? "ม.3" : selectedGrade === "m6" ? "ม.6" : "ยังไม่ได้เลือก");
  const fileName = excelPath.trim() ? compactPath(excelPath.trim()) : "ยังไม่ได้เลือกไฟล์";
  const reportPath = currentJob?.report_path ?? null;
  const reviewReportPath = currentJob?.review_report_path ?? null;
  const reportDirectory = reportPath?.replace(/[\\/][^\\/]+$/, "") ?? reviewReportPath?.replace(/[\\/][^\\/]+$/, "");
  const runSummary = currentJob?.run_summary ?? null;
  const processedLabel =
    currentJob?.total !== null && currentJob?.total !== undefined && currentJob.processed > currentJob.total
      ? `${currentJob.processed} แถวบนเว็บ`
      : `${currentJob?.processed ?? 0}/${currentJob?.total ?? "-"}`;

  const rowsForPreview = useMemo(() => preview?.preview.slice(0, 5) ?? [], [preview]);
  const visibleErrorMessage = errorMessage?.includes("transformCallback") ? null : errorMessage;

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
                label="Sidecar"
                value={connectionLabel(connectionState)}
                tone={connectionState === "ready" ? "success" : connectionState === "error" ? "danger" : "warning"}
              />
              <SystemPill
                label="License"
                value={licenseStatus ? describeLicenseStatus(licenseStatus) : "-"}
                tone={licenseReady ? "success" : "warning"}
              />
              <SystemPill
                label="Chromium"
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
              <Progress value={preview ? 100 : progressPercent} className="h-3" />
            </div>

            <div className="grid gap-3 rounded-xl border bg-slate-50 p-4">
              <div className="grid grid-cols-[1fr_auto] items-center gap-3">
                <Label htmlFor="wizard-min-score">Minimum score</Label>
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
              <Button
                className="h-16 bg-blue-600 text-lg hover:bg-blue-700"
                disabled={!canStart}
                onClick={onStartLive}
              >
                <RefreshCw className="h-7 w-7" />
                เริ่มส่งข้อมูลเข้า DMC
              </Button>
              <Button variant="outline" disabled={!canStart} onClick={onStartDryRun}>
                <FileCheck2 className="h-4 w-4" />
                เริ่ม Dry Run ก่อนส่งจริง
              </Button>
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
                  <Badge variant="outline">{currentJob.status}</Badge>
                </div>
                <div>สำเร็จ: {currentJob.succeeded}</div>
                <div>ต้องตรวจเพิ่ม/ผิดพลาด: {currentJob.failed}</div>
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
                Pause
              </Button>
              <Button size="sm" variant="secondary" disabled={!currentJobNeedsAuth} onClick={onResume}>
                <LogIn className="h-4 w-4" />
                Resume หลัง Login
              </Button>
              <Button variant="destructive" size="sm" disabled={!activeJobId} onClick={onCancel}>
                <Square className="h-4 w-4" />
                Cancel
              </Button>
            </div>

            {(reportPath || reviewReportPath) ? (
              <div className="flex flex-wrap gap-2">
                {reportPath ? (
                  <Button size="sm" onClick={() => onRevealPath(reportPath)}>
                    เปิด report
                  </Button>
                ) : null}
                {reviewReportPath ? (
                  <Button size="sm" variant="outline" onClick={() => onRevealPath(reviewReportPath)}>
                    เปิด review
                  </Button>
                ) : null}
                {reportDirectory ? (
                  <Button size="sm" variant="outline" onClick={() => onRevealPath(reportDirectory)}>
                    โฟลเดอร์ report
                  </Button>
                ) : null}
              </div>
            ) : null}
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
                การตั้งค่า, ประวัติการใช้งาน และข้อความจาก sidecar
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
                ข้อความจาก Sidecar ({sidecarMessages.length})
              </Button>
            </div>

            {supportSection === "settings" ? (
              <div className="grid gap-4 lg:grid-cols-3">
                <div className="space-y-3 rounded-xl border bg-slate-50 p-4">
                  <div className="font-semibold">เชื่อมต่อ Sidecar</div>
                  <div className="text-sm text-slate-600">{connectionLabel(connectionState)}</div>
                  <Button className="w-full" variant="outline" onClick={onConnect} disabled={connectionState === "connecting"}>
                    {connectionState === "connecting" ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
                    เชื่อมต่อระบบ
                  </Button>
                </div>

                <div className="space-y-3 rounded-xl border bg-slate-50 p-4">
                  <div className="font-semibold">License</div>
                  <Input value={licenseKey} onChange={(event) => onLicenseKeyChange(event.target.value)} placeholder="DMC-XXXX-XXXX" />
                  <Input value={deviceName} onChange={(event) => onDeviceNameChange(event.target.value)} placeholder="desktop-01" />
                  <div className="flex flex-wrap gap-2">
                    <Button disabled={connectionState !== "ready" || isActivatingLicense} onClick={onActivateLicense}>
                      {isActivatingLicense ? <Loader2 className="h-4 w-4 animate-spin" /> : <KeyRound className="h-4 w-4" />}
                      Activate
                    </Button>
                    <Button variant="outline" onClick={onRefreshLicense}>
                      <ShieldCheck className="h-4 w-4" />
                      Refresh
                    </Button>
                  </div>
                </div>

                <div className="space-y-3 rounded-xl border bg-slate-50 p-4">
                  <div className="font-semibold">Config / Chromium</div>
                  <div className="text-sm text-slate-600">
                    Config: {moduleConfigStatus ? `${moduleConfigStatus.version} (${moduleConfigStatus.source})` : "-"}
                  </div>
                  <div className="text-sm text-slate-600">
                    Runtime: {browserRuntimeStatus?.message ?? browserRuntimeStatus?.state ?? "-"}
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
                      Sync Config
                    </Button>
                    {browserRuntimeStatus && !browserRuntimeStatus.installed ? (
                      <Button
                        disabled={connectionState !== "ready" || isBootstrappingBrowser || !browserRuntimeStatus.bootstrap_supported}
                        onClick={onBootstrapBrowserRuntime}
                      >
                        {isBootstrappingBrowser ? <Loader2 className="h-4 w-4 animate-spin" /> : <UploadCloud className="h-4 w-4" />}
                        Install Chromium
                      </Button>
                    ) : (
                      <Button variant="outline" onClick={onReloadBrowserRuntime}>
                        <RefreshCw className="h-4 w-4" />
                        Re-check Runtime
                      </Button>
                    )}
                  </div>
                  {browserRuntimeStatus?.estimated_download_bytes ? (
                    <div className="text-xs text-slate-500">
                      Download size: {formatBytes(browserRuntimeStatus.estimated_download_bytes)}
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
                onSelectJob={onSelectJob}
                onResumeExisting={onResumeExisting}
                onRevealPath={onRevealPath}
              />
            ) : null}

            {supportSection === "messages" ? <SidecarLogPanel sidecarMessages={sidecarMessages} /> : null}
          </CardContent>
        ) : null}
      </Card>

      <Card className="rounded-2xl border-slate-200 bg-white/80 px-4 py-3 text-xs text-slate-500">
        สถานะล่าสุด: license checked {formatTimestamp(licenseStatus?.last_checked_at ?? null)} · config checked{" "}
        {formatTimestamp(moduleConfigStatus?.checked_at ?? null)}
      </Card>
    </div>
  );
}
