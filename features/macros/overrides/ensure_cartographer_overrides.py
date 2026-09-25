#!/usr/bin/env python3
"""Add and organize user-editable Cartographer settings in overrides.cfg."""

import os
import re
import stat
import sys
import tempfile
from typing import List, Optional, Tuple


SECTION_RE = re.compile(r"^[ \t]*\[([^]]+)\][ \t]*(?:#.*)?$", re.I)
OPTION_RE_TEMPLATE = r"^[ \t]*%s[ \t]*:"
PROBE_COUNT_LINE_RE = re.compile(
    r"^[ \t]*probe_count[ \t]*:[ \t]*([0-9]+[ \t]*,[ \t]*[0-9]+).*$",
    re.I,
)
SPEED_LINE_RE = re.compile(
    r"^[ \t]*speed[ \t]*:[ \t]*([0-9]+(?:\.[0-9]+)?).*$",
    re.I,
)
STOCK_PROBE_COUNT = "19,19"
CARTOGRAPHER_PROBE_COUNT = "50,50"
LEGACY_MANAGED_SPEED_COMMENTS = (
    "150 recommended for lite firmware",
    "lite firmware: 150 recommended",
)

BED_MESH = "bed_mesh"
START_PRINT = "gcode_macro _START_PRINT_VARS"
CARTOGRAPHER_TOUCH = "cartographer touch"
CARTOGRAPHER_SCAN = "cartographer scan"
M191 = "gcode_macro _M191_VARS"
KAMP = "gcode_macro _KAMP_Settings"
KAMP_HEADING = "# User-selected KAMP settings. Preserved during KAMP reinstalls."

DISPLAY_ORDER = (
    "virtual_sdcard",
    BED_MESH,
    START_PRINT,
    CARTOGRAPHER_TOUCH,
    CARTOGRAPHER_SCAN,
    M191,
    KAMP,
)


def _section_name(block: str) -> str:
    first_line = block.splitlines()[0]
    match = SECTION_RE.match(first_line)
    if not match:
        raise ValueError("invalid config section: %s" % first_line)
    return match.group(1).strip()


def _split(contents: str) -> Tuple[str, List[str]]:
    lines = contents.splitlines(keepends=True)
    starts = [
        index
        for index, line in enumerate(lines)
        if SECTION_RE.match(line.rstrip("\r\n"))
    ]
    if not starts:
        return contents, []

    preamble = "".join(lines[: starts[0]])
    blocks = []
    for position, start in enumerate(starts):
        end = starts[position + 1] if position + 1 < len(starts) else len(lines)
        blocks.append("".join(lines[start:end]))
    return preamble, blocks


def _find(blocks: List[str], name: str) -> Optional[int]:
    matches = [
        index
        for index, block in enumerate(blocks)
        if _section_name(block).casefold() == name.casefold()
    ]
    if len(matches) > 1:
        raise ValueError("multiple [%s] sections were found" % name)
    return matches[0] if matches else None


def _has_option(block: str, option: str) -> bool:
    option_re = re.compile(OPTION_RE_TEMPLATE % re.escape(option), re.I)
    return any(option_re.match(line) for line in block.splitlines()[1:])


def _add_option(block: str, line: str, after: Optional[str] = None) -> str:
    newline = "\r\n" if "\r\n" in block else "\n"
    lines = block.splitlines(keepends=True)
    insertion = 1
    if after:
        after_re = re.compile(OPTION_RE_TEMPLATE % re.escape(after), re.I)
        for index, existing in enumerate(lines[1:], 1):
            if after_re.match(existing):
                insertion = index + 1
                break
    lines.insert(insertion, line + newline)
    return "".join(lines)


def _ensure_section(blocks: List[str], name: str, newline: str) -> int:
    index = _find(blocks, name)
    if index is not None:
        return index
    blocks.append("[%s]%s" % (name, newline))
    return len(blocks) - 1


def _normalize_bed_mesh_presentation(block: str) -> str:
    newline = "\r\n" if "\r\n" in block else "\n"
    rendered = []
    for raw in block.splitlines(keepends=True):
        body = raw.rstrip("\r\n")
        probe_count = PROBE_COUNT_LINE_RE.match(body)
        if probe_count:
            value = re.sub(r"[ \t]*,[ \t]*", ",", probe_count.group(1))
            if value == STOCK_PROBE_COUNT:
                value = CARTOGRAPHER_PROBE_COUNT
            rendered.append(
                "probe_count: {:<24} # Cartographer default: 50,50{}".format(
                    value, newline
                )
            )
            continue
        speed = SPEED_LINE_RE.match(body)
        if speed:
            value = speed.group(1)
            if value == "200" and any(
                marker in body.casefold() for marker in LEGACY_MANAGED_SPEED_COMMENTS
            ):
                value = "150"
            rendered.append(
                "speed: {:<30} # 200 can be set for Full firmware{}".format(
                    value, newline
                )
            )
            continue
        rendered.append(raw)
    return "".join(rendered)


