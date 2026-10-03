#!/usr/bin/env python3
"""Package a verified Fluidd build with stable, nginx-readable ZIP metadata."""

import argparse
import json
import os
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


def build(dist: Path, output: Path) -> None:
    version = (dist / ".version").read_text(encoding="utf-8").strip()
    overlay = (dist / "k2-ui-overlay-support.txt").read_text(encoding="utf-8").strip()
    release = json.loads((dist / "release_info.json").read_text(encoding="utf-8"))
    if version != "v1.37.4" or overlay != "7":
        raise ValueError("Expected Jacob Fluidd v1.37.4 with UI overlay 7")
    if release.get("project_owner") != "Jacob10383" or release.get("version") != version:
        raise ValueError("Fluidd release metadata does not identify Jacob v1.37.4")
    if not (dist / "index.html").is_file() or not (dist / "sw.js").is_file():
        raise ValueError("Fluidd build is missing index.html or sw.js")

    files = sorted(path for path in dist.rglob("*") if path.is_file())
    temporary = output.with_name(output.name + ".new")
    try:
        with ZipFile(temporary, "w", compression=ZIP_DEFLATED, compresslevel=9) as archive:
            for path in files:
                name = path.relative_to(dist).as_posix()
                info = ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
                info.create_system = 3
                info.external_attr = 0o100644 << 16
                info.compress_type = ZIP_DEFLATED
                archive.writestr(info, path.read_bytes(), compress_type=ZIP_DEFLATED, compresslevel=9)
        os.replace(temporary, output)
    finally:
        if temporary.exists():
            temporary.unlink()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dist", type=Path, help="Fluidd dist directory")
    parser.add_argument("output", type=Path, help="Bundled Fluidd ZIP path")
    arguments = parser.parse_args()
    build(arguments.dist, arguments.output)
