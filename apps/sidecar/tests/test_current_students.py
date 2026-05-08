from __future__ import annotations

import json
from pathlib import Path

import pytest
from openpyxl import Workbook, load_workbook  # type: ignore[import-untyped]

from dmc_sidecar.current_students import (
    ExportDmcFormJsonRequest,
    ExportCurrentStudentsBlankFormRequest,
    ExportCurrentStudentsImportExcelRequest,
    PreviewDmcFormJsonRequest,
    ReconcileCurrentStudentsRequest,
    ValidateCurrentStudentsImportFormRequest,
    export_dmc_form_json,
    export_current_students_blank_form,
    export_current_students_import_excel,
    preview_dmc_form_json,
    reconcile_current_students,
    validate_current_students_import_form,
)
from dmc_sidecar.rpc import RpcServer


def _write_roster(path: Path) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "1.1"
    sheet["A1"] = "รายชื่อนักเรียนชั้นมัธยมศึกษาปีที่ 1/1 ปีการศึกษา 2569"
    sheet["A2"] = "โรงเรียนเหนือคลองประชาบำรุง"
    sheet.append(["เลขที่", "เลขประจำตัว", None, "ชื่อ - สกุล"])
    sheet.append([1, 19984, "เด็กหญิง", "กัญญาณัฐ  กุลดี"])
    sheet.append([2, 19985, "เด็กชาย", "ภูริณัฐ  หาเหม"])
    sheet.append([3, 19986, "เด็กหญิง", "กนกวรรณ  นวลปั้น"])
    sheet.append([4, 19987, "เด็กชาย", "อนุวัฒน์  เดชอุดม"])
    workbook.save(path)


def _thai_id_row(
    *,
    citizen_id: str,
    prefix: str,
    first_name: str,
    last_name: str,
    row_no: int,
) -> list[str]:
    row = [""] * 45
    row[0] = "2026-03-19"
    row[1] = "08:39:05"
    row[2] = f"{row_no:06d}"
    row[3] = "ลงบันทึก"
    row[6] = f'="{citizen_id}"' if citizen_id.isdigit() else citizen_id
    row[7] = prefix
    row[8] = first_name
    row[10] = last_name
    row[15] = "28"
    row[16] = "4"
    row[20] = "คลองขนาน"
    row[21] = "เหนือคลอง"
    row[22] = "กระบี่"
    row[23] = "ชาย" if prefix == "ด.ช." else "หญิง"
    row[24] = "13 กุมภาพันธ์ 2557"
    return row


def _write_thai_id_csv(path: Path) -> None:
    header = [f"col-{index}" for index in range(45)]
    rows = [
        _thai_id_row(citizen_id="1819900905157", prefix="ด.ญ.", first_name="กัญญาณัฐ", last_name="กุลดี", row_no=1),
        _thai_id_row(citizen_id="1819900915055", prefix="ด.ช.", first_name="ภุริณัฐ", last_name="หาเหม", row_no=2),
        _thai_id_row(citizen_id='="18199..968591"', prefix="ด.ญ.", first_name="กนกวรรณ", last_name="นวลปั้น", row_no=3),
        _thai_id_row(citizen_id="1810800164408", prefix="ด.ช.", first_name="อนุวัฒน์", last_name="เดชอุดม", row_no=4),
        _thai_id_row(citizen_id="1810800164408", prefix="ด.ช.", first_name="อนุวัฒน์", last_name="เดชอุดม", row_no=5),
        _thai_id_row(citizen_id="1819900943555", prefix="ด.ช.", first_name="ปารมี", last_name="เชาว์ช่าง", row_no=6),
    ]
    lines = [",".join(header), *(",".join(row) for row in rows)]
    path.write_bytes(("\n".join(lines) + "\n").encode("cp874"))


