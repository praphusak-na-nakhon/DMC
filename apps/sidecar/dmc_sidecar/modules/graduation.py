from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Protocol, TypeVar, cast

import pandas as pd
from playwright.sync_api import BrowserContext, Error as PlaywrightError, Page, sync_playwright

from ..checkpoint import JobCheckpoint
from ..config import profile_dir_for_license, profiles_dir, reports_dir
from ..errors import DomainError
from ..module_config import load_effective_config, sync_module_config
from ..runtime import JobContext, utc_now
from ..schemas import PreviewRow, ValidateExcelResponse, ValidationWarning
from .base import AutomationModule
from . import graduation_legacy

T = TypeVar("T")


class GraduationLegacyModule(Protocol):
    LOGIN_URL: str
    TARGET_URL_TEMPLATE: str
    LEVEL_RULES: dict[str, graduation_legacy.LevelRule]
    STATUS_CODE_MAP: dict[str, str]

    def open_target_page_after_login(self, page: Page, target_url: str) -> None: ...

    def wait_for_student_table(self, page: Page) -> None: ...


class ChromiumLauncher(Protocol):
    def launch_persistent_context(
        self,
        user_data_dir: str | Path,
        *,
        headless: bool | None = None,
        viewport: Any = None,
    ) -> BrowserContext: ...


