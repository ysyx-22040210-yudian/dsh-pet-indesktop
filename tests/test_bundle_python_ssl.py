"""A contaminated search path must not determine packaged OpenSSL binaries."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.skipif(sys.platform != "win32", reason="Windows DLL packaging")
def test_ssl_bundle_uses_loaded_interpreter_binaries_and_imports_cleanly(tmp_path):
    internal = tmp_path / "_internal"
    internal.mkdir()
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    for name in ("libssl-3-x64.dll", "libcrypto-3-x64.dll"):
        (foreign / name).write_bytes(b"wrong DLL from PATH")
        (internal / name).write_bytes(b"stale collected DLL")
    record = tmp_path / "ssl.json"
    env = {**os.environ, "PATH": str(foreign) + os.pathsep + os.environ.get("PATH", "")}
    helper = Path(__file__).resolve().parents[1] / "scripts" / "bundle_python_ssl.py"
    subprocess.run([sys.executable, str(helper), "--internal", str(internal),
                    "--record", str(record)], env=env, check=True, capture_output=True)
    evidence = json.loads(record.read_text(encoding="utf-8"))
    assert len(evidence["files"]) == 3
    for item in evidence["files"]:
        assert Path(item["source"]).parent != foreign
        assert hashlib.sha256(Path(item["target"]).read_bytes()).hexdigest() == item["sha256"]
    # Load the copied extension in a fresh process; no prior ssl import can hide a bad copy.
    probe = """
import ctypes, importlib.util, os, pathlib, sys
root = pathlib.Path(sys.argv[1])
handle = os.add_dll_directory(str(root))
dlls = [ctypes.WinDLL(str(root / n)) for n in ('libcrypto-3-x64.dll', 'libssl-3-x64.dll')]
spec = importlib.util.spec_from_file_location('_ssl', root / '_ssl.pyd')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
import ssl
context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
assert context.verify_mode == ssl.CERT_REQUIRED
print(mod.OPENSSL_VERSION)
"""
    loaded = subprocess.run([sys.executable, "-I", "-c", probe, str(internal)],
                            env=env, check=True, capture_output=True, text=True)
    assert loaded.stdout.strip() == evidence["openssl"]