def _write_ocr_markdown(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "หน้า 1",
                "เลขประจำตัวประชาชน* 1 8199 00905 15 7 เลขประจำตัวนักเรียน 19984 คำนำหน้านาม* ด.ญ. เพศ* หญิง ชื่อ* กัญญาณัฐ นามสกุล* กุลดี ชื่อ (อังกฤษ)* Kanyanat นามสกุล (อังกฤษ)* Kuldee วัน/เดือน/ปีเกิด* 13 กุมภาพันธ์ 2557 จังหวัดที่เกิด* กระบี่ สถานพยาบาลที่เกิด* ร.พ. เหนือคลอง กลุ่มเลือด* O เชื้อชาติ* ไทย สัญชาติ* ไทย ศาสนา* พุทธ",
                "๒. ที่อยู่อาศัย",
                "ตามทะเบียนบ้าน รหัสประจำบ้าน* 8101-004408-9 บ้านเลขที่* 28 หมู่ที่ (ถ้าไม่มีใส่ -) 4 ถนน (ถ้าไม่มีใส่ -) - จังหวัด* กระบี่ อำเภอ* เหนือคลอง ตำบล* คลองขนาน รหัสไปรษณีย์* 81130 หมายเลขโทรศัพท์บ้าน - มือถือ* -",
                "ที่อยู่ปัจจุบัน รหัสประจำบ้าน* 8101-004408-9 บ้านเลขที่* 28 หมู่ที่ (ถ้าไม่มีใส่ -) 4 ถนน (ถ้าไม่มีใส่ -) - จังหวัด* กระบี่ อำเภอ* เหนือคลอง ตำบล* คลองขนาน รหัสไปรษณีย์* 81130 หมายเลขโทรศัพท์บ้าน - มือถือ* -",
                "๓. รายละเอียดนักเรียน",
                "การเดินทางมาโรงเรียน* [ ] เดินเท้า [x] พาหนะไม่เสียค่าโดยสาร [ ] พาหนะเสียค่าโดยสาร ระยะทางจากบ้านมา ร.ร.* ทางน้ำ (กม.) - ถนนลูกรัง (กม.) - ถนนลาดยาง (กม.) 15 กม. รวมระยะเวลาการเดินทางมาโรงเรียน (นาที)* 20 นาที",
                "๔. สุขภาพ",
                "น้ำหนัก* 40 กิโลกรัม ส่วนสูง* 150 เซนติเมตร",
                "๕. ครอบครัว",
                "สถานภาพสมรสของบิดามารดา สถานภาพสมรส [ ] สมรส [x] แยกกันอยู่ ข้อมูลพี่น้อง จำนวนพี่ชาย* - คน จำนวนน้องชาย* - คน จำนวนพี่สาว* 1 คน จำนวนน้องสาว* - คน",
                "ข้อมูลบิดา เลขบัตรประจำตัวประชาชนบิดา* 3410100748561 ชนิดบัตร* [x] บัตรประชาชน [ ] อื่นๆ ชื่อบิดา* นาย ชวลิต นามสกุล* ตุ้มดำ กลุ่มเลือดบิดา* - อาชีพ* รับจ้างทั่วไป รายได้ต่อเดือน(บาท)* 5000 - 6000 บาท หมายเลขโทรศัพท์บิดา* 063-839-5699",
                "ข้อมูลมารดา เลขบัตรประจำตัวประชาชนมารดา* - ชนิดบัตร* [ ] บัตรประชาชน [ ] อื่นๆ ชื่อมารดา* - นามสกุล* - กลุ่มเลือดมารดา* - อาชีพ* - รายได้ต่อเดือน(บาท)* - หมายเลขโทรศัพท์มารดา* -",
                "ข้อมูลผู้ปกครอง เลขบัตรประจำตัวประชาชนผู้ปกครอง* 3410100748561 ชนิดบัตร* [x] บัตรประชาชน [ ] อื่นๆ ชื่อผู้ปกครอง* นาย ชวลิต นามสกุล* ตุ้มดำ กลุ่มเลือดผู้ปกครอง* - อาชีพ* รับจ้างทั่วไป รายได้ต่อเดือน(บาท)* 5000 - 6000 บาท หมายเลขโทรศัพท์ผู้ปกครอง* 063-839-5699 ความเกี่ยวข้องของผู้ปกครองกับนักเรียน* บิดาและบุตร",
                "**หมายเหตุ",
            ]
        ),
        encoding="utf-8",
    )


def _write_civil_registration_markdown(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "สำเนาทะเบียนบ้าน",
                "เลขรหัสประจำบ้าน 8101-008408-9",
                "รายการที่อยู่ 28 หมู่ที่ 4 ตำบลคลองขนาน อำเภอเหนือคลอง จังหวัดกระบี่ ชื่อหมู่บ้าน -",
                "รายการบุคคลในบ้าน ชื่อ ด.ญ. กัญญาณัฐ กุลดี สัญชาติ ไทย เพศ หญิง",
                "เลขประจำตัวประชาชน 1-8199-00905-15-7 สถานภาพ ผู้อาศัย",
                "เกิดเมื่อ 13 ก.พ. 2557",
                "มารดาผู้ให้กำเนิด ชื่อ กรานณิภา ตุ้มดำ เลขประจำตัวประชาชน 1-7603-00002-25-6 สัญชาติ ไทย",
                "บิดาผู้ให้กำเนิด ชื่อ ชวลิต ตุ้มดำ เลขประจำตัวประชาชน 3-4101-00748-56-1 สัญชาติ ไทย",
            ]
        ),
        encoding="utf-8",
    )


