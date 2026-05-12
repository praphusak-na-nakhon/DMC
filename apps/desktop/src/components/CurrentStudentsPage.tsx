import {
  AlertTriangle,
  CheckCircle2,
  Download,
  FileJson,
  FileSpreadsheet,
  Loader2,
  PauseCircle,
  PlayCircle,
  RefreshCw,
  Search,
  Square,
  UploadCloud,
  UserPlus,
} from "lucide-react";
import { useMemo, useState } from "react";
import type { ReactNode } from "react";
import { describeUserFacingError } from "../lib/errorMessages";
import {
  exportCurrentStudentBlankForm,
  openCurrentStudentImportDialog,
  saveTemplateDialog,
  validateCurrentStudentImportForm,
} from "../lib/rpcClient";
import type { CurrentStudentsImportRowPreview, ValidateCurrentStudentsImportFormResponse } from "../types/contracts";
import type { JobStatusSnapshot } from "../types/contracts";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./ui/card";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { Progress } from "./ui/progress";
import { PageHeader } from "./PageHeader";
import { JobProgressPanel } from "./JobProgressPanel";
import { SystemErrorAlert } from "./SystemErrorAlert";

type CurrentStudentsPageProps = {
  onBackHome: () => void;
  onRevealPath: (path: string) => void;
  onRetryRuntime?: () => void;
  currentJob?: JobStatusSnapshot | null;
  activeJobId?: string | null;
  progressPercent?: number;
  isStartingJob?: boolean;
  externalErrorMessage?: string | null;
  onStartDmcImport?: (jsonPath: string, readyRows: number, dryRun: boolean) => Promise<void> | void;
  onRefreshStatus?: () => void;
  onPause?: () => void;
  onResume?: () => void;
  onCancel?: () => void;
};

const errorMessages: Record<string, string> = {
  CURRENT_STUDENTS_INPUT_NOT_FOUND: "ไม่พบไฟล์ที่เลือก",
  CURRENT_STUDENTS_INPUT_NOT_FILE: "พาธที่เลือกไม่ใช่ไฟล์",
  CURRENT_STUDENTS_UNSUPPORTED_INPUT_TYPE: "รองรับเฉพาะไฟล์ .xlsx, .xlsm หรือ .json",
  CURRENT_STUDENTS_IMPORT_HEADERS_NOT_FOUND: "ไม่พบหัวตารางของฟอร์มนักเรียนปัจจุบัน",
  CURRENT_STUDENTS_TEMPLATE_UNSUPPORTED_TYPE: "ฟอร์มเปล่าต้องเป็นไฟล์ .xlsx",
  CURRENT_STUDENTS_JSON_INVALID: "ไฟล์ JSON ไม่ถูกต้อง",
  CURRENT_STUDENTS_JSON_UNSUPPORTED_SCHEMA: "ไฟล์ JSON ต้องเป็น schema dmc_form_json.v1 จากเมนูแปลงฟอร์ม",
};

const issueLabels: Record<string, string> = {
  INVALID_OPERATION_TYPE: "ประเภทงานไม่ถูกต้อง",
  INVALID_CITIZEN_ID: "เลขประจำตัวประชาชนไม่ผ่าน checksum",
  INVALID_STUDENT_NO: "เลขประจำตัวนักเรียนต้องเป็นตัวเลขไม่เกิน 10 หลัก",
  INVALID_ROOM: "ห้องที่ย้ายเข้าต้องเป็นตัวเลขไม่เกิน 2 หลัก",
  DUPLICATE_CITIZEN_ID: "เลขประจำตัวประชาชนซ้ำ",
  DMC_TRANSFER_LEVEL_UNSUPPORTED: "ยังแปลงชั้นเป็นรหัส DMC สำหรับย้ายเข้าไม่ได้",
  MISSING_OPERATION_TYPE: "ยังไม่กรอกประเภทงาน",
  MISSING_SCHOOL_YEAR: "ยังไม่กรอกปีการศึกษา",
  MISSING_STUDENT_NO: "ยังไม่มีเลขประจำตัวนักเรียน",
  MISSING_GRADE: "ยังไม่มีชั้นที่ย้ายเข้า",
  MISSING_ROOM: "ยังไม่มีห้องที่ย้ายเข้า",
  MISSING_CITIZEN_ID: "ยังไม่กรอกเลขประจำตัวประชาชน",
  MISSING_PREFIX: "ยังไม่กรอกคำนำหน้า",
  MISSING_FIRST_NAME: "ยังไม่กรอกชื่อ",
  MISSING_LAST_NAME: "ยังไม่กรอกนามสกุล",
};

