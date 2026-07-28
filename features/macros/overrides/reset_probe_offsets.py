#!/usr/bin/env python3
"""Reset probe-dependent START_PRINT offsets during a Cartographer conversion."""

import os
import re
import stat
import sys
import tempfile


SECTION_RE = re.compile(r"^\s*\[gcode_macro\s+_START_PRINT_VARS\]\s*$", re.I)
OFFSET_RE = re.compile(
    r"^(\s*)(variable_offset_(PLA|PETG|ABS|ASA|DEFAULT|PROBE))"
    r"(\s*:\s*)([^#\r\n]*?)([ \t]*(?:#.*)?)$",
    re.I,
)


def main() -> int:
    path = os.path.expanduser(
        sys.argv[1]
        if len(sys.argv) > 1
        else "~/printer_data/config/custom/overrides.cfg"
    )
    if not os.path.isfile(path):
        return 0

    with open(path, "r", encoding="utf-8", newline="") as handle:
        lines = handle.readlines()

    in_start_vars = False
    changed = []
    updated = []

    for line in lines:
        body = line.rstrip("\r\n")
        newline = line[len(body) :]

        if body.lstrip().startswith("["):
            in_start_vars = bool(SECTION_RE.match(body))

        match = OFFSET_RE.match(body) if in_start_vars else None
        if not match:
            updated.append(line)
            continue

        old_value = match.group(5).strip()
        if old_value != "0":
            changed.append(match.group(3).upper())

        updated.append(
            "{}{}{}0{}{}".format(
                match.group(1),
                match.group(2),
                match.group(4),
                match.group(6),
                newline,
            )
        )

    if not changed:
        print("I: probe/material offsets are already zero in {}".format(path))
        return 0

    mode = stat.S_IMODE(os.stat(path).st_mode)
    directory = os.path.dirname(path) or "."
    fd, temp_path = tempfile.mkstemp(prefix=".overrides-", dir=directory, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.writelines(updated)
        os.chmod(temp_path, mode)
        os.replace(temp_path, path)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)

    print(
        "I: reset probe/material offsets for Cartographer conversion: {}".format(
            ", ".join(changed)
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
