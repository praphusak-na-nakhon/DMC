import messages from "../i18n/th.json";

const accountErrors = messages.app.account.errors as Record<string, string>;
const formConverterErrors = messages.app.formConverter.errors as Record<string, string>;
const generalErrors: Record<string, string> = {
  CONFIG_SIGNATURE_INVALID: "ลายเซ็น config ไม่ถูกต้อง ระบบจะใช้ config ที่ปลอดภัยจากเครื่องแทน",
  CONFIG_CACHE_INVALID: "ไฟล์ config ที่เก็บไว้เสียหาย ระบบจะกลับไปใช้ config ที่มากับแอป",
  CONFIG_SYNC_UNAVAILABLE: "เชื่อมต่อ cloud เพื่ออัปเดต config ไม่ได้",
  OCR_PROVIDER_UNSUPPORTED: "ยังไม่รองรับ AI provider ที่ตั้งค่าไว้",
  OCR_PROVIDER_RESPONSE_INVALID: "ผลลัพธ์จาก AI อยู่ในรูปแบบที่ระบบอ่านไม่ได้ กรุณาลองใหม่หรือส่ง diagnostics",
  PSAR_EVIDENCE_FILE_NOT_FOUND: "ไม่พบไฟล์หลักฐานที่เลือก",
  PSAR_EVIDENCE_PATH_NOT_FILE: "พาธหลักฐานที่เลือกไม่ใช่ไฟล์",
  PSAR_EVIDENCE_UNSUPPORTED_TYPE: "หลักฐานต้องเป็นไฟล์ PDF, DOCX, XLSX หรือรูปภาพ",
  PSAR_PROJECT_ID_INVALID: "รหัสโปรเจกต์ใช้ได้เฉพาะตัวอักษร ตัวเลข ขีดกลาง ขีดล่าง และจุด",
};

const errorMaps = [accountErrors, formConverterErrors, generalErrors];

export function describeAccountCode(code: string | null | undefined): string | null {
  if (!code) {
    return null;
  }
  return accountErrors[code] ?? null;
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
  for (const mapping of errorMaps) {
    for (const [code, message] of Object.entries(mapping)) {
      if (raw.includes(code)) {
        return message;
      }
    }
  }
  return raw;
}
