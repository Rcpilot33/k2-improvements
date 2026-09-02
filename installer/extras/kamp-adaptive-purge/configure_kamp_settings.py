#!/usr/bin/env python3
"""Review and persist K2 Plus KAMP settings in custom/overrides.cfg.

An optional third input is the installed legacy kamp_settings.cfg.  Older
versions told users to customize that file directly.  Import it before the
installer replaces the maintained defaults so those values survive the first
tracker-aware refresh.
"""

import math
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Dict, NoReturn, Set


SECTION = "gcode_macro _KAMP_Settings"
SETTINGS = (
    ("variable_verbose_enable", "Verbose console messages", "bool", None),
    (
        "variable_stock_purge_fallback",
        "Stock purge if object data is missing (0/1)",
        "flag",
        None,
    ),
    ("variable_purge_height", "Purge height (mm)", "float", lambda value: value > 0),
    ("variable_tip_distance", "Filament tip distance (mm)", "float", lambda value: value >= 0),
    ("variable_purge_margin", "Distance from print boundary (mm)", "float", lambda value: value > 0),
    ("variable_purge_amount", "Filament to purge (mm)", "float", lambda value: value > 0),
    ("variable_flow_rate", "Purge flow rate (mm^3/s)", "float", lambda value: value > 0),
)
SETTING_KEYS = {item[0] for item in SETTINGS}
SECTION_RE = re.compile(r"^\s*\[([^]]+)]\s*(?:[#;].*)?$")
OPTION_RE = re.compile(r"^(\s*)([A-Za-z0-9_]+)(\s*:\s*)(.*?)(\s*(?:[#;].*)?)$")


def fail(message: str) -> NoReturn:
    print("E: {}".format(message), file=sys.stderr)
    raise SystemExit(1)


def section_values(path: Path) -> Dict[str, str]:
    if not path.exists():
        return {}
    values = {}
    active = False
    for raw in path.read_text(encoding="utf-8").splitlines():
        match = SECTION_RE.match(raw)
        if match:
            active = match.group(1).strip().lower() == SECTION.lower()
            continue
        if not active:
            continue
        match = OPTION_RE.match(raw)
        if match and match.group(2) in SETTING_KEYS:
            values[match.group(2)] = match.group(4).strip()
    return values


def normalize_bool(value: str) -> str:
    lowered = value.strip().lower()
    if lowered in {"true", "yes", "y", "1", "on"}:
        return "True"
    if lowered in {"false", "no", "n", "0", "off"}:
        return "False"
    raise ValueError("enter True or False")


def normalize_flag(value: str) -> str:
    lowered = value.strip().lower()
    if lowered in {"1", "true", "yes", "y", "on"}:
        return "1"
    if lowered in {"0", "false", "no", "n", "off"}:
        return "0"
    raise ValueError("enter 0 or 1")


def normalize_number(value: str, validator) -> str:
    number = float(value)
    if not math.isfinite(number) or not validator(number):
        raise ValueError("value is outside the allowed range")
    return format(number, "g")


def normalized(key: str, value: str) -> str:
    for setting_key, _label, kind, validator in SETTINGS:
        if key != setting_key:
            continue
        if kind == "bool":
            return normalize_bool(value)
        if kind == "flag":
            return normalize_flag(value)
        return normalize_number(value, validator)
    raise ValueError("unknown setting {}".format(key))


def effective_values(
    defaults: Dict[str, str], legacy: Dict[str, str], existing: Dict[str, str]
) -> Dict[str, str]:
    """Return normalized settings with overrides > legacy > current defaults."""
    effective = {}
    for key, *_rest in SETTINGS:
        value = existing.get(key, legacy.get(key, defaults[key]))
        effective[key] = normalized(key, value)
    return effective


def display(values: Dict[str, str]) -> None:
    print("")
    print("KAMP settings")
    print("-------------")
    for key, label, _kind, _validator in SETTINGS:
        print("  {:<38} {}".format(label, values[key]))
    print("")


def prompt_values(values: Dict[str, str]) -> Dict[str, str]:
    display(values)
    answer = input("Keep these settings? [Y/n] ").strip().lower()
    if answer not in {"n", "no"}:
        return values

    updated = dict(values)
    print("Press Enter at any prompt to keep the displayed value.")
    print("")
    for key, label, _kind, _validator in SETTINGS:
        while True:
            answer = input("{} [{}]: ".format(label, updated[key])).strip()
            if not answer:
                break
            try:
                updated[key] = normalized(key, answer)
                break
            except (TypeError, ValueError) as exc:
                print("  Invalid value: {}".format(exc))
    display(updated)
    return updated


