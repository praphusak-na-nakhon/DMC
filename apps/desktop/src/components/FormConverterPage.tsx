import { AlertTriangle, ArrowLeft, FileOutput, FileText, Loader2, UploadCloud } from "lucide-react";
import { useState } from "react";
import {
  exportDmcFormJson,
  openCsvDialog,
  openExcelDialog,
  openMarkdownDialog,
  previewDmcFormJson,
} from "../lib/rpcClient";
import type {
  DmcFormJsonRecord,
  CurrentStudentsFieldConflict,
  ExportDmcFormJsonResponse,
  PreviewDmcFormJsonResponse,
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
  CURRENT_STUDENTS_OCR_REQUIRED: "กรุณาเพิ่มไฟล์ OCR จากแบบฟอร์ม DMC อย่างน้อย 1 ไฟล์",
  CURRENT_STUDENTS_OCR_NO_RECORDS: "ไม่พบข้อมูลนักเรียนจากไฟล์ OCR จากแบบฟอร์ม DMC ที่เลือก",
};

type PreviewColumn = {
  fieldName: string;
  label: string;
  groupLabel: string;
};

type PreviewColumnDefinition = {
  fieldName: string;
  label: string;
  required?: boolean;
};

type PreviewColumnGroupDefinition = {
  label: string;
  columns: PreviewColumnDefinition[];
};

type PreviewColumnGroup = {
  label: string;
  colSpan: number;
};

const previewRowHeight = 40;
const previewTableMaxHeight = 560;
const previewVirtualOverscan = 6;

const priorityPreviewColumnGroups: PreviewColumnGroupDefinition[] = [
  {
    label: "ข้อมูลนักเรียน",
    columns: [
      { fieldName: "student_no", label: "เลขประจำตัวนักเรียน", required: true },
      { fieldName: "citizen_id", label: "เลขประจำตัวประชาชน", required: true },
      { fieldName: "grade", label: "ชั้น", required: true },
      { fieldName: "room", label: "ห้อง", required: true },
      { fieldName: "seat_no", label: "เลขที่", required: true },
      { fieldName: "sex", label: "เพศ", required: true },
      { fieldName: "prefix", label: "คำนำหน้าชื่อ", required: true },
      { fieldName: "first_name", label: "ชื่อ", required: true },
      { fieldName: "last_name", label: "นามสกุล", required: true },
      { fieldName: "birth_date", label: "วันเกิด", required: true },
      { fieldName: "birth_province", label: "จังหวัดที่เกิด", required: true },
      { fieldName: "weight_kg", label: "น้ำหนัก", required: true },
      { fieldName: "height_cm", label: "ส่วนสูง", required: true },
      { fieldName: "religion", label: "ศาสนา", required: true },
      { fieldName: "race", label: "เชื้อชาติ", required: true },
      { fieldName: "nationality", label: "สัญชาติ", required: true },
    ],
  },
  {
    label: "ที่อยู่ตามทะเบียนบ้าน",
    columns: [
      { fieldName: "registered_address.house_id", label: "รหัสประจำบ้าน", required: true },
      { fieldName: "registered_address.house_no", label: "บ้านเลขที่", required: true },
      { fieldName: "registered_address.subdistrict", label: "ตำบล", required: true },
      { fieldName: "registered_address.district", label: "อำเภอ", required: true },
      { fieldName: "registered_address.province", label: "จังหวัด", required: true },
      { fieldName: "registered_address.postal_code", label: "รหัสไปรษณีย์", required: true },
    ],
  },
  {
    label: "ข้อมูลบิดา",
    columns: [
      { fieldName: "father.first_name", label: "ชื่อบิดา", required: true },
      { fieldName: "father.last_name", label: "นามสกุลบิดา", required: true },
    ],
  },
  {
    label: "ข้อมูลมารดา",
    columns: [
      { fieldName: "mother.first_name", label: "ชื่อมารดา", required: true },
      { fieldName: "mother.last_name", label: "นามสกุลมารดา", required: true },
    ],
  },
  {
    label: "ข้อมูลผู้ปกครอง",
    columns: [
      { fieldName: "guardian.first_name", label: "ชื่อผู้ปกครอง", required: true },
      { fieldName: "guardian.last_name", label: "นามสกุลผู้ปกครอง", required: true },
    ],
  },
];

