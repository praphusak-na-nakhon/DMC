import { ArrowLeft, Download, FileSpreadsheet, Loader2, UploadCloud } from "lucide-react";
import { useMemo, useState } from "react";
import { exportStudentBasicInfoForm, openExcelDialog } from "../lib/rpcClient";
import type { ExportStudentBasicInfoFormResponse } from "../types/contracts";
import { Alert, AlertDescription } from "./ui/alert";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./ui/card";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { Progress } from "./ui/progress";

type StudentBasicInfoPageProps = {
  onBackHome: () => void;
  onRevealPath: (path: string) => void;
};

const errorMessages: Record<string, string> = {
  STUDENT_BASIC_INFO_INPUT_NOT_FOUND: "ไม่พบไฟล์ Excel ที่เลือก",
  STUDENT_BASIC_INFO_INPUT_NOT_FILE: "พาธที่เลือกไม่ใช่ไฟล์",
  STUDENT_BASIC_INFO_UNSUPPORTED_TYPE: "รองรับเฉพาะไฟล์ .xlsx หรือ .xlsm",
  STUDENT_BASIC_INFO_TEMPLATE_NOT_FOUND: "ไม่พบไฟล์ฟอร์ม student_basic_info_form.xlsx",
  STUDENT_BASIC_INFO_HEADERS_NOT_FOUND: "หาแถวหัวตารางของไฟล์ DMC ไม่เจอ",
  STUDENT_BASIC_INFO_MISSING_COLUMN: "ไฟล์ DMC ไม่มีคอลัมน์ที่จำเป็น",
  STUDENT_BASIC_INFO_NO_ROWS: "ไม่พบข้อมูลนักเรียนในไฟล์ DMC",
};

export function StudentBasicInfoPage({ onBackHome, onRevealPath }: StudentBasicInfoPageProps) {
  const [excelPath, setExcelPath] = useState("");
  const [result, setResult] = useState<ExportStudentBasicInfoFormResponse | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [progress, setProgress] = useState(0);
  const [stageLabel, setStageLabel] = useState("รอเลือกไฟล์");

  const classPreview = useMemo(() => result?.classes.slice(0, 10) ?? [], [result]);

  async function handleBrowseExcel() {
    const selected = await openExcelDialog();
    if (selected) {
      setExcelPath(selected);
      setResult(null);
      setErrorMessage(null);
      setProgress(0);
      setStageLabel("พร้อมประมวลผล");
    }
  }

  async function handleExport() {
    const selectedPath = excelPath.trim();
    if (!selectedPath) {
      setErrorMessage("กรุณาเลือกไฟล์นักเรียนจาก DMC ก่อน");
      return;
    }

    setIsProcessing(true);
    setResult(null);
    setErrorMessage(null);
    setProgress(12);
    setStageLabel("กำลังอ่านไฟล์ DMC");
    const timer = window.setInterval(() => {
      setProgress((current) => Math.min(current + 9, 88));
    }, 300);

    try {
      const response = await exportStudentBasicInfoForm(selectedPath);
      setResult(response);
      setProgress(100);
      setStageLabel("สร้างไฟล์เสร็จแล้ว");
    } catch (error) {
      setProgress(0);
      setStageLabel("ประมวลผลไม่สำเร็จ");
      setErrorMessage(readableError(error));
    } finally {
      window.clearInterval(timer);
      setIsProcessing(false);
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
              <FileSpreadsheet className="h-6 w-6 text-primary" />
            </div>
            <div>
              <Badge variant="default">พร้อมใช้งาน</Badge>
              <h1 className="mt-2 text-3xl font-bold tracking-normal">บันทึกข้อมูลพื้นฐานนักเรียน(งานพยาบาล)</h1>
              <p className="mt-2 max-w-3xl text-muted-foreground">
                อัปโหลดไฟล์นักเรียนจาก DMC แล้วระบบจะสร้าง Excel ตามฟอร์ม แยกเป็นชีตตามระดับชั้นและห้องเรียน
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

      <section className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_360px]">
        <Card>
          <CardHeader>
            <CardTitle>อัปโหลดไฟล์ DMC</CardTitle>
            <CardDescription>เลือกไฟล์เช่น 2568-3-student.xlsx หรือไฟล์รายชื่อนักเรียน DMC ชื่ออื่น</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4">
            <div className="grid gap-2">
              <Label>ไฟล์นักเรียนจาก DMC</Label>
              <div className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_auto]">
                <Input
                  value={excelPath}
                  onChange={(event) => {
                    setExcelPath(event.target.value);
                    setResult(null);
                    setProgress(0);
                    setStageLabel(event.target.value.trim() ? "พร้อมประมวลผล" : "รอเลือกไฟล์");
                  }}
                  placeholder="C:\\dmc\\2568-3-student.xlsx"
                />
                <Button variant="outline" disabled={isProcessing} onClick={() => void handleBrowseExcel()}>
                  <UploadCloud className="h-4 w-4" />
                  เลือกไฟล์
                </Button>
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button disabled={!excelPath.trim() || isProcessing} onClick={() => void handleExport()}>
                {isProcessing ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileSpreadsheet className="h-4 w-4" />}
                สร้างไฟล์ตามฟอร์ม
              </Button>
              {result ? (
                <Button variant="outline" onClick={() => onRevealPath(result.output_path)}>
                  <Download className="h-4 w-4" />
                  ดาวน์โหลดไฟล์
                </Button>
              ) : null}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>สถานะ</CardTitle>
            <CardDescription>{stageLabel}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Progress value={progress} />
            <div className="grid gap-3 text-sm">
              <SummaryRow label="นักเรียน" value={result ? String(result.students_exported) : "-"} />
              <SummaryRow label="ระดับชั้น/ห้อง" value={result ? String(result.classes_exported) : "-"} />
              <SummaryRow label="ปีการศึกษา" value={result?.school_year ?? "-"} />
              <SummaryRow label="เทอม" value={result?.term ?? "-"} />
            </div>
          </CardContent>
        </Card>
      </section>

      {result ? (
        <Card>
          <CardHeader>
            <CardTitle>ไฟล์ผลลัพธ์</CardTitle>
            <CardDescription className="break-words">{result.output_path}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-3 sm:grid-cols-3">
              <Metric label="โรงเรียน" value={result.school_name ?? "-"} />
              <Metric label="ข้อมูลที่อ่านได้" value={`${result.students_exported}/${result.rows_total} แถว`} />
              <Metric label="ชีตที่สร้าง" value={`${result.classes_exported} ชีต`} />
            </div>
            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
              {classPreview.map((item) => (
                <div key={item.sheet_name} className="rounded-md border bg-muted/40 p-3 text-sm">
                  <div className="font-semibold">{`${item.level}/${item.room}`}</div>
                  <div className="mt-1 text-muted-foreground">{item.students} คน</div>
                </div>
              ))}
            </div>
            {result.classes.length > classPreview.length ? (
              <div className="text-sm text-muted-foreground">ยังมีอีก {result.classes.length - classPreview.length} ห้องในไฟล์ผลลัพธ์</div>
            ) : null}
          </CardContent>
        </Card>
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

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border bg-muted/40 p-3">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="mt-1 break-words font-semibold">{value}</div>
    </div>
  );
}
