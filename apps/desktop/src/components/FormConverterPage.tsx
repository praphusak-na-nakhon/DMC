import { AlertTriangle, ArrowLeft, FileOutput, FileText, Loader2, UploadCloud } from "lucide-react";
import { useState } from "react";
import {
  exportDmcFormJson,
  openCsvDialog,
  openExcelDialog,
  openMarkdownDialog,
} from "../lib/rpcClient";
import type {
  CurrentStudentsFieldConflict,
  ExportDmcFormJsonResponse,
} from "../types/contracts";
import { Alert, AlertDescription } from "./ui/alert";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./ui/card";
import { Input } from "./ui/input";
import { Label } from "./ui/label";

type FormConverterPageProps = {
  onBackHome: () => void;
  onRevealPath: (path: string) => void;
};

const errorMessages: Record<string, string> = {
  CURRENT_STUDENTS_INPUT_NOT_FOUND: "ไม่พบไฟล์ที่เลือก",
  CURRENT_STUDENTS_INPUT_NOT_FILE: "พาธที่เลือกไม่ใช่ไฟล์",
  CURRENT_STUDENTS_UNSUPPORTED_INPUT_TYPE: "ชนิดไฟล์ไม่รองรับ",
  CURRENT_STUDENTS_ROSTER_EMPTY: "ไม่พบรายชื่อนักเรียนในไฟล์บัญชีรายชื่อ",
  CURRENT_STUDENTS_EXPORT_UNSUPPORTED_TYPE: "ไฟล์ปลายทางต้องเป็น .xlsx",
  DMC_FORM_JSON_EXPORT_UNSUPPORTED_TYPE: "ไฟล์ปลายทางต้องเป็น .json",
  CURRENT_STUDENTS_OCR_REQUIRED: "กรุณาเพิ่มไฟล์ OCR markdown อย่างน้อย 1 ไฟล์",
  CURRENT_STUDENTS_OCR_NO_RECORDS: "ไม่พบข้อมูลนักเรียนจากไฟล์ OCR markdown ที่เลือก",
};

