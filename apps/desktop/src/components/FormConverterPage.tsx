import {
  AlertTriangle,
  File as FileIcon,
  FileOutput,
  FileSpreadsheet,
  FileText,
  FolderOpen,
  Loader2,
  UploadCloud,
  X,
} from "lucide-react";
import { useState, type DragEvent } from "react";
import messages from "../i18n/th.json";
import { describeUserFacingError } from "../lib/errorMessages";
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
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./ui/card";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { PageHeader } from "./PageHeader";
import { SystemErrorAlert } from "./SystemErrorAlert";

type FormConverterPageProps = {
  onBackHome: () => void;
  onRevealPath: (path: string) => void;
  onRetryRuntime?: () => void;
};

const errorMessages: Record<string, string> = {
  ...(messages.app.formConverter.errors as Record<string, string>),
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
      { fieldName: "school_year", label: "ปีการศึกษา" },
      { fieldName: "grade", label: "ชั้น", required: true },
      { fieldName: "room", label: "ห้อง", required: true },
      { fieldName: "seat_no", label: "เลขที่", required: true },
      { fieldName: "citizen_id", label: "เลขประจำตัวประชาชน", required: true },
      { fieldName: "student_no", label: "เลขประจำตัวนักเรียน", required: true },
      { fieldName: "prefix", label: "คำนำหน้าชื่อ", required: true },
      { fieldName: "sex", label: "เพศ", required: true },
      { fieldName: "first_name", label: "ชื่อ", required: true },
      { fieldName: "last_name", label: "นามสกุล", required: true },
      { fieldName: "first_name_en", label: "ชื่ออังกฤษ" },
      { fieldName: "last_name_en", label: "นามสกุลอังกฤษ" },
      { fieldName: "birth_date", label: "วันเกิด", required: true },
      { fieldName: "birth_province", label: "จังหวัดที่เกิด", required: true },
      { fieldName: "birth_hospital", label: "สถานพยาบาลเกิด" },
      { fieldName: "blood_type", label: "กลุ่มเลือด" },
      { fieldName: "race", label: "เชื้อชาติ", required: true },
      { fieldName: "nationality", label: "สัญชาติ", required: true },
      { fieldName: "religion", label: "ศาสนา", required: true },
    ],
  },
  {
    label: "ที่อยู่ตามทะเบียนบ้าน",
    columns: [
      { fieldName: "registered_address.house_id", label: "รหัสประจำบ้าน", required: true },
      { fieldName: "registered_address.house_no", label: "บ้านเลขที่", required: true },
      { fieldName: "registered_address.moo", label: "หมู่ที่ตามทะเบียน" },
      { fieldName: "registered_address.road", label: "ถนนตามทะเบียน" },
      { fieldName: "registered_address.province", label: "จังหวัด", required: true },
      { fieldName: "registered_address.district", label: "อำเภอ", required: true },
      { fieldName: "registered_address.subdistrict", label: "ตำบล", required: true },
      { fieldName: "registered_address.postal_code", label: "รหัสไปรษณีย์", required: true },
    ],
  },
  {
    label: "ที่อยู่ปัจจุบัน",
    columns: [
      { fieldName: "current_address.house_id", label: "รหัสประจำบ้านปัจจุบัน" },
      { fieldName: "current_address.house_no", label: "บ้านเลขที่ปัจจุบัน" },
      { fieldName: "current_address.moo", label: "หมู่ที่ปัจจุบัน" },
      { fieldName: "current_address.road", label: "ถนนปัจจุบัน" },
      { fieldName: "current_address.province", label: "จังหวัดปัจจุบัน" },
      { fieldName: "current_address.district", label: "อำเภอปัจจุบัน" },
      { fieldName: "current_address.subdistrict", label: "ตำบลปัจจุบัน" },
      { fieldName: "current_address.postal_code", label: "รหัสไปรษณีย์ปัจจุบัน" },
    ],
  },
  {
    label: "การเดินทางและสุขภาพ",
    columns: [
      { fieldName: "commute_method", label: "การเดินทาง" },
      { fieldName: "distance_paved_road_km", label: "ระยะทางถนนลาดยาง กม." },
      { fieldName: "commute_minutes", label: "เวลาเดินทาง นาที" },
      { fieldName: "weight_kg", label: "น้ำหนัก", required: true },
      { fieldName: "height_cm", label: "ส่วนสูง", required: true },
    ],
  },
  {
    label: "ข้อมูลครอบครัว",
    columns: [
      { fieldName: "parents_marital_status", label: "สถานภาพบิดามารดา" },
      { fieldName: "older_brothers", label: "จำนวนพี่ชาย" },
      { fieldName: "younger_brothers", label: "จำนวนน้องชาย" },
      { fieldName: "older_sisters", label: "จำนวนพี่สาว" },
      { fieldName: "younger_sisters", label: "จำนวนน้องสาว" },
      { fieldName: "siblings_studying_count", label: "จำนวนพี่น้องที่ศึกษาอยู่" },
      { fieldName: "child_order", label: "นักเรียนเป็นบุตรคนที่" },
    ],
  },
  {
    label: "ข้อมูลบิดา",
    columns: [
      { fieldName: "father.citizen_id", label: "เลขบัตรบิดา" },
      { fieldName: "father.first_name", label: "ชื่อบิดา", required: true },
      { fieldName: "father.last_name", label: "นามสกุลบิดา", required: true },
      { fieldName: "father.occupation", label: "อาชีพบิดา" },
      { fieldName: "father.income_text", label: "รายได้บิดา" },
      { fieldName: "father.phone", label: "โทรศัพท์บิดา" },
    ],
  },
  {
    label: "ข้อมูลมารดา",
    columns: [
      { fieldName: "mother.citizen_id", label: "เลขบัตรมารดา" },
      { fieldName: "mother.first_name", label: "ชื่อมารดา", required: true },
      { fieldName: "mother.last_name", label: "นามสกุลมารดา", required: true },
      { fieldName: "mother.occupation", label: "อาชีพมารดา" },
      { fieldName: "mother.income_text", label: "รายได้มารดา" },
      { fieldName: "mother.phone", label: "โทรศัพท์มารดา" },
    ],
  },
  {
    label: "ข้อมูลผู้ปกครอง",
    columns: [
      { fieldName: "guardian.citizen_id", label: "เลขบัตรผู้ปกครอง" },
      { fieldName: "guardian.first_name", label: "ชื่อผู้ปกครอง", required: true },
      { fieldName: "guardian.last_name", label: "นามสกุลผู้ปกครอง", required: true },
      { fieldName: "guardian.occupation", label: "อาชีพผู้ปกครอง" },
      { fieldName: "guardian.income_text", label: "รายได้ผู้ปกครอง" },
      { fieldName: "guardian.phone", label: "โทรศัพท์ผู้ปกครอง" },
      { fieldName: "guardian_relationship", label: "ความเกี่ยวข้องผู้ปกครอง" },
    ],
  },
];

