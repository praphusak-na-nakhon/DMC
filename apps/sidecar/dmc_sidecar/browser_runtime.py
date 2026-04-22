from __future__ import annotations

import io
import os
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from .config import playwright_browsers_dir
from .schemas import BrowserRuntimeStatus


CHROMIUM_EXECUTABLE_RELATIVE_PATHS = (
    Path("chrome-win") / "chrome.exe",
    Path("chrome-linux") / "chrome",
    Path("chrome-mac") / "Chromium.app" / "Contents" / "MacOS" / "Chromium",
)


def _playwright_cli_available() -> bool:
    try:
        import playwright.__main__  # noqa: F401
    except Exception:
        return False
    return True


def chromium_runtime_dir() -> Path:
    return playwright_browsers_dir()


def find_chromium_executable(install_dir: Path | None = None) -> Path | None:
    search_root = install_dir or chromium_runtime_dir()
    if not search_root.exists():
        return None

    for candidate_root in sorted(search_root.glob("chromium-*"), reverse=True):
        for relative_path in CHROMIUM_EXECUTABLE_RELATIVE_PATHS:
            executable_path = candidate_root / relative_path
            if executable_path.exists():
                return executable_path
    return None


def get_browser_runtime_status(
    *,
    bootstrap_performed: bool = False,
    last_error: str | None = None,
) -> BrowserRuntimeStatus:
    install_dir = chromium_runtime_dir()
    executable_path = find_chromium_executable(install_dir)
    installed = executable_path is not None
    bootstrap_supported = _playwright_cli_available()
    if installed:
        message = "Chromium browser runtime is ready."
    elif bootstrap_supported:
        message = "Chromium browser runtime is not installed yet."
    else:
        message = "Playwright CLI is unavailable in this sidecar build."

    return BrowserRuntimeStatus(
        installed=installed,
        install_dir=str(install_dir),
        executable_path=str(executable_path) if executable_path is not None else None,
        bootstrap_supported=bootstrap_supported,
        bootstrap_performed=bootstrap_performed,
        message=message,
        last_error=last_error,
    )


def _run_playwright_cli(args: list[str], install_dir: Path) -> tuple[int, str]:
    from playwright.__main__ import main as playwright_main

    previous_argv = sys.argv[:]
    previous_browsers_path = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
    output_buffer = io.StringIO()
    exit_code = 0

    try:
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(install_dir)
        sys.argv = ["playwright", *args]
        with redirect_stdout(output_buffer), redirect_stderr(output_buffer):
            try:
                playwright_main()
            except SystemExit as exc:  # pragma: no cover - behavior depends on playwright CLI internals
                if isinstance(exc.code, int):
                    exit_code = exc.code
                else:
                    exit_code = 0 if exc.code in {None, ""} else 1
    finally:
        sys.argv = previous_argv
        if previous_browsers_path is None:
            os.environ.pop("PLAYWRIGHT_BROWSERS_PATH", None)
        else:
            os.environ["PLAYWRIGHT_BROWSERS_PATH"] = previous_browsers_path

    return exit_code, output_buffer.getvalue().strip()


def bootstrap_browser_runtime() -> BrowserRuntimeStatus:
    if not _playwright_cli_available():
        return get_browser_runtime_status(
            bootstrap_performed=True,
            last_error="PLAYWRIGHT_CLI_UNAVAILABLE",
        )

    install_dir = chromium_runtime_dir()
    install_dir.mkdir(parents=True, exist_ok=True)

    try:
        exit_code, output = _run_playwright_cli(["install", "chromium", "--no-shell"], install_dir)
    except Exception as exc:  # pragma: no cover - defensive boundary
        return get_browser_runtime_status(
            bootstrap_performed=True,
            last_error=f"PLAYWRIGHT_INSTALL_FAILED: {exc}",
        )

    status = get_browser_runtime_status(bootstrap_performed=True)
    if exit_code != 0:
        tail = output.splitlines()[-1] if output else "Playwright CLI exited with a non-zero status."
        status.last_error = f"PLAYWRIGHT_INSTALL_FAILED: {tail}"
        return status

    if not status.installed:
        status.last_error = "PLAYWRIGHT_INSTALL_INCOMPLETE"
        status.message = "Playwright install finished but Chromium was not found in the runtime directory."
        return status

    return status
