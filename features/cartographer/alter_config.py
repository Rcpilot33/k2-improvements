#!/usr/bin/env python3
"""Move the stock PR Touch section aside without damaging SAVE_CONFIG."""

import os
import re
import shutil
import stat
import sys
import tempfile


SECTION_RE = re.compile(r"^\s*\[(.*?)\]\s*$")
SAVE_CONFIG_RE = re.compile(r"^\s*#\*#")


def write_atomic(path, contents, source_mode=None):
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)
    if source_mode is None:
        source_mode = 0o644
        if os.path.exists(path):
            source_mode = stat.S_IMODE(os.stat(path).st_mode)
    descriptor, temporary = tempfile.mkstemp(
        prefix=".cartographer-config-", dir=directory, text=True
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as output:
            output.write(contents)
            output.flush()
            os.fsync(output.fileno())
        os.chmod(temporary, source_mode)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def split_section(contents, section_to_remove):
    removed_lines = []
    kept_lines = []
    in_target_section = False
    found_section = False

    for line in contents.splitlines(keepends=True):
        section_match = SECTION_RE.match(line)
        if section_match:
            in_target_section = (
                section_match.group(1).strip().casefold()
                == section_to_remove.casefold()
            )
            found_section = found_section or in_target_section
        elif in_target_section and SAVE_CONFIG_RE.match(line):
            # Klipper's generated block is comment-prefixed rather than a real
            # section. It and everything after it must remain in printer.cfg.
            in_target_section = False

        if in_target_section:
            removed_lines.append(line)
        else:
            kept_lines.append(line)

    return "".join(kept_lines), "".join(removed_lines), found_section


def remove_section_from_ini(
    input_file: str,
    section_to_remove: str,
    backup_dir: str = "backup",
) -> tuple[bool, str]:
    """Remove one section, preserving a copy and Klipper's SAVE_CONFIG block."""
    try:
        input_file = os.path.realpath(os.path.expanduser(input_file))
        backup_dir = os.path.realpath(os.path.expanduser(backup_dir))
        os.makedirs(backup_dir, exist_ok=True)

        with open(input_file, "r", encoding="utf-8", newline="") as source:
            contents = source.read()
        kept, removed, found = split_section(contents, section_to_remove)
        if not found:
            return False, "Section '%s' not found in %s" % (
                section_to_remove,
                input_file,
            )

        mode = stat.S_IMODE(os.stat(input_file).st_mode)
        section_backup = os.path.join(backup_dir, section_to_remove + ".cfg")
        write_atomic(section_backup, removed)

        original_backup = input_file + ".before-cartographer.bak"
        if not os.path.exists(original_backup):
            shutil.copy2(input_file, original_backup)

        write_atomic(input_file, kept, source_mode=mode)
        return True, (
            "Section removed successfully. Backup saved to %s; original saved to %s"
            % (section_backup, original_backup)
        )
    except Exception as exc:
        return False, "Error: %s" % exc


def main():
    success, message = remove_section_from_ini(
        "~/printer_data/config/printer.cfg",
        "prtouch_v3",
        "~/printer_data/config/custom",
    )
    print(message)
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
