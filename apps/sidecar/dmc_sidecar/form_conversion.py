from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from openpyxl import Workbook  # type: ignore[import-untyped]

from .account_client import capture_credits, release_credits, request_form_converter_ocr, reserve_credits
from .account_store import AccountSessionStore
from .config import reports_dir
from .errors import DomainError
from .form_template import (
    EXPORT_HEADERS,
    FIELD_DEFINITIONS,
    FIELD_BY_NAME,
    SUPPORTED_FORM_TEMPLATE,
    ensure_supported_template,
    normalized_record,
    record_status,
)
from .schemas import (
    ExportFormExcelResponse,
    FormConversionField,
    FormConversionRecord,
    FormConversionStatusResponse,
    FormConversionSummary,
    FormPdfValidationWarning,
    StartFormConversionRequest,
    StartFormConversionResponse,
    ValidateFormPdfResponse,
)


PDF_PAGE_PATTERN = re.compile(rb"/Type\s*/Page\b")


@dataclass(frozen=True)
class PdfInspection:
    path: Path
    page_count: int
    warnings: list[FormPdfValidationWarning]


def validate_form_pdf(path: Path, *, template_type: str = SUPPORTED_FORM_TEMPLATE) -> ValidateFormPdfResponse:
    inspection = inspect_pdf(path)
    supported_template = template_type == SUPPORTED_FORM_TEMPLATE
    warnings = list(inspection.warnings)
    if not supported_template:
        warnings.append(
            FormPdfValidationWarning(
                code="UNSUPPORTED_TEMPLATE",
                message_th="รองรับแบบฟอร์มประวัตินักเรียนเวอร์ชันเดียวใน v1",
            )
        )
    return ValidateFormPdfResponse(
        module="formConverter",
        path=str(path),
        file_name=path.name,
        template_type=template_type,
        page_count=inspection.page_count,
        estimated_records=inspection.page_count,
        credit_estimate=inspection.page_count,
        supported_template=supported_template,
        requires_ai_consent=True,
        warnings=warnings,
    )


def inspect_pdf(path: Path) -> PdfInspection:
    if not path.exists():
        raise DomainError("PDF_FILE_NOT_FOUND", "PDF file was not found.")
    if not path.is_file():
        raise DomainError("PDF_PATH_NOT_FILE", "Selected path is not a file.")
    if path.suffix.lower() != ".pdf":
        raise DomainError("PDF_UNSUPPORTED_TYPE", "Only scanned PDF files are supported.")
    data = path.read_bytes()
    if not data.startswith(b"%PDF"):
        raise DomainError("PDF_INVALID", "Selected file is not a valid PDF.")
    page_count = len(PDF_PAGE_PATTERN.findall(data))
    warnings: list[FormPdfValidationWarning] = []
    if page_count <= 0:
        page_count = 1
        warnings.append(
            FormPdfValidationWarning(
                code="PDF_PAGE_COUNT_ESTIMATED",
                message_th="อ่านจำนวนหน้า PDF ไม่ได้ชัดเจน ระบบประเมินเป็น 1 หน้า",
            )
        )
    return PdfInspection(path=path, page_count=page_count, warnings=warnings)