class GraduationModule(AutomationModule):
    name = "graduation"

    def validate_excel(self, path: Path) -> ValidateExcelResponse:
        legacy = graduation_legacy
        self._apply_module_config(legacy, load_effective_config(self.name).config)
        dataframe = pd.read_excel(path, dtype=str).fillna("")
        students, detected_level = legacy.load_source_data(path)

        warnings: list[ValidationWarning] = []
        for student in students:
            if not student.status_code:
                warnings.append(
                    ValidationWarning(
                        code="INPUT_STATUS_NOT_MAPPED",
                        row_index=student.order,
                        message_th="ไม่พบ mapping สำหรับสถานะนี้",
                    )
                )

        preview = [
            PreviewRow(
                order=student.order,
                level_label=student.level_label,
                room=student.room,
                student_no=student.student_no,
                first_name=student.first_name,
                last_name=student.last_name,
                status_text=student.status_text,
                status_code=student.status_code,
            )
            for student in students[:5]
        ]

        return ValidateExcelResponse(
            module="graduation",
            detected_level=detected_level,
            rows_total=len(dataframe.index),
            rows_accepted=len(students),
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
        legacy = graduation_legacy
        module_config_state = sync_module_config(self.name)
        self._apply_module_config(legacy, module_config_state.config)
        if module_config_state.last_error:
            context.emit_event(
                {
                    "type": "sidecar_stderr",
                    "message": f"module config fallback: {module_config_state.last_error}",
                }
            )
        students, level_label = legacy.load_source_data(excel_path)
        level_rules = legacy.LEVEL_RULES[level_label]
        base_url = legacy.build_target_url(str(level_rules["level_code"]))

        checkpoint = context.job_store.load_checkpoint(job_id)
        if checkpoint is None:
            checkpoint = JobCheckpoint.initial(level_label=level_label, base_url=base_url)

        checkpoint.level_label = level_label
        checkpoint.base_url = base_url
        if not checkpoint.options:
            checkpoint.options = dict(options)

        context.snapshot.total = len(students)
        context.snapshot.processed = checkpoint.processed
        context.snapshot.succeeded = checkpoint.succeeded
        context.snapshot.failed = checkpoint.failed
        context.snapshot.current_page = checkpoint.next_page
        context.snapshot.needs_auth = checkpoint.awaiting_auth
        context.snapshot.auth_reason = checkpoint.auth_reason
        context.snapshot.level_label = level_label
        context.snapshot.status = "running"
        context.job_store.mark_running(
            job_id,
            total_records=len(students),
            checkpoint=checkpoint,
            started_at=utc_now(),
        )

        license_record = context.license_store.get_license()
        profile_dir = profile_dir_for_license(
            license_record.license_key if license_record is not None else None
        )

        report_dir = reports_dir() / job_id
        report_dir.mkdir(parents=True, exist_ok=True)
        report_json = report_dir / "obec-fill-report.json"
        report_csv = report_dir / "obec-fill-report.csv"
        review_csv = report_dir / "obec-fill-review.csv"

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
                page.goto(legacy.LOGIN_URL, wait_until="domcontentloaded", timeout=90000)
                self._authenticate_and_open(
                    page=page,
                    legacy=legacy,
                    target_url=legacy.get_page_url(base_url, checkpoint.next_page),
                    context=context,
                    checkpoint=checkpoint,
                    current_page=checkpoint.next_page,
                    reason="login_required",
                )
                legacy.wait_for_student_table(page)

                current_page = checkpoint.next_page
                total_pages = legacy.get_total_pages(page)
                checkpoint.total_pages = total_pages

                while True:
                    context.control.wait_point()
                    context.snapshot.current_page = current_page
                    checkpoint.next_page = current_page
                    context.job_store.save_checkpoint(job_id, checkpoint)

                    self._ensure_authenticated_page(
                        page=page,
                        legacy=legacy,
                        target_url=legacy.get_page_url(base_url, current_page),
                        context=context,
                        checkpoint=checkpoint,
                        current_page=current_page,
                        reason="session_expired",
                    )

                    baseline_processed = checkpoint.processed
                    baseline_succeeded = checkpoint.succeeded
                    baseline_failed = checkpoint.failed

                    context.snapshot.processed = baseline_processed
                    context.snapshot.succeeded = baseline_succeeded
                    context.snapshot.failed = baseline_failed
                    page_results, stop_item = self._run_with_auth_recovery(
                        page=page,
                        legacy=legacy,
                        target_url=legacy.get_page_url(base_url, current_page),
                        context=context,
                        checkpoint=checkpoint,
                        current_page=current_page,
                        reason="session_expired_during_fill",
                        action=lambda: legacy.fill_current_page(
                            page=page,
                            students=students,
                            used_orders=set(checkpoint.used_orders),
                            min_score=self._int_option(options, "min_score", 72),
                            dry_run=bool(options.get("dry_run", False)),
                            stop_on_review=bool(options.get("stop_on_review", False)),
                            level_label=level_label,
                            before_row=context.control.wait_point,
                            after_row=lambda result: self._handle_row_result(result, context),
                        ),
                    )

                    if stop_item is not None:
                        checkpoint.stopped_item = stop_item
                        context.snapshot.status = "stopped_on_review"
                        context.snapshot.stopped_item = stop_item
                        context.job_store.save_checkpoint(job_id, checkpoint)
                        context.job_store.set_status(job_id, "stopped_on_review")
                        context.emit_event(
                            {
                                "type": "job_stopped",
                                "job_id": job_id,
                                "status": "stopped_on_review",
                                "stopped_item": stop_item,
                            }
                        )
                        return

                    if not bool(options.get("dry_run", False)):
                        self._run_with_auth_recovery(
                            page=page,
                            legacy=legacy,
                            target_url=legacy.get_page_url(base_url, current_page),
                            context=context,
                            checkpoint=checkpoint,
                            current_page=current_page,
                            reason="session_expired_during_save",
                            action=lambda: legacy.save_current_page(page),
                        )

                    checkpoint.results.extend(page_results)
                    checkpoint.used_orders = self._merge_used_orders(checkpoint.used_orders, page_results)
                    checkpoint.processed = context.snapshot.processed
                    checkpoint.succeeded = context.snapshot.succeeded
                    checkpoint.failed = context.snapshot.failed
                    checkpoint.next_page = current_page + 1
                    context.job_store.save_checkpoint(job_id, checkpoint)

                    if current_page >= total_pages:
                        json_path, csv_path, review_path = legacy.save_reports(
                            checkpoint.results,
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
                        context.emit_event(
                            {
                                "type": "job_done",
                                "job_id": job_id,
                                "status": "done",
                                "report_path": str(csv_path),
                                "review_report_path": str(review_path),
                            }
                        )
                        return

                    current_page += 1
                    self._run_with_auth_recovery(
                        page=page,
                        legacy=legacy,
                        target_url=legacy.get_page_url(base_url, current_page),
                        context=context,
                        checkpoint=checkpoint,
                        current_page=current_page,
                        reason="session_expired_during_navigation",
                        action=lambda: legacy.goto_page_number(page, current_page, base_url),
                    )
                    legacy.wait_for_student_table(page)
            finally:
                browser_context.close()

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
                    "message": (
                        "Chromium profile เดิมเปิดไม่ได้หรือถูก lock; "
                        f"retry ด้วย profile สำรอง {fallback_profile_dir}"
                    ),
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
                    (
                        "Chromium เปิด profile สำหรับ automation ไม่ได้ "
                        "ให้ปิดหน้าต่าง Chromium/DMC ที่ค้างอยู่ทั้งหมด แล้วลองเริ่มงานอีกครั้ง"
                    ),
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

    def _apply_module_config(self, legacy: GraduationLegacyModule, module_config: dict[str, Any]) -> None:
        login_url = module_config.get("login_url")
        target_url_template = module_config.get("target_url_template")
        level_rules = module_config.get("level_rules")
        status_code_map = module_config.get("status_code_map")

        if isinstance(login_url, str) and login_url.strip():
            legacy.LOGIN_URL = login_url.strip()
        if isinstance(target_url_template, str) and target_url_template.strip():
            legacy.TARGET_URL_TEMPLATE = target_url_template.strip()
        if isinstance(level_rules, dict):
            legacy.LEVEL_RULES = cast(dict[str, graduation_legacy.LevelRule], level_rules)
        if isinstance(status_code_map, dict):
            legacy.STATUS_CODE_MAP = {
                str(key): str(value)
                for key, value in status_code_map.items()
            }

    def _authenticate_and_open(
        self,
        *,
        page: Page,
        legacy: GraduationLegacyModule,
        target_url: str,
        context: JobContext,
        checkpoint: JobCheckpoint,
        current_page: int,
        reason: str,
    ) -> None:
        checkpoint.next_page = current_page
        checkpoint.awaiting_auth = True
        checkpoint.auth_reason = reason
        context.job_store.save_checkpoint(context.job_id, checkpoint)
        context.control.request_auth()
        context.snapshot.status = "paused"
        context.emit_needs_auth(reason)
        context.job_store.set_status(context.job_id, "paused")
        context.control.wait_point()
        context.snapshot.status = "running"
        context.snapshot.needs_auth = False
        context.snapshot.auth_reason = None
        checkpoint.awaiting_auth = False
        checkpoint.auth_reason = None
        checkpoint.next_page = current_page
        context.job_store.save_checkpoint(context.job_id, checkpoint)
        context.job_store.set_status(context.job_id, "running")
        legacy.open_target_page_after_login(page, target_url)
        page.wait_for_timeout(1200)

    def _ensure_authenticated_page(
        self,
        *,
        page: Page,
        legacy: GraduationLegacyModule,
        target_url: str,
        context: JobContext,
        checkpoint: JobCheckpoint,
        current_page: int,
        reason: str,
    ) -> None:
        if "/auth/" not in page.url:
            return
        self._authenticate_and_open(
            page=page,
            legacy=legacy,
            target_url=target_url,
            context=context,
            checkpoint=checkpoint,
            current_page=current_page,
            reason=reason,
        )
        legacy.wait_for_student_table(page)

    def _run_with_auth_recovery(
        self,
        *,
        page: Page,
        legacy: GraduationLegacyModule,
        target_url: str,
        context: JobContext,
        checkpoint: JobCheckpoint,
        current_page: int,
        reason: str,
        action: Callable[[], T],
    ) -> T:
        while True:
            try:
                result = action()
            except Exception:
                if "/auth/" in page.url:
                    self._authenticate_and_open(
                        page=page,
                        legacy=legacy,
                        target_url=target_url,
                        context=context,
                        checkpoint=checkpoint,
                        current_page=current_page,
                        reason=reason,
                    )
                    legacy.wait_for_student_table(page)
                    continue
                raise

            if "/auth/" in page.url:
                self._authenticate_and_open(
                    page=page,
                    legacy=legacy,
                    target_url=target_url,
                    context=context,
                    checkpoint=checkpoint,
                    current_page=current_page,
                    reason=reason,
                )
                legacy.wait_for_student_table(page)
                continue

            return result

    def _merge_used_orders(
        self,
        used_orders: list[int],
        page_results: list[dict[str, Any]],
    ) -> list[int]:
        merged = set(used_orders)
        merged.update(
            int(item["matched_order"])
            for item in page_results
            if item.get("matched_order") is not None and item.get("note") in {"filled", "dry_run"}
        )
        return sorted(merged)

    def _handle_row_result(self, result: dict[str, Any], context: JobContext) -> None:
        context.snapshot.processed += 1
        status = "success"
        note = str(result.get("note", ""))
        if note == "no_match":
            context.snapshot.failed += 1
            status = "not_found"
        elif note.startswith("low_confidence") or note in {
            "status_code_not_mapped",
            "option_value_not_found",
        }:
            context.snapshot.failed += 1
            status = "review"
        else:
            context.snapshot.succeeded += 1

        context.emit_record_done(int(result["portal_row_index"]), status)
        context.emit_progress()

    def _int_option(self, options: dict[str, object], key: str, default: int) -> int:
        value = options.get(key, default)
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.strip().isdigit():
            return int(value)
        return default