export function CurrentStudentsPage({
  onBackHome,
  onRevealPath,
  onRetryRuntime,
  currentJob = null,
  activeJobId = null,
  progressPercent = 0,
  isStartingJob = false,
  externalErrorMessage = null,
  onStartDmcImport,
  onRefreshStatus,
  onPause,
  onResume,
  onCancel,
}: CurrentStudentsPageProps) {
  const [excelPath, setExcelPath] = useState("");
  const [blankFormPath, setBlankFormPath] = useState<string | null>(null);
  const [validation, setValidation] = useState<ValidateCurrentStudentsImportFormResponse | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isDownloadingTemplate, setIsDownloadingTemplate] = useState(false);
  const [isValidating, setIsValidating] = useState(false);
  const [progress, setProgress] = useState(0);

  const visiblePreview = useMemo(() => validation?.preview.slice(0, 50) ?? [], [validation]);
  const selectedImportPath = excelPath.trim();
  const isJsonImport = /\.json$/i.test(selectedImportPath);
  const canStartDmcImport = Boolean(
    validation &&
      isJsonImport &&
      validation.summary.ready_rows > 0 &&
      validation.summary.invalid_rows === 0 &&
      validation.summary.needs_review_rows === 0,
  );
  const currentStudentsJob = currentJob?.module === "currentStudents" ? currentJob : null;

  async function handleDownloadBlankForm() {
    setIsDownloadingTemplate(true);
    setErrorMessage(null);
    try {
      const outputPath = await saveTemplateDialog("current-students-import-template.xlsx");
      if (!outputPath) {
        return;
      }
      const result = await exportCurrentStudentBlankForm(outputPath);
      setBlankFormPath(result.output_path);
      onRevealPath(result.output_path);
    } catch (error) {
      setErrorMessage(readableError(error));
    } finally {
      setIsDownloadingTemplate(false);
    }
  }

  async function handleBrowseExcel() {
    const selected = await openCurrentStudentImportDialog();
    if (selected) {
      setExcelPath(selected);
      setValidation(null);
      setErrorMessage(null);
      setProgress(0);
    }
  }

  async function handleValidate() {
    const selectedPath = excelPath.trim();
    if (!selectedPath) {
      setErrorMessage("กรุณาเลือกไฟล์ Excel หรือ JSON ที่มีข้อมูลครบแล้วก่อน");
      return;
    }
    setIsValidating(true);
    setValidation(null);
    setErrorMessage(null);
    setProgress(20);
    try {
      const result = await validateCurrentStudentImportForm(selectedPath);
      setValidation(result);
      setProgress(100);
    } catch (error) {
      setProgress(0);
      setErrorMessage(readableError(error));
    } finally {
      setIsValidating(false);
    }
  }

  async function handleStartDmcImport(dryRun: boolean) {
    if (!validation) {
      setErrorMessage("กรุณาตรวจไฟล์ JSON ก่อนเริ่มงาน DMC");
      return;
    }
    if (!isJsonImport) {
      setErrorMessage("งานกรอกหน้า DMC ย้ายเข้านักเรียนรองรับเฉพาะไฟล์ JSON");
      return;
    }
    if (!canStartDmcImport) {
      setErrorMessage("ไฟล์ JSON ยังมีรายการที่ต้องแก้ไขก่อนส่งเข้า DMC");
      return;
    }
    setErrorMessage(null);
    await onStartDmcImport?.(selectedImportPath, validation.summary.ready_rows, dryRun);
  }

  function readableError(error: unknown): string {
    const raw = error instanceof Error ? error.message : String(error);
    const code = raw.match(/[A-Z][A-Z0-9_]+/)?.[0] ?? raw;
    return errorMessages[code] ?? describeUserFacingError(error);
  }

  return (
    <div className="space-y-6">
      <PageHeader
        onBackHome={onBackHome}
        badge="รับไฟล์พร้อมนำเข้า"
        title="นักเรียนปัจจุบัน (ย้ายเข้า/เพิ่มนักเรียน)"
        description="ดาวน์โหลดฟอร์มเปล่า หรืออัปโหลด Excel/JSON จากเมนูแปลงฟอร์ม/จากผู้ใช้ เพื่อเตรียมตรวจข้อมูลก่อนนำเข้า DMC"
        icon={<UserPlus className="h-5 w-5 text-primary" />}
      />

      {errorMessage || externalErrorMessage ? (
        <SystemErrorAlert message={errorMessage ?? externalErrorMessage ?? ""} onRetry={onRetryRuntime} retryWhen="runtime" />
      ) : null}

      <section className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_390px]">
        <Card>
          <CardHeader>
            <CardTitle>ฟอร์มนักเรียนปัจจุบัน</CardTitle>
            <CardDescription>รองรับฟอร์ม Excel จากหน้านี้ หรือ JSON dmc_form_json.v1 จากเมนูแปลงฟอร์ม</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4">
            <div className="flex flex-wrap gap-2">
              <Button variant="outline" disabled={isDownloadingTemplate} onClick={() => void handleDownloadBlankForm()}>
                {isDownloadingTemplate ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
                ดาวน์โหลดฟอร์มเปล่า
              </Button>
              {blankFormPath ? (
                <Button variant="secondary" onClick={() => onRevealPath(blankFormPath)}>
                  <FileSpreadsheet className="h-4 w-4" />
                  เปิดฟอร์มล่าสุด
                </Button>
              ) : null}
            </div>

            <div className="grid gap-2">
              <Label>Excel หรือ JSON ที่กรอกข้อมูลครบแล้ว</Label>
              <div className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_auto]">
                <Input
                  value={excelPath}
                  onChange={(event) => {
                    setExcelPath(event.target.value);
                    setValidation(null);
                    setProgress(0);
                  }}
                  placeholder="C:\\dmc\\current-students-import.xlsx หรือ C:\\dmc\\dmc-form-data-2569.json"
                />
                <Button variant="outline" onClick={() => void handleBrowseExcel()}>
                  <UploadCloud className="h-4 w-4" />
                  เลือกไฟล์
                </Button>
              </div>
            </div>

            <div className="flex flex-wrap gap-2">
              <Button disabled={isValidating || !excelPath.trim()} onClick={() => void handleValidate()}>
                {isValidating ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
                ตรวจไฟล์นำเข้า
              </Button>
            </div>
            {!excelPath.trim() ? (
              <div className="text-sm text-muted-foreground">เลือก Excel หรือ JSON ที่กรอกข้อมูลครบแล้วก่อนตรวจไฟล์นำเข้า</div>
            ) : null}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>สถานะ</CardTitle>
            <CardDescription className="flex items-center gap-2">
              {isValidating ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
              {validation ? "ผลตรวจไฟล์ล่าสุด" : isValidating ? "กำลังตรวจไฟล์นำเข้า" : "รออัปโหลดฟอร์ม"}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Progress value={progress} />
            {validation ? (
              <div className="grid gap-3 text-sm">
                <SummaryRow label="แถวทั้งหมด" value={`${validation.summary.rows_total}`} />
                <SummaryRow label="พร้อมใช้" value={`${validation.summary.ready_rows}`} />
                <SummaryRow label="ต้องตรวจ" value={`${validation.summary.needs_review_rows}`} />
                <SummaryRow label="ผิดรูปแบบ" value={`${validation.summary.invalid_rows}`} />
              </div>
            ) : (
              <div className="rounded-md border bg-muted/40 p-3 text-sm text-muted-foreground">
                ยังไม่มีผลตรวจ เลือกไฟล์ Excel แล้วกดตรวจไฟล์นำเข้าเพื่อดูสถานะ
              </div>
            )}
          </CardContent>
        </Card>
      </section>

      {validation ? (
        <>
          <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Metric icon={<CheckCircle2 className="h-4 w-4" />} label="พร้อมนำเข้า" value={validation.summary.ready_rows} />
            <Metric icon={<Search className="h-4 w-4" />} label="ต้องตรวจ" value={validation.summary.needs_review_rows} />
            <Metric icon={<AlertTriangle className="h-4 w-4" />} label="ผิดรูปแบบ" value={validation.summary.invalid_rows} />
            <Metric icon={<FileSpreadsheet className="h-4 w-4" />} label="เลขบัตรซ้ำ" value={validation.summary.duplicate_citizen_ids} />
          </section>

          <Card>
            <CardHeader>
              <CardTitle>ส่งเข้า DMC ย้ายเข้านักเรียน</CardTitle>
              <CardDescription>
                ใช้เฉพาะ JSON schema dmc_form_json.v1 เพื่อกรอกหน้า https://portal.bopp-obec.info/obec69/studentin/add_cif
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex flex-wrap gap-2">
                <Button
                  variant="outline"
                  disabled={!onStartDmcImport || isStartingJob || !canStartDmcImport}
                  onClick={() => void handleStartDmcImport(true)}
                >
                  {isStartingJob ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileJson className="h-4 w-4" />}
                  Dry run หน้า DMC
                </Button>
                <Button
                  variant="destructive"
                  disabled={!onStartDmcImport || isStartingJob || !canStartDmcImport}
                  onClick={() => void handleStartDmcImport(false)}
                >
                  {isStartingJob ? <Loader2 className="h-4 w-4 animate-spin" /> : <UploadCloud className="h-4 w-4" />}
                  นำเข้า DMC จริง
                </Button>
              </div>
              {!isJsonImport ? (
                <div className="text-sm text-muted-foreground">การกรอกหน้า DMC อัตโนมัติรองรับ JSON เท่านั้น ส่วน Excel ใช้สำหรับตรวจและเตรียมข้อมูล</div>
              ) : !canStartDmcImport ? (
                <div className="text-sm text-muted-foreground">ต้องไม่มีรายการผิดรูปแบบหรือรายการต้องตรวจ ก่อนเริ่มส่งเข้า DMC</div>
              ) : (
                <div className="text-sm text-muted-foreground">พร้อมส่ง {validation.summary.ready_rows} รายการ ระบบจะเปิด Chromium และหยุดให้ login DMC เมื่อจำเป็น</div>
              )}
            </CardContent>
          </Card>

          <DmcJobControls
            currentJob={currentStudentsJob}
            activeJobId={activeJobId}
            progressPercent={progressPercent}
            onRevealPath={onRevealPath}
            onRefreshStatus={onRefreshStatus}
            onPause={onPause}
            onResume={onResume}
            onCancel={onCancel}
          />

          <Card>
            <CardHeader>
              <CardTitle>ตัวอย่างผลตรวจ</CardTitle>
              <CardDescription>แสดงไม่เกิน 50 แถวแรกจากไฟล์ที่อัปโหลด</CardDescription>
            </CardHeader>
            <CardContent>
              {visiblePreview.length > 0 ? (
                <div className="grid gap-3">
                  {visiblePreview.map((row) => (
                    <ImportPreviewRow key={row.row_index} row={row} />
                  ))}
                </div>
              ) : (
                <div className="rounded-md border bg-muted/40 p-4 text-sm text-muted-foreground">ไม่พบข้อมูลในไฟล์</div>
              )}
            </CardContent>
          </Card>
        </>
      ) : null}
      {!validation ? (
        <DmcJobControls
          currentJob={currentStudentsJob}
          activeJobId={activeJobId}
          progressPercent={progressPercent}
          onRevealPath={onRevealPath}
          onRefreshStatus={onRefreshStatus}
          onPause={onPause}
          onResume={onResume}
          onCancel={onCancel}
        />
      ) : null}
    </div>
  );
}

