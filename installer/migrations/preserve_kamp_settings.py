#!/usr/bin/env python3
"""Move legacy KAMP setting edits into the durable overrides file."""

import os
import re
import sys
import tempfile
from pathlib import Path


SECTION = "gcode_macro _kamp_settings"
SECTION_RE = re.compile(r"^\s*\[([^]]+)]\s*(?:[#;].*)?$")
OPTION_RE = re.compile(r"^(\s*)(variable_[A-Za-z0-9_]+)(\s*:\s*)(.*?)(\s*(?:[#;].*)?)$")


def section_values(path):
    values = {}
    active = False
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        section = SECTION_RE.match(raw)
        if section:
            active = section.group(1).strip().lower() == SECTION
            continue
        option = OPTION_RE.match(raw) if active else None
        if option:
            values[option.group(2)] = option.group(4).strip()
    return values


def update_overrides(path, legacy):
    if not legacy:
        return False
    original = path.read_text(encoding="utf-8") if path.exists() else ""
    lines = original.splitlines(keepends=True)
    start = None
    end = len(lines)
    for index, raw in enumerate(lines):
        section = SECTION_RE.match(raw.rstrip("\r\n"))
        if not section:
            continue
        if section.group(1).strip().lower() == SECTION:
            start = index
        elif start is not None:
            end = index
            break

    if start is None:
        if lines and lines[-1].strip():
            lines.append("\n")
        lines.extend([
            "# KAMP settings preserved by the installer updater.\n",
            "[gcode_macro _KAMP_Settings]\n",
        ])
        lines.extend("{}: {}\n".format(key, value) for key, value in legacy.items())
        lines.append("\n")
    else:
        found = set()
        for index in range(start + 1, end):
            raw = lines[index]
            option = OPTION_RE.match(raw.rstrip("\r\n"))
            if not option or option.group(2) not in legacy:
                continue
            # Existing overrides are already the user's durable choice and
            # therefore take precedence over edits in the legacy defaults.
            found.add(option.group(2))
        missing = [(key, value) for key, value in legacy.items() if key not in found]
        lines[end:end] = ["{}: {}\n".format(key, value) for key, value in missing]

    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".kamp.", dir=str(path.parent), text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.writelines(lines)
        os.replace(temporary, str(path))
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return True


def main():
    if len(sys.argv) != 3:
        raise SystemExit("usage: preserve_kamp_settings.py LEGACY_CFG OVERRIDES_CFG")
    legacy_path = Path(sys.argv[1]).expanduser()
    overrides_path = Path(sys.argv[2]).expanduser()
    legacy = section_values(legacy_path)
    if update_overrides(overrides_path, legacy):
        print("I: preserved legacy KAMP settings in {}".format(overrides_path))
    else:
        print("I: no legacy KAMP settings were found")


if __name__ == "__main__":
    main()
