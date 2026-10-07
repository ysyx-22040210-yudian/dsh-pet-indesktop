"""Bundle the OpenSSL DLLs actually loaded by the build interpreter on Windows."""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
from pathlib import Path
import shutil
import ssl
import sys


def loaded_ssl_sources() -> list[Path]:
    if sys.platform != "win32":
        raise RuntimeError("Windows OpenSSL bundling requires a Windows interpreter")
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetModuleHandleW.argtypes = [ctypes.c_wchar_p]
    kernel.GetModuleHandleW.restype = ctypes.c_void_p
    kernel.GetModuleFileNameW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_uint]
    kernel.GetModuleFileNameW.restype = ctypes.c_uint
    sources = []
    for name in ("libcrypto-3-x64.dll", "libssl-3-x64.dll"):
        handle = kernel.GetModuleHandleW(name)
        if not handle:
            raise RuntimeError(f"Build Python did not load {name}: {ssl.OPENSSL_VERSION}")
        buf = ctypes.create_unicode_buffer(32768)
        length = kernel.GetModuleFileNameW(handle, buf, len(buf))
        if not length or length >= len(buf):
            raise ctypes.WinError(ctypes.get_last_error())
        source = Path(buf.value).resolve(strict=True)
        sources.append(source)
    return sources


def bundle_ssl(internal: Path) -> dict:
    internal = internal.resolve(strict=True)
    import _ssl

    sources = [Path(_ssl.__file__).resolve(strict=True), *loaded_ssl_sources()]
    files = []
    for source in sources:
        target = internal / source.name
        if source != target:
            shutil.copy2(source, target)
        source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
        if hashlib.sha256(target.read_bytes()).hexdigest() != source_hash:
            raise RuntimeError(f"SSL copy hash mismatch: {target}")
        files.append({"source": str(source), "target": str(target), "sha256": source_hash})
    return {"python": sys.executable, "openssl": ssl.OPENSSL_VERSION, "files": files}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--internal", type=Path, required=True)
    parser.add_argument("--record", type=Path)
    args = parser.parse_args()
    result = bundle_ssl(args.internal)
    encoded = json.dumps(result, ensure_ascii=False, indent=2)
    if args.record:
        args.record.write_text(encoded + "\n", encoding="utf-8")
    print(encoded)


if __name__ == "__main__":
    main()
