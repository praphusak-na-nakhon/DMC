import {
  AlertTriangle,
  File as FileIcon,
  FileOutput,
  FileSpreadsheet,
  FileText,
  FolderOpen,
  Loader2,
  ScanText,
  UploadCloud,
  X,
  type LucideIcon,
} from "lucide-react";
import { useState, type DragEvent, type ReactNode } from "react";
import messages from "../i18n/th.json";
import { describeUserFacingError } from "../lib/errorMessages";
import {
  exportDmcFormJson,
  openCsvDialog,
  openExcelDialog,
  openMarkdownDialog,
  openOcrSourceDialog,
  ocrDmcFormWithGemini,
  previewDmcFormJson,
  copyOcrMarkdownFile,
  saveOcrMarkdownDialog,
} from "../lib/rpcClient";
import type {
  GeminiOcrDmcFormResponse,
  DmcFormJsonRecord,
  CurrentStudentsFieldConflict,
  CurrentStudentsWarning,
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

type OcrInputMode = "ocrFile" | "scanFile";

const ROSTER_WARNING_FIELDS = [
  "student_no",
  "citizen_id",
  "grade",
  "room",
  "sex",
  "prefix",
  "first_name",
  "last_name",
  "birth_date",
];

const THAI_ID_WARNING_FIELDS = [
  "citizen_id",
  "prefix",
  "first_name",
  "last_name",
  "sex",
  "birth_date",
  "first_name_en",
  "last_name_en",
  "registered_address.house_no",
  "registered_address.moo",
  "registered_address.road",
  "registered_address.subdistrict",
  "registered_address.district",
  "registered_address.province",
];

const OCR_FORM_WARNING_FIELDS = [
  "citizen_id",
  "student_no",
  "prefix",
  "first_name",
  "last_name",
  "sex",
  "birth_date",
  "birth_province",
  "weight_kg",
  "height_cm",
  "religion",
  "race",
  "nationality",
  "registered_address.house_id",
  "registered_address.house_no",
  "registered_address.subdistrict",
  "registered_address.district",
  "registered_address.province",
  "registered_address.postal_code",
  "father.first_name",
  "father.last_name",
  "mother.first_name",
  "mother.last_name",
  "guardian.first_name",
  "guardian.last_name",
];

const CIVIL_REGISTRATION_WARNING_FIELDS = [
  "citizen_id",
  "registered_address.house_id",
  "registered_address.house_no",
  "registered_address.moo",
  "registered_address.subdistrict",
  "registered_address.district",
  "registered_address.province",
  "father.citizen_id",
  "father.first_name",
  "father.last_name",
  "mother.citizen_id",
  "mother.first_name",
  "mother.last_name",
];

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
  SIGN_IN_REQUIRED: "กรุณาเข้าสู่ระบบก่อนใช้ OCR แบบคิดเครดิต",
  INSUFFICIENT_CREDITS: "เครดิตไม่พอสำหรับ OCR จำนวนหน้านี้",
  GEMINIOCR_API_KEY_REQUIRED: "ยังไม่ได้ตั้งค่า Gemini API key ฝั่งระบบ",
  GEMINIOCR_DEPENDENCY_MISSING: "ระบบยังไม่พร้อมเรียก Gemini ใน sidecar",
  GEMINIOCR_MODEL_UNSUPPORTED: "โมเดล Gemini OCR นี้ยังไม่รองรับ",
  GEMINIOCR_INPUT_NOT_FOUND: "ไม่พบไฟล์ PDF/รูปภาพที่เลือกสำหรับ Gemini",
  GEMINIOCR_INPUT_NOT_FILE: "พาธที่เลือกสำหรับ Gemini ไม่ใช่ไฟล์",
  GEMINIOCR_INPUT_EMPTY: "ไฟล์ที่เลือกสำหรับ Gemini ไม่มีข้อมูล",
  GEMINIOCR_UNSUPPORTED_INPUT_TYPE: "Gemini รองรับเฉพาะไฟล์ .pdf, .png, .jpg, .jpeg, .webp",
  GEMINIOCR_FILE_TOO_LARGE: "ไฟล์ใหญ่เกินขีดจำกัด Gemini: สูงสุด 200 MB ต่อครั้ง",
  GEMINIOCR_PAGE_LIMIT_EXCEEDED: "ไฟล์ PDF เกิน 1000 หน้า สำหรับ Gemini",
  GEMINIOCR_PAGE_COUNT_UNKNOWN: "ไม่สามารถนับจำนวนหน้า PDF ก่อนทำ OCR ได้",
  GEMINIOCR_PDF_SPLIT_FAILED: "ไม่สามารถแยก PDF เป็นชุดละ 2 หน้าก่อนส่ง Gemini Batch OCR ได้",
  GEMINIOCR_AUTH_FAILED: "Gemini API key ไม่ถูกต้องหรือไม่มีสิทธิ์ใช้งาน",
  GEMINIOCR_RATE_LIMITED: "Gemini จำกัดจำนวนคำขอชั่วคราว กรุณาลองใหม่อีกครั้ง",
  GEMINIOCR_NETWORK_ERROR: "เชื่อมต่อ Gemini ไม่สำเร็จ กรุณาตรวจสอบอินเทอร์เน็ต",
  GEMINIOCR_UPLOAD_REJECTED: "Gemini ปฏิเสธไฟล์หรือคำขอที่ส่งไป",
  GEMINIOCR_FILE_PROCESSING_FAILED: "Gemini ประมวลผลไฟล์ที่อัปโหลดไม่สำเร็จ",
  GEMINIOCR_FILE_PROCESSING_TIMEOUT: "รอ Gemini ประมวลผลไฟล์นานเกินไป กรุณาลองใหม่อีกครั้ง",
  GEMINIOCR_PROCESSING_FAILED: "Gemini ประมวลผลไฟล์ไม่สำเร็จ",
  GEMINIOCR_RESPONSE_INVALID: "Gemini ส่งผลลัพธ์กลับมาในรูปแบบที่ระบบอ่านไม่ได้",
  GEMINIOCR_BATCH_TIMEOUT: "Gemini Batch OCR ยังไม่เสร็จภายในเวลาที่กำหนด กรุณาลองไฟล์เล็กลงหรือตรวจสถานะใน Google AI Studio",
  GEMINIOCR_BATCH_FAILED: "Gemini Batch OCR ทำงานไม่สำเร็จ กรุณาลองใหม่อีกครั้ง",
  GEMINIOCR_BATCH_RESPONSE_MISSING: "Gemini Batch OCR เสร็จแล้วแต่ไม่มีผลลัพธ์ที่ระบบอ่านได้",
  OCR_MARKDOWN_SOURCE_NOT_FOUND: "ไม่พบไฟล์ OCR ต้นทางสำหรับบันทึกเป็นไฟล์ใหม่",
  OCR_MARKDOWN_SOURCE_NOT_FILE: "ตำแหน่งไฟล์ OCR ต้นทางไม่ใช่ไฟล์",
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
  const [ocrInputMode, setOcrInputMode] = useState<OcrInputMode>("ocrFile");
  const [geminiSourcePath, setGeminiSourcePath] = useState("");
  const [geminiOcrResult, setGeminiOcrResult] = useState<GeminiOcrDmcFormResponse | null>(null);
  const [civilRegistrationInputMode, setCivilRegistrationInputMode] = useState<OcrInputMode>("ocrFile");
  const [civilRegistrationGeminiSourcePath, setCivilRegistrationGeminiSourcePath] = useState("");
  const [civilRegistrationGeminiOcrResult, setCivilRegistrationGeminiOcrResult] =
    useState<GeminiOcrDmcFormResponse | null>(null);
  const [schoolYear, setSchoolYear] = useState("2569");
  const [gradeLevels, setGradeLevels] = useState("1");
  const [admissionDate, setAdmissionDate] = useState("");
  const [jsonPreview, setJsonPreview] = useState<PreviewDmcFormJsonResponse | null>(null);
  const [jsonExport, setJsonExport] = useState<ExportDmcFormJsonResponse | null>(null);
  const [showTablePreview, setShowTablePreview] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isPreviewing, setIsPreviewing] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [isRunningGeminiOcr, setIsRunningGeminiOcr] = useState(false);
  const [isRunningCivilRegistrationGeminiOcr, setIsRunningCivilRegistrationGeminiOcr] = useState(false);
  const activeResult = jsonExport ?? jsonPreview;
  const activeConflicts = activeResult?.conflicts ?? [];
  const activeWarnings = activeResult?.warnings ?? [];
  const blockingMissingWarnings = filterWarningsForMissingNoFallback(activeWarnings, activeConflicts);
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

  async function handleBrowseGeminiSource() {
    try {
      const selected = await openOcrSourceDialog();
      if (selected) {
        setGeminiSourcePath(selected);
        setGeminiOcrResult(null);
        setErrorMessage(null);
      }
    } catch (error) {
      setErrorMessage(readableError(error));
    }
  }

  async function handleRunGeminiOcr() {
    const sourcePath = geminiSourcePath.trim();
    if (!sourcePath) {
      setErrorMessage("กรุณาเลือกไฟล์ PDF หรือรูปภาพก่อนสร้างไฟล์ OCR");
      return;
    }

    setIsRunningGeminiOcr(true);
    setErrorMessage(null);
    try {
      const result = await ocrDmcFormWithGemini({
        sourcePath,
        apiKey: null,
        model: "gemini-3.5-flash",
        processingMode: "batch",
        forceRefresh: false,
      });
      setGeminiOcrResult(result);
      setOcrMarkdownPaths((current) => appendPathList(current, [result.markdown_path]));
      resetResult();
    } catch (error) {
      setErrorMessage(readableError(error));
    } finally {
      setIsRunningGeminiOcr(false);
    }
  }

  async function handleSaveGeminiOcrAs() {
    if (!geminiOcrResult) {
      return;
    }

    setErrorMessage(null);
    try {
      const destinationPath = await saveOcrMarkdownDialog(fileNameFromPath(geminiOcrResult.markdown_path));
      if (!destinationPath) {
        return;
      }
      const savedPath = await copyOcrMarkdownFile(geminiOcrResult.markdown_path, destinationPath);
      const originalPath = geminiOcrResult.markdown_path;
      setGeminiOcrResult({ ...geminiOcrResult, markdown_path: savedPath });
      setOcrMarkdownPaths((current) => replacePathList(current, originalPath, savedPath));
      resetResult();
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

  async function handleBrowseCivilRegistrationGeminiSource() {
    try {
      const selected = await openOcrSourceDialog();
      if (selected) {
        setCivilRegistrationGeminiSourcePath(selected);
        setCivilRegistrationGeminiOcrResult(null);
        setErrorMessage(null);
      }
    } catch (error) {
      setErrorMessage(readableError(error));
    }
  }

  async function handleRunCivilRegistrationGeminiOcr() {
    const sourcePath = civilRegistrationGeminiSourcePath.trim();
    if (!sourcePath) {
      setErrorMessage("กรุณาเลือกไฟล์ PDF หรือรูปภาพก่อนสร้างไฟล์ OCR");
      return;
    }

    setIsRunningCivilRegistrationGeminiOcr(true);
    setErrorMessage(null);
    try {
      const result = await ocrDmcFormWithGemini({
        sourcePath,
        apiKey: null,
        model: "gemini-3.5-flash",
        processingMode: "batch",
        forceRefresh: false,
      });
      setCivilRegistrationGeminiOcrResult(result);
      setCivilRegistrationMarkdownPaths((current) => appendPathList(current, [result.markdown_path]));
      resetResult();
    } catch (error) {
      setErrorMessage(readableError(error));
    } finally {
      setIsRunningCivilRegistrationGeminiOcr(false);
    }
  }

  async function handleSaveCivilRegistrationGeminiOcrAs() {
    if (!civilRegistrationGeminiOcrResult) {
      return;
    }

    setErrorMessage(null);
    try {
      const destinationPath = await saveOcrMarkdownDialog(
        fileNameFromPath(civilRegistrationGeminiOcrResult.markdown_path),
      );
      if (!destinationPath) {
        return;
      }
      const savedPath = await copyOcrMarkdownFile(civilRegistrationGeminiOcrResult.markdown_path, destinationPath);
      const originalPath = civilRegistrationGeminiOcrResult.markdown_path;
      setCivilRegistrationGeminiOcrResult({ ...civilRegistrationGeminiOcrResult, markdown_path: savedPath });
      setCivilRegistrationMarkdownPaths((current) => replacePathList(current, originalPath, savedPath));
      resetResult();
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
      admissionDate: admissionDate.trim() || null,
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
    const message = errorMessages[code];
    if (message && code === "GEMINIOCR_BATCH_FAILED") {
      const detail = raw.replace(/^.*GEMINIOCR_BATCH_FAILED[:\s-]*/s, "").trim();
      if (detail && !detail.includes(message)) {
        return `${message}\nรายละเอียดจาก Gemini: ${detail}`;
      }
    }
    return message ?? describeUserFacingError(error);
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
              description="เลือกใช้ไฟล์ OCR ที่มีอยู่ หรือสร้างไฟล์ OCR จาก PDF/รูปภาพด้วย Gemini"
              value={ocrMarkdownPaths}
              placeholder="C:\\dmc\\uploadTest\\1-3ex.md"
              acceptedDescription="รองรับไฟล์ .json, .txt, .md, .csv"
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
              beforePicker={
                <OcrInputModeSelector
                  ariaLabel="โหมดไฟล์ OCR แบบฟอร์ม DMC"
                  mode={ocrInputMode}
                  onModeChange={(mode) => {
                    setOcrInputMode(mode);
                    setErrorMessage(null);
                  }}
                />
              }
              showPicker={ocrInputMode === "ocrFile"}
            >
              {ocrInputMode === "scanFile" ? (
                <GeminiOcrTool
                  sourcePath={geminiSourcePath}
                  result={geminiOcrResult}
                  isRunning={isRunningGeminiOcr}
                  onSourcePathChange={(value) => {
                    setGeminiSourcePath(value);
                    setGeminiOcrResult(null);
                  }}
                  onBrowseSource={() => void handleBrowseGeminiSource()}
                  onRun={() => void handleRunGeminiOcr()}
                  onSaveAs={() => void handleSaveGeminiOcrAs()}
                  onRevealPath={onRevealPath}
                />
              ) : null}
            </PrepareFileCard>

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
              description="เลือกใช้ไฟล์ OCR ที่มีอยู่ หรือสร้างไฟล์ OCR จาก PDF/รูปภาพด้วย Gemini"
              value={civilRegistrationMarkdownPaths}
              placeholder="D:\\DMC\\2569\\CivilDoc.md"
              acceptedDescription="รองรับไฟล์ .json, .txt, .md, .csv"
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
              beforePicker={
                <OcrInputModeSelector
                  ariaLabel="โหมดไฟล์ OCR ทะเบียนบ้าน"
                  mode={civilRegistrationInputMode}
                  onModeChange={(mode) => {
                    setCivilRegistrationInputMode(mode);
                    setErrorMessage(null);
                  }}
                />
              }
              showPicker={civilRegistrationInputMode === "ocrFile"}
            >
              {civilRegistrationInputMode === "scanFile" ? (
                <GeminiOcrTool
                  sourcePath={civilRegistrationGeminiSourcePath}
                  result={civilRegistrationGeminiOcrResult}
                  isRunning={isRunningCivilRegistrationGeminiOcr}
                  onSourcePathChange={(value) => {
                    setCivilRegistrationGeminiSourcePath(value);
                    setCivilRegistrationGeminiOcrResult(null);
                  }}
                  onBrowseSource={() => void handleBrowseCivilRegistrationGeminiSource()}
                  onRun={() => void handleRunCivilRegistrationGeminiOcr()}
                  onSaveAs={() => void handleSaveCivilRegistrationGeminiOcrAs()}
                  onRevealPath={onRevealPath}
                />
              ) : null}
            </PrepareFileCard>
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
              <div className="grid gap-2">
                <Label htmlFor="dmc-admission-date">วันที่มอบตัว</Label>
                <Input
                  id="dmc-admission-date"
                  type="date"
                  value={admissionDate}
                  onChange={(event) => {
                    setAdmissionDate(event.target.value);
                    resetResult();
                  }}
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
                <SummaryItem label="คำเตือน" value={blockingMissingWarnings.length} />
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
                <WarningAudit warnings={blockingMissingWarnings} />
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
  beforePicker?: ReactNode;
  showPicker?: boolean;
  children?: ReactNode;
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
  beforePicker,
  showPicker = true,
  children,
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

      {beforePicker ? <div className="mt-4">{beforePicker}</div> : null}

      {showPicker ? (
        <>
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
        </>
      ) : null}
      {children ? <div className={showPicker ? "mt-4 border-t pt-4" : "mt-4"}>{children}</div> : null}
    </section>
  );
}

function OcrInputModeSelector({
  ariaLabel,
  mode,
  onModeChange,
}: {
  ariaLabel: string;
  mode: OcrInputMode;
  onModeChange: (mode: OcrInputMode) => void;
}) {
  const options: Array<{ value: OcrInputMode; label: string; icon: LucideIcon }> = [
    { value: "ocrFile", label: "มีไฟล์ OCR แล้ว", icon: FileText },
    { value: "scanFile", label: "มีไฟล์สแกน PDF/รูปภาพ", icon: ScanText },
  ];

  return (
    <div className="grid gap-2 rounded-md bg-slate-100 p-1 sm:grid-cols-2" role="tablist" aria-label={ariaLabel}>
      {options.map((option) => {
        const Icon = option.icon;
        const selected = mode === option.value;
        return (
          <button
            key={option.value}
            type="button"
            role="tab"
            aria-selected={selected}
            className={
              selected
                ? "inline-flex h-9 items-center justify-center gap-2 rounded-md bg-background px-3 text-sm font-semibold text-slate-950 shadow-sm"
                : "inline-flex h-9 items-center justify-center gap-2 rounded-md px-3 text-sm font-medium text-slate-600 hover:bg-background/70 hover:text-slate-950"
            }
            onClick={() => onModeChange(option.value)}
          >
            <Icon className="h-4 w-4" />
            {option.label}
          </button>
        );
      })}
    </div>
  );
}

function GeminiOcrTool({
  sourcePath,
  result,
  isRunning,
  onSourcePathChange,
  onBrowseSource,
  onRun,
  onSaveAs,
  onRevealPath,
}: {
  sourcePath: string;
  result: GeminiOcrDmcFormResponse | null;
  isRunning: boolean;
  onSourcePathChange: (value: string) => void;
  onBrowseSource: () => void;
  onRun: () => void;
  onSaveAs: () => void;
  onRevealPath: (path: string) => void;
}) {
  const canRun = sourcePath.trim().length > 0 && !isRunning;

  return (
    <div className="grid gap-3 rounded-md border bg-slate-50/50 p-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="text-sm font-semibold">สร้างไฟล์ OCR จาก PDF/รูปภาพ</div>
          <div className="mt-0.5 text-xs leading-5 text-muted-foreground">
            สร้าง JSON เฉพาะฟิลด์ที่ต้องใช้และบันทึก token usage สำหรับคำนวณต้นทุนจริง
          </div>
        </div>
        <span className="rounded-full bg-blue-50 px-2 py-0.5 text-xs font-semibold text-blue-700">
          Gemini Flash Batch
        </span>
      </div>

      <div className="grid gap-2 xl:grid-cols-[minmax(0,1fr)_auto]">
        <div className="relative min-w-0">
          <FileIcon className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
          <Input
            aria-label="ไฟล์ PDF หรือรูปภาพสำหรับ Gemini"
            className="h-9 pl-9"
            value={sourcePath}
            onChange={(event) => onSourcePathChange(event.target.value)}
            placeholder="C:\\dmc\\uploadTest\\dmc-form.pdf"
          />
        </div>
        <Button
          type="button"
          variant="outline"
          className="border-blue-300 text-blue-700 hover:bg-blue-50 hover:text-blue-800"
          aria-label="เลือกไฟล์ PDF หรือรูปภาพสำหรับ Gemini"
          onClick={onBrowseSource}
        >
          <FolderOpen className="h-4 w-4" />
          เลือก PDF/รูปภาพ
        </Button>
      </div>

      <Button type="button" disabled={!canRun} onClick={onRun}>
        {isRunning ? <Loader2 className="h-4 w-4 animate-spin" /> : <ScanText className="h-4 w-4" />}
        สร้างไฟล์ OCR
      </Button>

      {result ? (
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-md border bg-background px-3 py-2 text-xs">
          <div className="min-w-0">
            <span className="font-medium text-emerald-700">{result.cached ? "ใช้ไฟล์ OCR ที่เคยสร้างแล้ว" : "สร้างไฟล์ OCR แล้ว"}</span>
            <span className="mx-1 text-muted-foreground">·</span>
            <span className="break-all text-muted-foreground">{fileNameFromPath(result.markdown_path)}</span>
            <span className="mx-1 text-muted-foreground">·</span>
            <span className="text-muted-foreground">
              {result.pages_processed} หน้า
              {formatGeminiMode(result)}
              {result.average_confidence === null ? "" : ` · confidence ${formatConfidence(result.average_confidence)}`}
              {formatGeminiUsage(result)}
              {result.cached
                ? " · ไม่คิดเครดิตซ้ำ"
                : result.charged
                  ? ` · ใช้ ${result.credits_charged} เครดิต (${result.credits_per_page} เครดิต/หน้า)`
                  : " · ไม่คิดเครดิตระบบ"}
            </span>
          </div>
          <div className="flex shrink-0 flex-wrap items-center gap-1">
            <Button type="button" variant="ghost" size="sm" onClick={onSaveAs}>
              <FileOutput className="h-4 w-4" />
              บันทึกเป็น...
            </Button>
            <Button type="button" variant="ghost" size="sm" onClick={() => onRevealPath(result.markdown_path)}>
              เปิดไฟล์
            </Button>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function filterWarningsForMissingNoFallback(
  warnings: CurrentStudentsWarning[],
  conflicts: CurrentStudentsFieldConflict[],
): CurrentStudentsWarning[] {
  const missingConflicts = conflicts.filter(isMissingNoFallbackConflict);
  if (!missingConflicts.length) {
    return [];
  }

  return warnings.filter((warning) => {
    const impactedFields = warningImpactedFields(warning);
    if (!impactedFields.length) {
      return false;
    }
    return missingConflicts.some(
      (conflict) =>
        impactedFields.includes(conflict.field_name) && warningCanAffectConflictRecord(warning, conflict),
    );
  });
}

function isMissingNoFallbackConflict(conflict: CurrentStudentsFieldConflict): boolean {
  return (
    conflict.reason === "missing_after_all_sources" &&
    conflict.selected_value === null &&
    conflict.selected_source === null &&
    conflict.source_values.length === 0
  );
}

function warningImpactedFields(warning: CurrentStudentsWarning): string[] {
  switch (warning.code) {
    case "ROSTER_CITIZEN_ID_INVALID":
      return ["citizen_id"];
    case "ROSTER_NO_MATCHING_SHEETS":
      return ROSTER_WARNING_FIELDS;
    case "THAI_ID_INVALID_OR_MASKED":
      return ["citizen_id"];
    case "THAI_ID_CSV_SHORT_ROW":
      return THAI_ID_WARNING_FIELDS;
    case "OCR_CITIZEN_ID_INVALID_OR_MISSING":
      return OCR_FORM_WARNING_FIELDS;
    case "CIVIL_REGISTRATION_CITIZEN_ID_INVALID_OR_MISSING":
    case "CIVIL_REGISTRATION_NO_MATCH_KEY":
      return CIVIL_REGISTRATION_WARNING_FIELDS;
    default:
      return [];
  }
}

function warningCanAffectConflictRecord(
  warning: CurrentStudentsWarning,
  conflict: CurrentStudentsFieldConflict,
): boolean {
  if (warning.source === "roster" && warning.row_index !== null) {
    const rosterRecord = parseRosterRecordId(conflict.record_id);
    return (
      rosterRecord !== null &&
      rosterRecord.rowIndex === warning.row_index &&
      (!warning.sheet_name || rosterRecord.sheetName === warning.sheet_name)
    );
  }

  if (warning.source === "thai_id_scan" && warning.row_index !== null) {
    const scanRecord = parseSourceRecordId(conflict.record_id, "scan");
    return (
      scanRecord !== null &&
      scanRecord.rowIndex === warning.row_index &&
      (!warning.source_path || scanRecord.fileName === fileNameFromPath(warning.source_path))
    );
  }

  return true;
}

function parseRosterRecordId(recordId: string): { sheetName: string; rowIndex: number } | null {
  const parts = recordId.split(":");
  if (parts.length < 4 || parts[0] !== "roster") {
    return null;
  }
  const rowIndex = Number.parseInt(parts[2], 10);
  if (!Number.isInteger(rowIndex)) {
    return null;
  }
  return { sheetName: parts[1], rowIndex };
}

function parseSourceRecordId(recordId: string, prefix: string): { fileName: string; rowIndex: number } | null {
  const parts = recordId.split(":");
  if (parts.length < 3 || parts[0] !== prefix) {
    return null;
  }
  const rowIndex = Number.parseInt(parts[2], 10);
  if (!Number.isInteger(rowIndex)) {
    return null;
  }
  return { fileName: parts[1], rowIndex };
}

function WarningAudit({ warnings }: { warnings: CurrentStudentsWarning[] }) {
  if (!warnings.length) {
    return null;
  }

  return (
    <section className="mb-3 grid gap-3 rounded-md border border-amber-200 bg-amber-50/70 p-4">
      <div className="flex items-start gap-2">
        <AlertTriangle className="mt-0.5 h-4 w-4 text-amber-700" />
        <div>
          <div className="font-medium text-amber-950">คำเตือนจากไฟล์ที่เลือก</div>
          <div className="text-sm text-amber-900">
            แสดงเฉพาะคำเตือนที่ทำให้ข้อมูลจำเป็นยังขาดและไม่มีแหล่งอื่นช่วยเติมได้
          </div>
        </div>
      </div>
      <div className="grid gap-2">
        {warnings.map((warning, index) => (
          <div
            key={`${warning.code}-${warning.source_path ?? "unknown"}-${warning.row_index ?? index}`}
            className="grid gap-1 rounded-md border bg-background px-3 py-2 text-sm lg:grid-cols-[minmax(0,1fr)_auto] lg:items-center"
          >
            <div className="min-w-0">
              <div className="font-medium text-amber-950">{warningMessage(warning)}</div>
              <div className="mt-1 break-words text-xs text-muted-foreground">{warningContext(warning)}</div>
            </div>
            <span className="w-fit rounded-full bg-amber-100 px-2 py-0.5 text-xs font-semibold text-amber-800">
              {warning.code}
            </span>
          </div>
        ))}
      </div>
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

function warningMessage(warning: CurrentStudentsWarning): string {
  const messagesByCode: Record<string, string> = {
    THAI_ID_CSV_SHORT_ROW: "แถวใน CSV เครื่องสแกนบัตรมีคอลัมน์น้อยกว่าที่คาดไว้",
    THAI_ID_INVALID_OR_MASKED: "เลขประจำตัวประชาชนจาก CSV เครื่องสแกนบัตรหาย ถูกปิดบัง หรือ checksum ไม่ผ่าน",
    ROSTER_NO_MATCHING_SHEETS: "ไม่พบชีตบัญชีรายชื่อที่ตรงกับปีการศึกษาและระดับชั้นที่เลือก",
    OCR_CITIZEN_ID_INVALID_OR_MISSING: "ไฟล์ OCR แบบฟอร์ม DMC ไม่มีเลขประจำตัวประชาชน หรือเลขไม่ผ่านการตรวจสอบ",
    CIVIL_REGISTRATION_CITIZEN_ID_INVALID_OR_MISSING:
      "ไฟล์ OCR ทะเบียนบ้านไม่มีเลขประจำตัวประชาชนนักเรียน หรือเลขไม่ผ่านการตรวจสอบ",
    CIVIL_REGISTRATION_NO_MATCH_KEY: "ไฟล์ OCR ทะเบียนบ้านไม่มีเลขประจำตัวประชาชนหรือชื่อนักเรียนที่ใช้จับคู่ได้",
  };
  return messagesByCode[warning.code] ?? warning.message;
}

function warningContext(warning: CurrentStudentsWarning): string {
  const parts = [sourceLabel(warning.source)];
  if (warning.source_path) {
    parts.push(fileNameFromPath(warning.source_path));
  }
  if (warning.sheet_name) {
    parts.push(`ชีต ${warning.sheet_name}`);
  }
  if (warning.row_index) {
    parts.push(`แถว ${warning.row_index}`);
  }
  return parts.filter(Boolean).join(" · ");
}

function sourceLabel(source: CurrentStudentsWarning["source"]): string {
  const labels: Record<NonNullable<CurrentStudentsWarning["source"]>, string> = {
    roster: "บัญชีรายชื่อนักเรียน",
    thai_id_scan: "CSV เครื่องสแกนบัตร",
    ocr_form: "OCR แบบฟอร์ม DMC",
    civil_registration: "OCR ทะเบียนบ้าน",
    derived: "ข้อมูลที่ระบบอนุมาน",
    manual: "ข้อมูลที่กรอกเอง",
  };
  return source ? labels[source] : "ไม่ระบุแหล่งข้อมูล";
}

function fileNameFromPath(path: string): string {
  return path.split(/[\\/]/).pop() ?? path;
}

function formatConfidence(value: number): string {
  return Number.isInteger(value) ? String(value) : value.toFixed(2).replace(/0+$/, "").replace(/\.$/, "");
}

function formatGeminiMode(result: GeminiOcrDmcFormResponse): string {
  const modelLabel = result.model === "gemini-3-pro-preview" ? "Gemini 3 Pro Preview" : "Gemini 3.5 Flash";
  const modeLabel = result.processing_mode === "batch" ? "Batch" : "Standard";
  return ` · ${modelLabel} ${modeLabel}`;
}

function formatGeminiUsage(result: GeminiOcrDmcFormResponse): string {
  const usage = result.usage_metadata;
  if (!usage?.total_token_count) {
    return "";
  }
  const total = usage.total_token_count.toLocaleString("en-US");
  const perPage = usage.total_tokens_per_page;
  if (typeof perPage !== "number" || Number.isNaN(perPage)) {
    return ` · ${total} tokens`;
  }
  return ` · ${total} tokens (${Math.round(perPage).toLocaleString("en-US")}/หน้า)`;
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

function replacePathList(current: string, oldPath: string, newPath: string): string {
  const trimmedOldPath = oldPath.trim();
  const trimmedNewPath = newPath.trim();
  if (!trimmedNewPath) {
    return current;
  }
  const currentPaths = markdownPaths(current);
  const replacedPaths = currentPaths.map((path) => (path === trimmedOldPath ? trimmedNewPath : path));
  if (!currentPaths.includes(trimmedOldPath)) {
    replacedPaths.push(trimmedNewPath);
  }
  return Array.from(new Set(replacedPaths)).join("\n");
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
