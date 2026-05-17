from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Protocol

from playwright.sync_api import BrowserContext, Error as PlaywrightError, Page, TimeoutError, sync_playwright

from ..checkpoint import JobCheckpoint
from ..config import profile_dir_for_account, profiles_dir, reports_dir
from ..current_students import (
    DMC_TRANSFER_IN_URL,
    DmcTransferInImportRecord,
    ValidateCurrentStudentsImportFormRequest,
    load_dmc_transfer_in_import_records,
    validate_current_students_import_form,
)
from ..errors import DomainError
from ..runtime import JobContext, utc_now
from ..schemas import PreviewRow, ValidateExcelResponse, ValidationWarning
from .base import AutomationModule
from .dry_run_review import pause_for_dry_run_review, should_pause_for_dry_run_review

DMC_PORTAL_HOME_URL = "https://portal.bopp-obec.info/obec69/"
DMC_TRANSFER_IN_LIST_URL = "https://portal.bopp-obec.info/obec69/studentin/"
DMC_THAID_AUTH_URL = "https://portal.bopp-obec.info/obec69/auth/OSBSAuth"
DMC_LOGIN_URL = "https://portal.bopp-obec.info/obec69/auth/login?login_error=1"
AUTH_ENTRY_URLS = (
    DMC_THAID_AUTH_URL,
    DMC_LOGIN_URL,
)
DMC_HISTORY_FORM_URL_MARKER = "/studentin/add"
DMC_HISTORY_REVIEW_NOTE = "history_filled_for_review"
DMC_ADDRESS_CHAIN_FIELDS = {
    "psProvinceCode",
    "psAmphurCode",
    "psTumbolCode",
    "provinceCode",
    "amphurCode",
    "tumbolCode",
}


class ChromiumLauncher(Protocol):
    def launch_persistent_context(
        self,
        user_data_dir: str | Path,
        *,
        headless: bool | None = None,
        viewport: Any = None,
    ) -> BrowserContext: ...