function DmcJobControls({
  currentJob,
  activeJobId,
  progressPercent,
  onRevealPath,
  onRefreshStatus,
  onPause,
  onResume,
  onCancel,
}: {
  currentJob: JobStatusSnapshot | null;
  activeJobId: string | null;
  progressPercent: number;
  onRevealPath: (path: string) => void;
  onRefreshStatus?: () => void;
  onPause?: () => void;
  onResume?: () => void;
  onCancel?: () => void;
}) {
  if (!currentJob) {
    return null;
  }
  const canResume = Boolean(activeJobId && (currentJob.needs_auth || currentJob.status === "paused"));
  const canPause = Boolean(activeJobId && currentJob.status === "running");
  const canCancel = Boolean(activeJobId && (currentJob.status === "running" || currentJob.status === "paused"));
  return (
    <section className="grid gap-3">
      <JobProgressPanel currentJob={currentJob} progressPercent={progressPercent} onRevealPath={onRevealPath} />
      <div className="flex flex-wrap gap-2">
        <Button variant="outline" disabled={!activeJobId || !onRefreshStatus} onClick={() => onRefreshStatus?.()}>
          <RefreshCw className="h-4 w-4" />
          Refresh
        </Button>
        <Button variant="outline" disabled={!canResume || !onResume} onClick={() => onResume?.()}>
          <PlayCircle className="h-4 w-4" />
          Resume
        </Button>
        <Button variant="outline" disabled={!canPause || !onPause} onClick={() => onPause?.()}>
          <PauseCircle className="h-4 w-4" />
          Pause
        </Button>
        <Button variant="destructive" disabled={!canCancel || !onCancel} onClick={() => onCancel?.()}>
          <Square className="h-4 w-4" />
          Cancel
        </Button>
      </div>
    </section>
  );
}