def update_overrides(path: Path, values: Dict[str, str]) -> None:
    original = path.read_text(encoding="utf-8") if path.exists() else ""
    lines = original.splitlines(keepends=True)
    section_start = None
    section_end = len(lines)

    for index, raw in enumerate(lines):
        match = SECTION_RE.match(raw.rstrip("\r\n"))
        if not match:
            continue
        if match.group(1).strip().lower() == SECTION.lower():
            if section_start is not None:
                fail("multiple [{}] sections found in {}".format(SECTION, path))
            section_start = index
        elif section_start is not None and section_end == len(lines):
            section_end = index

    if section_start is None:
        if lines and lines[-1].strip():
            lines.append("\n")
        lines.extend(
            [
                "# User-selected KAMP settings. Preserved during KAMP reinstalls.\n",
                "[{}]\n".format(SECTION),
            ]
        )
        lines.extend("{}: {}\n".format(key, values[key]) for key, *_rest in SETTINGS)
        lines.append("\n")
    else:
        found: Set[str] = set()
        for index in range(section_start + 1, section_end):
            raw = lines[index]
            ending = "\r\n" if raw.endswith("\r\n") else "\n"
            match = OPTION_RE.match(raw.rstrip("\r\n"))
            if not match or match.group(2) not in SETTING_KEYS:
                continue
            key = match.group(2)
            lines[index] = "{}{}{}{}{}{}".format(
                match.group(1), key, match.group(3), values[key], match.group(5), ending
            )
            found.add(key)

        missing = [key for key, *_rest in SETTINGS if key not in found]
        if missing:
            insert_at = section_end
            while insert_at > section_start + 1 and not lines[insert_at - 1].strip():
                insert_at -= 1
            lines[insert_at:insert_at] = [
                "{}: {}\n".format(key, values[key]) for key in missing
            ]

        section_limit = section_end + len(missing)
        index = section_start + 1
        while index < section_limit:
            if lines[index].strip():
                index += 1
                continue
            blank_start = index
            while index < section_limit and not lines[index].strip():
                index += 1
            previous = OPTION_RE.match(lines[blank_start - 1].rstrip("\r\n"))
            following = (
                OPTION_RE.match(lines[index].rstrip("\r\n"))
                if index < section_limit
                else None
            )
            if (
                previous
                and previous.group(2) in SETTING_KEYS
                and following
                and following.group(2) in SETTING_KEYS
            ):
                del lines[blank_start:index]
                section_limit -= index - blank_start
                index = blank_start

    path.parent.mkdir(parents=True, exist_ok=True)
    mode = path.stat().st_mode if path.exists() else None
    fd, temporary = tempfile.mkstemp(
        prefix=".{}.".format(path.name), dir=str(path.parent), text=True
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.writelines(lines)
        if mode is not None:
            os.chmod(temporary, mode)
        os.replace(temporary, str(path))
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main() -> None:
    if len(sys.argv) not in {3, 4}:
        fail(
            "usage: configure_kamp_settings.py "
            "DEFAULTS_CFG OVERRIDES_CFG [LEGACY_INSTALLED_CFG]"
        )

    defaults_path = Path(sys.argv[1]).expanduser()
    overrides_path = Path(sys.argv[2]).expanduser()
    legacy_path = Path(sys.argv[3]).expanduser() if len(sys.argv) == 4 else None
    defaults = section_values(defaults_path)
    missing = [key for key, *_rest in SETTINGS if key not in defaults]
    if missing:
        fail("missing KAMP defaults in {}: {}".format(defaults_path, ", ".join(missing)))

    legacy = section_values(legacy_path) if legacy_path is not None else {}
    existing = section_values(overrides_path)
    try:
        effective = effective_values(defaults, legacy, existing)
    except (TypeError, ValueError) as exc:
        fail("invalid existing KAMP override: {}".format(exc))

    if not sys.stdin.isatty():
        update_overrides(overrides_path, effective)
        if legacy:
            print("I: imported legacy KAMP settings from {}".format(legacy_path))
        print("I: non-interactive run; saved effective KAMP settings in {}".format(overrides_path))
        return

    selected = prompt_values(effective)
    update_overrides(overrides_path, selected)
    print("I: saved user-selected KAMP settings in {}".format(overrides_path))


if __name__ == "__main__":
    main()
