from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from urllib.parse import parse_qs, urlparse

import pandas as pd
import pytest
from playwright.sync_api import sync_playwright

from dmc_sidecar import config as sidecar_config
from dmc_sidecar.account_store import AccountSessionStore
from dmc_sidecar.job_store import JobStore
from dmc_sidecar.license_store import LicenseStore
from dmc_sidecar.modules import graduation as graduation_module
from dmc_sidecar.modules import graduation_legacy as legacy
from dmc_sidecar.runtime import JobContext, JobControl, JobSnapshot


M6 = "\u0e21.6"


def _require_playwright_chromium() -> None:
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            browser.close()
    except Exception as exc:
        pytest.skip(f"Playwright Chromium is not installed or launchable: {exc}")


class MockPortalState:
    def __init__(self) -> None:
        self.saved_pages: list[dict[str, list[str]]] = []
        self._lock = threading.Lock()

    def record_save(self, payload: dict[str, list[str]]) -> None:
        with self._lock:
            self.saved_pages.append(payload)

    def snapshot_saved_pages(self) -> list[dict[str, list[str]]]:
        with self._lock:
            return list(self.saved_pages)


def _portal_rows(page_number: int) -> list[dict[str, str]]:
    rows_by_page = {
        1: [
            {
                "row_id": "tr-1",
                "seq_no": "1",
                "room": "1",
                "student_no": "1001",
                "first_name": "\u0e2a\u0e21\u0e0a\u0e32\u0e22",
                "last_name": "\u0e43\u0e08\u0e14\u0e35",
            }
        ],
        2: [
            {
                "row_id": "tr-2",
                "seq_no": "2",
                "room": "1",
                "student_no": "1002",
                "first_name": "\u0e2a\u0e21\u0e2b\u0e0d\u0e34\u0e07",
                "last_name": "\u0e14\u0e35\u0e43\u0e08",
            }
        ],
    }
    return rows_by_page.get(page_number, [])


def _student_table_html(page_number: int) -> str:
    rows = []
    for index, item in enumerate(_portal_rows(page_number)):
        cells = [""] * 11
        cells[1] = item["seq_no"]
        cells[3] = item["room"]
        cells[4] = item["student_no"]
        cells[5] = "\u0e14.\u0e0a."
        cells[6] = item["first_name"]
        cells[7] = item["last_name"]
        cell_html = "".join(f"<td>{value}</td>" for value in cells)
        rows.append(
            f"""
            <tr id="{item['row_id']}">
              {cell_html}
              <td>
                <select name="students[{index}].studyTypeCode">
                  <option value="">--</option>
                  <option value="301">301</option>
                  <option value="317">317</option>
                </select>
              </td>
            </tr>
            """
        )
    pagination_items = []
    for page in (1, 2):
        class_name = " class=\"active\"" if page == page_number else ""
        pagination_items.append(
            f"<li{class_name}><a href=\"/obec68/studentpendingupl/add?page.page={page}\">{page}</a></li>"
        )
    return f"""
    <!doctype html>
    <html>
      <body>
        <form class="form-horizontal form-condensed" method="post" action="/save?page.page={page_number}">
          <table><tbody>{''.join(rows)}</tbody></table>
          <button name="action" value="confirm" type="submit">save</button>
        </form>
        <div class="pagination"><ul>{''.join(pagination_items)}</ul></div>
      </body>
    </html>
    """


def _make_handler(state: MockPortalState) -> type[BaseHTTPRequestHandler]:
    class MockPortalHandler(BaseHTTPRequestHandler):
        def log_message(self, _format: str, *_args: object) -> None:
            return

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/obec68/auth/login":
                self._send_html("<html><body>login ok</body></html>")
                return
            if parsed.path == "/obec68/studentpendingupl/add":
                page_number = int(parse_qs(parsed.query).get("page.page", ["1"])[0])
                self._send_html(_student_table_html(page_number))
                return
            self.send_error(404)

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path != "/save":
                self.send_error(404)
                return
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length).decode("utf-8")
            state.record_save(parse_qs(body))
            page_number = parse_qs(parsed.query).get("page.page", ["1"])[0]
            self.send_response(303)
            self.send_header("Location", f"/obec68/studentpendingupl/add?page.page={page_number}&saved=1")
            self.end_headers()

        def _send_html(self, body: str) -> None:
            encoded = body.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

    return MockPortalHandler


