"""Smoke-test Windows GUI builds with isolated preferences and graceful exit."""
from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time

import psutil


def windows_for(pid: int) -> list[int]:
    user = ctypes.WinDLL("user32", use_last_error=True)
    found = []
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    @callback_type
    def collect(hwnd, _param):
        owner = wintypes.DWORD()
        user.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value == pid and user.IsWindowVisible(hwnd):
            found.append(int(hwnd))
        return True

    user.EnumWindows(collect, 0)
    return found


def quit_owned_process(proc: subprocess.Popen, exe: Path) -> None:
    if proc.poll() is not None:
        return
    owner = psutil.Process(proc.pid)
    if Path(owner.exe()).resolve() != exe.resolve():
        raise RuntimeError("Process identity changed; refusing to send WM_QUIT")
    user = ctypes.WinDLL("user32", use_last_error=True)
    user.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user.GetWindowThreadProcessId.restype = wintypes.DWORD
    user.PostThreadMessageW.argtypes = [wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    user.PostThreadMessageW.restype = wintypes.BOOL
    gui_threads = {user.GetWindowThreadProcessId(hwnd, None) for hwnd in windows_for(proc.pid)}
    if not gui_threads:
        raise RuntimeError("Owned process has no visible GUI thread to quit gracefully")
    for thread in gui_threads:
        if not user.PostThreadMessageW(thread, 0x0012, 0, 0):  # WM_QUIT on GUI only
            raise ctypes.WinError(ctypes.get_last_error())
    proc.wait(timeout=20)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, required=True)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--config-dir-name", default="")
    args = parser.parse_args()
    exe = args.exe.resolve(strict=True)
    args.evidence_root.mkdir(parents=True, exist_ok=True)
    results = []
    for mode, argv in (("pet", []), ("settings", ["--settings"])):
        with tempfile.TemporaryDirectory(prefix=mode + "-", dir=args.evidence_root) as base:
            env = {**os.environ, "APPDATA": base, "LOCALAPPDATA": base,
                   "QT_QPA_PLATFORM": "windows"}
            # Helpers stay windowless; Qt creates the real application window.
            proc = subprocess.Popen([str(exe), *argv], cwd=exe.parent, env=env,
                                    creationflags=subprocess.CREATE_NO_WINDOW)
            started = time.monotonic()
            try:
                deadline = started + 30
                windows = []
                while time.monotonic() < deadline:
                    if proc.poll() is not None:
                        raise RuntimeError(f"{mode} exited early: {proc.returncode}")
                    windows = windows_for(proc.pid)
                    if windows:
                        break
                    time.sleep(0.1)
                if not windows:
                    raise RuntimeError(f"No visible {mode} window within 30s")
                if mode == "settings":
                    lock = Path(base) / (args.config_dir_name or exe.stem) / "settings.lock"
                    if not lock.exists():
                        raise RuntimeError("Settings window did not acquire isolated settings.lock")
                results.append({"mode": mode, "pid": proc.pid, "windows": windows,
                                "startup_seconds": round(time.monotonic() - started, 3),
                                "isolated_config": True})
            finally:
                quit_owned_process(proc, exe)
            if proc.returncode != 0:
                raise RuntimeError(f"{mode} graceful exit returned {proc.returncode}")
    record = {"result": "PASS", "exe": str(exe), "results": results}
    (args.evidence_root / "startup.json").write_text(
        json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(record))


if __name__ == "__main__":
    main()
