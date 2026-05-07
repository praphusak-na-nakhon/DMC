from __future__ import annotations

import base64
import hashlib
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from binascii import Error as Base64Error
from typing import Any, Protocol

from fastapi import HTTPException, status

from .config import settings
from .schemas import (
    OcrFieldResponse,
    OcrFieldStatus,
    OcrFormConverterRequest,
    OcrFormConverterResponse,
    OcrRecordResponse,
    OcrRecordStatus,
)


FIELD_LABELS: tuple[tuple[str, str], ...] = (
    ("student_id", "เลขประจำตัวนักเรียน"),
    ("first_name", "ชื่อ"),
    ("last_name", "นามสกุล"),
    ("birth_date", "วันเกิด"),
    ("phone", "เบอร์โทรศัพท์"),
    ("address", "ที่อยู่"),
)
OCR_PROVIDER_MAX_RESPONSE_BYTES = 8 * 1024 * 1024


class OcrProvider(Protocol):
    name: str

    def extract(self, request: OcrFormConverterRequest, document_bytes: bytes) -> OcrFormConverterResponse:
        pass


class OcrProviderError(Exception):
    def __init__(self, code: str, *, status_code: int = status.HTTP_502_BAD_GATEWAY) -> None:
        super().__init__(code)
        self.code = code
        self.status_code = status_code


class MockOcrProvider:
    name = "mock-form-ocr-v1"

    def extract(self, request: OcrFormConverterRequest, document_bytes: bytes) -> OcrFormConverterResponse:
        records: list[OcrRecordResponse] = []
        for page_number in range(1, request.page_count + 1):
            fields = _mock_fields_for_page(page_number)
            record_status: OcrRecordStatus = "needs_review"
            if any(field.status == "invalid" for field in fields):
                record_status = "invalid"
            records.append(
                OcrRecordResponse(
                    record_id=f"page-{page_number}",
                    page_number=page_number,
                    status=record_status,
                    fields=fields,
                )
            )
        return OcrFormConverterResponse(
            job_id=request.job_id,
            module=request.module,
            template_type=request.template_type,
            provider=self.name,
            records=records,
        )


class OpenAiOcrProvider:
    name = "openai-responses"

    def extract(self, request: OcrFormConverterRequest, document_bytes: bytes) -> OcrFormConverterResponse:
        if not settings.ocr_openai_api_key:
            raise OcrProviderError("OCR_OPENAI_API_KEY_MISSING", status_code=status.HTTP_503_SERVICE_UNAVAILABLE)

        api_request = urllib.request.Request(
            f"{settings.ocr_openai_base_url}/responses",
            data=json.dumps(self._payload(request)).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {settings.ocr_openai_api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(api_request, timeout=90) as response:
                raw_response = _read_provider_response(response)
        except urllib.error.HTTPError as exc:
            raise OcrProviderError(f"OCR_OPENAI_HTTP_{exc.code}") from exc
        except urllib.error.URLError as exc:
            raise OcrProviderError("OCR_OPENAI_UNREACHABLE") from exc
        except TimeoutError as exc:
            raise OcrProviderError("OCR_OPENAI_TIMEOUT") from exc

        return self._parse_response(request, raw_response)

    def _payload(self, request: OcrFormConverterRequest) -> dict[str, Any]:
        return {
            "model": settings.ocr_openai_model,
            "input": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_file",
                            "filename": "student-history.pdf",
                            "file_data": f"data:application/pdf;base64,{request.document_base64}",
                        },
                        {
                            "type": "input_text",
                            "text": _ocr_prompt(request),
                        },
                    ],
                }
            ],
        }

    def _parse_response(
        self,
        request: OcrFormConverterRequest,
        raw_response: str,
    ) -> OcrFormConverterResponse:
        try:
            provider_payload = json.loads(raw_response)
            output_text = _extract_output_text(provider_payload)
            parsed = json.loads(_extract_json_object(output_text))
            records = [OcrRecordResponse.model_validate(record) for record in parsed["records"]]
        except (KeyError, TypeError, ValueError) as exc:
            raise OcrProviderError("OCR_PROVIDER_RESPONSE_INVALID") from exc

        return OcrFormConverterResponse(
            job_id=request.job_id,
            module=request.module,
            template_type=request.template_type,
            provider=f"{self.name}:{settings.ocr_openai_model}",
            records=records,
        )


