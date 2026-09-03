from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


@pytest.fixture
def readiness(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    scripts = Path(__file__).resolve().parents[3] / "scripts"
    spec = importlib.util.spec_from_file_location("release_readiness", scripts / "check_release_readiness.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    files = {
        "TAURI_CONFIG_PATH": ("tauri.conf.json", {"bundle": {"resources": ["bundled-sidecar", "templates"], "active": True, "targets": "msi"}}),
        "TAURI_PACKAGE_CONFIG_PATH": ("tauri.package.conf.json", {"bundle": {"active": True, "targets": "msi"}}),
        "PACKAGE_JSON_PATH": ("package.json", {"scripts": {
            "ci:verify": "checks", "sidecar:bundle": "bundle",
            "desktop:package": "corepack pnpm run sidecar:bundle && corepack pnpm --dir apps/desktop exec tauri build --config src-tauri/tauri.package.conf.json",
        }}),
    }
    for attribute, (name, data) in files.items():
        path = tmp_path / name
        path.write_text(json.dumps(data), encoding="utf-8")
        monkeypatch.setattr(module, attribute, path, raising=False)
    gitignore = tmp_path / ".gitignore"
    gitignore.write_text(
        "apps/desktop/src-tauri/bundled-sidecar/*\n"
        "!apps/desktop/src-tauri/bundled-sidecar/.gitkeep\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "GITIGNORE_PATH", gitignore)
    monkeypatch.setattr(sys, "argv", ["check_release_readiness.py"])
    return module


def test_manual_package_is_ready_without_cloud_or_updater_config(readiness, capsys):
    readiness.main()
    assert json.loads(capsys.readouterr().out) == {"status": "ok"}


@pytest.mark.parametrize("resource", ["bundled-sidecar", "templates"])
def test_missing_native_resource_is_rejected(readiness, resource):
    config = json.loads(readiness.TAURI_CONFIG_PATH.read_text(encoding="utf-8"))
    config["bundle"]["resources"].remove(resource)
    readiness.TAURI_CONFIG_PATH.write_text(json.dumps(config), encoding="utf-8")
    with pytest.raises(SystemExit, match=resource):
        readiness.check_tauri_config()


def test_non_msi_package_is_rejected(readiness):
    readiness.TAURI_PACKAGE_CONFIG_PATH.write_text('{"bundle":{"active":true,"targets":"nsis"}}', encoding="utf-8")
    with pytest.raises(SystemExit, match="msi"):
        readiness.check_tauri_config()


def test_package_script_must_use_manual_package_config(readiness):
    package = json.loads(readiness.PACKAGE_JSON_PATH.read_text(encoding="utf-8"))
    package["scripts"]["desktop:package"] = "corepack pnpm --dir apps/desktop exec tauri build"
    readiness.PACKAGE_JSON_PATH.write_text(json.dumps(package), encoding="utf-8")
    with pytest.raises(SystemExit, match="tauri.package.conf.json"):
        readiness.check_package_scripts()


def test_unignored_sidecar_artifacts_are_rejected(readiness):
    readiness.GITIGNORE_PATH.write_text("", encoding="utf-8")
    with pytest.raises(SystemExit, match="bundled sidecar artifacts"):
        readiness.check_gitignore()
