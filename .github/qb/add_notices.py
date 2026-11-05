"""Add license files to repaired wheels: <name>.dist-info/licenses/<file> for each given file, RECORD updated.

Usage: python add_notices.py WHEEL [WHEEL ...] --add FILE [FILE ...]

delvewheel bundles the MinGW-w64 runtime and BLAS/LAPACK DLLs into tblite.libs/; their licenses (and
tblite's own COPYING/COPYING.LESSER, which the meson-python wheel does not carry) go next to the metadata.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import os
import shutil
import tempfile
import zipfile
from pathlib import Path


def record_line(name: str, data: bytes) -> str:
    digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode()
    return f"{name},sha256={digest},{len(data)}"


def add_files(wheel: Path, files: list[Path]) -> None:
    with zipfile.ZipFile(wheel) as zin:
        infos = zin.infolist()
        dist_info = next(i.filename.split("/")[0] for i in infos if i.filename.endswith(".dist-info/RECORD"))
        record_name = f"{dist_info}/RECORD"
        extra = {f"{dist_info}/licenses/{f.name}": f.read_bytes() for f in files}
        fd, tmp = tempfile.mkstemp(suffix=".whl", dir=wheel.parent)
        os.close(fd)
        with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED) as zout:
            record = []
            for info in infos:
                if info.filename == record_name or info.filename in extra:
                    continue
                data = zin.read(info)
                zout.writestr(info, data)
                if not info.is_dir():
                    record.append(record_line(info.filename, data))
            for name, data in extra.items():
                zout.writestr(name, data)
                record.append(record_line(name, data))
            record.append(f"{record_name},,")
            zout.writestr(record_name, "\n".join(record) + "\n")
    shutil.move(tmp, wheel)
    print(f"{wheel.name}: added {', '.join(extra)}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("wheels", nargs="+", type=Path)
    ap.add_argument("--add", nargs="+", type=Path, required=True)
    args = ap.parse_args()
    for wheel in args.wheels:
        add_files(wheel, args.add)


if __name__ == "__main__":
    main()
