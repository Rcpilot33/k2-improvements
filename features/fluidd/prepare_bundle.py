#!/usr/bin/env python3
"""Validate a complete K2 Fluidd build before touching the installed UI."""
import argparse
import json
import hashlib
from pathlib import Path, PurePosixPath
import stat
from zipfile import ZipFile


def prepare(archive, staging):
    staging = Path(staging)
    if not staging.is_dir() or any(staging.iterdir()):
        raise ValueError("Staging must be an empty directory")
    with ZipFile(archive) as bundle:
        for entry in bundle.infolist():
            path = PurePosixPath(entry.filename)
            if (path.is_absolute() or '..' in path.parts or '\\' in entry.filename
                    or ':' in entry.filename or stat.S_ISLNK(entry.external_attr >> 16)):
                raise ValueError("Unsafe ZIP entry: " + entry.filename)
        release = json.loads(bundle.read("release_info.json"))
        version = bundle.read(".version").decode().strip()
        if (release.get("project_owner") != "Rcpilot33" or
                release.get("project_name") != "fluidd" or release.get("version") != version):
            raise ValueError("Expected matching Rcpilot33 Fluidd release metadata")
        if (bundle.read("k2-ui-overlay-support.txt").rstrip(b"\n") != b"8" or
                bundle.read("k2-settings-api.txt").decode().strip() != "1" or
                bundle.read("k2-device-cards-api.txt").decode().strip() != "1"):
            raise ValueError("Build does not include the consolidated K2 dialogs and device cards")
        for required in ("index.html", "sw.js"):
            if not bundle.read(required):
                raise ValueError("Missing Fluidd entry point: " + required)
        bundle.extractall(staging)
    digest = hashlib.sha256()
    with Path(archive).open('rb') as source:
        for chunk in iter(lambda: source.read(65536), b''):
            digest.update(chunk)
    (staging / 'k2-installed-build.json').write_text(
        json.dumps({'sha256': digest.hexdigest()}) + '\n', encoding='utf-8')
    # mktemp creates this directory as 0700. rglob only visits its children;
    # nginx must also be able to traverse the UI root after the directory swap.
    staging.chmod(0o755)
    for path in staging.rglob('*'):
        path.chmod(0o755 if path.is_dir() else 0o644)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('staging', type=Path)
    args = parser.parse_args()
    prepare(args.archive, args.staging)
