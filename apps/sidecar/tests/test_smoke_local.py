from __future__ import annotations

import ctypes
import json
import os
import sys
import threading
import time
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


def test_exited_parent_live_descendant_does_not_block_cleanup(tmp_path):
    # The descendant inherits both pipes and self-exits, so RED cannot leak it.
    image = ctypes.create_unicode_buffer(32768)
    assert ctypes.windll.kernel32.GetModuleFileNameW(None, image, len(image))
    code = f"import subprocess; subprocess.Popen([{image.value!r},'-c','import time; time.sleep(14)'])"
    client = smoke.SidecarProcess([sys.executable, "-u", "-c", code], env=os.environ.copy(), cwd=tmp_path)
    client.process.wait(timeout=5)
    assert client.process.poll() is not None
    assert all(reader.is_alive() for reader in client.readers)
    errors = []

    def close():
        try:
            client.close()
        except Exception as exc:
            errors.append(exc)

    closer = threading.Thread(target=close, daemon=True)
    started = time.monotonic()
    closer.start()
    closer.join(timeout=8)
    finished_in_time = not closer.is_alive()
    # Let the finite RED probe retire naturally instead of killing a stale PID.
    closer.join(timeout=16)
    assert finished_in_time, f"cleanup blocked for {time.monotonic() - started:.1f}s after parent exited"
    assert not errors
    assert all(not reader.is_alive() for reader in client.readers)
    assert all(stream.closed for stream in (client.process.stdin, client.process.stdout, client.process.stderr))


def test_job_cleanup_waits_for_owned_descendant_to_release_exclusive_file(tmp_path):
    profile = tmp_path / "profile"
    profile.mkdir()
    locked = profile / "chrome_debug.log"
    ready = tmp_path / "ready"
    image = ctypes.create_unicode_buffer(32768)
    assert ctypes.windll.kernel32.GetModuleFileNameW(None, image, len(image))
    child = (
        "import ctypes,os,time; from ctypes import wintypes; from pathlib import Path; "
        "api=ctypes.WinDLL('kernel32',use_last_error=True); "
        "api.CreateFileW.argtypes=[wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,ctypes.c_void_p,"
        "wintypes.DWORD,wintypes.DWORD,wintypes.HANDLE]; api.CreateFileW.restype=wintypes.HANDLE; "
        f"handle=api.CreateFileW({str(locked)!r},0x40000000,0,None,2,0x80,None); "
        f"assert handle not in (None,-1); Path({str(ready)!r}).write_text(str(os.getpid())); time.sleep(30)"
    )
    parent = (
        "import subprocess; "
        f"subprocess.Popen([{image.value!r},'-u','-c',{child!r}],stdin=subprocess.DEVNULL,"
        "stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)"
    )
    client = smoke.SidecarProcess([sys.executable, "-u", "-c", parent], env=os.environ.copy(), cwd=tmp_path)
    client.process.wait(timeout=5)
    deadline = time.monotonic() + 5
    while not ready.exists() and time.monotonic() < deadline:
        time.sleep(0.01)
    assert ready.exists()
    child_pid = int(ready.read_text())
    api = client.ownership.api
    api.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
    api.OpenProcess.restype = ctypes.c_void_p
    api.IsProcessInJob.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_int)]
    api.IsProcessInJob.restype = ctypes.c_int
    child_handle = api.OpenProcess(0x1000, False, child_pid)
    assert child_handle
    in_job = ctypes.c_int()
    assert api.IsProcessInJob(child_handle, client.ownership.handle, ctypes.byref(in_job))
    api.CloseHandle(child_handle)
    assert in_job.value == 1
    with pytest.raises(PermissionError):
        locked.unlink()

    client.close()
    smoke._remove_temporary_root(profile)

    assert not profile.exists()
    assert all(not reader.is_alive() for reader in client.readers)


def test_job_cleanup_waits_for_zero_active_processes_before_closing_handle():
    events = []
    counts = [2, 1, 0]

    class FakeApi:
        def TerminateJobObject(self, handle, exit_code):
            events.append(("terminate", handle, exit_code))
            return True

        def QueryInformationJobObject(self, handle, info_class, accounting, size, returned):
            events.append(("query", handle, info_class))
            accounting._obj.ActiveProcesses = counts.pop(0)
            returned._obj.value = size
            return True

        def CloseHandle(self, handle):
            events.append(("close", handle))
            return True

    job = smoke.WindowsProcessJob.__new__(smoke.WindowsProcessJob)
    job.api = FakeApi()
    job.handle = 123

    job.close()
    job.close()

    assert events == [
        ("terminate", 123, 1),
        ("query", 123, 1),
        ("query", 123, 1),
        ("query", 123, 1),
        ("close", 123),
    ]
    assert job.handle is None


def test_store_alias_descendant_fails_boundedly_if_broker_escapes_job(tmp_path):
    # Store aliases may launch via a broker, not as an OS descendant. Never
    # chase/kill these by PID. A finite child allows observing bounded failure.
    code = "import subprocess,sys; subprocess.Popen([sys.executable,'-u','-c','import os,time; print(os.getpid(),flush=True); time.sleep(7)'])"
    client = smoke.SidecarProcess([sys.executable, "-u", "-c", code], env=os.environ.copy(), cwd=tmp_path)
    child_pid = int(client.lines.get(timeout=5))
    client.process.wait(timeout=5)
    api = client.ownership.api
    api.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
    api.OpenProcess.restype = ctypes.c_void_p
    api.IsProcessInJob.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_int)]
    api.IsProcessInJob.restype = ctypes.c_int
    # Query/synchronize rights only; this test never terminates by process ID.
    handle = api.OpenProcess(0x1000 | 0x100000, False, child_pid)
    assert handle
    in_job = ctypes.c_int()
    assert api.IsProcessInJob(handle, client.ownership.handle, ctypes.byref(in_job))
    api.CloseHandle(handle)
    errors = []

    def close():
        try:
            client.close()
        except Exception as exc:
            errors.append(exc)

    closer = threading.Thread(target=close, daemon=True)
    closer.start()
    closer.join(timeout=5)
    finished_in_time = not closer.is_alive()
    # Any unrelated finite broker process retires naturally; then reap readers.
    for reader in client.readers:
        reader.join(timeout=10)
    closer.join(timeout=2)
    client.close()
    assert finished_in_time, "Alias cleanup hung instead of succeeding or failing within its bound"
    if in_job.value:
        assert not errors  # Ordinary Python has no broker escape to exercise.
    else:
        assert len(errors) == 1 and isinstance(errors[0], smoke.SmokeFailure)
        assert "pipe readers did not stop" in str(errors[0])
    assert all(not reader.is_alive() for reader in client.readers)
    assert all(stream.closed for stream in (client.process.stdin, client.process.stdout, client.process.stderr))


def test_failed_job_assignment_never_launches_command_and_reaps_gate(monkeypatch, tmp_path):
    processes = []

    def fail_assignment(self, process):
        processes.append(process)
        raise OSError("injected assignment failure")

    monkeypatch.setattr(smoke.WindowsProcessJob, "_assign", fail_assignment)
    code = "from pathlib import Path; Path('must-not-run').touch()"
    with pytest.raises(OSError, match="injected assignment failure"):
        smoke.SidecarProcess([sys.executable, "-c", code], env=os.environ.copy(), cwd=tmp_path)
    assert not (tmp_path / "must-not-run").exists()
    assert len(processes) == 1 and processes[0].poll() is not None
    assert all(stream.closed for stream in (processes[0].stdin, processes[0].stdout, processes[0].stderr))


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
