"""Disposable source-sidecar smoke. Requires Chromium; never auto-installs it.

Portal traffic is localhost-only. Browser status may probe Playwright's CDN.
Builds and typechecks belong to ci:verify, not this smoke.
"""
from __future__ import annotations

import json
import os
import queue
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
from collections import deque
from contextlib import closing, contextmanager
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import urlparse

from openpyxl import Workbook
from dmc_sidecar.module_config import GraduationConfig
from smoke_portal import synthetic_portal

ROOT = Path(__file__).resolve().parents[1]
JOB_ID = "smoke-synthetic-graduation"


class SmokeFailure(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SmokeFailure(message)


@contextmanager
def smoke_environment(base_url: str) -> Iterator[tuple[Path, dict[str, str], Path]]:
    parsed = urlparse(base_url)
    require(parsed.scheme == "http" and parsed.hostname == "127.0.0.1" and bool(parsed.port)
            and not any((parsed.username, parsed.password, parsed.path, parsed.query, parsed.fragment)),
            "Smoke requires an explicit loopback portal origin")
    # Validate real shipped bytes before changing only URLs in a temporary copy.
    payload = GraduationConfig.model_validate_json(
        (ROOT / "packages/module-configs/graduation/v1.json").read_bytes()
    ).model_dump()
    with tempfile.TemporaryDirectory(prefix="dmc-local-smoke-") as directory:
        root = Path(directory).resolve()
        resources = root / "resources"
        config_path = resources / "module-configs/graduation/v1.json"
        config_path.parent.mkdir(parents=True)
        payload["login_url"] = f"{base_url}/obec68/auth/login"
        payload["target_url_template"] = f"{base_url}/obec68/studentpendingupl/add?levelDtlCode={{level_code}}&action=search"
        config_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        excel = root / "synthetic.xlsx"
        workbook = Workbook()
        sheet = workbook.active
        assert sheet is not None
        sheet.append(["order", "level", "room", "student_no", "first_name", "last_name", "status"])
        for order, first, last in [(1, "สมชาย", "ใจดี"), (2, "สมหญิง", "ดีใจ")]:
            sheet.append([order, "ม.6", 1, str(1000 + order), first, last, "(ม.6) ไม่ศึกษาต่อ รับจ้างทั่วไป"])
        workbook.save(excel)
        workbook.close()
        env = os.environ.copy()
        env.update({"DMC_DATA_DIR": str(root / "data"), "DMC_BUNDLED_RESOURCES_DIR": str(resources),
                    "DMC_REPO_ROOT": str(ROOT), "PYTHONPATH": str(ROOT / "apps/sidecar"), "PYTHONIOENCODING": "utf-8"})
        if env.get("PLAYWRIGHT_BROWSERS_PATH"):
            env["PLAYWRIGHT_BROWSERS_PATH"] = str(Path(env["PLAYWRIGHT_BROWSERS_PATH"]).resolve())
        yield root, env, excel


class SidecarProcess:
    """One stdout reader, bounded requests, and ownership-scoped cleanup."""

    def __init__(self, command: list[str], *, env: dict[str, str], cwd: Path) -> None:
        self.events: list[dict[str, Any]] = []
        self.stderr_lines: deque[str] = deque(maxlen=30)
        self.lines: queue.Queue[str | None] = queue.Queue()
        self.process = subprocess.Popen(
            command, cwd=cwd, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        self.readers = [threading.Thread(target=self._read_stdout, daemon=True),
                        threading.Thread(target=self._read_stderr, daemon=True)]
        for reader in self.readers:
            reader.start()

    def __enter__(self) -> SidecarProcess:
        return self

    def __exit__(self, *_args: Any) -> None:
        self.close()

    def _read_stdout(self) -> None:
        assert self.process.stdout is not None
        try:
            for line in self.process.stdout:
                self.lines.put(line)
        finally:
            self.lines.put(None)

    def _read_stderr(self) -> None:
        assert self.process.stderr is not None
        for line in self.process.stderr:
            self.stderr_lines.append(line.rstrip())

    def close(self) -> None:
        assert self.process.stdin is not None
        self.process.stdin.close()
        try:
            self.process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            # This owned PID's tree only, never a global image-name sweep.
            if os.name == "nt" and self.process.poll() is None:
                subprocess.run(["taskkill", "/PID", str(self.process.pid), "/T", "/F"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               timeout=10, check=False, creationflags=subprocess.CREATE_NO_WINDOW)
            elif self.process.poll() is None:
                self.process.kill()
            self.process.wait(timeout=10)
        for reader in self.readers:
            reader.join(timeout=3)
        for stream in (self.process.stdout, self.process.stderr):
            assert stream is not None
            stream.close()

    def rpc(self, method: str, params: dict[str, Any] | None = None, *, timeout: float = 45) -> Any:
        request_id = f"smoke-{time.monotonic_ns()}"
        request = {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {}}
        assert self.process.stdin is not None
        self.process.stdin.write(json.dumps(request) + "\n")
        self.process.stdin.flush()
        deadline = time.monotonic() + timeout
        while True:
            try:
                line = self.lines.get(timeout=max(0, deadline - time.monotonic()))
            except queue.Empty as exc:
                raise SmokeFailure(self._diagnostic(f"timed out waiting for {method}")) from exc
            if line is None:
                raise SmokeFailure(self._diagnostic(f"stdout closed waiting for {method}"))
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                raise SmokeFailure(self._diagnostic(f"non-JSON stdout: {line[:200]}")) from exc
            require(isinstance(payload, dict), "Invalid JSON-RPC message")
            if payload.get("method") == "event" and "id" not in payload:
                self.events.append(payload["params"])
            elif payload.get("id") == request_id:
                if "error" in payload:
                    raise SmokeFailure(self._diagnostic(f"{method}: {payload['error']}"))
                return payload.get("result")
            if time.monotonic() >= deadline:
                raise SmokeFailure(self._diagnostic(f"timed out waiting for {method}"))

    def _diagnostic(self, message: str) -> str:
        return f"{message}\nprocess_status={self.process.poll()}\n" + "\n".join(self.stderr_lines)


def run_smoke() -> dict[str, Any]:
    with synthetic_portal() as (base_url, portal), smoke_environment(base_url) as (root, env, excel):
        with SidecarProcess([sys.executable, "-u", "-m", "dmc_sidecar"], env=env, cwd=root) as sidecar:
            require(sidecar.rpc("ping").get("value") == "pong", "Ping did not return pong")
            database = sidecar.rpc("get_database_status")
            require(database["schema_generation"] == 2, f"Wrong database generation: {database}")
            require(set(database["tables"]) == {"job", "job_record", "schema_metadata"}, "Unexpected local tables")
            db_path = Path(database["path"]).resolve()
            require(db_path == root / "data/desktop.sqlite3", "Database escaped temporary data directory")
            require("checkpoint_json" in database["job_columns"], "Missing local checkpoint persistence")
            runtime = sidecar.rpc("get_browser_runtime_status", timeout=60)
            require(runtime.get("installed") and runtime.get("state") == "ready",
                    "Chromium runtime missing/not ready. Install via sidecar Python's `-m playwright install chromium` "
                    "and set PLAYWRIGHT_BROWSERS_PATH. No automatic download attempted. " + str(runtime))
            validation = sidecar.rpc("validate_excel", {"module": "graduation", "path": str(excel)})
            require(validation["rows_total"] == validation["rows_accepted"] == 2, f"Unexpected validation: {validation}")
            require(validation["detected_level"] == "ม.6" and not validation["warnings"], "Invalid synthetic Graduation input")
            require([row["first_name"] for row in validation["preview"]] == ["สมชาย", "สมหญิง"], "Thai preview mismatch")
            started = False
            try:
                accepted = sidecar.rpc("start_job", {"job_id": JOB_ID, "module": "graduation", "excel_path": str(excel),
                                      "options": {"dry_run": True, "headless": True, "stop_on_review": False}}, timeout=60)
                started = True
                require(accepted.get("accepted") is True, f"Job not accepted: {accepted}")
                deadline = time.monotonic() + 90
                resumed = False
                while time.monotonic() < deadline:
                    status = sidecar.rpc("get_job_status", {"job_id": JOB_ID})
                    if not resumed and any(e.get("type") == "needs_auth" and e.get("job_id") == JOB_ID for e in sidecar.events):
                        sidecar.rpc("resume_job", {"job_id": JOB_ID})
                        resumed = True
                    # Completion notification follows database/report persistence.
                    if any(e.get("type") == "job_done" and e.get("job_id") == JOB_ID for e in sidecar.events):
                        break
                    require(status["status"] not in {"failed", "cancelled", "stopped_on_review"}, f"Job failed: {status}")
                    time.sleep(0.1)
                else:
                    raise SmokeFailure(f"Timed out completing local dry run: {status}")
                require(resumed, "Synthetic job never requested authentication")
            finally:
                if started:
                    status = sidecar.rpc("get_job_status", {"job_id": JOB_ID}, timeout=5)
                    if status["status"] not in {"done", "failed", "cancelled", "stopped_on_review"}:
                        sidecar.rpc("cancel_job", {"job_id": JOB_ID}, timeout=5)
                        end = time.monotonic() + 5
                        while time.monotonic() < end:
                            if sidecar.rpc("get_job_status", {"job_id": JOB_ID}, timeout=5)["status"] == "cancelled":
                                break
                            time.sleep(0.1)

        # Read persisted state after the actual subprocess exits.
        with closing(sqlite3.connect(db_path)) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute("SELECT * FROM job WHERE id = ?", (JOB_ID,)).fetchone()
            require(row is not None and row["status"] == "done", "Completion was not persisted")
            require(row["processed"] == row["succeeded"] == 2 and row["failed"] == 0, "Incorrect persisted counts")
            summary = json.loads(row["run_summary_json"])
            require(summary["dry_run_rows"] == 2 and summary["applied_rows"] == 0, f"Incorrect dry run summary: {summary}")
            records = connection.execute("SELECT result_json FROM job_record WHERE job_id = ? ORDER BY portal_row_index", (JOB_ID,)).fetchall()
            require(len(records) == 2, "Missing persisted job results")
            report = Path(row["report_path"]).resolve()
            review = Path(row["review_report_path"]).resolve()
        for path in (report, review, report.with_suffix(".json")):
            require(path.is_relative_to(root / "data/reports") and path.is_file(), f"Missing or unisolated report: {path}")
        report_rows = json.loads(report.with_suffix(".json").read_text(encoding="utf-8"))
        require(report_rows == [json.loads(record["result_json"]) for record in records], "Report differs from persisted results")
        notes = [item["note"] for item in report_rows]
        require(notes == ["dry_run", "dry_run"] and all(item["applied"] is False for item in report_rows), "Report is not a dry run")
        require(portal.post_saves == 0, "Dry run sent a portal POST save")
        result = {"schema_generation": 2, "rows_accepted": 2, "status": "done", "dry_run_rows": 2,
                  "post_saves": portal.post_saves, "report_notes": notes, "temporary_root": str(root)}
    return result


def main() -> int:
    if len(sys.argv) != 1:
        print("Usage: smoke_local.py (source mode; builds/typechecks run separately via ci:verify)", file=sys.stderr)
        return 2
    try:
        result = run_smoke()
    except Exception as exc:
        print(f"[smoke] FAILED: {exc}", file=sys.stderr)
        return 1
    print("[smoke] PASS " + json.dumps(result, ensure_ascii=True))
    print("[smoke] Temporary data removed. Browser status may contact the official Playwright CDN.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