def test_reconcile_current_students_builds_canonical_records_and_review_queue(tmp_path: Path) -> None:
    roster_path = tmp_path / "studentListM1-M4 2569.xlsx"
    thai_id_path = tmp_path / "ThaiID M1-2569.CSV"
    ocr_path = tmp_path / "1-3ex.md"
    _write_roster(roster_path)
    _write_thai_id_csv(thai_id_path)
    _write_ocr_markdown(ocr_path)

    result = reconcile_current_students(
        ReconcileCurrentStudentsRequest(
            roster_excel_path=str(roster_path),
            thai_id_csv_path=str(thai_id_path),
            ocr_markdown_paths=[str(ocr_path)],
            school_year=2569,
            grade_levels=[1],
        )
    )

    assert result.module == "currentStudents"
    assert result.summary.roster_records == 4
    assert result.summary.thai_id_scan_records == 6
    assert result.summary.ocr_form_records == 1
    assert result.summary.records_total == 6
    assert result.summary.auto_matched == 1
    assert result.summary.needs_review == 2
    assert result.summary.invalid_id_records == 1
    assert result.summary.duplicate_records == 1
    assert result.summary.duplicate_scan_records == 2
    assert result.summary.new_or_transfer_candidates == 1
    assert result.summary.ocr_attached_records == 1
    assert result.summary.review_queue_records == 5

    by_student_no = {record.student_no: record for record in result.records if record.student_no}
    matched = by_student_no["19984"]
    assert matched.match_status == "auto_matched"
    assert matched.citizen_id == "1819900905157"
    assert matched.dmc_fields["citizen_id"].source == "thai_id_scan"
    assert matched.dmc_fields["weight_kg"].source == "ocr_form"
    assert matched.dmc_fields["guardian.phone"].value == "063-839-5699"
    assert any(conflict.field_name == "prefix" for conflict in matched.conflicts)

    assert by_student_no["19985"].match_status == "needs_review"
    assert "missing_thai_id_scan" in by_student_no["19985"].review_reasons
    assert by_student_no["19986"].match_status == "invalid_id"
    assert by_student_no["19987"].match_status == "duplicate"

    fuzzy_record = next(record for record in result.records if record.citizen_id == "1819900915055")
    assert fuzzy_record.match_status == "needs_review"
    assert fuzzy_record.suggestions[0].student_no == "19985"
    assert fuzzy_record.suggestions[0].score >= 0.9

    new_candidate = next(record for record in result.records if record.citizen_id == "1819900943555")
    assert new_candidate.match_status == "new_or_transfer_candidate"
    assert "not_found_in_roster" in new_candidate.review_reasons


def test_validate_current_student_sources_rpc(tmp_path: Path) -> None:
    roster_path = tmp_path / "studentListM1-M4 2569.xlsx"
    thai_id_path = tmp_path / "ThaiID M1-2569.CSV"
    _write_roster(roster_path)
    _write_thai_id_csv(thai_id_path)
    server = RpcServer(emit_notification=lambda _payload: None)

    response = json.loads(
        server.handle_text(
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": "req-current-students",
                    "method": "validate_current_student_sources",
                    "params": {
                        "roster_excel_path": str(roster_path),
                        "thai_id_csv_path": str(thai_id_path),
                        "school_year": 2569,
                        "grade_levels": [1],
                    },
                }
            )
        )
    )

    assert response["result"]["module"] == "currentStudents"
    assert response["result"]["summary"]["roster_records"] == 4
    assert response["result"]["summary"]["thai_id_scan_records"] == 6
    assert response["result"]["summary"]["review_queue_records"] == 5


def test_export_blank_form_and_validate_completed_import_form(tmp_path: Path) -> None:
    output_path = tmp_path / "current-students-import-template.xlsx"

    blank_form = export_current_students_blank_form(
        ExportCurrentStudentsBlankFormRequest(output_path=str(output_path))
    )

    assert blank_form.module == "currentStudents"
    assert output_path.exists()
    assert "citizen_id" in blank_form.required_fields

    workbook = load_workbook(output_path)
    sheet = workbook.active
    field_columns = {str(cell.value): index for index, cell in enumerate(sheet[2], start=1) if cell.value}
    sheet.cell(row=3, column=field_columns["operation_type"], value="current")
    sheet.cell(row=3, column=field_columns["school_year"], value=2569)
    sheet.cell(row=3, column=field_columns["student_no"], value="19984")
    sheet.cell(row=3, column=field_columns["citizen_id"], value="1819900905157")
    sheet.cell(row=3, column=field_columns["prefix"], value="Miss")
    sheet.cell(row=3, column=field_columns["first_name"], value="Kanyanat")
    sheet.cell(row=3, column=field_columns["last_name"], value="Kuldee")
    workbook.save(output_path)

    validation = validate_current_students_import_form(
        ValidateCurrentStudentsImportFormRequest(excel_path=str(output_path))
    )

    assert validation.module == "currentStudents"
    assert validation.summary.rows_total == 1
    assert validation.summary.ready_rows == 1
    assert validation.summary.invalid_rows == 0
    assert validation.preview[0].student_no == "19984"


