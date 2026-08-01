from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DESKTOP_TAURI = ROOT / "apps" / "desktop" / "src-tauri"
BUNDLED_SIDECAR = DESKTOP_TAURI / "bundled-sidecar"
DEBUG_SIDECAR = DESKTOP_TAURI / "target" / "debug" / "bundled-sidecar"
SIDECAR_EXE = DEBUG_SIDECAR / "dmc-sidecar.exe"
SAMPLE_EXCEL = ROOT / "m3-obec-study-form.xlsx"
PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"


class SmokeFailure(RuntimeError):
    pass


def info(message: str) -> None:
    print(f"[smoke] {message}", flush=True)


def run_command(command: list[str], *, timeout: int = 300, retries: int = 1) -> None:
    resolved_command = command.copy()
    resolved_executable = shutil.which(resolved_command[0])
    if resolved_executable is not None:
        resolved_command[0] = resolved_executable
    completed: subprocess.CompletedProcess[str] | None = None
    for attempt in range(1, retries + 1):
        info(f"running: {' '.join(command)}" + (f" (attempt {attempt}/{retries})" if retries > 1 else ""))
        completed = subprocess.run(
            resolved_command,
            cwd=ROOT,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=timeout,
        )
        combined_output = f"{completed.stdout}\n{completed.stderr}".lower()
        if completed.returncode == 0:
            break
        if attempt < retries and "being used by another process" in combined_output:
            stop_desktop_processes()
            time.sleep(2)
            continue
        break
    if completed is None:
        raise SmokeFailure(f"command did not run: {' '.join(command)}")
    if completed.returncode != 0:
        raise SmokeFailure(
            "\n".join(
                [
                    f"command failed with exit code {completed.returncode}: {' '.join(command)}",
                    "--- stdout ---",
                    completed.stdout,
                    "--- stderr ---",
                    completed.stderr,
                ]
            )
        )
    if completed.stdout.strip():
        print(completed.stdout, end="" if completed.stdout.endswith("\n") else "\n")
    if completed.stderr.strip():
        print(completed.stderr, end="" if completed.stderr.endswith("\n") else "\n")