class GeminiOcrProvider:
    name = "gemini-generate-content"

    def extract(self, request: OcrFormConverterRequest, document_bytes: bytes) -> OcrFormConverterResponse:
        if not settings.ocr_gemini_api_key:
            raise OcrProviderError("OCR_GEMINI_API_KEY_MISSING", status_code=status.HTTP_503_SERVICE_UNAVAILABLE)

        file_name: str | None = None
        try:
            file_resource = self._upload_pdf(request, document_bytes)
            file_name = _require_string(file_resource, "name")
            file_uri = _require_string(file_resource, "uri")
            raw_response = self._generate_content(request, file_uri)
            return self._parse_response(request, raw_response)
        except OcrProviderError:
            raise
        except (KeyError, TypeError, ValueError) as exc:
            raise OcrProviderError("OCR_PROVIDER_RESPONSE_INVALID") from exc
        finally:
            if file_name:
                self._delete_file(file_name)

    def _upload_pdf(self, request: OcrFormConverterRequest, document_bytes: bytes) -> dict[str, Any]:
        start_request = urllib.request.Request(
            _gemini_upload_url("/upload/v1beta/files"),
            data=json.dumps({"file": {"displayName": f"dmc-form-{request.job_id}.pdf"}}).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": settings.ocr_gemini_api_key,
                "X-Goog-Upload-Command": "start",
                "X-Goog-Upload-Header-Content-Length": str(len(document_bytes)),
                "X-Goog-Upload-Header-Content-Type": "application/pdf",
                "X-Goog-Upload-Protocol": "resumable",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(start_request, timeout=90) as response:
                upload_url = response.headers.get("X-Goog-Upload-URL")
        except urllib.error.HTTPError as exc:
            raise OcrProviderError(_provider_http_error_code("OCR_GEMINI_UPLOAD_START", exc)) from exc
        except urllib.error.URLError as exc:
            raise OcrProviderError("OCR_GEMINI_UNREACHABLE") from exc
        except TimeoutError as exc:
            raise OcrProviderError("OCR_GEMINI_TIMEOUT") from exc

        if not upload_url:
            raise OcrProviderError("OCR_GEMINI_UPLOAD_FAILED")

        upload_request = urllib.request.Request(
            upload_url,
            data=document_bytes,
            headers={
                "Content-Length": str(len(document_bytes)),
                "Content-Type": "application/pdf",
                "X-Goog-Upload-Command": "upload, finalize",
                "X-Goog-Upload-Offset": "0",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(upload_request, timeout=90) as response:
                raw_response = _read_provider_response(response)
        except urllib.error.HTTPError as exc:
            raise OcrProviderError(_provider_http_error_code("OCR_GEMINI_UPLOAD_FINALIZE", exc)) from exc
        except urllib.error.URLError as exc:
            raise OcrProviderError("OCR_GEMINI_UNREACHABLE") from exc
        except TimeoutError as exc:
            raise OcrProviderError("OCR_GEMINI_TIMEOUT") from exc

        payload = json.loads(raw_response)
        file_resource = payload.get("file", payload)
        if not isinstance(file_resource, dict):
            raise OcrProviderError("OCR_GEMINI_UPLOAD_FAILED")
        return file_resource

    def _generate_content(self, request: OcrFormConverterRequest, file_uri: str) -> str:
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"text": _ocr_prompt(request)},
                        {"fileData": {"mimeType": "application/pdf", "fileUri": file_uri}},
                    ],
                }
            ],
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": 0,
            },
        }
        api_request = urllib.request.Request(
            _gemini_api_url(f"/v1beta/models/{urllib.parse.quote(settings.ocr_gemini_model, safe='')}:generateContent"),
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json", "x-goog-api-key": settings.ocr_gemini_api_key},
            method="POST",
        )
        try:
            with urllib.request.urlopen(api_request, timeout=90) as response:
                return _read_provider_response(response)
        except urllib.error.HTTPError as exc:
            raise OcrProviderError(_provider_http_error_code("OCR_GEMINI_GENERATE", exc)) from exc
        except urllib.error.URLError as exc:
            raise OcrProviderError("OCR_GEMINI_UNREACHABLE") from exc
        except TimeoutError as exc:
            raise OcrProviderError("OCR_GEMINI_TIMEOUT") from exc

    def _delete_file(self, file_name: str) -> None:
        api_request = urllib.request.Request(
            _gemini_api_url(f"/v1beta/{file_name.lstrip('/')}"),
            headers={"x-goog-api-key": settings.ocr_gemini_api_key},
            method="DELETE",
        )
        try:
            with urllib.request.urlopen(api_request, timeout=20):
                pass
        except (OSError, TimeoutError, urllib.error.URLError, urllib.error.HTTPError):
            return

    def _parse_response(
        self,
        request: OcrFormConverterRequest,
        raw_response: str,
    ) -> OcrFormConverterResponse:
        provider_payload = json.loads(raw_response)
        output_text = _extract_gemini_output_text(provider_payload)
        parsed = json.loads(_extract_json_object(output_text))
        records = [OcrRecordResponse.model_validate(record) for record in parsed["records"]]
        return OcrFormConverterResponse(
            job_id=request.job_id,
            module=request.module,
            template_type=request.template_type,
            provider=f"{self.name}:{settings.ocr_gemini_model}",
            records=records,
        )