def test_export_current_student_import_excel_writes_workbook(tmp_path: Path) -> None:
    roster_path = tmp_path / "studentListM1-M4 2569.xlsx"
    thai_id_path = tmp_path / "ThaiID M1-2569.CSV"
    ocr_path = tmp_path / "1-3ex.md"
    output_path = tmp_path / "current-students-import-2569.xlsx"
    _write_roster(roster_path)
    _write_thai_id_csv(thai_id_path)
    _write_ocr_markdown(ocr_path)

    result = export_current_students_import_excel(
        ExportCurrentStudentsImportExcelRequest(
            roster_excel_path=str(roster_path),
            thai_id_csv_path=str(thai_id_path),
            ocr_markdown_paths=[str(ocr_path)],
            school_year=2569,
            grade_levels=[1],
            output_path=str(output_path),
        )
    )

    assert result.module == "formConverter"
    assert result.output_path == str(output_path)
    assert result.rows_exported == 1
    assert result.summary.records_total == 1
    conflict_fields = {conflict.field_name for conflict in result.conflicts}
    assert "prefix" not in conflict_fields
    assert {"mother.first_name", "mother.last_name"}.issubset(conflict_fields)
    assert all(conflict.reason == "missing_after_all_sources" for conflict in result.conflicts)
    workbook = load_workbook(output_path, read_only=True, data_only=True)
    sheet = workbook.active
    field_columns = {str(cell.value): index for index, cell in enumerate(sheet[2], start=1) if cell.value}
    data_rows = [row for row in sheet.iter_rows(min_row=3, values_only=True) if any(row)]
    assert len(data_rows) == 1
    citizen_values = [
        row[field_columns["citizen_id"] - 1]
        for row in data_rows
        if row[field_columns["citizen_id"] - 1]
    ]
    assert "1819900905157" in citizen_values


def test_export_dmc_form_json_writes_operation_neutral_json(tmp_path: Path) -> None:
    roster_path = tmp_path / "studentListM1-M4 2569.xlsx"
    thai_id_path = tmp_path / "ThaiID M1-2569.CSV"
    ocr_path = tmp_path / "1-3ex.md"
    output_path = tmp_path / "dmc-form-data-2569.json"
    _write_roster(roster_path)
    _write_thai_id_csv(thai_id_path)
    _write_ocr_markdown(ocr_path)

    result = export_dmc_form_json(
        ExportDmcFormJsonRequest(
            roster_excel_path=str(roster_path),
            thai_id_csv_path=str(thai_id_path),
            ocr_markdown_paths=[str(ocr_path)],
            school_year=2569,
            grade_levels=[1],
            output_path=str(output_path),
        )
    )

    assert result.module == "formConverter"
    assert result.output_path == str(output_path)
    assert result.records_exported == 1
    assert result.records[0].fields["citizen_id"] == "1819900905157"
    assert result.records[0].field_details["citizen_id"].source == "thai_id_scan"
    assert "operation_type" not in result.records[0].fields

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "dmc_form_json.v1"
    assert payload["records_exported"] == 1
    assert "operation_type" not in payload
    assert "operation_type" not in payload["records"][0]
    assert "operation_type" not in payload["records"][0]["fields"]


