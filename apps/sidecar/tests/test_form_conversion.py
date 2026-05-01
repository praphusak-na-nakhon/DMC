from __future__ import annotations

import time
from pathlib import Path

import pytest
from openpyxl import load_workbook  # type: ignore[import-untyped]

from dmc_sidecar import config as sidecar_config
from dmc_sidecar.account_store import AccountSessionStore
from dmc_sidecar.errors import DomainError
from dmc_sidecar.form_conversion import FormConversionService, validate_form_pdf
from dmc_sidecar.account_client import FormConverterOcrResult
from dmc_sidecar.schemas import (
    CreditReservationSnapshot,
    FormConversionField,
    FormConversionRecord,
    StartFormConversionRequest,
    WalletSnapshot,
)


def _write_pdf(path: Path, *, pages: int = 2) -> None:
    page_objects = "\n".join(f"{index} 0 obj << /Type /Page >> endobj" for index in range(1, pages + 1))
    path.write_bytes(f"%PDF-1.4\n{page_objects}\n%%EOF".encode("ascii"))


def _wallet(*, balance: int = 10, reserved: int = 0) -> WalletSnapshot:
    return WalletSnapshot(user_id="user-1", balance=balance, reserved=reserved, available=balance - reserved)


def _record(page: int) -> FormConversionRecord:
    return FormConversionRecord(
        record_id=f"page-{page}",
        page_number=page,
        status="needs_review",
        fields=[
            FormConversionField(
                field_name="student_id",
                label_th="เลขประจำตัวนักเรียน",
                value=f"MOCK{page:04d}",
                confidence=0.9,
                status="needs_review",
            ),
            FormConversionField(
                field_name="first_name",
                label_th="ชื่อ",
                value=f"ตัวอย่าง{page}",
                confidence=0.8,
                status="needs_review",
            ),
            FormConversionField(
                field_name="last_name",
                label_th="นามสกุล",
                value="นักเรียน",
                confidence=0.8,
                status="needs_review",
            ),
        ],
    )


def _signed_in_store() -> AccountSessionStore:
    store = AccountSessionStore()
    store.save_session(
        token="token-1",
        user_id="user-1",
        email="teacher@example.test",
        display_name="Teacher",
        status="active",
        token_expires_at="2030-01-01T00:00:00Z",
        checked_at="2026-04-29T00:00:00Z",
        wallet=_wallet(),
        module_catalog=[],
    )
    return store


