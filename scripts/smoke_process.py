"""Windows-only, handle-based ownership for the smoke's subprocess tree.

OS descendants are owned even after parent exit. Broker-activated unrelated
processes are not: callers must report bounded pipe-shutdown failure for those,
never enumerate/kill external processes. The smoke uses real executable images.
"""
from __future__ import annotations

import ctypes
import os
import subprocess
import sys
from ctypes import wintypes
from pathlib import Path


class _BasicLimits(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
        ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
        ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD), ("SchedulingClass", wintypes.DWORD),
    ]


class _ExtendedLimits(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", _BasicLimits), ("IoInfo", ctypes.c_uint64 * 6),
        ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


# A raw read consumes only the gate byte, never prefetched JSON-RPC input.
# No requested command can spawn before the wrapper is assigned to our job.
_GATED_COMMAND = (
    "import os,subprocess,sys\n"
    "if os.read(0, 1) != b'\\0': sys.exit(125)\n"
    "env = os.environ.copy()\n"
    "if sys.argv[1]: env['__PYVENV_LAUNCHER__'] = sys.argv[1]\n"
    "sys.exit(subprocess.call(sys.argv[2:], env=env, stdin=sys.stdin, stdout=sys.stdout, stderr=sys.stderr))\n"
)


class WindowsProcessJob:
    def __init__(self, command: list[str], *, env: dict[str, str], cwd: Path) -> None:
        if os.name != "nt":
            raise RuntimeError("Durable smoke process ownership currently requires Windows")
        self.api = ctypes.WinDLL("kernel32", use_last_error=True)
        self.api.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        self.api.CreateJobObjectW.restype = wintypes.HANDLE
        self.api.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
        self.api.SetInformationJobObject.restype = wintypes.BOOL
        self.api.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        self.api.AssignProcessToJobObject.restype = wintypes.BOOL
        self.api.CloseHandle.argtypes = [wintypes.HANDLE]
        self.api.CloseHandle.restype = wintypes.BOOL
        self.api.GetModuleFileNameW.argtypes = [wintypes.HMODULE, wintypes.LPWSTR, wintypes.DWORD]
        self.api.GetModuleFileNameW.restype = wintypes.DWORD
        image = ctypes.create_unicode_buffer(32768)
        length = self.api.GetModuleFileNameW(None, image, len(image))
        if not length or length >= len(image):
            raise ctypes.WinError(ctypes.get_last_error())
        # Bypass venv/Store activation redirectors: their actual interpreter may
        # be launched by a broker, outside our job. Preserve the current venv
        # using the same launcher environment mechanism as multiprocessing.
        launcher = ""
        if os.path.normcase(command[0]) == os.path.normcase(sys.executable):
            launcher = sys.executable
            command = [image.value, *command[1:]]
        # NULL security attributes make this job handle non-inheritable.
        self.handle = self.api.CreateJobObjectW(None, None)
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())
        process = None
        try:
            limits = _ExtendedLimits()
            limits.BasicLimitInformation.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            if not self.api.SetInformationJobObject(self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
                raise ctypes.WinError(ctypes.get_last_error())
            process = subprocess.Popen(
                [image.value, "-u", "-c", _GATED_COMMAND, launcher, *command],
                cwd=cwd, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, encoding="utf-8", errors="replace", creationflags=subprocess.CREATE_NO_WINDOW,
            )
            self._assign(process)
            assert process.stdin is not None
            process.stdin.write("\0")
            process.stdin.flush()
            self.process = process
        except BaseException:
            self.close()
            if process is not None:
                # Before assignment the wrapper can only wait for its gate.
                # EOF aborts it without launching the requested command.
                assert process.stdin is not None
                process.stdin.close()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    # Popen retains a live process HANDLE, never a stale PID.
                    process.kill()
                    process.wait(timeout=5)
                assert process.stdout is not None and process.stderr is not None
                process.stdout.close()
                process.stderr.close()
            raise

    def _assign(self, process: subprocess.Popen[str]) -> None:
        # CPython's Windows Popen handle remains valid even after process exit.
        if not self.api.AssignProcessToJobObject(self.handle, int(process._handle)):
            raise ctypes.WinError(ctypes.get_last_error())

    def close(self) -> None:
        if self.handle:
            if not self.api.CloseHandle(self.handle):
                raise ctypes.WinError(ctypes.get_last_error())
            self.handle = None
