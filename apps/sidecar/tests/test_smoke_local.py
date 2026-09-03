from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[3] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import smoke_local as smoke


def test_environment_is_temporary_and_preserves_shipped_config(monkeypatch, tmp_path):
    shipped = smoke.ROOT / "packages/module-configs/graduation/v1.json"
    original = shipped.read_bytes()
    monkeypatch.setenv("DMC_DATA_DIR", str(tmp_path / "user-data"))
    monkeypatch.setenv("DMC_BUNDLED_RESOURCES_DIR", str(tmp_path / "user-resources"))
    monkeypatch.setenv("DMC_REPO_ROOT", str(tmp_path / "other-checkout"))
    with pytest.raises(RuntimeError, match="injected failure"):
        with smoke.smoke_environment("http://127.0.0.1:12345") as (root, env, excel):
            assert Path(env["DMC_DATA_DIR"]).is_relative_to(root)
            assert Path(env["DMC_BUNDLED_RESOURCES_DIR"]).is_relative_to(root)
            assert env["DMC_REPO_ROOT"] == str(smoke.ROOT)
            assert excel.is_file() and excel.is_relative_to(root)
            copied = json.loads((Path(env["DMC_BUNDLED_RESOURCES_DIR"]) / "module-configs/graduation/v1.json").read_text(encoding="utf-8"))
            expected = json.loads(original)
            expected["login_url"] = "http://127.0.0.1:12345/obec68/auth/login"
            expected["target_url_template"] = "http://127.0.0.1:12345/obec68/studentpendingupl/add?levelDtlCode={level_code}&action=search"
            assert copied == expected
            raise RuntimeError("injected failure")
    assert not root.exists()
    assert not (tmp_path / "user-data").exists()
    assert shipped.read_bytes() == original


def test_rpc_matches_ids_across_notifications_and_late_responses(tmp_path):
    code = """
import json, sys
for line in sys.stdin:
    req = json.loads(line)
    print(json.dumps({'jsonrpc': '2.0', 'method': 'event', 'params': {'type': 'progress'}}), flush=True)
    print(json.dumps({'jsonrpc': '2.0', 'id': 'old-request', 'result': 'wrong'}), flush=True)
    print(json.dumps({'jsonrpc': '2.0', 'id': req['id'], 'result': req['method']}), flush=True)
"""
    with smoke.SidecarProcess([sys.executable, "-u", "-c", code], env=os.environ.copy(), cwd=tmp_path) as client:
        assert client.rpc("first") == "first"
        assert client.rpc("second") == "second"
        assert [event["type"] for event in client.events] == ["progress", "progress"]
    assert client.process.poll() is not None
    assert all(not reader.is_alive() for reader in client.readers)
    assert all(stream.closed for stream in (client.process.stdin, client.process.stdout, client.process.stderr))


def test_rpc_timeout_closes_only_owned_process_and_readers(tmp_path):
    code = "import sys, time; sys.stdin.readline(); time.sleep(30)"
    with pytest.raises(smoke.SmokeFailure, match="timed out"):
        with smoke.SidecarProcess([sys.executable, "-u", "-c", code], env=os.environ.copy(), cwd=tmp_path) as client:
            client.rpc("never-replies", timeout=0.1)
    assert client.process.poll() is not None
    assert all(not reader.is_alive() for reader in client.readers)


def test_real_localhost_dry_run_persists_reports_without_saving():
    result = smoke.run_smoke()
    assert result["schema_generation"] == 2
    assert result["rows_accepted"] == 2
    assert result["status"] == "done"
    assert result["dry_run_rows"] == 2
    assert result["post_saves"] == 0
    assert result["report_notes"] == ["dry_run", "dry_run"]
    assert not Path(result["temporary_root"]).exists()


@pytest.mark.parametrize("base_url", ["https://example.com", "http://localhost:1234", "http://127.0.0.1:1234/other"])
def test_smoke_refuses_non_loopback_or_ambiguous_portal_urls(base_url):
    with pytest.raises(smoke.SmokeFailure, match="loopback"):
        with smoke.smoke_environment(base_url):
            pytest.fail("Unsafe portal URL accepted")


def test_missing_browser_fails_without_downloading_and_cleans_temporary_data(monkeypatch, tmp_path):
    browser_dir = tmp_path / "empty-browsers"
    browser_dir.mkdir()
    monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", str(browser_dir))
    monkeypatch.setattr(smoke.tempfile, "tempdir", str(tmp_path))
    with pytest.raises(smoke.SmokeFailure, match="Chromium runtime missing/not ready"):
        smoke.run_smoke()
    assert list(browser_dir.iterdir()) == []
    assert list(tmp_path.glob("dmc-local-smoke-*")) == []