@pytest.fixture
def mock_portal() -> tuple[str, MockPortalState]:
    state = MockPortalState()
    server = ThreadingHTTPServer(("127.0.0.1", 0), _make_handler(state))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        yield f"http://{host}:{port}", state
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def _wait_until(assertion, *, timeout: float = 8.0) -> None:  # noqa: ANN001
    deadline = time.time() + timeout
    last_error: AssertionError | None = None
    while time.time() < deadline:
        try:
            result = assertion()
            if result is False:
                raise AssertionError("Condition not satisfied yet.")
            return
        except AssertionError as exc:
            last_error = exc
            time.sleep(0.05)
    if last_error is not None:
        raise last_error
    raise AssertionError("Timed out waiting for assertion.")


def test_graduation_job_runs_against_mock_obec_portal(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    mock_portal: tuple[str, MockPortalState],
) -> None:
    _require_playwright_chromium()
    base_url, portal_state = mock_portal
    job_id = "job-playwright-graduation"
    events: list[dict[str, Any]] = []
    status_text = next(key for key, value in legacy.STATUS_CODE_MAP.items() if value == "317")
    source_rows = pd.DataFrame(
        [
            [1, M6, 1, "1001", "\u0e2a\u0e21\u0e0a\u0e32\u0e22", "\u0e43\u0e08\u0e14\u0e35", status_text],
            [2, M6, 1, "1002", "\u0e2a\u0e21\u0e2b\u0e0d\u0e34\u0e07", "\u0e14\u0e35\u0e43\u0e08", status_text],
        ]
    )

    monkeypatch.setattr(sidecar_config, "default_data_dir", lambda: tmp_path)
    monkeypatch.setattr(legacy, "LOGIN_URL", legacy.LOGIN_URL)
    monkeypatch.setattr(legacy, "TARGET_URL_TEMPLATE", legacy.TARGET_URL_TEMPLATE)
    monkeypatch.setattr(legacy, "LEVEL_RULES", legacy.LEVEL_RULES.copy())
    monkeypatch.setattr(legacy, "STATUS_CODE_MAP", legacy.STATUS_CODE_MAP.copy())
    monkeypatch.setattr(legacy.pd, "read_excel", lambda *args, **kwargs: source_rows)
    monkeypatch.setattr(
        graduation_module,
        "sync_module_config",
        lambda module: SimpleNamespace(
            config={
                "login_url": f"{base_url}/obec68/auth/login",
                "target_url_template": f"{base_url}/obec68/studentpendingupl/add?levelDtlCode={{level_code}}&action=search",
                "level_rules": legacy.LEVEL_RULES,
                "status_code_map": legacy.STATUS_CODE_MAP,
            },
            last_error=None,
        ),
    )

    job_store = JobStore()
    job_store.create_pending_job(job_id, "graduation", str(tmp_path / "source.xlsx"))
    context = JobContext(
        job_id=job_id,
        options={"dry_run": False, "stop_on_review": False, "min_score": 72, "headless": True},
        emit_event=events.append,
        control=JobControl(),
        job_store=job_store,
        license_store=LicenseStore(),
        account_store=AccountSessionStore(),
        snapshot=JobSnapshot(job_id=job_id, module="graduation", status="pending"),
    )

    thread = threading.Thread(
        target=lambda: graduation_module.GraduationModule().start_job(
            job_id=job_id,
            excel_path=tmp_path / "source.xlsx",
            options=context.options,
            context=context,
        ),
        daemon=True,
    )
    thread.start()

    _wait_until(lambda: any(event.get("type") == "needs_auth" for event in events))
    context.control.resume()
    thread.join(timeout=15)
    assert not thread.is_alive()

    status = job_store.get_status(job_id)
    assert status is not None
    assert status["status"] == "done"
    assert status["processed"] == 2
    assert status["succeeded"] == 2
    assert status["failed"] == 0
    assert status["run_summary"] == {
        "dmc_rows_total": 2,
        "matched_from_excel": 2,
        "default_207": 0,
        "excel_missing": 0,
        "review_rows": 0,
        "applied_rows": 2,
        "dry_run_rows": 0,
    }
    assert any(event.get("type") == "job_done" for event in events)
    assert [event.get("type") for event in events].count("record_done") == 2

    saved_pages = portal_state.snapshot_saved_pages()
    assert len(saved_pages) == 2
    assert all(payload["action"] == ["confirm"] for payload in saved_pages)
    assert all("317" in next(value for key, value in payload.items() if key.endswith(".studyTypeCode")) for payload in saved_pages)

    report_path = Path(status["report_path"])
    review_report_path = Path(status["review_report_path"])
    assert report_path.exists()
    assert review_report_path.exists()
    report_rows = json.loads(report_path.with_suffix(".json").read_text(encoding="utf-8"))
    assert [row["note"] for row in report_rows] == ["filled", "filled"]