def test_preview_dmc_form_json_reports_missing_required_data_read_only(tmp_path: Path) -> None:
    roster_path = tmp_path / "studentListM1-M4 2569.xlsx"
    thai_id_path = tmp_path / "ThaiID M1-2569.CSV"
    ocr_path = tmp_path / "1-3ex.md"
    output_path = tmp_path / "dmc-form-data-2569.json"
    _write_roster(roster_path)
    _write_thai_id_csv(thai_id_path)
    _write_ocr_markdown(ocr_path)

    preview = preview_dmc_form_json(
        PreviewDmcFormJsonRequest(
            roster_excel_path=str(roster_path),
            thai_id_csv_path=str(thai_id_path),
            ocr_markdown_paths=[str(ocr_path)],
            school_year=2569,
            grade_levels=[1],
        )
    )

    assert preview.records_previewed == 1
    assert preview.records[0].fields["citizen_id"] == "1819900905157"
    assert {"mother.first_name", "mother.last_name"}.issubset(
        {conflict.field_name for conflict in preview.conflicts}
    )
    assert "operation_type" not in preview.records[0].fields

    result = export_dmc_form_json(
        ExportDmcFormJsonRequest(
            roster_excel_path=str(roster_path),
            thai_id_csv_path=str(thai_id_path),
            ocr_markdown_paths=[str(ocr_path)],
            school_year=2569,
            grade_levels=[1],
            output_path=str(output_path),
        )
    )

    assert {"mother.first_name", "mother.last_name"}.issubset(
        {conflict.field_name for conflict in result.conflicts}
    )
    assert result.records[0].fields["mother.first_name"] is None
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["records"][0]["fields"]["mother.last_name"] is None


def test_dmc_form_json_uses_civil_registration_ocr_as_supplement(tmp_path: Path) -> None:
    roster_path = tmp_path / "studentListM1-M4 2569.xlsx"
    thai_id_path = tmp_path / "ThaiID M1-2569.CSV"
    ocr_path = tmp_path / "1-3ex.md"
    civil_path = tmp_path / "CivilDoc.md"
    output_path = tmp_path / "dmc-form-data-2569.json"
    _write_roster(roster_path)
    _write_thai_id_csv(thai_id_path)
    _write_ocr_markdown(ocr_path)
    _write_civil_registration_markdown(civil_path)

    preview = preview_dmc_form_json(
        PreviewDmcFormJsonRequest(
            roster_excel_path=str(roster_path),
            thai_id_csv_path=str(thai_id_path),
            ocr_markdown_paths=[str(ocr_path)],
            civil_registration_markdown_paths=[str(civil_path)],
            school_year=2569,
            grade_levels=[1],
        )
    )

    record = preview.records[0]
    conflict_fields = {conflict.field_name for conflict in preview.conflicts}
    assert preview.summary.civil_registration_records == 1
    assert record.fields["registered_address.house_id"] == "8101-008408-9"
    assert record.fields["father.citizen_id"] == "3410100748561"
    assert record.fields["father.first_name"] == "ชวลิต"
    assert record.fields["mother.citizen_id"] == "1760300002256"
    assert record.fields["mother.first_name"] == "กรานณิภา"
    assert record.fields["mother.last_name"] == "ตุ้มดำ"
    assert record.field_details["registered_address.house_id"].source == "civil_registration"
    assert record.field_details["mother.first_name"].source == "civil_registration"
    assert "mother.first_name" not in conflict_fields
    assert "mother.last_name" not in conflict_fields

    result = export_dmc_form_json(
        ExportDmcFormJsonRequest(
            roster_excel_path=str(roster_path),
            thai_id_csv_path=str(thai_id_path),
            ocr_markdown_paths=[str(ocr_path)],
            civil_registration_markdown_paths=[str(civil_path)],
            school_year=2569,
            grade_levels=[1],
            output_path=str(output_path),
        )
    )

    assert result.records[0].fields["registered_address.house_id"] == "8101-008408-9"
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["records"][0]["field_details"]["mother.first_name"]["source"] == "civil_registration"


UPLOAD_TEST_DIR = Path(__file__).parents[3] / "uploadTest"


@pytest.mark.skipif(
    not all(
        path.exists()
        for path in (
            UPLOAD_TEST_DIR / "ThaiID M1-2569.CSV",
            UPLOAD_TEST_DIR / "studentListM1-M4 2569.xlsx",
            UPLOAD_TEST_DIR / "1-3ex.md",
        )
    ),
    reason="uploadTest sample files are local fixtures",
)
def test_reconcile_current_students_with_upload_test_samples() -> None:
    result = reconcile_current_students(
        ReconcileCurrentStudentsRequest(
            roster_excel_path=str(UPLOAD_TEST_DIR / "studentListM1-M4 2569.xlsx"),
            thai_id_csv_path=str(UPLOAD_TEST_DIR / "ThaiID M1-2569.CSV"),
            ocr_markdown_paths=[str(UPLOAD_TEST_DIR / "1-3ex.md")],
            school_year=2569,
            grade_levels=[1],
        )
    )

    assert result.summary.roster_records == 328
    assert result.summary.thai_id_scan_records == 263
    assert result.summary.auto_matched >= 245
    assert result.summary.review_queue_records > 0
    assert result.summary.invalid_id_records >= 1
    assert result.summary.duplicate_scan_records >= 2