function ImportPreviewRow({ row }: { row: CurrentStudentsImportRowPreview }) {
  const variant = row.status === "ready" ? "default" : row.status === "invalid" ? "destructive" : "secondary";
  return (
    <div className="rounded-md border bg-background p-4">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant={variant}>{row.status === "ready" ? "พร้อมใช้" : row.status === "invalid" ? "ผิดรูปแบบ" : "ต้องตรวจ"}</Badge>
            <Badge variant="outline">แถว {row.row_index}</Badge>
            {row.operation_type ? <Badge variant="outline">{row.operation_type}</Badge> : null}
          </div>
          <div className="mt-2 break-words text-lg font-semibold">{row.full_name || "-"}</div>
          <div className="mt-1 text-sm text-muted-foreground">
            เลขประจำตัว: {row.student_no ?? "-"} | เลขบัตร: {row.citizen_id ?? "-"}
          </div>
        </div>
      </div>
      {row.issues.length > 0 ? (
        <div className="mt-3 flex flex-wrap gap-2">
          {row.issues.map((issue) => (
            <Badge key={issue} variant="secondary">
              {issueLabels[issue] ?? issue}
            </Badge>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function SummaryRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-3">
      <span className="text-muted-foreground">{label}</span>
      <strong className="text-right">{value}</strong>
    </div>
  );
}

function Metric({ icon, label, value }: { icon: ReactNode; label: string; value: number }) {
  return (
    <div className="rounded-md border bg-muted/40 p-3">
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        {icon}
        {label}
      </div>
      <div className="mt-2 text-2xl font-bold">{value}</div>
    </div>
  );
}