class FormConversionService:
    def __init__(self, *, account_store: AccountSessionStore) -> None:
        self.account_store = account_store

    def start_conversion(self, request: StartFormConversionRequest) -> StartFormConversionResponse:
        ensure_supported_template(request.template_type)
        if not request.confirmed_ai_processing:
            raise DomainError(
                "AI_PROCESSING_CONSENT_REQUIRED",
                "User confirmation is required before sending the scanned form to cloud AI.",
            )
        pdf_path = Path(request.pdf_path)
        validation = validate_form_pdf(pdf_path, template_type=request.template_type)
        credits_reserved = max(validation.credit_estimate, 1)
        reservation = reserve_credits(
            self.account_store,
            job_id=request.job_id,
            module="formConverter",
            units=credits_reserved,
            idempotency_key=f"{request.job_id}:form-converter:reserve",
        )
        status = self._base_status(
            job_id=request.job_id,
            pdf_path=pdf_path,
            template_type=request.template_type,
            school_year=request.school_year,
            page_count=validation.page_count,
            credit_reservation_id=reservation.reservation_id,
            credits_reserved=credits_reserved,
        )
        status["status"] = "processing"
        self._save_status(status)
        try:
            ocr_result = request_form_converter_ocr(
                self.account_store,
                job_id=request.job_id,
                pdf_path=pdf_path,
                template_type=request.template_type,
                page_count=validation.page_count,
                credit_reservation_id=reservation.reservation_id,
            )
        except Exception:
            release_credits(
                self.account_store,
                reservation_id=reservation.reservation_id,
                units=credits_reserved,
                idempotency_key=f"{request.job_id}:form-converter:release-after-failed-ocr",
            )
            status["status"] = "failed"
            status["credit_status"] = "released"
            status["credits_refunded"] = credits_reserved
            status["last_error"] = "OCR_REQUEST_FAILED"
            self._save_status(status)
            raise

        normalized_records = [normalized_record(record, reviewed=False) for record in ocr_result.records]
        status["status"] = "needs_review"
        status["ocr_provider"] = ocr_result.provider
        status["processed"] = validation.page_count
        status["records"] = [record.model_dump() for record in normalized_records]
        status["summary"] = _summary(normalized_records).model_dump()
        self._save_status(status)
        return StartFormConversionResponse(
            accepted=True,
            job_id=request.job_id,
            credit_reservation_id=reservation.reservation_id,
            credits_reserved=credits_reserved,
        )

    def get_status(self, job_id: str) -> FormConversionStatusResponse:
        return FormConversionStatusResponse.model_validate(self._load_status(job_id))

    def save_review_edits(
        self,
        *,
        job_id: str,
        records: list[FormConversionRecord],
    ) -> FormConversionStatusResponse:
        status = self._load_status(job_id)
        previous = FormConversionStatusResponse.model_validate(status)
        reviewed_records = _reviewed_records(previous.records, records)
        status["status"] = "reviewed"
        status["processed"] = len(reviewed_records)
        status["records"] = [record.model_dump() for record in reviewed_records]
        status["summary"] = _summary(reviewed_records).model_dump()
        status["review_confirmed"] = True
        self._save_status(status)
        return FormConversionStatusResponse.model_validate(status)

    def export_excel(self, job_id: str) -> ExportFormExcelResponse:
        status = self._load_status(job_id)
        if status.get("review_confirmed") is not True:
            raise DomainError("FORM_REVIEW_REQUIRED", "Review and confirm OCR results before exporting Excel.")
        current = FormConversionStatusResponse.model_validate(status)
        if any(record.status == "invalid" for record in current.records):
            raise DomainError("FORM_REVIEW_HAS_INVALID_RECORDS", "Fix invalid records before exporting Excel.")

        output_dir = _job_dir(job_id)
        excel_path = output_dir / "student-history.xlsx"
        report_path = output_dir / "form-conversion-report.csv"
        review_report_path = output_dir / "form-conversion-review.csv"
        _write_excel(excel_path, current.records)
        _write_review_csv(report_path, current.records)
        _write_review_csv(review_report_path, current.records)

        exported_records = len(current.records)
        captured = 0
        refunded = 0
        if current.credit_reservation_id and current.credits_reserved > 0:
            capture_result = capture_credits(
                self.account_store,
                reservation_id=current.credit_reservation_id,
                units=exported_records,
                idempotency_key=f"{job_id}:form-converter:capture",
            )
            captured = capture_result.units_captured
            release_units = max(current.credits_reserved - exported_records, 0)
            if release_units:
                release_result = release_credits(
                    self.account_store,
                    reservation_id=current.credit_reservation_id,
                    units=release_units,
                    idempotency_key=f"{job_id}:form-converter:release",
                )
                refunded = release_result.units_released

        status["status"] = "done"
        status["excel_path"] = str(excel_path)
        status["report_path"] = str(report_path)
        status["review_report_path"] = str(review_report_path)
        status["credits_captured"] = captured
        status["credits_refunded"] = refunded
        status["credit_status"] = "finalized"
        status["summary"] = _summary(current.records, exported_records=exported_records).model_dump()
        self._save_status(status)
        return ExportFormExcelResponse(
            job_id=job_id,
            excel_path=str(excel_path),
            report_path=str(report_path),
            review_report_path=str(review_report_path),
            exported_records=exported_records,
            credit_reservation_id=current.credit_reservation_id,
            credits_captured=captured,
            credits_refunded=refunded,
        )

    def _base_status(
        self,
        *,
        job_id: str,
        pdf_path: Path,
        template_type: str,
        school_year: str | None,
        page_count: int,
        credit_reservation_id: str | None,
        credits_reserved: int,
    ) -> dict[str, Any]:
        return {
            "job_id": job_id,
            "module": "formConverter",
            "status": "pending",
            "pdf_path": str(pdf_path),
            "template_type": template_type,
            "ocr_provider": None,
            "school_year": school_year,
            "page_count": page_count,
            "processed": 0,
            "total": page_count,
            "records": [],
            "summary": FormConversionSummary(
                records_total=0,
                ready_records=0,
                needs_review_records=0,
                invalid_records=0,
                exported_records=0,
            ).model_dump(),
            "excel_path": None,
            "report_path": None,
            "review_report_path": None,
            "credit_reservation_id": credit_reservation_id,
            "credits_reserved": credits_reserved,
            "credits_captured": 0,
            "credits_refunded": 0,
            "credit_status": "reserved" if credit_reservation_id else None,
            "last_error": None,
            "review_confirmed": False,
        }

    def _load_status(self, job_id: str) -> dict[str, Any]:
        path = _status_path(job_id)
        if not path.exists():
            raise DomainError("FORM_CONVERSION_NOT_FOUND", "Form conversion job was not found.")
        return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))

    def _save_status(self, status: dict[str, Any]) -> None:
        path = _status_path(str(status["job_id"]))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")