export function FormConverterPage({ onBackHome, onRevealPath }: FormConverterPageProps) {
  const [rosterPath, setRosterPath] = useState("");
  const [thaiIdCsvPath, setThaiIdCsvPath] = useState("");
  const [ocrMarkdownPaths, setOcrMarkdownPaths] = useState("");
  const [schoolYear, setSchoolYear] = useState("2569");
  const [gradeLevels, setGradeLevels] = useState("1");
  const [jsonPreview, setJsonPreview] = useState<PreviewDmcFormJsonResponse | null>(null);
  const [jsonExport, setJsonExport] = useState<ExportDmcFormJsonResponse | null>(null);
  const [showTablePreview, setShowTablePreview] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isPreviewing, setIsPreviewing] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const activeResult = jsonExport ?? jsonPreview;
  const activeConflicts = activeResult?.conflicts ?? [];

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

  function readFormInput() {
    const selectedRosterPath = rosterPath.trim();
    const selectedOcrPaths = markdownPaths(ocrMarkdownPaths);
    if (!selectedRosterPath) {
      setErrorMessage("กรุณาเลือกไฟล์บัญชีรายชื่อก่อนสร้าง JSON");
      return null;
    }
    if (!selectedOcrPaths.length) {
      setErrorMessage("กรุณาเพิ่มไฟล์ OCR จากแบบฟอร์ม DMC อย่างน้อย 1 ไฟล์");
      return null;
    }
    const parsedSchoolYear = Number.parseInt(schoolYear.trim(), 10);
    if (!Number.isInteger(parsedSchoolYear)) {
      setErrorMessage("ปีการศึกษาต้องเป็นตัวเลข เช่น 2569");
      return null;
    }
    return {
      rosterExcelPath: selectedRosterPath,
      thaiIdCsvPath: thaiIdCsvPath.trim() || null,
      ocrMarkdownPaths: selectedOcrPaths,
      schoolYear: parsedSchoolYear,
      gradeLevels: parseGradeLevels(gradeLevels),
    };
  }

  async function handlePreviewDmcFormJson() {
    const input = readFormInput();
    if (!input) {
      return;
    }

    setIsPreviewing(true);
    setErrorMessage(null);
    setJsonPreview(null);
    setJsonExport(null);
    try {
      const result = await previewDmcFormJson({
        ...input,
      });
      setJsonPreview(result);
      setShowTablePreview(false);
    } catch (error) {
      setErrorMessage(readableError(error));
    } finally {
      setIsPreviewing(false);
    }
  }

  async function handleExportDmcFormJson() {
    const input = readFormInput();
    if (!input) {
      return;
    }
    setIsExporting(true);
    setErrorMessage(null);
    setJsonExport(null);
    try {
      const result = await exportDmcFormJson({
        ...input,
        outputPath: null,
      });
      setJsonExport(result);
    } catch (error) {
      setErrorMessage(readableError(error));
    } finally {
      setIsExporting(false);
    }
  }

  function resetResult() {
    setJsonPreview(null);
    setJsonExport(null);
    setShowTablePreview(false);
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
                แปลงข้อมูลจากไฟล์ OCR จากแบบฟอร์ม DMC ของแบบฟอร์มที่นักเรียนกรอกจริงเป็น JSON กลาง โดยใช้บัญชีรายชื่อและ CSV เครื่องสแกนบัตรเป็นข้อมูลอ้างอิง
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
                ไฟล์ OCR จากแบบฟอร์ม DMC คือรายการหลักที่จะถูก export; บัญชีรายชื่อและ CSV ใช้ช่วยจับคู่นักเรียนและเติมข้อมูลอ้างอิงเท่านั้น โดยยังไม่กำหนดประเภทงาน
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
                <Label>ไฟล์ OCR จากแบบฟอร์ม DMC</Label>
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
                disabled={isPreviewing || !rosterPath.trim() || markdownPaths(ocrMarkdownPaths).length === 0}
                onClick={() => void handlePreviewDmcFormJson()}
              >
                {isPreviewing ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileOutput className="h-4 w-4" />}
                ตรวจและแสดงตัวอย่าง
              </Button>
            </div>
          </div>

          {activeResult ? (
            <div className="grid gap-4 rounded-md border bg-muted/30 p-4 lg:grid-cols-[minmax(0,1fr)_auto]">
              <div className="grid gap-3 sm:grid-cols-5">
                <SummaryItem label="รายการที่พบ" value={jsonExport?.records_exported ?? jsonPreview?.records_previewed ?? 0} />
                <SummaryItem label="จับคู่ได้" value={activeResult.summary.auto_matched} />
                <SummaryItem label="ต้องตรวจ" value={activeResult.summary.review_queue_records} />
                <SummaryItem label="ข้อมูลจำเป็นขาด" value={activeConflicts.length} />
                <SummaryItem label="คำเตือน" value={activeResult.summary.warnings_total} />
              </div>
              <div className="flex flex-wrap gap-2 lg:justify-end">
                <Button variant="outline" onClick={() => setShowTablePreview((current) => !current)}>
                  <FileText className="h-4 w-4" />
                  {showTablePreview ? "ซ่อนตัวอย่างข้อมูล" : "แสดงตัวอย่างข้อมูล"}
                </Button>
                <Button disabled={isExporting} onClick={() => void handleExportDmcFormJson()}>
                  {isExporting ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileOutput className="h-4 w-4" />}
                  สร้าง JSON
                </Button>
                {jsonExport ? (
                  <Button variant="outline" onClick={() => onRevealPath(jsonExport.output_path)}>
                    <FileOutput className="h-4 w-4" />
                    เปิดไฟล์ JSON
                  </Button>
                ) : null}
              </div>
              <div className="lg:col-span-2">
                <ConflictAudit conflicts={activeConflicts} />
                {showTablePreview ? (
                  <DmcFormTablePreview
                    records={activeResult.records}
                    fieldLabels={activeResult.field_labels}
                    conflicts={activeConflicts}
                  />
                ) : null}
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

function DmcFormTablePreview({
  records,
  fieldLabels,
  conflicts,
}: {
  records: DmcFormJsonRecord[];
  fieldLabels: Record<string, string>;
  conflicts: CurrentStudentsFieldConflict[];
}) {
  const columns = previewColumnsFromRecords(records, fieldLabels);
  const columnGroups = previewColumnGroupsFromColumns(columns);
  const tableMinWidth = Math.max(1280, columns.length * 160 + 140);
  const [scrollTop, setScrollTop] = useState(0);
  const shouldVirtualize = records.length > 50;
  const visibleHeight = shouldVirtualize ? previewTableMaxHeight : records.length * previewRowHeight;
  const visibleCount = Math.ceil(visibleHeight / previewRowHeight) + previewVirtualOverscan * 2;
  const startIndex = shouldVirtualize ? Math.max(0, Math.floor(scrollTop / previewRowHeight) - previewVirtualOverscan) : 0;
  const endIndex = shouldVirtualize ? Math.min(records.length, startIndex + visibleCount) : records.length;
  const visibleRecords = records.slice(startIndex, endIndex);
  const topPadding = shouldVirtualize ? startIndex * previewRowHeight : 0;
  const bottomPadding = shouldVirtualize ? Math.max(0, (records.length - endIndex) * previewRowHeight) : 0;

  return (
    <div
      className="mt-4 overflow-auto rounded-md border bg-background"
      style={shouldVirtualize ? { maxHeight: previewTableMaxHeight } : undefined}
      onScroll={(event) => {
        if (shouldVirtualize) {
          setScrollTop(event.currentTarget.scrollTop);
        }
      }}
    >
      <table className="w-full border-collapse text-sm" style={{ minWidth: tableMinWidth }}>
        <thead className="sticky top-0 z-10 bg-muted/60 text-left">
          <tr>
            <th rowSpan={2} className="whitespace-nowrap border-b px-3 py-2 font-medium">
              สถานะ
            </th>
            {columnGroups.map((group) => (
              <th
                key={group.label}
                colSpan={group.colSpan}
                className="whitespace-nowrap border-b border-l px-3 py-2 text-center text-xs font-semibold text-muted-foreground"
              >
                {group.label}
              </th>
            ))}
          </tr>
          <tr>
            {columns.map(({ fieldName, label }) => (
              <th key={fieldName} className="whitespace-nowrap border-b px-3 py-2 font-medium">
                {label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {topPadding > 0 ? (
            <tr aria-hidden="true">
              <td colSpan={columns.length + 1} style={{ height: topPadding, padding: 0, border: 0 }} />
            </tr>
          ) : null}
          {visibleRecords.map((record) => {
            const missingCount = unresolvedConflictCount(record.record_id, conflicts);
            return (
              <tr
                key={record.record_id}
                className="align-top"
                style={shouldVirtualize ? { height: previewRowHeight } : undefined}
              >
                <td className="border-b px-3 py-2">
                  <span className={missingCount ? "font-medium text-amber-800" : "font-medium text-emerald-700"}>
                    {missingCount ? `ขาด ${missingCount} ช่อง` : "พร้อม"}
                  </span>
                </td>
                {columns.map(({ fieldName }) => (
                  <td key={`${record.record_id}-${fieldName}`} className="whitespace-nowrap border-b px-3 py-2">
                    {formatFieldValue(recordFieldValue(record, fieldName))}
                  </td>
                ))}
              </tr>
            );
          })}
          {bottomPadding > 0 ? (
            <tr aria-hidden="true">
              <td colSpan={columns.length + 1} style={{ height: bottomPadding, padding: 0, border: 0 }} />
            </tr>
          ) : null}
        </tbody>
      </table>
    </div>
  );
}

function previewColumnsFromRecords(
  records: DmcFormJsonRecord[],
  fieldLabels: Record<string, string>,
): PreviewColumn[] {
  const fieldNames = new Set(Object.keys(fieldLabels));
  for (const record of records) {
    for (const fieldName of Object.keys(record.fields)) {
      fieldNames.add(fieldName);
    }
  }

  const columns: PreviewColumn[] = [];
  for (const group of priorityPreviewColumnGroups) {
    for (const column of group.columns) {
      if (!fieldNames.delete(column.fieldName)) {
        continue;
      }
      columns.push({
        fieldName: column.fieldName,
        label: column.required ? `${column.label}*` : column.label,
        groupLabel: group.label,
      });
    }
  }

  for (const fieldName of fieldNames) {
    columns.push({
      fieldName,
      label: fieldLabels[fieldName] ?? fieldName,
      groupLabel: "ข้อมูลอื่น",
    });
  }
  return columns;
}

function previewColumnGroupsFromColumns(columns: PreviewColumn[]): PreviewColumnGroup[] {
  const groups: PreviewColumnGroup[] = [];
  for (const column of columns) {
    const lastGroup = groups[groups.length - 1];
    if (lastGroup?.label === column.groupLabel) {
      lastGroup.colSpan += 1;
      continue;
    }
    groups.push({ label: column.groupLabel, colSpan: 1 });
  }
  return groups;
}

function recordFieldValue(record: DmcFormJsonRecord, fieldName: string): string | number | boolean | null {
  return record.fields[fieldName] ?? null;
}

function unresolvedConflictCount(
  recordId: string,
  conflicts: CurrentStudentsFieldConflict[],
): number {
  return conflicts.filter((conflict) => conflict.record_id === recordId).length;
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