export function FormConverterPage({ onBackHome, onRevealPath }: FormConverterPageProps) {
  const [rosterPath, setRosterPath] = useState("");
  const [thaiIdCsvPath, setThaiIdCsvPath] = useState("");
  const [ocrMarkdownPaths, setOcrMarkdownPaths] = useState("");
  const [schoolYear, setSchoolYear] = useState("2569");
  const [gradeLevels, setGradeLevels] = useState("1");
  const [currentStudentExport, setCurrentStudentExport] =
    useState<ExportDmcFormJsonResponse | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isExporting, setIsExporting] = useState(false);

  async function handleBrowseRoster() {
    const selected = await openExcelDialog();
    if (selected) {
      setRosterPath(selected);
      resetResult();
    }
  }

  async function handleBrowseThaiIdCsv() {
    const selected = await openCsvDialog();
    if (selected) {
      setThaiIdCsvPath(selected);
      resetResult();
    }
  }

  async function handleBrowseOcrMarkdown() {
    const selected = await openMarkdownDialog();
    if (selected) {
      setOcrMarkdownPaths((current) => [...markdownPaths(current), selected].join("\n"));
      resetResult();
    }
  }

  async function handleExportDmcFormJson() {
    const selectedRosterPath = rosterPath.trim();
    const selectedOcrPaths = markdownPaths(ocrMarkdownPaths);
    if (!selectedRosterPath) {
      setErrorMessage("กรุณาเลือกไฟล์บัญชีรายชื่อก่อนสร้าง JSON");
      return;
    }
    if (!selectedOcrPaths.length) {
      setErrorMessage("กรุณาเพิ่มไฟล์ OCR markdown อย่างน้อย 1 ไฟล์");
      return;
    }
    const parsedSchoolYear = Number.parseInt(schoolYear.trim(), 10);
    if (!Number.isInteger(parsedSchoolYear)) {
      setErrorMessage("ปีการศึกษาต้องเป็นตัวเลข เช่น 2569");
      return;
    }

    setIsExporting(true);
    setErrorMessage(null);
    setCurrentStudentExport(null);
    try {
      const result = await exportDmcFormJson({
        rosterExcelPath: selectedRosterPath,
        thaiIdCsvPath: thaiIdCsvPath.trim() || null,
        ocrMarkdownPaths: selectedOcrPaths,
        schoolYear: parsedSchoolYear,
        gradeLevels: parseGradeLevels(gradeLevels),
        outputPath: null,
      });
      setCurrentStudentExport(result);
    } catch (error) {
      setErrorMessage(readableError(error));
    } finally {
      setIsExporting(false);
    }
  }

  function resetResult() {
    setCurrentStudentExport(null);
    setErrorMessage(null);
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
            <div className="flex h-12 w-12 items-center justify-center rounded-xl border bg-background">
              <FileText className="h-6 w-6 text-primary" />
            </div>
            <div>
              <Badge variant="default">พร้อมสร้าง JSON</Badge>
              <h1 className="mt-2 text-3xl font-bold tracking-normal">แปลงเอกสารแบบฟอร์ม DMC เป็น JSON</h1>
              <p className="mt-2 max-w-3xl text-muted-foreground">
                แปลงข้อมูลจากไฟล์ OCR markdown ของแบบฟอร์มที่นักเรียนกรอกจริงเป็น JSON กลาง โดยใช้บัญชีรายชื่อและ CSV เครื่องสแกนบัตรเป็นข้อมูลอ้างอิง
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

      <Card>
        <CardHeader>
          <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <CardTitle>สร้าง JSON จากแบบฟอร์ม DMC</CardTitle>
              <CardDescription>
                ไฟล์ OCR markdown คือรายการหลักที่จะถูก export; บัญชีรายชื่อและ CSV ใช้ช่วยจับคู่นักเรียนและเติมข้อมูลอ้างอิงเท่านั้น โดยยังไม่กำหนดประเภทงาน
              </CardDescription>
            </div>
            <Badge variant="outline">DMC form JSON</Badge>
          </div>
        </CardHeader>
        <CardContent className="grid gap-5">
          <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_260px]">
            <div className="grid gap-4">
              <div className="grid gap-2">
                <Label>ไฟล์รายชื่อนักเรียน Excel</Label>
                <div className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_auto]">
                  <Input
                    value={rosterPath}
                    onChange={(event) => {
                      setRosterPath(event.target.value);
                      resetResult();
                    }}
                    placeholder="C:\\dmc\\uploadTest\\studentListM1-M4 2569.xlsx"
                  />
                  <Button variant="outline" onClick={() => void handleBrowseRoster()}>
                    <FileText className="h-4 w-4" />
                    เลือก Excel
                  </Button>
                </div>
              </div>

              <div className="grid gap-2">
                <Label>CSV จากเครื่องสแกนบัตรนักเรียน</Label>
                <div className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_auto]">
                  <Input
                    value={thaiIdCsvPath}
                    onChange={(event) => {
                      setThaiIdCsvPath(event.target.value);
                      resetResult();
                    }}
                    placeholder="C:\\dmc\\uploadTest\\ThaiID M1-2569.CSV"
                  />
                  <Button variant="outline" onClick={() => void handleBrowseThaiIdCsv()}>
                    <UploadCloud className="h-4 w-4" />
                    เลือก CSV
                  </Button>
                </div>
              </div>

              <div className="grid gap-2">
                <Label>ไฟล์ OCR markdown</Label>
                <textarea
                  className="min-h-28 w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm outline-none focus-visible:ring-1 focus-visible:ring-ring"
                  value={ocrMarkdownPaths}
                  onChange={(event) => {
                    setOcrMarkdownPaths(event.target.value);
                    resetResult();
                  }}
                  placeholder="หนึ่งไฟล์ต่อหนึ่งบรรทัด เช่น C:\\dmc\\uploadTest\\1-3ex.md"
                />
                <div>
                  <Button variant="outline" size="sm" onClick={() => void handleBrowseOcrMarkdown()}>
                    <FileText className="h-4 w-4" />
                    เพิ่มไฟล์ OCR
                  </Button>
                </div>
              </div>
            </div>

            <div className="grid content-start gap-4">
              <div className="grid gap-2">
                <Label>ปีการศึกษา</Label>
                <Input
                  value={schoolYear}
                  onChange={(event) => {
                    setSchoolYear(event.target.value);
                    resetResult();
                  }}
                  placeholder="2569"
                />
              </div>
              <div className="grid gap-2">
                <Label>ระดับชั้น</Label>
                <Input
                  value={gradeLevels}
                  onChange={(event) => {
                    setGradeLevels(event.target.value);
                    resetResult();
                  }}
                  placeholder="1 หรือ 1,2,3"
                />
              </div>
              <Button
                disabled={isExporting || !rosterPath.trim() || markdownPaths(ocrMarkdownPaths).length === 0}
                onClick={() => void handleExportDmcFormJson()}
              >
                {isExporting ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileOutput className="h-4 w-4" />}
                สร้าง JSON
              </Button>
            </div>
          </div>

          {currentStudentExport ? (
            <div className="grid gap-4 rounded-md border bg-muted/30 p-4 lg:grid-cols-[minmax(0,1fr)_auto]">
              <div className="grid gap-3 sm:grid-cols-5">
                <SummaryItem label="รายการที่สร้าง" value={currentStudentExport.records_exported} />
                <SummaryItem label="จับคู่ได้" value={currentStudentExport.summary.auto_matched} />
                <SummaryItem label="ต้องตรวจ" value={currentStudentExport.summary.review_queue_records} />
                <SummaryItem label="ข้อมูลจำเป็นขาด" value={currentStudentExport.conflicts.length} />
                <SummaryItem label="คำเตือน" value={currentStudentExport.summary.warnings_total} />
              </div>
              <Button variant="outline" onClick={() => onRevealPath(currentStudentExport.output_path)}>
                <FileOutput className="h-4 w-4" />
                เปิดไฟล์ JSON
              </Button>
              <div className="lg:col-span-2">
                <ConflictAudit conflicts={currentStudentExport.conflicts} />
              </div>
            </div>
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}

function SummaryItem({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="mt-1 text-xl font-semibold">{value}</div>
    </div>
  );
}

function ConflictAudit({ conflicts }: { conflicts: CurrentStudentsFieldConflict[] }) {
  if (!conflicts.length) {
    return (
      <div className="rounded-md border bg-background p-4 text-sm text-muted-foreground">
        ไม่พบข้อมูลจำเป็นที่ขาดจากทั้ง 3 แหล่ง
      </div>
    );
  }

  return (
    <section className="grid gap-3 rounded-md border border-amber-200 bg-amber-50/70 p-4">
      <div className="flex items-start gap-2">
        <AlertTriangle className="mt-0.5 h-4 w-4 text-amber-700" />
        <div>
          <div className="font-medium text-amber-950">ข้อมูลจำเป็นที่ยังไม่พบ</div>
          <div className="text-sm text-amber-900">
            แสดงเฉพาะข้อมูลบังคับที่ตรวจจากบัญชีรายชื่อ, CSV เครื่องสแกนบัตร และ OCR แล้วไม่พบข้อมูล
          </div>
        </div>
      </div>
      <div className="grid gap-3">
        {conflicts.map((conflict, index) => (
          <FieldConflictRow key={`${conflict.record_id}-${conflict.field_name}-${index}`} conflict={conflict} />
        ))}
      </div>
    </section>
  );
}

function FieldConflictRow({ conflict }: { conflict: CurrentStudentsFieldConflict }) {
  const isMissingBlocker = conflict.reason === "missing_after_all_sources";
  const outcomeLabel = isMissingBlocker ? "ผลลัพธ์หลังตรวจครบ" : "ผลลัพธ์ที่เลือก";
  const outcomeValue = isMissingBlocker ? "ไม่มีข้อมูล ต้องเติมก่อนนำเข้า" : formatFieldValue(conflict.selected_value);

  return (
    <div className="grid gap-2 rounded-md border bg-background px-3 py-2 text-sm lg:grid-cols-[180px_minmax(0,1fr)_auto] lg:items-center">
      <div className="font-medium">{conflict.field_label}</div>
      <div className="min-w-0 truncate text-muted-foreground">{conflict.full_name ?? "ไม่ระบุชื่อ"}</div>
      <div className="flex min-w-0 flex-wrap items-center gap-2 lg:justify-end">
        <span className="text-xs font-medium text-muted-foreground">{outcomeLabel}</span>
        <span className="font-semibold text-amber-900">{outcomeValue}</span>
      </div>
    </div>
  );
}

function formatFieldValue(value: string | number | boolean | null): string {
  if (value === null || value === "") return "-";
  if (typeof value === "boolean") return value ? "true" : "false";
  return String(value);
}

function parseGradeLevels(value: string): number[] | null {
  const levels = value
    .split(/[,\s]+/)
    .map((item) => Number.parseInt(item.trim(), 10))
    .filter((item) => Number.isInteger(item));
  return levels.length ? levels : null;
}

function markdownPaths(value: string): string[] {
  return value
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean);
}
