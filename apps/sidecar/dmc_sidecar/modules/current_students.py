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

DMC_PORTAL_HOME_URL = "https://portal.bopp-obec.info/obec69/"
DMC_TRANSFER_IN_LIST_URL = "https://portal.bopp-obec.info/obec69/studentin/"
DMC_THAID_AUTH_URL = "https://portal.bopp-obec.info/obec69/auth/OSBSAuth"
DMC_LOGIN_URL = "https://portal.bopp-obec.info/obec69/auth/login?login_error=1"
AUTH_ENTRY_URLS = (
    DMC_THAID_AUTH_URL,
    DMC_LOGIN_URL,
)


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
            if dry_run:
                return self._result(
                    record=record,
                    record_number=record_number,
                    applied=False,
                    note="dry_run",
                    status="success",
                    message="Form fields were filled without submitting.",
                    page_url=page.url,
                )

            submitted = self._submit_transfer_form(page)
            if submitted["note"] == "session_expired" and attempt == 0:
                self._pause_for_auth(
                    page=page,
                    context=context,
                    checkpoint=checkpoint,
                    current_record=record_number,
                    reason="session_expired_during_submit",
                )
                continue

            return self._result(
                record=record,
                record_number=record_number,
                applied=bool(submitted["applied"]),
                note=str(submitted["note"]),
                status="success" if bool(submitted["applied"]) else "review",
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

    def _fill_transfer_form(self, page: Page, record: DmcTransferInImportRecord) -> None:
        page.locator('input[name="studentNo"]').fill(record.student_no)
        page.locator('select[name="levelDtlCode"]').select_option(value=record.level_dtl_code)
        page.locator('input[name="classroom"]').fill(record.classroom)
        page.locator('input[name="cifNo"]').fill(record.citizen_id)
        page.evaluate(
            """
            (citizenId) => {
              const input = document.querySelector('input[name="cifNoChk"]');
              if (input) input.value = citizenId;
            }
            """,
            record.citizen_id,
        )

    def _submit_transfer_form(self, page: Page) -> dict[str, object]:
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
                "message": "DMC redirected to login while submitting.",
            }

        error_text = self._extract_error_text(page)
        if error_text:
            return {
                "applied": False,
                "note": "dmc_validation_error",
                "message": error_text,
            }

        return {
            "applied": True,
            "note": "submitted",
            "message": "DMC transfer-in form was submitted.",
        }

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
