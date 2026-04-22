from __future__ import annotations

from pathlib import Path

from dmc_sidecar import browser_runtime


def test_get_browser_runtime_status_detects_missing_runtime(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", str(tmp_path / "ms-playwright"))

    status = browser_runtime.get_browser_runtime_status()

    assert status.installed is False
    assert status.executable_path is None
    assert status.install_dir == str(tmp_path / "ms-playwright")


def test_get_browser_runtime_status_detects_installed_chromium(monkeypatch, tmp_path: Path) -> None:
    install_dir = tmp_path / "ms-playwright"
    executable = install_dir / "chromium-1208" / "chrome-win" / "chrome.exe"
    executable.parent.mkdir(parents=True)
    executable.write_text("", encoding="utf-8")
    monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", str(install_dir))

    status = browser_runtime.get_browser_runtime_status()

    assert status.installed is True
    assert status.executable_path == str(executable)


def test_bootstrap_browser_runtime_uses_playwright_cli_result(monkeypatch, tmp_path: Path) -> None:
    install_dir = tmp_path / "ms-playwright"
    executable = install_dir / "chromium-1208" / "chrome-win" / "chrome.exe"
    monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", str(install_dir))

    def fake_run(args: list[str], target_dir: Path) -> tuple[int, str]:
        assert args == ["install", "chromium", "--no-shell"]
        assert target_dir == install_dir
        executable.parent.mkdir(parents=True, exist_ok=True)
        executable.write_text("", encoding="utf-8")
        return 0, "ok"

    monkeypatch.setattr(browser_runtime, "_run_playwright_cli", fake_run)

    status = browser_runtime.bootstrap_browser_runtime()

    assert status.bootstrap_performed is True
    assert status.installed is True
    assert status.last_error is None
    assert status.executable_path == str(executable)
