import messages from "../i18n/th.json";

const formConverterErrors = messages.app.formConverter.errors as Record<string, string>;
const generalErrors: Record<string, string> = {
  CONFIG_BUNDLED_INVALID: "ไฟล์ตั้งค่าที่มากับแอปเสียหายหรือไม่ครบ กรุณาติดตั้งแอปใหม่ก่อนใช้งาน Graduation",
  AI_API_KEY_REQUIRED: "กรุณาตั้งค่า Gemini API key ที่หน้าหลักก่อนใช้ OCR",
  AI_API_KEY_INVALID: "Gemini API key ไม่ถูกต้องหรือไม่มีสิทธิ์ใช้งาน กรุณาตรวจสอบที่หน้าหลัก",
  AI_CREDENTIAL_STORE_UNAVAILABLE: "ไม่สามารถเข้าถึงที่เก็บ API key ที่ปลอดภัยได้ กรุณาตรวจสอบการตั้งค่า AI ที่หน้าหลัก",
  AI_PROVIDER_UNAVAILABLE: "ผู้ให้บริการ AI ยังไม่พร้อมใช้งาน กรุณาลองใหม่ภายหลัง",
  AI_RATE_LIMITED: "AI จำกัดจำนวนคำขอชั่วคราว กรุณารอสักครู่แล้วลองใหม่",
  AI_REQUEST_TIMEOUT: "รอผลลัพธ์จาก AI นานเกินไป กรุณาลองใหม่",
  AI_RESPONSE_INVALID: "AI ส่งผลลัพธ์ในรูปแบบที่อ่านไม่ได้ กรุณาลองใหม่",
  AI_INPUT_UNSUPPORTED: "ไฟล์ไม่รองรับหรืออ่านไม่ได้ กรุณาเลือกไฟล์ PDF หรือรูปภาพที่ถูกต้อง",
  AI_JOB_FAILED: "AI ประมวลผลเอกสารไม่สำเร็จ กรุณาลองใหม่",
  OCR_PROVIDER_UNSUPPORTED: "ยังไม่รองรับ AI provider ที่ตั้งค่าไว้",
  OCR_PROVIDER_RESPONSE_INVALID: "ผลลัพธ์จาก AI อยู่ในรูปแบบที่ระบบอ่านไม่ได้ กรุณาลองใหม่หรือส่ง diagnostics",
};

const errorMaps = [formConverterErrors, generalErrors];
const desktopRuntimeRecoveryMessage =
  "Desktop runtime ยังไม่เชื่อมต่อ ฟังก์ชันนี้ต้องเปิดผ่านหน้าต่าง DMC Assistant desktop ไม่ใช่ browser preview/localhost หากกำลังทดสอบให้รัน `corepack pnpm --dir apps/desktop exec tauri dev` แล้วใช้หน้าต่างแอปที่เด้งขึ้นมา หรือกดลองเชื่อมต่อใหม่";
const sidecarRecoveryMessage =
  "ตัวเชื่อมระบบยังไม่พร้อม กรุณากดลองเชื่อมต่อใหม่ หากยังไม่หายให้ปิดหน้าต่าง DMC Assistant แล้วรัน `corepack pnpm --dir apps/desktop exec tauri dev` ใหม่อีกครั้ง";
const genericRecoveryMessage = "ระบบทำรายการไม่สำเร็จ กรุณาลองอีกครั้ง หากยังเกิดซ้ำให้ส่ง diagnostics ให้ผู้ดูแล";

export type RuntimeConnectionErrorKind = "desktop" | "sidecar";

function includesAny(value: string, patterns: string[]): boolean {
  return patterns.some((pattern) => value.includes(pattern));
}

export function getRuntimeConnectionErrorKind(error: unknown): RuntimeConnectionErrorKind | null {
  const raw = error instanceof Error ? error.message : String(error);
  const normalized = raw.toLowerCase();
  const isOwnDesktopRecoveryMessage =
    normalized.includes("desktop runtime") && normalized.includes("browser preview/localhost");
  const isOwnSidecarRecoveryMessage = raw.includes("ตัวเชื่อมระบบยังไม่พร้อม");
  if (
    isOwnDesktopRecoveryMessage ||
    includesAny(normalized, [
      "desktop_runtime_unavailable",
      "tauri ipc is not available",
      "window.__tauri",
      "__tauri",
      "transformcallback",
      "reading 'invoke'",
      'reading "invoke"',
      "invoke is not a function",
      "invoke is undefined",
    ])
  ) {
    return "desktop";
  }
  if (
    isOwnSidecarRecoveryMessage ||
    includesAny(normalized, [
      "sidecar process",
      "sidecar runtime",
      "sidecar owner",
      "sidecar stdout",
      "sidecar stdin",
      "sidecar response channel",
      "sidecar output line",
      "timed out waiting for sidecar response",
      "stdout closed before a response",
      "stdin closed while writing",
      "failed writing to sidecar stdin",
      "failed reading sidecar",
      "no sidecar runtime candidate",
      "could not start sidecar",
    ])
  ) {
    return "sidecar";
  }
  return null;
}

export function isRuntimeConnectionError(error: unknown): boolean {
  return getRuntimeConnectionErrorKind(error) !== null;
}

export function describeErrorCode(code: string | null | undefined): string | null {
  if (!code) {
    return null;
  }
  for (const mapping of errorMaps) {
    if (mapping[code]) {
      return mapping[code];
    }
  }
  return null;
}

export function describeUserFacingError(error: unknown): string {
  const raw = error instanceof Error ? error.message : String(error);
  const runtimeKind = getRuntimeConnectionErrorKind(raw);
  if (runtimeKind === "desktop") {
    return desktopRuntimeRecoveryMessage;
  }
  if (runtimeKind === "sidecar") {
    return sidecarRecoveryMessage;
  }
  for (const mapping of errorMaps) {
    for (const [code, message] of Object.entries(mapping)) {
      if (raw.includes(code)) {
        return message;
      }
    }
  }
  if (
    raw.includes("Cannot read properties") ||
    raw.includes("TypeError") ||
    raw.includes("undefined") ||
    raw.includes("null")
  ) {
    return genericRecoveryMessage;
  }
  return raw;
}

export function describeAiError(error: unknown): string {
  if (getRuntimeConnectionErrorKind(error)) {
    return describeUserFacingError(error);
  }
  const raw = error instanceof Error ? error.message : String(error);
  const code = raw.match(/\bAI_[A-Z_]+\b/)?.[0];
  return (code && generalErrors[code]) || generalErrors.AI_JOB_FAILED;
}