def stop_desktop_processes() -> None:
    for image_name in ("dmc-desktop.exe", "dmc-sidecar.exe"):
        subprocess.run(
            ["taskkill", "/F", "/IM", image_name],
            cwd=ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        running = False
        for image_name in ("dmc-desktop.exe", "dmc-sidecar.exe"):
            completed = subprocess.run(
                ["tasklist", "/FI", f"IMAGENAME eq {image_name}"],
                cwd=ROOT,
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                check=False,
            )
            running = running or image_name.lower() in completed.stdout.lower()
        if not running:
            return
        time.sleep(0.5)


def sync_debug_sidecar() -> None:
    if not BUNDLED_SIDECAR.exists():
        raise SmokeFailure(f"bundled sidecar directory does not exist: {BUNDLED_SIDECAR}")
    DEBUG_SIDECAR.mkdir(parents=True, exist_ok=True)
    for source in BUNDLED_SIDECAR.iterdir():
        target = DEBUG_SIDECAR / source.name
        for attempt in range(1, 8):
            try:
                if source.is_dir():
                    shutil.copytree(source, target, dirs_exist_ok=True)
                else:
                    shutil.copy2(source, target)
                break
            except PermissionError:
                if attempt == 7:
                    raise
                stop_desktop_processes()
                time.sleep(1)
    if not SIDECAR_EXE.exists():
        raise SmokeFailure(f"debug sidecar executable does not exist after sync: {SIDECAR_EXE}")


def app_data_sidecar_dir() -> Path:
    appdata = os.environ.get("APPDATA")
    if not appdata:
        return ROOT / ".dmc-assistant-data"
    return Path(appdata) / "info.bopp.dmcassistant" / "sidecar"


class SidecarProcess:
    def __init__(self) -> None:
        self.stderr_lines: list[str] = []
        data_dir = app_data_sidecar_dir()
        env = os.environ.copy()
        env["DMC_DATA_DIR"] = str(data_dir)
        env["PLAYWRIGHT_BROWSERS_PATH"] = str(data_dir / "ms-playwright")
        env["DMC_BUNDLED_RESOURCES_DIR"] = str(DEBUG_SIDECAR / "sidecar-resources")
        env["DMC_CLOUD_BASE_URL"] = "http://127.0.0.1:8000"
        env["DMC_ALLOW_UNLICENSED_JOBS"] = "1"
        self.process = subprocess.Popen(
            [str(SIDECAR_EXE)],
            cwd=DEBUG_SIDECAR,
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        threading.Thread(target=self._drain_stderr, daemon=True).start()

    def _drain_stderr(self) -> None:
        assert self.process.stderr is not None
        for raw in self.process.stderr:
            self.stderr_lines.append(raw.decode("utf-8", "replace").rstrip())

    def close(self) -> None:
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()

    def rpc(self, method: str, params: dict[str, Any] | None = None, *, timeout: int = 45) -> Any:
        request = {
            "jsonrpc": "2.0",
            "id": f"smoke-{method}-{time.monotonic_ns()}",
            "method": method,
            "params": params or {},
        }
        assert self.process.stdin is not None
        assert self.process.stdout is not None
        self.process.stdin.write((json.dumps(request, separators=(",", ":")) + "\n").encode("utf-8"))
        self.process.stdin.flush()

        line_holder: list[bytes] = []

        def read_line() -> None:
            assert self.process.stdout is not None
            line_holder.append(self.process.stdout.readline())

        reader = threading.Thread(target=read_line, daemon=True)
        reader.start()
        reader.join(timeout)

        if not line_holder:
            raise SmokeFailure(self._diagnostic(f"timed out waiting for sidecar response to {method}"))
        raw_line = line_holder[0]
        if raw_line == b"":
            raise SmokeFailure(self._diagnostic(f"sidecar stdout closed while waiting for {method}"))
        try:
            text = raw_line.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise SmokeFailure(self._diagnostic(f"sidecar stdout was not valid UTF-8 for {method}: {exc}")) from exc
        if any(byte >= 128 for byte in raw_line):
            raise SmokeFailure(self._diagnostic(f"sidecar stdout for {method} contained non-ASCII protocol bytes"))
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise SmokeFailure(self._diagnostic(f"sidecar stdout was not JSON for {method}: {text[:500]}")) from exc
        if "error" in payload:
            raise SmokeFailure(self._diagnostic(f"sidecar RPC {method} failed: {json.dumps(payload['error'], ensure_ascii=False)}"))
        if payload.get("id") != request["id"]:
            raise SmokeFailure(self._diagnostic(f"sidecar RPC {method} returned unexpected id: {payload.get('id')}"))
        return payload.get("result")

    def _diagnostic(self, message: str) -> str:
        poll = self.process.poll()
        tail = "\n".join(self.stderr_lines[-30:])
        return "\n".join(
            [
                message,
                f"process_status={poll if poll is not None else 'running'}",
                "--- sidecar stderr tail ---",
                tail or "(empty)",
            ]
        )


def assert_sidecar_smoke() -> None:
    if not SAMPLE_EXCEL.exists():
        raise SmokeFailure(f"sample Excel file not found: {SAMPLE_EXCEL}")
    sidecar = SidecarProcess()
    try:
        ping = sidecar.rpc("ping", timeout=60)
        if ping.get("value") != "pong":
            raise SmokeFailure(f"unexpected ping payload: {ping}")

        runtime = sidecar.rpc("get_browser_runtime_status", timeout=60)
        if not runtime.get("installed") or runtime.get("state") != "ready":
            raise SmokeFailure(
                "browser runtime is not ready:\n"
                + json.dumps(runtime, ensure_ascii=False, indent=2)
            )

        config = sidecar.rpc("get_module_config_status", {"module": "graduation"}, timeout=60)
        if config.get("module") != "graduation" or not config.get("version"):
            raise SmokeFailure(f"unexpected module config payload: {config}")

        license_status = sidecar.rpc("get_license_status", timeout=60)
        if "status" not in license_status:
            raise SmokeFailure(f"unexpected license payload: {license_status}")
        if not license_status.get("can_start_jobs"):
            raise SmokeFailure(f"development license gate blocked job start: {license_status}")

        validation = sidecar.rpc(
            "validate_excel",
            {"path": str(SAMPLE_EXCEL), "module": "graduation"},
            timeout=120,
        )
        preview = validation.get("preview") or []
        if validation.get("detected_level") != "ม.3":
            raise SmokeFailure(f"unexpected detected level: {validation.get('detected_level')}")
        if validation.get("rows_total", 0) <= 0 or validation.get("rows_accepted", 0) <= 0:
            raise SmokeFailure(f"unexpected validation counts: {validation}")
        if not preview or preview[0].get("first_name") != "ทวีศักดิ์":
            raise SmokeFailure(f"Thai preview did not decode correctly: {preview[:1]}")

        info(
            "sidecar executable smoke passed: "
            f"runtime={runtime.get('state')} "
            f"rows={validation.get('rows_accepted')}/{validation.get('rows_total')} "
            f"first_name={preview[0].get('first_name')}"
        )
    finally:
        sidecar.close()


def run_all(args: argparse.Namespace) -> None:
    stop_desktop_processes()
    if not args.skip_build:
        run_command(["corepack", "pnpm", "run", "sidecar:bundle"], timeout=300)
    sync_debug_sidecar()
    assert_sidecar_smoke()
    stop_desktop_processes()

    run_command(["corepack", "pnpm", "run", "sidecar:typecheck"], timeout=240)
    run_command(
        [
            str(PYTHON),
            "-m",
            "pytest",
            "apps/sidecar/tests/test_account_client.py",
            "apps/sidecar/tests/test_rpc.py",
            "apps/sidecar/tests/test_browser_runtime.py",
            "apps/sidecar/tests/test_graduation_module.py",
            "apps/sidecar/tests/test_workflow_e2e.py",
        ],
        timeout=300,
    )
    run_command(["corepack", "pnpm", "run", "desktop:typecheck"], timeout=240)
    stop_desktop_processes()
    run_command(["corepack", "pnpm", "run", "desktop:cargo-check"], timeout=240, retries=3)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run local DMC Assistant smoke checks.")
    parser.add_argument(
        "--skip-build",
        action="store_true",
        help="Use the existing staged sidecar bundle instead of rebuilding it first.",
    )
    return parser.parse_args()


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    args = parse_args()
    started_at = time.monotonic()
    try:
        run_all(args)
    except (SmokeFailure, subprocess.TimeoutExpired) as exc:
        print("\n[smoke] FAILED", file=sys.stderr)
        print(str(exc), file=sys.stderr)
        return 1
    elapsed = time.monotonic() - started_at
    info(f"all local smoke checks passed in {elapsed:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