def test_validate_form_pdf_counts_pages(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(sidecar_config, "default_data_dir", lambda: tmp_path)
    pdf_path = tmp_path / "student-history.pdf"
    _write_pdf(pdf_path, pages=3)

    result = validate_form_pdf(pdf_path)

    assert result.module == "formConverter"
    assert result.page_count == 3
    assert result.credit_estimate == 3
    assert result.requires_ai_consent is True


@pytest.mark.parametrize("pages", [100, 1000])
def test_validate_form_pdf_handles_large_synthetic_scans(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    pages: int,
) -> None:
    monkeypatch.setattr(sidecar_config, "default_data_dir", lambda: tmp_path)
    pdf_path = tmp_path / f"student-history-{pages}.pdf"
    _write_pdf(pdf_path, pages=pages)

    started_at = time.perf_counter()
    result = validate_form_pdf(pdf_path)
    elapsed = time.perf_counter() - started_at

    assert result.page_count == pages
    assert result.credit_estimate == pages
    assert elapsed < 2


def test_form_conversion_requires_review_before_excel_export(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(sidecar_config, "default_data_dir", lambda: tmp_path)
    pdf_path = tmp_path / "student-history.pdf"
    _write_pdf(pdf_path, pages=2)
    captured: list[int] = []
    released: list[int] = []

    monkeypatch.setattr(
        "dmc_sidecar.form_conversion.reserve_credits",
        lambda *_args, **_kwargs: CreditReservationSnapshot(
            reservation_id="reservation-1",
            job_id="form-job-1",
            module="formConverter",
            status="active",
            units_reserved=2,
            units_captured=0,
            units_released=0,
            wallet=_wallet(balance=10, reserved=2),
        ),
    )
    monkeypatch.setattr(
        "dmc_sidecar.form_conversion.request_form_converter_ocr",
        lambda *_args, **_kwargs: FormConverterOcrResult(provider="test-provider", records=[_record(1), _record(2)]),
    )

    def fake_capture(*_args, units: int, **_kwargs) -> CreditReservationSnapshot:
        captured.append(units)
        return CreditReservationSnapshot(
            reservation_id="reservation-1",
            job_id="form-job-1",
            module="formConverter",
            status="captured",
            units_reserved=2,
            units_captured=units,
            units_released=0,
            wallet=_wallet(balance=10 - units),
        )

    def fake_release(*_args, units: int, **_kwargs) -> CreditReservationSnapshot:
        released.append(units)
        return CreditReservationSnapshot(
            reservation_id="reservation-1",
            job_id="form-job-1",
            module="formConverter",
            status="captured",
            units_reserved=2,
            units_captured=sum(captured),
            units_released=units,
            wallet=_wallet(balance=8),
        )

    monkeypatch.setattr("dmc_sidecar.form_conversion.capture_credits", fake_capture)
    monkeypatch.setattr("dmc_sidecar.form_conversion.release_credits", fake_release)

    service = FormConversionService(account_store=_signed_in_store())
    started = service.start_conversion(
        request=StartFormConversionRequest(
            job_id="form-job-1",
            pdf_path=str(pdf_path),
            template_type="student_history_v1",
            school_year="2569",
            confirmed_ai_processing=True,
        )
    )
    assert started.credits_reserved == 2
    status = service.get_status("form-job-1")
    assert status.status == "needs_review"
    assert status.ocr_provider == "test-provider"
    assert status.summary.needs_review_records == 2

    with pytest.raises(DomainError, match="Review"):
        service.export_excel("form-job-1")

    reviewed = service.save_review_edits(job_id="form-job-1", records=status.records)
    assert reviewed.status == "reviewed"
    assert reviewed.summary.ready_records == 2

    exported = service.export_excel("form-job-1")
    assert Path(exported.excel_path).exists()
    assert Path(exported.report_path).exists()
    assert captured == [2]
    assert released == []

    done = service.get_status("form-job-1")
    assert done.status == "done"
    assert done.summary.exported_records == 2

    workbook = load_workbook(exported.excel_path)
    sheet = workbook.active
    assert [cell.value for cell in sheet[1]] == [
        "record_id",
        "page_number",
        "student_id",
        "first_name",
        "last_name",
        "birth_date",
        "phone",
        "address",
    ]


def test_form_conversion_template_validation_can_be_fixed_during_review(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(sidecar_config, "default_data_dir", lambda: tmp_path)
    pdf_path = tmp_path / "student-history.pdf"
    _write_pdf(pdf_path, pages=1)

    invalid_record = _record(1).model_copy(
        update={
            "fields": [
                *_record(1).fields,
                FormConversionField(
                    field_name="phone",
                    label_th="เบอร์โทรศัพท์",
                    value="not-a-phone",
                    confidence=0.91,
                    status="ready",
                ),
            ]
        }
    )

    monkeypatch.setattr(
        "dmc_sidecar.form_conversion.reserve_credits",
        lambda *_args, **_kwargs: CreditReservationSnapshot(
            reservation_id="reservation-2",
            job_id="form-job-2",
            module="formConverter",
            status="active",
            units_reserved=1,
            units_captured=0,
            units_released=0,
            wallet=_wallet(balance=10, reserved=1),
        ),
    )
    monkeypatch.setattr(
        "dmc_sidecar.form_conversion.request_form_converter_ocr",
        lambda *_args, **_kwargs: FormConverterOcrResult(provider="test-provider", records=[invalid_record]),
    )

    service = FormConversionService(account_store=_signed_in_store())
    service.start_conversion(
        request=StartFormConversionRequest(
            job_id="form-job-2",
            pdf_path=str(pdf_path),
            template_type="student_history_v1",
            school_year=None,
            confirmed_ai_processing=True,
        )
    )
    status = service.get_status("form-job-2")
    assert status.summary.invalid_records == 1

    fixed_records = []
    for record in status.records:
        fixed_fields = [
            field.model_copy(update={"value": "0800000000"}) if field.field_name == "phone" else field
            for field in record.fields
        ]
        fixed_records.append(record.model_copy(update={"fields": fixed_fields}))

    reviewed = service.save_review_edits(job_id="form-job-2", records=fixed_records)

    assert reviewed.status == "reviewed"
    assert reviewed.summary.ready_records == 1
    phone = next(field for field in reviewed.records[0].fields if field.field_name == "phone")
    assert phone.edited is True
