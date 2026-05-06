import { AlertTriangle, ArrowLeft, CheckCircle2, Download, FileSpreadsheet, Loader2, Search, UploadCloud, UserPlus } from "lucide-react";
import { useMemo, useState } from "react";
import type { ReactNode } from "react";
import { exportCurrentStudentBlankForm, openExcelDialog, saveTemplateDialog, validateCurrentStudentImportForm } from "../lib/rpcClient";
import type { CurrentStudentsImportRowPreview, ValidateCurrentStudentsImportFormResponse } from "../types/contracts";
import { Alert, AlertDescription } from "./ui/alert";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./ui/card";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { Progress } from "./ui/progress";

type CurrentStudentsPageProps = {
  onBackHome: () => void;
  onRevealPath: (path: string) => void;
};

const errorMessages: Record<string, string> = {
  CURRENT_STUDENTS_INPUT_NOT_FOUND: "ไม่พบไฟล์ที่เลือก",
  CURRENT_STUDENTS_INPUT_NOT_FILE: "พาธที่เลือกไม่ใช่ไฟล์",
  CURRENT_STUDENTS_UNSUPPORTED_INPUT_TYPE: "รองรับเฉพาะไฟล์ .xlsx หรือ .xlsm",
  CURRENT_STUDENTS_IMPORT_HEADERS_NOT_FOUND: "ไม่พบหัวตารางของฟอร์มนักเรียนปัจจุบัน",
  CURRENT_STUDENTS_TEMPLATE_UNSUPPORTED_TYPE: "ฟอร์มเปล่าต้องเป็นไฟล์ .xlsx",
};

const issueLabels: Record<string, string> = {
  INVALID_OPERATION_TYPE: "ประเภทงานไม่ถูกต้อง",
  INVALID_CITIZEN_ID: "เลขประจำตัวประชาชนไม่ผ่าน checksum",
  DUPLICATE_CITIZEN_ID: "เลขประจำตัวประชาชนซ้ำ",
  MISSING_OPERATION_TYPE: "ยังไม่กรอกประเภทงาน",
  MISSING_SCHOOL_YEAR: "ยังไม่กรอกปีการศึกษา",
  MISSING_CITIZEN_ID: "ยังไม่กรอกเลขประจำตัวประชาชน",
  MISSING_PREFIX: "ยังไม่กรอกคำนำหน้า",
  MISSING_FIRST_NAME: "ยังไม่กรอกชื่อ",
  MISSING_LAST_NAME: "ยังไม่กรอกนามสกุล",
};

export function CurrentStudentsPage({ onBackHome, onRevealPath }: CurrentStudentsPageProps) {
  const [excelPath, setExcelPath] = useState("");
  const [blankFormPath, setBlankFormPath] = useState<string | null>(null);
  const [validation, setValidation] = useState<ValidateCurrentStudentsImportFormResponse | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isDownloadingTemplate, setIsDownloadingTemplate] = useState(false);
  const [isValidating, setIsValidating] = useState(false);
  const [progress, setProgress] = useState(0);

  const visiblePreview = useMemo(() => validation?.preview.slice(0, 50) ?? [], [validation]);

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
    const selected = await openExcelDialog();
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
      setErrorMessage("กรุณาเลือกไฟล์ Excel ที่กรอกข้อมูลครบแล้วก่อน");
      return;
    }
    setIsValidating(true);
    setValidation(null);
    setErrorMessage(null);
    setProgress(20);
    const timer = window.setInterval(() => {
      setProgress((current) => Math.min(current + 12, 88));
    }, 250);
    try {
      const result = await validateCurrentStudentImportForm(selectedPath);
      setValidation(result);
      setProgress(100);
    } catch (error) {
      setProgress(0);
      setErrorMessage(readableError(error));
    } finally {
      window.clearInterval(timer);
      setIsValidating(false);
    }
  }

  function readableError(error: unknown): string {
    const raw = error instanceof Error ? error.message : String(error);
    const code = raw.match(/[A-Z][A-Z0-9_]+/)?.[0] ?? raw;
    return errorMessages[code] ?? raw;
  }

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-4 border-b pb-6 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <Button variant="outline" size="sm" onClick={onBackHome}>
            <ArrowLeft className="h-4 w-4" />
            กลับหน้าหลัก
          </Button>
          <div className="mt-5 flex items-center gap-4">
            <div className="flex h-12 w-12 items-center justify-center rounded-lg border bg-background">
              <UserPlus className="h-6 w-6 text-primary" />
            </div>
            <div>
              <Badge variant="default">รับไฟล์พร้อมนำเข้า</Badge>
              <h1 className="mt-2 text-3xl font-bold tracking-normal">นักเรียนปัจจุบัน (ย้ายเข้า/เพิ่มนักเรียน)</h1>
              <p className="mt-2 max-w-3xl text-muted-foreground">
                ดาวน์โหลดฟอร์มเปล่า หรืออัปโหลด Excel ที่กรอกครบแล้วจากเมนูแปลงฟอร์ม/จากผู้ใช้ เพื่อเตรียมตรวจข้อมูลก่อนนำเข้า DMC
              </p>
            </div>
          </div>
        </div>
      </header>

      {errorMessage ? (
        <Alert variant="destructive">
          <AlertDescription>{errorMessage}</AlertDescription>
        </Alert>
      ) : null}

      <section className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_390px]">
        <Card>
          <CardHeader>
            <CardTitle>ฟอร์มนักเรียนปัจจุบัน</CardTitle>
            <CardDescription>ไฟล์ที่อัปโหลดควรเป็นฟอร์ม Excel เดียวกับที่ดาวน์โหลดจากหน้านี้</CardDescription>
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
              <Label>Excel ที่กรอกข้อมูลครบแล้ว</Label>
              <div className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_auto]">
                <Input
                  value={excelPath}
                  onChange={(event) => {
                    setExcelPath(event.target.value);
                    setValidation(null);
                    setProgress(0);
                  }}
                  placeholder="C:\\dmc\\current-students-import.xlsx"
                />
                <Button variant="outline" onClick={() => void handleBrowseExcel()}>
                  <UploadCloud className="h-4 w-4" />
                  เลือก Excel
                </Button>
              </div>
            </div>

            <div className="flex flex-wrap gap-2">
              <Button disabled={isValidating || !excelPath.trim()} onClick={() => void handleValidate()}>
                {isValidating ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
                ตรวจไฟล์นำเข้า
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>สถานะ</CardTitle>
            <CardDescription>{validation ? "ผลตรวจไฟล์ล่าสุด" : "รออัปโหลดฟอร์ม"}</CardDescription>
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
              <div className="text-sm text-muted-foreground">ยังไม่มีผลตรวจ</div>
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
    </div>
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