export function FormConverterPage({
  onBackHome,
  onRevealPath,
  onRetryRuntime,
}: FormConverterPageProps) {
  const [rosterPath, setRosterPath] = useState("");
  const [thaiIdCsvPath, setThaiIdCsvPath] = useState("");
  const [ocrMarkdownPaths, setOcrMarkdownPaths] = useState("");
  const [civilRegistrationMarkdownPaths, setCivilRegistrationMarkdownPaths] = useState("");
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
  const selectedOcrCount = markdownPaths(ocrMarkdownPaths).length;
  const canPreview = !isPreviewing && rosterPath.trim().length > 0 && selectedOcrCount > 0;
  const previewHint = !rosterPath.trim()
    ? "เลือกไฟล์รายชื่อนักเรียน Excel ก่อนตรวจและแสดงตัวอย่าง"
    : selectedOcrCount === 0
      ? "เพิ่มไฟล์ OCR จากแบบฟอร์ม DMC อย่างน้อย 1 ไฟล์ก่อนตรวจและแสดงตัวอย่าง"
      : null;

  async function handleBrowseRoster() {
    try {
      const selected = await openExcelDialog();
      if (selected) {
        setRosterPath(selected);
        resetResult();
      }
    } catch (error) {
      setErrorMessage(readableError(error));
    }
  }

  async function handleBrowseThaiIdCsv() {
    try {
      const selected = await openCsvDialog();
      if (selected) {
        setThaiIdCsvPath(selected);
        resetResult();
      }
    } catch (error) {
      setErrorMessage(readableError(error));
    }
  }

  async function handleBrowseOcrMarkdown() {
    try {
      const selected = await openMarkdownDialog();
      if (selected) {
        setOcrMarkdownPaths((current) => [...markdownPaths(current), selected].join("\n"));
        resetResult();
      }
    } catch (error) {
      setErrorMessage(readableError(error));
    }
  }

  async function handleBrowseCivilRegistrationMarkdown() {
    try {
      const selected = await openMarkdownDialog();
      if (selected) {
        setCivilRegistrationMarkdownPaths((current) => [...markdownPaths(current), selected].join("\n"));
        resetResult();
      }
    } catch (error) {
      setErrorMessage(readableError(error));
    }
  }

  function readFormInput() {
    const selectedRosterPath = rosterPath.trim();
    const selectedOcrPaths = markdownPaths(ocrMarkdownPaths);
    const selectedCivilRegistrationPaths = markdownPaths(civilRegistrationMarkdownPaths);
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
      civilRegistrationMarkdownPaths: selectedCivilRegistrationPaths,
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
    return errorMessages[code] ?? describeUserFacingError(error);
  }

  return (
    <div className="space-y-6">
      <PageHeader
        onBackHome={onBackHome}
        backLabel={messages.app.formConverter.backHome}
        badge="พร้อมสร้างไฟล์ JSON"
        title="แปลงเอกสารแบบฟอร์ม DMC เป็นไฟล์ JSON"
        description="แปลงข้อมูลจากไฟล์ OCR ของแบบฟอร์มที่นักเรียนกรอกจริงเป็นไฟล์ JSON กลาง โดยใช้บัญชีรายชื่อและ CSV เครื่องสแกนบัตรเป็นข้อมูลอ้างอิง"
        icon={<FileText className="h-5 w-5 text-primary" />}
      />

      {errorMessage ? (
        <SystemErrorAlert message={errorMessage} onRetry={onRetryRuntime} retryWhen="runtime" />
      ) : null}

      <Card>
        <CardHeader>
          <div className="flex items-start gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-blue-50 text-blue-600">
              <UploadCloud className="h-5 w-5" />
            </div>
            <div className="min-w-0">
              <CardTitle>เตรียมไฟล์สำหรับแปลง DMC</CardTitle>
              <CardDescription>
                เลือกไฟล์ที่ต้องใช้ แล้วอัปโหลดไฟล์ให้ครบก่อนตรวจและส่งออก
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="grid gap-5">
          <section className="grid gap-4 lg:grid-cols-2">
            <PrepareFileCard
              order={1}
              title="ไฟล์รายชื่อนักเรียน Excel"
              statusLabel="บังคับ"
              description="ต้องมีไฟล์รายชื่อนักเรียน Excel เพื่อใช้เป็นบัญชีรายชื่อหลักของแบบฟอร์ม DMC ที่จะตรวจส่งออกได้"
              value={rosterPath}
              placeholder="C:\\dmc\\uploadTest\\studentListM1-M4 2569.xlsx"
              acceptedDescription="รองรับไฟล์ .xlsx เท่านั้น"
              browseButtonLabel="เลือกไฟล์ Excel"
              iconKind="excel"
              onBrowse={() => void handleBrowseRoster()}
              onClear={() => {
                setRosterPath("");
                resetResult();
              }}
              onDropPaths={(paths) => {
                setRosterPath(paths[0]);
                resetResult();
              }}
              onUnsupportedDrop={() => setErrorMessage("ไม่สามารถอ่านพาธไฟล์จากการลากวางได้ กรุณากดเลือกไฟล์แทน")}
              onValueChange={(value) => {
                setRosterPath(value);
                resetResult();
              }}
            />

            <PrepareFileCard
              order={2}
              title="ไฟล์ OCR จากแบบฟอร์ม DMC"
              statusLabel="บังคับ"
              description="ไฟล์ OCR ที่ได้จากการสแกนแบบฟอร์ม DMC เช่น .txt, .md, .csv"
              value={ocrMarkdownPaths}
              placeholder="C:\\dmc\\uploadTest\\1-3ex.md"
              acceptedDescription="รองรับไฟล์ .txt, .md, .csv"
              browseButtonLabel="เลือกไฟล์ OCR"
              browseButtonAriaLabel="เลือกไฟล์ OCR จากแบบฟอร์ม DMC"
              iconKind="file"
              onBrowse={() => void handleBrowseOcrMarkdown()}
              onClear={() => {
                setOcrMarkdownPaths("");
                resetResult();
              }}
              onDropPaths={(paths) => {
                setOcrMarkdownPaths((current) => appendPathList(current, paths));
                resetResult();
              }}
              onUnsupportedDrop={() => setErrorMessage("ไม่สามารถอ่านพาธไฟล์จากการลากวางได้ กรุณากดเลือกไฟล์แทน")}
              onValueChange={(value) => {
                setOcrMarkdownPaths(value);
                resetResult();
              }}
            />

            <PrepareFileCard
              order={3}
              title="CSV จากเครื่องสแกนบัตรนักเรียน"
              statusLabel="ตัวเลือก"
              description="เพิ่มเพื่อจับคู่นักเรียน เติมชื่อบัตรกับผู้ปกครองให้แม่นยำขึ้น"
              value={thaiIdCsvPath}
              placeholder="C:\\dmc\\uploadTest\\ThaiID M1-2569.CSV"
              acceptedDescription="รองรับไฟล์ .csv เท่านั้น"
              browseButtonLabel="เลือกไฟล์ CSV"
              iconKind="file"
              optional
              onBrowse={() => void handleBrowseThaiIdCsv()}
              onClear={() => {
                setThaiIdCsvPath("");
                resetResult();
              }}
              onDropPaths={(paths) => {
                setThaiIdCsvPath(paths[0]);
                resetResult();
              }}
              onUnsupportedDrop={() => setErrorMessage("ไม่สามารถอ่านพาธไฟล์จากการลากวางได้ กรุณากดเลือกไฟล์แทน")}
              onValueChange={(value) => {
                setThaiIdCsvPath(value);
                resetResult();
              }}
            />

            <PrepareFileCard
              order={4}
              title="ไฟล์ OCR จากสำเนาทะเบียนบ้านนักเรียน"
              statusLabel="ตัวเลือก"
              description="ใช้เติมข้อมูลรหัสประจำบ้าน ที่อยู่ตามทะเบียนบ้าน และข้อมูลบิดา/มารดา"
              value={civilRegistrationMarkdownPaths}
              placeholder="D:\\DMC\\2569\\CivilDoc.md"
              acceptedDescription="รองรับไฟล์ .txt, .md, .csv"
              browseButtonLabel="เลือกไฟล์ OCR"
              browseButtonAriaLabel="เลือกไฟล์ OCR จากสำเนาทะเบียนบ้านนักเรียน"
              iconKind="file"
              optional
              onBrowse={() => void handleBrowseCivilRegistrationMarkdown()}
              onClear={() => {
                setCivilRegistrationMarkdownPaths("");
                resetResult();
              }}
              onDropPaths={(paths) => {
                setCivilRegistrationMarkdownPaths((current) => appendPathList(current, paths));
                resetResult();
              }}
              onUnsupportedDrop={() => setErrorMessage("ไม่สามารถอ่านพาธไฟล์จากการลากวางได้ กรุณากดเลือกไฟล์แทน")}
              onValueChange={(value) => {
                setCivilRegistrationMarkdownPaths(value);
                resetResult();
              }}
            />
          </section>

          <section className="grid gap-4 rounded-lg border bg-muted/20 p-4 lg:grid-cols-[minmax(0,1fr)_260px]">
            <div>
              <Badge variant="default">3. ตรวจและส่งออก</Badge>
              <h2 className="mt-2 text-lg font-semibold">ตั้งค่าก่อนตรวจตัวอย่าง</h2>
              <p className="mt-1 text-sm text-muted-foreground">
                ตรวจตัวอย่างก่อนสร้างไฟล์ JSON เพื่อดูจำนวนรายการ คำเตือน และข้อมูลจำเป็นที่ยังขาด
              </p>
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
              <Button disabled={!canPreview} onClick={() => void handlePreviewDmcFormJson()}>
                {isPreviewing ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileOutput className="h-4 w-4" />}
                ตรวจและแสดงตัวอย่าง
              </Button>
              {previewHint ? <div className="text-sm text-muted-foreground">{previewHint}</div> : null}
            </div>
          </section>

          {activeResult ? (
            <div className="grid gap-4 rounded-md border bg-muted/30 p-4 lg:grid-cols-[minmax(0,1fr)_auto]">
              <div className="grid gap-3 sm:grid-cols-6">
                <SummaryItem label="รายการที่พบ" value={jsonExport?.records_exported ?? jsonPreview?.records_previewed ?? 0} />
                <SummaryItem label="จับคู่ได้" value={activeResult.summary.auto_matched} />
                <SummaryItem label="ทะเบียนบ้าน" value={activeResult.summary.civil_registration_records} />
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

type PrepareFileCardProps = {
  order: number;
  title: string;
  statusLabel: string;
  description: string;
  value: string;
  placeholder: string;
  acceptedDescription: string;
  browseButtonLabel: string;
  browseButtonAriaLabel?: string;
  iconKind: "excel" | "file";
  optional?: boolean;
  onBrowse: () => void;
  onClear: () => void;
  onDropPaths: (paths: string[]) => void;
  onUnsupportedDrop: () => void;
  onValueChange: (value: string) => void;
};

function PrepareFileCard({
  order,
  title,
  statusLabel,
  description,
  value,
  placeholder,
  acceptedDescription,
  browseButtonLabel,
  browseButtonAriaLabel,
  iconKind,
  optional = false,
  onBrowse,
  onClear,
  onDropPaths,
  onUnsupportedDrop,
  onValueChange,
}: PrepareFileCardProps) {
  const InputIcon = iconKind === "excel" ? FileSpreadsheet : FileIcon;
  const selectedValue = pathInputValue(value);
  const hasValue = selectedValue.length > 0;

  function handleDrop(event: DragEvent<HTMLButtonElement>) {
    event.preventDefault();
    const paths = droppedFilePaths(event);
    if (paths.length) {
      onDropPaths(paths);
      return;
    }
    onUnsupportedDrop();
  }

  return (
    <section className="min-w-0 rounded-lg border bg-background p-4 shadow-sm">
      <div className="flex items-start gap-3">
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-slate-900 text-sm font-semibold text-white">
          {order}
        </div>
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-base font-semibold leading-6">{title}</h3>
            <span
              className={
                optional
                  ? "rounded-full bg-slate-100 px-2 py-0.5 text-xs font-semibold text-slate-600"
                  : "rounded-full bg-rose-50 px-2 py-0.5 text-xs font-semibold text-rose-600"
              }
            >
              {statusLabel}
            </span>
          </div>
          <p className="mt-1 text-sm leading-6 text-muted-foreground">{description}</p>
        </div>
      </div>

      <div className="mt-4 grid gap-2 sm:grid-cols-[minmax(0,1fr)_auto]">
        <div className="relative min-w-0">
          <InputIcon
            className={
              iconKind === "excel"
                ? "pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-emerald-600"
                : "pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500"
            }
          />
          <Input
            className="h-9 pl-9 pr-9"
            value={selectedValue}
            onChange={(event) => onValueChange(event.target.value)}
            placeholder={placeholder}
          />
          {hasValue ? (
            <button
              type="button"
              className="absolute right-2 top-1/2 inline-flex h-6 w-6 -translate-y-1/2 items-center justify-center rounded-md text-slate-500 hover:bg-slate-100 hover:text-slate-900"
              aria-label={`ล้าง${title}`}
              onClick={onClear}
            >
              <X className="h-3.5 w-3.5" />
            </button>
          ) : null}
        </div>

        <Button
          type="button"
          variant="outline"
          className="border-blue-300 text-blue-700 hover:bg-blue-50 hover:text-blue-800"
          aria-label={browseButtonAriaLabel}
          onClick={onBrowse}
        >
          <FolderOpen className="h-4 w-4" />
          {browseButtonLabel}
        </Button>
      </div>

      <button
        type="button"
        className="mt-3 flex min-h-16 w-full flex-col items-center justify-center gap-1 rounded-md border border-dashed border-blue-200 bg-blue-50/20 px-3 py-3 text-center text-sm text-muted-foreground transition-colors hover:border-blue-300 hover:bg-blue-50 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
        onClick={onBrowse}
        onDragOver={(event) => event.preventDefault()}
        onDrop={handleDrop}
      >
        <span className="inline-flex items-center gap-1 font-medium text-blue-700">
          <UploadCloud className="h-4 w-4" />
          ลากไฟล์มาวางที่นี่ หรือ คลิกเพื่อเลือกไฟล์
        </span>
        <span>{acceptedDescription}</span>
      </button>
    </section>
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
            {columnGroups.map((group) => (
              <th
                key={group.label}
                colSpan={group.colSpan}
                className="whitespace-nowrap border-b border-l px-3 py-2 text-center text-xs font-semibold text-muted-foreground"
              >
                {group.label}
              </th>
            ))}
            <th rowSpan={2} className="whitespace-nowrap border-b border-l px-3 py-2 font-medium">
              สถานะ
            </th>
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
                {columns.map(({ fieldName }) => (
                  <td key={`${record.record_id}-${fieldName}`} className="whitespace-nowrap border-b px-3 py-2">
                    {formatFieldValue(recordFieldValue(record, fieldName))}
                  </td>
                ))}
                <td className="border-b border-l px-3 py-2">
                  <span className={missingCount ? "font-medium text-amber-800" : "font-medium text-emerald-700"}>
                    {missingCount ? `ขาด ${missingCount} ช่อง` : "พร้อม"}
                  </span>
                </td>
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

function pathInputValue(value: string): string {
  return markdownPaths(value).join("; ");
}

function appendPathList(current: string, paths: string[]): string {
  const mergedPaths = [...markdownPaths(current), ...paths.map((path) => path.trim()).filter(Boolean)];
  return Array.from(new Set(mergedPaths)).join("\n");
}

function droppedFilePaths(event: DragEvent): string[] {
  return Array.from(event.dataTransfer.files)
    .map((file) => (file as File & { path?: string }).path?.trim() ?? "")
    .filter(Boolean);
}

function markdownPaths(value: string): string[] {
  return value
    .split(/[\r\n;]+/)
    .map((item) => item.trim())
    .filter(Boolean);
}
