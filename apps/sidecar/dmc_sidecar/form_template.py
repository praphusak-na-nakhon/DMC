from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from .errors import DomainError
from .schemas import FormConversionField, FormConversionRecord


SUPPORTED_FORM_TEMPLATE = "student_history_v1"
FieldStatus = Literal["ready", "needs_review", "invalid"]


@dataclass(frozen=True)
class FormFieldDefinition:
    field_name: str
    label_th: str
    export_header: str
    required: bool
    min_confidence: float
    pattern: re.Pattern[str] | None = None


FIELD_DEFINITIONS: tuple[FormFieldDefinition, ...] = (
    FormFieldDefinition("student_id", "เลขประจำตัวนักเรียน", "student_id", True, 0.8),
    FormFieldDefinition("first_name", "ชื่อ", "first_name", True, 0.75),
    FormFieldDefinition("last_name", "นามสกุล", "last_name", True, 0.75),
    FormFieldDefinition(
        "birth_date",
        "วันเกิด",
        "birth_date",
        False,
        0.8,
        re.compile(r"^(\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{2,4})$"),
    ),
    FormFieldDefinition("phone", "เบอร์โทรศัพท์", "phone", False, 0.75, re.compile(r"^[0-9+\-\s]{8,20}$")),
    FormFieldDefinition("address", "ที่อยู่", "address", False, 0.65),
)

FIELD_BY_NAME = {field.field_name: field for field in FIELD_DEFINITIONS}
EXPORT_HEADERS = ("record_id", "page_number", *(field.export_header for field in FIELD_DEFINITIONS))
REQUIRED_FIELD_NAMES = frozenset(field.field_name for field in FIELD_DEFINITIONS if field.required)


def ensure_supported_template(template_type: str) -> None:
    if template_type != SUPPORTED_FORM_TEMPLATE:
        raise DomainError("UNSUPPORTED_TEMPLATE", "This form template is not supported yet.")


def normalized_record(record: FormConversionRecord, *, reviewed: bool) -> FormConversionRecord:
    existing_fields = {field.field_name: field for field in record.fields}
    fields = [
        normalized_field(
            existing_fields.get(definition.field_name)
            or FormConversionField(
                field_name=definition.field_name,
                label_th=definition.label_th,
                value="",
                confidence=0,
                status="invalid" if definition.required else "needs_review",
            ),
            reviewed=reviewed,
        )
        for definition in FIELD_DEFINITIONS
    ]
    return record.model_copy(update={"fields": fields, "status": record_status(fields)})


def normalized_field(field: FormConversionField, *, reviewed: bool) -> FormConversionField:
    definition = FIELD_BY_NAME.get(field.field_name)
    value = field.value.strip()
    if definition is None:
        status: FieldStatus = "ready" if reviewed else field.status
        return field.model_copy(update={"value": value, "status": status})
    return field.model_copy(
        update={
            "label_th": definition.label_th,
            "value": value,
            "status": field_status(field, definition=definition, reviewed=reviewed),
        }
    )


def field_status(field: FormConversionField, *, definition: FormFieldDefinition, reviewed: bool) -> FieldStatus:
    value = field.value.strip()
    if definition.required and not value:
        return "invalid"
    if value and definition.pattern is not None and definition.pattern.fullmatch(value) is None:
        return "invalid"
    if reviewed:
        return "ready"
    if field.status == "invalid":
        return "invalid"
    if field.confidence < definition.min_confidence:
        return "needs_review"
    return field.status


def record_status(fields: list[FormConversionField]) -> FieldStatus:
    if any(field.status == "invalid" for field in fields):
        return "invalid"
    if any(field.status == "needs_review" for field in fields):
        return "needs_review"
    return "ready"