def _organize(preamble: str, blocks: List[str], newline: str) -> str:
    # configure_kamp_settings.py writes this managed heading immediately before
    # the KAMP section. Section parsing normally associates inter-section
    # comments with the preceding block, so detach the known heading first and
    # render it with KAMP after the blocks are reordered.
    kamp_heading_present = any(KAMP_HEADING in block for block in blocks)
    if kamp_heading_present:
        cleaned = []
        for block in blocks:
            lines = [
                line
                for line in block.splitlines(keepends=True)
                if line.rstrip("\r\n") != KAMP_HEADING
            ]
            cleaned.append("".join(lines))
        blocks = cleaned

    ordered = []
    used = set()
    for desired in DISPLAY_ORDER:
        index = _find(blocks, desired)
        if index is not None:
            rendered = blocks[index].strip("\r\n")
            if desired == KAMP and kamp_heading_present:
                rendered = KAMP_HEADING + newline + rendered
            ordered.append(rendered)
            used.add(index)
    ordered.extend(
        block.strip("\r\n")
        for index, block in enumerate(blocks)
        if index not in used
    )

    prefix = preamble.rstrip("\r\n")
    rendered = (newline * 2).join(ordered)
    if prefix:
        rendered = prefix + newline * 2 + rendered
    return rendered + newline


def ensure_defaults(contents: str) -> Tuple[str, bool]:
    newline = "\r\n" if "\r\n" in contents else "\n"
    preamble, blocks = _split(contents)

    bed_index = _ensure_section(blocks, BED_MESH, newline)
    if not _has_option(blocks[bed_index], "probe_count"):
        blocks[bed_index] = _add_option(
            blocks[bed_index],
            "probe_count: 50,50                  # Cartographer default: 50,50",
        )
    if not _has_option(blocks[bed_index], "speed"):
        blocks[bed_index] = _add_option(
            blocks[bed_index],
            "speed: 150                         # 200 can be set for Full firmware",
            after="probe_count",
        )
    blocks[bed_index] = _normalize_bed_mesh_presentation(blocks[bed_index])

    touch_index = _ensure_section(blocks, CARTOGRAPHER_TOUCH, newline)
    if not _has_option(blocks[touch_index], "max_noisy_samples"):
        blocks[touch_index] = _add_option(
            blocks[touch_index],
            "max_noisy_samples: 2               # Maximum noisy samples allowed during Touch",
        )

    scan_index = _ensure_section(blocks, CARTOGRAPHER_SCAN, newline)
    if not _has_option(blocks[scan_index], "mesh_runs"):
        blocks[scan_index] = _add_option(
            blocks[scan_index],
            "mesh_runs: 1                       # Number of scan passes used for each mesh",
        )
    if not _has_option(blocks[scan_index], "mesh_path"):
        blocks[scan_index] = _add_option(
            blocks[scan_index],
            "mesh_path: spiral                   # Continuous spiral scanning path",
            after="mesh_runs",
        )

    updated = _organize(preamble, blocks, newline)
    return updated, updated != contents


def main() -> int:
    path = os.path.expanduser(
        sys.argv[1]
        if len(sys.argv) > 1
        else "~/printer_data/config/custom/overrides.cfg"
    )
    if not os.path.isfile(path):
        return 0

    with open(path, "r", encoding="utf-8", newline="") as handle:
        original = handle.read()

    try:
        updated, changed = ensure_defaults(original)
    except ValueError as exc:
        sys.stderr.write("ERROR: could not organize Cartographer overrides: %s\n" % exc)
        return 1
    if not changed:
        return 0

    mode = stat.S_IMODE(os.stat(path).st_mode)
    directory = os.path.dirname(path) or "."
    fd, temporary = tempfile.mkstemp(
        prefix=".cartographer-overrides-", dir=directory, text=True
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(updated)
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)

    print("I: organized user-editable Cartographer settings in overrides.cfg")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
