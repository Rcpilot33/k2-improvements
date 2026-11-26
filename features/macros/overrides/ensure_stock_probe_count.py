"""Backfill the stock probe count from the installer seed on existing K2 Pros."""

from pathlib import Path
import re
import sys

from ensure_m191_settings import write_atomic


SECTION = re.compile(r"^[ \t]*\[([^\]]+)\][ \t]*(?:[#;].*)?$")
COUNT = re.compile(r"^[ \t]*probe_count[ \t]*[:=][^\r\n]*", re.I | re.M)


def ensure_count(contents, seed_line):
    newline = "\r\n" if "\r\n" in contents else "\n"
    lines = contents.splitlines(keepends=True)
    first_section = len(lines)
    mesh_options = None
    in_mesh = False
    for index, line in enumerate(lines):
        section = SECTION.match(line.rstrip("\r\n"))
        if section:
            first_section = min(first_section, index)
            in_mesh = section[1].strip().lower() == "bed_mesh"
            if in_mesh:
                mesh_options = index + 1
        elif in_mesh and COUNT.match(line):
            return contents
    if mesh_options is None:
        index = first_section
        addition = "[bed_mesh]" + newline + seed_line + newline * 2
    else:
        index = mesh_options
        addition = seed_line + newline
    if index and not lines[index - 1].endswith(("\n", "\r")):
        addition = newline + addition
    lines.insert(index, addition)
    return "".join(lines)


def main(path):
    seed = Path(__file__).with_name("overrides.cfg").read_text(encoding="utf-8")
    seed_line = COUNT.search(seed)[0]
    with open(path, encoding="utf-8", newline="") as source:
        original = source.read()
    updated = ensure_count(original, seed_line)
    if updated != original:
        write_atomic(path, updated)
        print("I: added stock %s to %s" % (seed_line.split("#")[0].strip(), path))


if __name__ == "__main__":
    main(sys.argv[1])