def run_form_converter_ocr(request: OcrFormConverterRequest) -> OcrFormConverterResponse:
    document_bytes = _validate_document_hash(request)
    _validate_limits(request, document_bytes)
    try:
        return _provider().extract(request, document_bytes)
    except OcrProviderError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.code) from exc


def _provider() -> OcrProvider:
    if settings.ocr_provider == "mock":
        return MockOcrProvider()
    if settings.ocr_provider == "openai":
        return OpenAiOcrProvider()
    if settings.ocr_provider == "gemini":
        return GeminiOcrProvider()
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="OCR_PROVIDER_UNSUPPORTED",
    )


def _validate_document_hash(request: OcrFormConverterRequest) -> bytes:
    try:
        document_bytes = base64.b64decode(request.document_base64.encode("ascii"), validate=True)
    except (UnicodeEncodeError, Base64Error) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="document_base64 is invalid",
        ) from exc
    digest = hashlib.sha256(document_bytes).hexdigest()
    if digest != request.document_sha256:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="document_sha256 does not match document_base64",
        )
    return document_bytes


def _validate_limits(request: OcrFormConverterRequest, document_bytes: bytes) -> None:
    if len(document_bytes) > settings.ocr_max_pdf_bytes:
        raise HTTPException(
            status_code=413,
            detail="OCR_DOCUMENT_TOO_LARGE",
        )
    if request.page_count > settings.ocr_max_pages_per_job:
        raise HTTPException(
            status_code=413,
            detail="OCR_PAGE_LIMIT_EXCEEDED",
        )


def _ocr_prompt(request: OcrFormConverterRequest) -> str:
    fields = [{"field_name": field_name, "label_th": label_th} for field_name, label_th in FIELD_LABELS]
    schema_hint = {
        "records": [
            {
                "record_id": "page-1",
                "page_number": 1,
                "status": "ready|needs_review|invalid",
                "fields": [
                    {
                        "field_name": "student_id",
                        "label_th": "เลขประจำตัวนักเรียน",
                        "value": "",
                        "confidence": 0.0,
                        "status": "ready|needs_review|invalid",
                        "alternatives": [],
                    }
                ],
            }
        ]
    }
    return "\n".join(
        [
            "Read the scanned Thai DMC student history form PDF.",
            "Return JSON only. Do not include markdown or explanations.",
            f"Template type: {request.template_type}",
            f"Expected pages/records: {request.page_count}",
            "One PDF page equals one student record.",
            "Use empty string when a field cannot be read.",
            "Mark low confidence handwriting as needs_review.",
            f"Fields: {json.dumps(fields, ensure_ascii=False)}",
            f"Response shape: {json.dumps(schema_hint, ensure_ascii=False)}",
        ]
    )


def _extract_output_text(payload: dict[str, Any]) -> str:
    direct_output = payload.get("output_text")
    if isinstance(direct_output, str) and direct_output.strip():
        return direct_output
    output_items = payload.get("output")
    if not isinstance(output_items, list):
        raise ValueError("missing output text")
    parts: list[str] = []
    for output_item in output_items:
        if not isinstance(output_item, dict):
            continue
        content_items = output_item.get("content")
        if not isinstance(content_items, list):
            continue
        for content_item in content_items:
            if not isinstance(content_item, dict):
                continue
            text = content_item.get("text")
            if isinstance(text, str):
                parts.append(text)
    joined = "\n".join(parts).strip()
    if not joined:
        raise ValueError("empty output text")
    return joined