class CurrentStudentsModule(AutomationModule):
    name = "currentStudents"

    def validate_excel(self, path: Path) -> ValidateExcelResponse:
        validation = validate_current_students_import_form(
            ValidateCurrentStudentsImportFormRequest(excel_path=str(path))
        )
        warnings = [
            ValidationWarning(
                code=warning.code,
                row_index=warning.row_index or 0,
                message_th=warning.message,
            )
            for warning in validation.warnings
        ]
        preview = [
            PreviewRow(
                order=row.row_index,
                level_label=str(row.operation_type or "transfer_in"),
                room=None,
                student_no=row.student_no or "",
                first_name=row.full_name or "",
                last_name="",
                status_text=row.status,
                status_code="ready" if row.status == "ready" else "review",
            )
            for row in validation.preview[:5]
        ]
        return ValidateExcelResponse(
            module="currentStudents",
            detected_level="DMC transfer-in",
            rows_total=validation.summary.rows_total,
            rows_accepted=validation.summary.ready_rows,
            warnings=warnings,
            preview=preview,
        )

    def start_job(
        self,
        job_id: str,
        excel_path: Path,
        options: dict[str, object],
        context: JobContext,
    ) -> None:
        records = load_dmc_transfer_in_import_records(excel_path)
        checkpoint = context.job_store.load_checkpoint(job_id)
        if checkpoint is None:
            checkpoint = JobCheckpoint.initial(
                level_label="DMC transfer-in",
                base_url=DMC_TRANSFER_IN_URL,
            )
        if not checkpoint.options:
            checkpoint.options = dict(options)

        self._hydrate_snapshot(context, checkpoint, total=len(records))
        context.job_store.mark_running(
            job_id,
            total_records=len(records),
            checkpoint=checkpoint,
            started_at=utc_now(),
        )

        report_dir = reports_dir() / job_id
        report_dir.mkdir(parents=True, exist_ok=True)
        report_json = report_dir / "dmc-transfer-in-report.json"
        report_csv = report_dir / "dmc-transfer-in-report.csv"
        review_csv = report_dir / "dmc-transfer-in-review.csv"

        account_session = context.account_store.get_session()
        profile_dir = profile_dir_for_account(account_session.user_id if account_session is not None else None)

        with sync_playwright() as playwright:
            browser_context = self._launch_browser_context(
                chromium=playwright.chromium,
                primary_profile_dir=profile_dir,
                job_id=job_id,
                options=options,
                context=context,
            )
            try:
                page = browser_context.pages[0] if browser_context.pages else browser_context.new_page()
                dry_run = bool(options.get("dry_run", False))
                start_at = min(max(checkpoint.processed, 0), len(records))
                for record_number, record in enumerate(records[start_at:], start=start_at + 1):
                    context.control.wait_point()
                    context.snapshot.current_page = record_number
                    checkpoint.next_page = record_number
                    context.job_store.save_checkpoint(job_id, checkpoint)

                    result = self._process_record(
                        page=page,
                        record=record,
                        dry_run=dry_run,
                        context=context,
                        checkpoint=checkpoint,
                        record_number=record_number,
                    )
                    self._handle_record_result(result, context)
                    context.job_store.append_results(job_id, [result])
                    checkpoint.results.append(result)
                    checkpoint.processed = context.snapshot.processed
                    checkpoint.succeeded = context.snapshot.succeeded
                    checkpoint.failed = context.snapshot.failed
                    checkpoint.next_page = context.snapshot.processed + 1
                    context.job_store.save_checkpoint(job_id, checkpoint)
                    if result.get("note") == DMC_HISTORY_REVIEW_NOTE:
                        self._pause_after_history_review(
                            page=page,
                            record=record,
                            context=context,
                            checkpoint=checkpoint,
                            record_number=record_number,
                        )

                if should_pause_for_dry_run_review(options):
                    pause_for_dry_run_review(
                        context=context,
                        checkpoint=checkpoint,
                        module_name=self.name,
                        page_url=page.url,
                        current_record=context.snapshot.processed,
                    )

                self._finish_job(
                    job_id=job_id,
                    checkpoint=checkpoint,
                    context=context,
                    report_json=report_json,
                    report_csv=report_csv,
                    review_csv=review_csv,
                )
            finally:
                browser_context.close()

    def _hydrate_snapshot(self, context: JobContext, checkpoint: JobCheckpoint, *, total: int) -> None:
        context.snapshot.total = total
        context.snapshot.processed = checkpoint.processed
        context.snapshot.succeeded = checkpoint.succeeded
        context.snapshot.failed = checkpoint.failed
        context.snapshot.current_page = checkpoint.next_page
        context.snapshot.needs_auth = checkpoint.awaiting_auth
        context.snapshot.auth_reason = checkpoint.auth_reason
        context.snapshot.level_label = checkpoint.level_label
        context.snapshot.status = "running"

    def _process_record(
        self,
        *,
        page: Page,
        record: DmcTransferInImportRecord,
        dry_run: bool,
        context: JobContext,
        checkpoint: JobCheckpoint,
        record_number: int,
    ) -> dict[str, Any]:
        for attempt in range(2):
            page = self._open_transfer_form(
                page=page,
                context=context,
                checkpoint=checkpoint,
                current_record=record_number,
                reason="login_required" if attempt == 0 else "session_expired",
            )
            self._fill_transfer_form(page, record)
            submitted = self._submit_transfer_form(page, record, dry_run=dry_run)
            if submitted["note"] == "session_expired" and attempt == 0:
                self._pause_for_auth(
                    page=page,
                    context=context,
                    checkpoint=checkpoint,
                    current_record=record_number,
                    reason="session_expired_during_submit",
                )
                continue

            if dry_run and submitted["note"] == DMC_HISTORY_REVIEW_NOTE:
                submitted = {
                    **submitted,
                    "note": "dry_run",
                    "status": "success",
                    "message": "Dry run opened the student history form and filled it without clicking the final save button.",
                }

            return self._result(
                record=record,
                record_number=record_number,
                applied=bool(submitted["applied"]),
                note=str(submitted["note"]),
                status=str(submitted.get("status") or ("success" if bool(submitted["applied"]) else "review")),
                message=str(submitted["message"]),
                page_url=page.url,
            )

        return self._result(
            record=record,
            record_number=record_number,
            applied=False,
            note="session_expired",
            status="review",
            message="DMC session expired while submitting this record.",
            page_url=page.url,
        )

    def _open_transfer_form(
        self,
        *,
        page: Page,
        context: JobContext,
        checkpoint: JobCheckpoint,
        current_record: int,
        reason: str,
    ) -> Page:
        auth_reason = reason
        resumed_from_auth = False
        while True:
            page = self._select_relevant_page(page)
            try:
                self._navigate_to_transfer_form(page=page, context=context)
            except PlaywrightError as exc:
                context.emit_event(
                    {
                        "type": "sidecar_stderr",
                        "message": f"currentStudents navigation retry: {exc.__class__.__name__}: {exc}",
                    }
                )
                self._pause_for_auth(
                    page=page,
                    context=context,
                    checkpoint=checkpoint,
                    current_record=current_record,
                    reason="login_required",
                )
                auth_reason = "login_required"
                continue
            if self._is_transfer_form(page):
                self._wait_for_transfer_form(page)
                return page
            pause_reason = auth_reason
            if resumed_from_auth and self._is_login_error_page(page):
                pause_reason = "dmc_login_rejected"
                context.emit_event(
                    {
                        "type": "sidecar_stderr",
                        "message": f"currentStudents DMC login was rejected or not authorized: {page.url}",
                    }
                )
            elif resumed_from_auth and self._is_logged_in_portal_page(page):
                pause_reason = "dmc_transfer_form_unavailable"
                context.emit_event(
                    {
                        "type": "sidecar_stderr",
                        "message": f"currentStudents DMC session is logged in but transfer form was not reachable: {page.url}",
                    }
                )
            self._pause_for_auth(
                page=page,
                context=context,
                checkpoint=checkpoint,
                current_record=current_record,
                reason=pause_reason,
                open_auth_entry=not resumed_from_auth,
            )
            resumed_from_auth = True
            auth_reason = "login_required"

    def _pause_for_auth(
        self,
        *,
        page: Page,
        context: JobContext,
        checkpoint: JobCheckpoint,
        current_record: int,
        reason: str,
        open_auth_entry: bool = True,
    ) -> None:
        if open_auth_entry:
            self._open_auth_entry_page(page=page, context=context)
        checkpoint.next_page = current_record
        checkpoint.awaiting_auth = True
        checkpoint.auth_reason = reason
        context.job_store.save_checkpoint(context.job_id, checkpoint)
        context.control.request_auth()
        context.snapshot.status = "paused"
        context.snapshot.needs_auth = True
        context.snapshot.auth_reason = reason
        context.emit_needs_auth(reason)
        context.job_store.set_status(context.job_id, "paused")
        context.control.wait_point()
        context.snapshot.status = "running"
        context.snapshot.needs_auth = False
        context.snapshot.auth_reason = None
        checkpoint.awaiting_auth = False
        checkpoint.auth_reason = None
        checkpoint.next_page = current_record
        context.job_store.save_checkpoint(context.job_id, checkpoint)
        context.job_store.set_status(context.job_id, "running")

    def _pause_after_history_review(
        self,
        *,
        page: Page,
        record: DmcTransferInImportRecord,
        context: JobContext,
        checkpoint: JobCheckpoint,
        record_number: int,
    ) -> None:
        stopped_item = {
            "reason": DMC_HISTORY_REVIEW_NOTE,
            "row_index": record.row_index,
            "record_id": record.record_id,
            "student_no": record.student_no,
            "citizen_id": record.citizen_id,
            "full_name": record.full_name,
            "page_url": page.url,
        }
        checkpoint.next_page = context.snapshot.processed + 1
        checkpoint.stopped_item = stopped_item
        context.snapshot.status = "paused"
        context.snapshot.stopped_item = stopped_item
        context.job_store.save_checkpoint(context.job_id, checkpoint)
        context.job_store.set_status(context.job_id, "paused")
        context.emit_event(
            {
                "type": "job_stopped",
                "job_id": context.job_id,
                "status": "paused",
                "stopped_item": stopped_item,
            }
        )
        context.emit_event(
            {
                "type": "sidecar_stderr",
                "message": (
                    "currentStudents paused after filling the DMC history form "
                    f"for record {record_number}. Final save was not clicked."
                ),
            }
        )
        context.control.pause()
        context.control.wait_point()
        checkpoint.stopped_item = None
        context.snapshot.status = "running"
        context.snapshot.stopped_item = None
        context.job_store.save_checkpoint(context.job_id, checkpoint)
        context.job_store.set_status(context.job_id, "running")

    def _open_auth_entry_page(self, *, page: Page, context: JobContext) -> None:
        if self._is_interactive_auth_page(page):
            return
        for url in AUTH_ENTRY_URLS:
            try:
                response = page.goto(url, wait_until="domcontentloaded", timeout=90000)
            except PlaywrightError as exc:
                context.emit_event(
                    {
                        "type": "sidecar_stderr",
                        "message": f"currentStudents auth entry navigation failed: {url}: {exc.__class__.__name__}: {exc}",
                    }
                )
                continue
            if response is None or response.status < 400:
                return
            context.emit_event(
                {
                    "type": "sidecar_stderr",
                    "message": f"currentStudents auth entry returned HTTP {response.status}: {url}",
                }
            )

    def _select_relevant_page(self, page: Page) -> Page:
        pages = list(page.context.pages)
        for candidate in reversed(pages):
            if self._is_transfer_form(candidate):
                return candidate
        for candidate in reversed(pages):
            if "portal.bopp-obec.info/obec69" in candidate.url or "imauth.bora.dopa.go.th" in candidate.url:
                return candidate
        return page

    def _navigate_to_transfer_form(self, *, page: Page, context: JobContext) -> None:
        before_url = page.url
        response = page.goto(DMC_TRANSFER_IN_URL, wait_until="domcontentloaded", timeout=90000)
        page.wait_for_timeout(700)
        self._emit_navigation_state(
            context=context,
            label="direct_add_cif",
            before_url=before_url,
            response_status=response.status if response is not None else None,
            page=page,
        )
        if self._is_transfer_form(page) or not self._is_logged_in_portal_page(page):
            return

        before_url = page.url
        response = page.goto(DMC_TRANSFER_IN_LIST_URL, wait_until="domcontentloaded", timeout=90000)
        page.wait_for_timeout(700)
        self._emit_navigation_state(
            context=context,
            label="studentin_list",
            before_url=before_url,
            response_status=response.status if response is not None else None,
            page=page,
        )
        if self._is_transfer_form(page):
            return

        add_link = page.locator('a[href$="/studentin/add_cif"], a[href*="/studentin/add_cif"]').first
        try:
            if add_link.count() > 0:
                before_url = page.url
                with page.expect_navigation(wait_until="domcontentloaded", timeout=30000):
                    add_link.click(timeout=10000)
                page.wait_for_timeout(700)
                self._emit_navigation_state(
                    context=context,
                    label="studentin_add_link",
                    before_url=before_url,
                    response_status=None,
                    page=page,
                )
        except PlaywrightError as exc:
            context.emit_event(
                {
                    "type": "sidecar_stderr",
                    "message": f"currentStudents could not open add_cif from studentin list: {exc.__class__.__name__}: {exc}",
                }
            )

    def _emit_navigation_state(
        self,
        *,
        context: JobContext,
        label: str,
        before_url: str,
        response_status: int | None,
        page: Page,
    ) -> None:
        student_no_count = -1
        cif_no_count = -1
        try:
            student_no_count = page.locator('input[name="studentNo"]').count()
            cif_no_count = page.locator('input[name="cifNo"]').count()
        except PlaywrightError:
            pass
        context.emit_event(
            {
                "type": "sidecar_stderr",
                "message": (
                    "currentStudents navigation "
                    f"{label}: before={before_url} status={response_status} "
                    f"after={page.url} studentNo={student_no_count} cifNo={cif_no_count}"
                ),
            }
        )

    def _is_interactive_auth_page(self, page: Page) -> bool:
        url = page.url
        if "imauth.bora.dopa.go.th" in url:
            return True
        if "/obec69/auth/OSBSAuth" in url:
            return True
        if "/obec69/auth/callback" in url or "/obec69/auth/landing" in url:
            return True
        return False

    def _is_transfer_form(self, page: Page) -> bool:
        if "/auth/" in page.url:
            return False
        try:
            return page.locator('input[name="studentNo"]').count() > 0 and page.locator(
                'input[name="cifNo"]'
            ).count() > 0
        except PlaywrightError:
            return False

    def _is_history_form(self, page: Page) -> bool:
        if "/auth/" in page.url:
            return False
        try:
            if page.locator('form[action$="/studentin/add"]').count() > 0:
                return True
            return page.locator('input[name="firstNameTh"]').count() > 0 and page.locator(
                'input[name="psHomeIdNo"]'
            ).count() > 0
        except PlaywrightError:
            return False

    def _is_login_error_page(self, page: Page) -> bool:
        if "login_error=1" in page.url:
            return True
        try:
            body_text = page.locator("body").inner_text(timeout=2000)
        except PlaywrightError:
            return False
        return "พบข้อผิดพลาดในการ login" in body_text or "ยังไม่ได้รับการอนุมัติ" in body_text

    def _is_logged_in_portal_page(self, page: Page) -> bool:
        if "portal.bopp-obec.info/obec69" not in page.url or "/auth/" in page.url:
            return False
        try:
            body_text = page.locator("body").inner_text(timeout=2000)
        except PlaywrightError:
            return False
        return "ออกจากระบบ" in body_text or "SCHOOL_MANAGER" in body_text

    def _wait_for_transfer_form(self, page: Page) -> None:
        page.locator('input[name="studentNo"]').wait_for(state="visible", timeout=30000)
        page.locator('select[name="levelDtlCode"]').wait_for(state="visible", timeout=30000)
        page.locator('input[name="classroom"]').wait_for(state="visible", timeout=30000)
        page.locator('input[name="cifNo"]').wait_for(state="visible", timeout=30000)

    def _wait_for_history_form(self, page: Page) -> None:
        page.locator('input[name="firstNameTh"]').wait_for(state="attached", timeout=30000)
        page.locator('input[name="psHomeIdNo"]').wait_for(state="attached", timeout=30000)
        page.locator('input[name="fatherFirstNameTh"]').wait_for(state="attached", timeout=30000)

    def _fill_transfer_form(self, page: Page, record: DmcTransferInImportRecord) -> None:
        values = {
            "studentNo": record.student_no,
            "levelDtlCode": record.level_dtl_code,
            "classroom": record.classroom,
            "cifNo": record.citizen_id,
            "cifNoChk": record.citizen_id,
            "cifType": record.dmc_form_values.get("cifType", "I"),
        }
        self._fill_admission_date(page, self._string_form_value(record.dmc_form_values.get("admissionDate")))
        self._fill_form_values(page, values)

    def _submit_transfer_form(
        self,
        page: Page,
        record: DmcTransferInImportRecord,
        *,
        dry_run: bool,
    ) -> dict[str, object]:
        if self._is_history_form(page):
            self._fill_student_history_form(page, record)
            if dry_run:
                return self._history_review_result()
            return self._submit_student_history_form(page)

        try:
            with page.expect_navigation(wait_until="domcontentloaded", timeout=15000):
                page.locator('input[name="submit"]').click(timeout=10000)
        except TimeoutError:
            try:
                page.wait_for_load_state("domcontentloaded", timeout=15000)
            except TimeoutError:
                pass
        page.wait_for_timeout(800)

        if "/auth/" in page.url:
            return {
                "applied": False,
                "note": "session_expired",
                "message": "DMC redirected to login while submitting the add_cif form.",
            }

        error_text = self._extract_error_text(page)
        if error_text:
            return {
                "applied": False,
                "note": "dmc_validation_error",
                "message": error_text,
            }

        if not self._is_history_form(page):
            return {
                "applied": False,
                "note": "dmc_history_form_not_opened",
                "message": "DMC accepted the add_cif form but did not open the full history form.",
            }

        self._fill_student_history_form(page, record)
        if not dry_run:
            return self._submit_student_history_form(page)
        return self._history_review_result()

    def _history_review_result(self) -> dict[str, object]:
        return {
            "applied": False,
            "note": DMC_HISTORY_REVIEW_NOTE,
            "status": "review",
            "message": "DMC history form was filled for review. Final save was not clicked.",
        }

    def _submit_student_history_form(self, page: Page) -> dict[str, object]:
        try:
            with page.expect_navigation(wait_until="domcontentloaded", timeout=15000):
                page.locator('input[name="submit"]').click(timeout=10000)
        except TimeoutError:
            try:
                page.wait_for_load_state("domcontentloaded", timeout=15000)
            except TimeoutError:
                pass
        page.wait_for_timeout(800)

        if "/auth/" in page.url:
            return {
                "applied": False,
                "note": "session_expired",
                "message": "DMC redirected to login while saving the student history form.",
            }

        error_text = self._extract_error_text(page)
        if error_text:
            return {
                "applied": False,
                "note": "dmc_validation_error",
                "message": error_text,
            }

        if self._is_history_form(page):
            return {
                "applied": False,
                "note": "dmc_history_form_still_open",
                "message": "DMC kept the student history form open after save; no validation message was detected.",
            }

        return {
            "applied": True,
            "note": "submitted",
            "status": "success",
            "message": "DMC transfer-in history form was saved.",
        }

    def _fill_student_history_form(self, page: Page, record: DmcTransferInImportRecord) -> None:
        self._wait_for_history_form(page)
        values = dict(record.dmc_form_values)
        values.setdefault("studentNo", record.student_no)
        values.setdefault("levelDtlCode", record.level_dtl_code)
        values.setdefault("classroom", record.classroom)
        values.setdefault("cifNo", record.citizen_id)
        values.setdefault("cifNoChk", record.citizen_id)
        values.setdefault("cifType", "I")

        self._fill_admission_date(page, self._string_form_value(values.get("admissionDate")))
        non_chained_values = {
            name: value
            for name, value in values.items()
            if name not in DMC_ADDRESS_CHAIN_FIELDS and name != "admissionDate"
        }
        self._fill_form_values(page, non_chained_values)
        self._fill_address_chain(
            page,
            values,
            province_name="psProvinceCode",
            district_name="psAmphurCode",
            subdistrict_name="psTumbolCode",
        )
        self._fill_address_chain(
            page,
            values,
            province_name="provinceCode",
            district_name="amphurCode",
            subdistrict_name="tumbolCode",
        )
        gender_code = self._string_form_value(values.get("genderCode"))
        if gender_code:
            self._fill_form_values(page, {"genderCode": gender_code})
        page.wait_for_timeout(300)

    def _fill_admission_date(self, page: Page, value: str | None) -> None:
        page.evaluate(
            """
            (explicitValue) => {
              const field = document.querySelector('[name="admissionDate"]');
              if (!field) return;
              const dispatch = (element) => {
                element.dispatchEvent(new Event('input', { bubbles: true }));
                element.dispatchEvent(new Event('change', { bubbles: true }));
              };
              const postDate = document.querySelector('[name="postDate"]')?.value || "";
              const nextValue = explicitValue || postDate;
              if (field.tagName === 'SELECT') {
                if (nextValue && Array.from(field.options).some((option) => option.value === nextValue)) {
                  field.value = nextValue;
                } else {
                  const option = Array.from(field.options).find((item) => item.value);
                  if (option) field.value = option.value;
                }
              } else if (nextValue) {
                field.value = nextValue;
              }
              dispatch(field);
            }
            """,
            value,
        )

    def _fill_address_chain(
        self,
        page: Page,
        values: dict[str, Any],
        *,
        province_name: str,
        district_name: str,
        subdistrict_name: str,
    ) -> None:
        province_code = self._string_form_value(values.get(province_name))
        district_code = self._string_form_value(values.get(district_name))
        subdistrict_code = self._string_form_value(values.get(subdistrict_name))
        if not province_code:
            return
        self._set_named_field_value(page, province_name, province_code, trigger_change=False)
        if district_code:
            self._populate_address_child_options(
                page,
                child_name=district_name,
                remote_method="getAmphurListByProvinceCode",
                parent_code=province_code,
            )
            if not self._wait_for_select_option(page, district_name, district_code):
                return
            self._set_named_field_value(page, district_name, district_code, trigger_change=False)
            if subdistrict_code:
                self._populate_address_child_options(
                    page,
                    child_name=subdistrict_name,
                    remote_method="getTumbolListByAmphurCode",
                    parent_code=district_code,
                )
        if subdistrict_code:
            if not self._wait_for_select_option(page, subdistrict_name, subdistrict_code):
                return
            self._set_named_field_value(page, subdistrict_name, subdistrict_code, trigger_change=False)
        if district_code:
            self._set_named_field_value(page, district_name, district_code, trigger_change=False)

    def _select_has_option(self, page: Page, name: str, value: str) -> bool:
        try:
            return bool(
                page.evaluate(
                    """
                    ([fieldName, fieldValue]) => {
                      const field = document.getElementsByName(fieldName)[0];
                      return !!field && !!field.options && Array.from(field.options).some((option) => option.value === fieldValue);
                    }
                    """,
                    [name, value],
                )
            )
        except PlaywrightError:
            return False

    def _populate_address_child_options(
        self,
        page: Page,
        *,
        child_name: str,
        remote_method: str,
        parent_code: str,
    ) -> bool:
        try:
            return bool(
                page.evaluate(
                    """
                    ([childName, remoteMethod, parentCode]) => new Promise((resolve) => {
                      const target = document.getElementsByName(childName)[0];
                      const remote = window.studentInfoRemote;
                      if (!target || !remote || typeof remote[remoteMethod] !== 'function') {
                        resolve(false);
                        return;
                      }
                      let settled = false;
                      const finish = (value) => {
                        if (settled) return;
                        settled = true;
                        clearTimeout(timer);
                        resolve(value);
                      };
                      const timer = setTimeout(() => finish(false), 10000);
                      try {
                        remote[remoteMethod](parentCode, (data) => {
                          try {
                            const placeholder = target.options[0];
                            const placeholderText = placeholder?.text || (childName.toLowerCase().includes('tumbol') ? '-- ตำบล --' : '-- อำเภอ --');
                            const options = [];
                            for (const item of Array.isArray(data) ? data : []) {
                              const value = item && (item.code ?? item.value ?? '');
                              if (!value) continue;
                              const label = item.nameTh ?? item.name ?? item.text ?? value;
                              options.push([String(value), String(label)]);
                            }
                            if (options.length === 0) {
                              finish(false);
                              return;
                            }
                            target.innerHTML = '';
                            target.add(new Option(placeholderText, ''));
                            for (const [value, label] of options) {
                              target.add(new Option(label, value));
                            }
                            target.dispatchEvent(new Event('input', { bubbles: true }));
                            finish(true);
                          } catch (_error) {
                            finish(false);
                          }
                        });
                      } catch (_error) {
                        finish(false);
                      }
                    })
                    """,
                    [child_name, remote_method, parent_code],
                )
            )
        except PlaywrightError:
            return False

    def _wait_for_select_option(self, page: Page, name: str, value: str) -> bool:
        try:
            page.wait_for_function(
                """
                ([fieldName, fieldValue]) => {
                  const field = document.getElementsByName(fieldName)[0];
                  return !!field && !!field.options && Array.from(field.options).some((option) => option.value === fieldValue);
                }
                """,
                arg=[name, value],
                timeout=15000,
            )
            return True
        except TimeoutError:
            return False

    def _set_named_field_value(self, page: Page, name: str, value: str, *, trigger_change: bool = True) -> None:
        page.evaluate(
            """
            ([fieldName, fieldValue, shouldTriggerChange]) => {
              const field = document.getElementsByName(fieldName)[0];
              if (!field) return;
              const dispatch = (element) => {
                element.dispatchEvent(new Event('input', { bubbles: true }));
                if (!shouldTriggerChange) return;
                if (window.jQuery) {
                  window.jQuery(element).trigger('change');
                } else {
                  element.dispatchEvent(new Event('change', { bubbles: true }));
                }
              };
              if (field.tagName === 'SELECT') {
                if (!Array.from(field.options).some((option) => option.value === fieldValue)) {
                  return;
                }
                field.value = fieldValue;
                Array.from(field.options).forEach((option) => {
                  option.selected = option.value === fieldValue;
                });
                const selectedIndex = Array.from(field.options).findIndex((option) => option.value === fieldValue);
                if (selectedIndex >= 0) field.selectedIndex = selectedIndex;
              } else {
                field.value = fieldValue;
              }
              dispatch(field);
            }
            """,
            [name, value, trigger_change],
        )

    def _fill_form_values(self, page: Page, values: dict[str, Any]) -> None:
        page.evaluate(
            """
            (values) => {
              const dispatch = (element) => {
                element.dispatchEvent(new Event('input', { bubbles: true }));
                element.dispatchEvent(new Event('change', { bubbles: true }));
              };
              const asString = (value) => value === null || value === undefined ? "" : String(value);
              const setSelectValue = (field, value) => {
                const rawValues = Array.isArray(value) ? value.map(asString) : [asString(value)];
                for (const rawValue of rawValues) {
                  if (!Array.from(field.options).some((option) => option.value === rawValue)) {
                    field.add(new Option(rawValue, rawValue));
                  }
                }
                if (field.multiple) {
                  const selected = new Set(rawValues);
                  Array.from(field.options).forEach((option) => {
                    option.selected = selected.has(option.value);
                  });
                } else {
                  field.value = rawValues[0] ?? "";
                }
                dispatch(field);
                try {
                  if (window.jQuery && window.jQuery.fn && typeof window.jQuery(field).multiselect === 'function') {
                    window.jQuery(field).multiselect('refresh');
                  }
                } catch (_error) {
                  // Best effort only. The native select value has already been set.
                }
              };
              for (const [name, value] of Object.entries(values)) {
                const fields = Array.from(document.getElementsByName(name));
                if (fields.length === 0) continue;
                const first = fields[0];
                const tag = first.tagName;
                const type = (first.getAttribute('type') || '').toLowerCase();
                if (type === 'radio') {
                  const expected = asString(value);
                  for (const field of fields) {
                    field.checked = field.value === expected;
                    dispatch(field);
                  }
                  continue;
                }
                if (type === 'checkbox') {
                  if (Array.isArray(value)) {
                    const selected = new Set(value.map(asString));
                    for (const field of fields) {
                      field.checked = selected.has(field.value);
                      dispatch(field);
                    }
                  } else {
                    first.checked = value === true || asString(value).toLowerCase() === 'true' || first.value === asString(value);
                    dispatch(first);
                  }
                  continue;
                }
                if (tag === 'SELECT') {
                  setSelectValue(first, value);
                  continue;
                }
                if ('value' in first) {
                  first.value = asString(value);
                  dispatch(first);
                }
              }
            }
            """,
            values,
        )

    def _string_form_value(self, value: Any) -> str | None:
        if value is None or isinstance(value, bool) or isinstance(value, list):
            return None
        return str(value)

    def _extract_error_text(self, page: Page) -> str:
        selectors = [
            ".alert-error",
            ".alert-danger",
            ".control-group.error",
            ".error",
        ]
        messages: list[str] = []
        for selector in selectors:
            locator = page.locator(selector)
            try:
                count = min(locator.count(), 5)
            except PlaywrightError:
                continue
            for index in range(count):
                try:
                    text = locator.nth(index).inner_text(timeout=1000).strip()
                except PlaywrightError:
                    continue
                if text and text not in messages:
                    messages.append(text)
        return " | ".join(messages)

    def _result(
        self,
        *,
        record: DmcTransferInImportRecord,
        record_number: int,
        applied: bool,
        note: str,
        status: str,
        message: str,
        page_url: str,
    ) -> dict[str, Any]:
        return {
            "page": record_number,
            "portal_row_index": record_number,
            "matched_order": record.row_index,
            "row_index": record.row_index,
            "record_id": record.record_id,
            "student_no": record.student_no,
            "citizen_id": record.citizen_id,
            "full_name": record.full_name,
            "level_dtl_code": record.level_dtl_code,
            "classroom": record.classroom,
            "note": note,
            "status": status,
            "message": message,
            "applied": applied,
            "page_url": page_url,
        }

    def _handle_record_result(self, result: dict[str, Any], context: JobContext) -> None:
        context.snapshot.processed += 1
        if result.get("status") == "success":
            context.snapshot.succeeded += 1
        else:
            context.snapshot.failed += 1
        context.emit_record_done(int(result["portal_row_index"]), str(result["status"]))
        context.emit_progress()

    def _finish_job(
        self,
        *,
        job_id: str,
        checkpoint: JobCheckpoint,
        context: JobContext,
        report_json: Path,
        report_csv: Path,
        review_csv: Path,
    ) -> None:
        persisted_results = context.job_store.list_results(job_id)
        json_path, csv_path, review_path = self._save_reports(
            persisted_results,
            report_json=report_json,
            report_csv=report_csv,
            review_csv=review_csv,
        )
        checkpoint.report_path = str(csv_path)
        checkpoint.review_report_path = str(review_path)
        context.snapshot.report_path = str(csv_path)
        context.snapshot.review_report_path = str(review_path)
        context.snapshot.status = "done"
        context.job_store.mark_done(
            job_id,
            checkpoint=checkpoint,
            finished_at=utc_now(),
        )
        status = context.job_store.get_status(job_id) or {}
        context.emit_event(
            {
                "type": "job_done",
                "job_id": job_id,
                "status": "done",
                "processed": context.snapshot.processed,
                "total": context.snapshot.total,
                "succeeded": context.snapshot.succeeded,
                "failed": context.snapshot.failed,
                "current_page": context.snapshot.current_page,
                "report_path": str(csv_path),
                "review_report_path": str(review_path),
                "run_summary": status.get("run_summary"),
                "summary_report_path": status.get("summary_report_path"),
                "completion_summary": status.get("completion_summary"),
                "json_report_path": str(json_path),
            }
        )

    def _save_reports(
        self,
        results: list[dict[str, Any]],
        *,
        report_json: Path,
        report_csv: Path,
        review_csv: Path,
    ) -> tuple[Path, Path, Path]:
        report_json.write_text(
            json.dumps(results, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        columns = [
            "row_index",
            "record_id",
            "student_no",
            "citizen_id",
            "full_name",
            "level_dtl_code",
            "classroom",
            "status",
            "note",
            "applied",
            "message",
            "page_url",
        ]
        self._write_csv(report_csv, results, columns)
        review_rows = [
            result
            for result in results
            if result.get("status") != "success" or result.get("note") == "dmc_validation_error"
        ]
        self._write_csv(review_csv, review_rows, columns)
        return report_json, report_csv, review_csv

    def _write_csv(self, path: Path, rows: list[dict[str, Any]], columns: list[str]) -> None:
        with path.open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)

    def _launch_browser_context(
        self,
        *,
        chromium: ChromiumLauncher,
        primary_profile_dir: Path,
        job_id: str,
        options: dict[str, object],
        context: JobContext,
    ) -> BrowserContext:
        headless = bool(options.get("headless", False))
        viewport = {"width": 1600, "height": 1000}
        try:
            return chromium.launch_persistent_context(
                str(primary_profile_dir.resolve()),
                headless=headless,
                viewport=viewport,
            )
        except PlaywrightError as exc:
            if not self._is_retryable_browser_launch_error(exc):
                raise

            fallback_profile_dir = self._fallback_profile_dir(job_id)
            fallback_profile_dir.mkdir(parents=True, exist_ok=True)
            context.emit_event(
                {
                    "type": "sidecar_stderr",
                    "message": f"Chromium profile is locked; retrying with fallback profile {fallback_profile_dir}",
                }
            )
            try:
                return chromium.launch_persistent_context(
                    str(fallback_profile_dir.resolve()),
                    headless=headless,
                    viewport=viewport,
                )
            except PlaywrightError as fallback_exc:
                raise DomainError(
                    "BROWSER_PROFILE_UNAVAILABLE",
                    "Chromium profile for automation is unavailable. Close other DMC browser windows and retry.",
                ) from fallback_exc

    def _fallback_profile_dir(self, job_id: str) -> Path:
        safe_job_id = "".join(ch for ch in job_id if ch.isalnum() or ch in {"-", "_"})[:64] or "job"
        return profiles_dir() / "fallback" / safe_job_id

    def _is_retryable_browser_launch_error(self, exc: Exception) -> bool:
        message = str(exc).lower()
        return (
            "launch_persistent_context" in message
            and (
                "target page, context or browser has been closed" in message
                or "process did exit" in message
                or "singleton" in message
            )
        )
