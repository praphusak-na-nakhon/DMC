from __future__ import annotations

from pathlib import Path
import subprocess
from typing import Callable
from urllib.error import URLError
from urllib.request import Request, urlopen

from .config import playwright_browsers_dir
from .schemas import BrowserRuntimePackage, BrowserRuntimeStatus


CHROMIUM_EXECUTABLE_RELATIVE_PATHS = (
    Path("chrome-win") / "chrome.exe",
    Path("chrome-win64") / "chrome.exe",
    Path("chrome-linux") / "chrome",
    Path("chrome-mac") / "Chromium.app" / "Contents" / "MacOS" / "Chromium",
)

INSTALL_PLAN_TIMEOUT_SECS = 4
LOG_TAIL_LIMIT = 8
_INSTALL_PLAN_CACHE: tuple[list[BrowserRuntimePackage], str | None] | None = None


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


def _tail_lines(text: str) -> list[str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return lines[-LOG_TAIL_LIMIT:]


def _emit_progress(
    emit_progress: Callable[[dict[str, object]], None] | None,
    *,
    phase: str,
    message: str,
    percent: int | None = None,
    detail: str | None = None,
) -> None:
    if emit_progress is None:
        return
    emit_progress(
        {
            "type": "browser_runtime_progress",
            "phase": phase,
            "message": message,
            "percent": percent,
            "detail": detail,
        }
    )


def _run_playwright_cli(args: list[str], install_dir: Path) -> tuple[int, str]:
    from playwright._impl._driver import compute_driver_executable, get_driver_env

    node_executable, cli_script = compute_driver_executable()
    env = get_driver_env()
    env["PLAYWRIGHT_BROWSERS_PATH"] = str(install_dir)
    completed = subprocess.run(
        [node_executable, cli_script, *args],
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )

    output = "\n".join(part for part in (completed.stdout.strip(), completed.stderr.strip()) if part)
    return completed.returncode, output


def _probe_content_length(url: str) -> int | None:
    request = Request(url, method="HEAD")
    try:
        with urlopen(request, timeout=INSTALL_PLAN_TIMEOUT_SECS) as response:
            raw_value = response.headers.get("Content-Length")
    except (URLError, TimeoutError, OSError):
        return None

    if raw_value is None:
        return None
    try:
        return int(raw_value)
    except ValueError:
        return None


def _parse_install_plan_output(output: str) -> list[BrowserRuntimePackage]:
    packages: list[BrowserRuntimePackage] = []
    current_name: str | None = None
    current_install_location: str | None = None
    current_download_url: str | None = None

    def flush_current() -> None:
        nonlocal current_name, current_install_location, current_download_url
        if current_name and current_install_location and current_download_url:
            packages.append(
                BrowserRuntimePackage(
                    name=current_name,
                    install_location=current_install_location,
                    download_url=current_download_url,
                    download_bytes=_probe_content_length(current_download_url),
                )
            )
        current_name = None
        current_install_location = None
        current_download_url = None

    for raw_line in output.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            continue

        if not line.startswith(" "):
            flush_current()
            current_name = line.split(" (", 1)[0].strip()
            continue

        stripped = line.strip()
        if stripped.startswith("Install location:"):
            current_install_location = stripped.split(":", 1)[1].strip()
        elif stripped.startswith("Download url:") and current_download_url is None:
            current_download_url = stripped.split(":", 1)[1].strip()

    flush_current()
    return packages


def _load_install_plan() -> tuple[list[BrowserRuntimePackage], str | None]:
    global _INSTALL_PLAN_CACHE
    if _INSTALL_PLAN_CACHE is not None:
        return _INSTALL_PLAN_CACHE
    if not _playwright_cli_available():
        return [], "PLAYWRIGHT_CLI_UNAVAILABLE"

    install_dir = chromium_runtime_dir()
    try:
        exit_code, output = _run_playwright_cli(["install", "chromium", "--no-shell", "--dry-run"], install_dir)
    except FileNotFoundError:
        return [], "PLAYWRIGHT_CLI_UNAVAILABLE"
    except Exception as exc:  # pragma: no cover - defensive boundary
        error_code = _classify_install_failure(str(exc))
        return [], error_code
    if exit_code != 0:
        log_tail = _tail_lines(output)
        summary = log_tail[-1] if log_tail else "Playwright CLI dry-run failed."
        return [], f"PLAYWRIGHT_INSTALL_PLAN_FAILED: {summary}"

    _INSTALL_PLAN_CACHE = (_parse_install_plan_output(output), None)
    return _INSTALL_PLAN_CACHE


def _guidance_for_error(error_code: str | None) -> str | None:
    if error_code is None:
        return None
    if error_code == "PLAYWRIGHT_CLI_UNAVAILABLE":
        return "This packaged sidecar is missing the Playwright installer. Rebuild the sidecar bundle before shipping."
    if error_code == "PLAYWRIGHT_RUNTIME_DIR_NOT_WRITABLE":
        return "Check that the current Windows user can write into the app data folder, then try again."
    if error_code == "PLAYWRIGHT_DOWNLOAD_UNREACHABLE":
        return "Connect the machine to the internet and verify that the CDN is reachable. If the school uses a proxy, configure it before retrying."
    if error_code == "PLAYWRIGHT_PROXY_ERROR":
        return "A proxy or gateway blocked the download. Verify proxy settings or whitelist the Playwright CDN."
    if error_code == "PLAYWRIGHT_INSTALL_INCOMPLETE":
        return "Installation finished without a Chromium executable. Retry once; if it keeps failing, clear the runtime folder and bootstrap again."
    if error_code and error_code.startswith("PLAYWRIGHT_INSTALL_PLAN_FAILED"):
        return "Could not inspect the Playwright install plan. Check network connectivity and proxy settings, then retry."
    return "Retry the bootstrap. If it keeps failing, capture the diagnostic log and inspect the Playwright installer output."


def _classify_install_failure(raw_text: str) -> str:
    lowered = raw_text.lower()
    if any(token in lowered for token in ("407", "proxy", "proxyconnect", "tunneling socket")):
        return "PLAYWRIGHT_PROXY_ERROR"
    if any(token in lowered for token in ("eacces", "eperm", "permission denied", "access is denied")):
        return "PLAYWRIGHT_RUNTIME_DIR_NOT_WRITABLE"
    if any(
        token in lowered
        for token in (
            "enotfound",
            "etimedout",
            "ecconnreset",
            "econnreset",
            "econnrefused",
            "enetunreach",
            "offline",
            "network",
            "timed out",
            "socket hang up",
        )
    ):
        return "PLAYWRIGHT_DOWNLOAD_UNREACHABLE"
    return "PLAYWRIGHT_INSTALL_FAILED"


def _build_status(
    *,
    install_dir: Path,
    executable_path: Path | None,
    bootstrap_supported: bool,
    bootstrap_performed: bool,
    state: str,
    message: str,
    required_components: list[BrowserRuntimePackage],
    last_error: str | None = None,
    log_tail: list[str] | None = None,
) -> BrowserRuntimeStatus:
    estimated_download_bytes = sum(
        package.download_bytes for package in required_components if package.download_bytes is not None
    ) or None

    return BrowserRuntimeStatus(
        state=state,  # type: ignore[arg-type]
        installed=executable_path is not None,
        install_dir=str(install_dir),
        executable_path=str(executable_path) if executable_path is not None else None,
        bootstrap_supported=bootstrap_supported,
        bootstrap_performed=bootstrap_performed,
        estimated_download_bytes=estimated_download_bytes,
        required_components=required_components,
        message=message,
        guidance=_guidance_for_error(last_error),
        last_error=last_error,
        log_tail=log_tail or [],
    )


def get_browser_runtime_status(
    *,
    bootstrap_performed: bool = False,
    last_error: str | None = None,
    log_tail: list[str] | None = None,
) -> BrowserRuntimeStatus:
    install_dir = chromium_runtime_dir()
    executable_path = find_chromium_executable(install_dir)
    bootstrap_supported = _playwright_cli_available()
    required_components, plan_error = _load_install_plan()
    effective_error = last_error or plan_error

    if executable_path is not None:
        return _build_status(
            install_dir=install_dir,
            executable_path=executable_path,
            bootstrap_supported=bootstrap_supported,
            bootstrap_performed=bootstrap_performed,
            state="ready",
            message="Chromium browser runtime is ready.",
            required_components=required_components,
            last_error=effective_error,
            log_tail=log_tail,
        )

    if not bootstrap_supported:
        return _build_status(
            install_dir=install_dir,
            executable_path=None,
            bootstrap_supported=False,
            bootstrap_performed=bootstrap_performed,
            state="failed",
            message="Playwright CLI is unavailable in this sidecar build.",
            required_components=[],
            last_error=effective_error or "PLAYWRIGHT_CLI_UNAVAILABLE",
            log_tail=log_tail,
        )

    return _build_status(
        install_dir=install_dir,
        executable_path=None,
        bootstrap_supported=True,
        bootstrap_performed=bootstrap_performed,
        state="failed" if effective_error else "missing",
        message=(
            "Chromium browser runtime is not installed yet."
            if effective_error is None
            else "Chromium browser runtime is not ready yet."
        ),
        required_components=required_components,
        last_error=effective_error,
        log_tail=log_tail,
    )


def bootstrap_browser_runtime(
    *,
    emit_progress: Callable[[dict[str, object]], None] | None = None,
) -> BrowserRuntimeStatus:
    if not _playwright_cli_available():
        return get_browser_runtime_status(
            bootstrap_performed=True,
            last_error="PLAYWRIGHT_CLI_UNAVAILABLE",
        )

    install_dir = chromium_runtime_dir()
    required_components, plan_error = _load_install_plan()
    if plan_error is not None:
        return get_browser_runtime_status(
            bootstrap_performed=True,
            last_error=plan_error,
        )

    try:
        install_dir.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        return get_browser_runtime_status(
            bootstrap_performed=True,
            last_error="PLAYWRIGHT_RUNTIME_DIR_NOT_WRITABLE",
        )

    _emit_progress(
        emit_progress,
        phase="checking",
        message="Preparing the Chromium browser runtime installer.",
        percent=10,
        detail=f"{len(required_components)} components will be installed into {install_dir}",
    )
    _emit_progress(
        emit_progress,
        phase="installing",
        message="Downloading Chromium browser runtime. This can take a few minutes on first run.",
        percent=45,
    )

    try:
        exit_code, output = _run_playwright_cli(["install", "chromium", "--no-shell"], install_dir)
    except PermissionError:
        return get_browser_runtime_status(
            bootstrap_performed=True,
            last_error="PLAYWRIGHT_RUNTIME_DIR_NOT_WRITABLE",
        )
    except Exception as exc:  # pragma: no cover - defensive boundary
        error_code = _classify_install_failure(str(exc))
        return get_browser_runtime_status(
            bootstrap_performed=True,
            last_error=error_code,
            log_tail=_tail_lines(str(exc)),
        )

    _emit_progress(
        emit_progress,
        phase="verifying",
        message="Verifying the installed Chromium runtime.",
        percent=90,
    )

    if exit_code != 0:
        log_tail = _tail_lines(output)
        error_code = _classify_install_failure(output)
        _emit_progress(
            emit_progress,
            phase="failed",
            message="Chromium runtime installation failed.",
            percent=100,
            detail=log_tail[-1] if log_tail else error_code,
        )
        return get_browser_runtime_status(
            bootstrap_performed=True,
            last_error=error_code,
            log_tail=log_tail,
        )

    status = get_browser_runtime_status(bootstrap_performed=True, log_tail=_tail_lines(output))
    if not status.installed:
        _emit_progress(
            emit_progress,
            phase="failed",
            message="Chromium installer finished but the browser runtime was not found.",
            percent=100,
            detail="PLAYWRIGHT_INSTALL_INCOMPLETE",
        )
        return get_browser_runtime_status(
            bootstrap_performed=True,
            last_error="PLAYWRIGHT_INSTALL_INCOMPLETE",
            log_tail=_tail_lines(output),
        )

    _emit_progress(
        emit_progress,
        phase="ready",
        message="Chromium browser runtime is ready.",
        percent=100,
        detail=status.executable_path,
    )
    return status