def _provider_http_error_code(prefix: str, exc: urllib.error.HTTPError) -> str:
    try:
        body = exc.read()
    except OSError:
        body = b""
    reason = _extract_provider_error_reason(body)
    if reason:
        return f"{prefix}_HTTP_{exc.code}_{reason}"
    return f"{prefix}_HTTP_{exc.code}"


def _extract_provider_error_reason(body: bytes) -> str | None:
    if not body:
        return None
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    error = payload.get("error")
    if not isinstance(error, dict):
        return None
    status_text = error.get("status")
    if isinstance(status_text, str) and _is_provider_reason_safe(status_text):
        return status_text
    details = error.get("details")
    if isinstance(details, list):
        for detail in details:
            if not isinstance(detail, dict):
                continue
            reason = detail.get("reason")
            if isinstance(reason, str) and _is_provider_reason_safe(reason):
                return reason
    return None


def _is_provider_reason_safe(value: str) -> bool:
    return bool(re.fullmatch(r"[A-Z][A-Z0-9_]{1,80}", value))


def _extract_gemini_output_text(payload: dict[str, Any]) -> str:
    candidates = payload.get("candidates")
    if not isinstance(candidates, list):
        raise ValueError("missing candidates")
    parts: list[str] = []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        content = candidate.get("content")
        if not isinstance(content, dict):
            continue
        content_parts = content.get("parts")
        if not isinstance(content_parts, list):
            continue
        for content_part in content_parts:
            if not isinstance(content_part, dict):
                continue
            text = content_part.get("text")
            if isinstance(text, str):
                parts.append(text)
    joined = "\n".join(parts).strip()
    if not joined:
        raise ValueError("empty output text")
    return joined


def _extract_json_object(text: str) -> str:
    stripped = text.strip()
    decoder = json.JSONDecoder()
    for start_index, char in enumerate(stripped):
        if char != "{":
            continue
        try:
            parsed, end_index = decoder.raw_decode(stripped[start_index:])
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return stripped[start_index : start_index + end_index]
    raise ValueError("missing JSON object")


def _read_provider_response(response: Any) -> str:
    try:
        raw_response = response.read(OCR_PROVIDER_MAX_RESPONSE_BYTES + 1)
    except TypeError:  # test doubles and non-standard response objects may not accept a size argument.
        raw_response = response.read()
    if len(raw_response) > OCR_PROVIDER_MAX_RESPONSE_BYTES:
        raise OcrProviderError("OCR_PROVIDER_RESPONSE_TOO_LARGE")
    return raw_response.decode("utf-8")


def _gemini_api_url(path: str) -> str:
    return f"{settings.ocr_gemini_base_url}{path}"


def _gemini_upload_url(path: str) -> str:
    return f"{settings.ocr_gemini_base_url}{path}"


def _require_string(payload: dict[str, Any], key: str) -> str:
    value = payload[key]
    if not isinstance(value, str) or not value:
        raise ValueError(f"{key} must be a non-empty string")
    return value


def _mock_fields_for_page(page_number: int) -> list[OcrFieldResponse]:
    values = {
        "student_id": f"MOCK{page_number:04d}",
        "first_name": f"ตัวอย่าง{page_number}",
        "last_name": "นักเรียน",
        "birth_date": "2553-01-01",
        "phone": "0800000000",
        "address": "กรุณาตรวจทานจากแบบฟอร์มจริง",
    }
    fields: list[OcrFieldResponse] = []
    for field_name, label_th in FIELD_LABELS:
        confidence = 0.88
        field_status: OcrFieldStatus = "needs_review"
        alternatives: list[str] = []
        if field_name == "student_id":
            confidence = 0.94
            alternatives = [values[field_name], f"ALT{page_number:04d}"]
        if field_name == "address":
            confidence = 0.58
            alternatives = ["อ่านลายมือไม่ครบ", values[field_name]]
        fields.append(
            OcrFieldResponse(
                field_name=field_name,
                label_th=label_th,
                value=values[field_name],
                confidence=confidence,
                status=field_status,
                alternatives=alternatives,
            )
        )
    return fields