def _job_dir(job_id: str) -> Path:
    path = reports_dir() / job_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def _status_path(job_id: str) -> Path:
    return _job_dir(job_id) / "form-conversion.json"


def _reviewed_records(
    previous_records: list[FormConversionRecord],
    submitted_records: list[FormConversionRecord],
) -> list[FormConversionRecord]:
    previous_values = {
        (record.record_id, field.field_name): field.value
        for record in previous_records
        for field in record.fields
    }
    reviewed: list[FormConversionRecord] = []
    for submitted in submitted_records:
        normalized = normalized_record(submitted, reviewed=True)
        fields: list[FormConversionField] = []
        for field in normalized.fields:
            edited = previous_values.get((submitted.record_id, field.field_name)) != field.value
            fields.append(field.model_copy(update={"edited": edited}))
        reviewed.append(normalized.model_copy(update={"fields": fields, "status": record_status(fields)}))
    return reviewed


def _summary(records: list[FormConversionRecord], *, exported_records: int = 0) -> FormConversionSummary:
    return FormConversionSummary(
        records_total=len(records),
        ready_records=sum(1 for record in records if record.status == "ready"),
        needs_review_records=sum(1 for record in records if record.status == "needs_review"),
        invalid_records=sum(1 for record in records if record.status == "invalid"),
        exported_records=exported_records,
    )


def _field_map(record: FormConversionRecord) -> dict[str, str]:
    return {field.field_name: field.value for field in record.fields}


def _write_excel(path: Path, records: list[FormConversionRecord]) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "student_history"
    sheet.append(list(EXPORT_HEADERS))
    for record in records:
        fields = _field_map(record)
        sheet.append(
            [
                record.record_id,
                record.page_number,
                *(fields.get(definition.field_name, "") for definition in FIELD_DEFINITIONS),
            ]
        )
    workbook.save(path)


def _write_review_csv(path: Path, records: list[FormConversionRecord]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "record_id",
                "page_number",
                "field_name",
                "label_th",
                "export_header",
                "value",
                "confidence",
                "status",
                "edited",
                "alternatives",
            ],
        )
        writer.writeheader()
        for record in records:
            for field in record.fields:
                definition = FIELD_BY_NAME.get(field.field_name)
                writer.writerow(
                    {
                        "record_id": record.record_id,
                        "page_number": record.page_number,
                        "field_name": field.field_name,
                        "label_th": field.label_th,
                        "export_header": definition.export_header if definition else field.field_name,
                        "value": field.value,
                        "confidence": f"{field.confidence:.2f}",
                        "status": field.status,
                        "edited": "yes" if field.edited else "no",
                        "alternatives": " | ".join(field.alternatives),
                    }
                )
