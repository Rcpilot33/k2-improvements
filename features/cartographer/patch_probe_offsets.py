#!/usr/bin/env python3
"""Enable probe XY offsets without silently accepting an unknown probe.py."""

import os
import stat
import sys
import tempfile


OLD = "self.use_offsets = False"
NEW = "self.use_offsets = True"


def patch(contents):
    old_count = contents.count(OLD)
    new_count = contents.count(NEW)
    if old_count == 1 and new_count == 0:
        return contents.replace(OLD, NEW, 1), True
    if old_count == 0 and new_count == 1:
        return contents, False
    raise ValueError(
        "expected exactly one probe offset setting; found %d disabled and %d enabled"
        % (old_count, new_count)
    )


def write_atomic(path, contents):
    mode = stat.S_IMODE(os.stat(path).st_mode)
    directory = os.path.dirname(path) or "."
    descriptor, temporary = tempfile.mkstemp(
        prefix=".probe-offsets-", dir=directory, text=True
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as output:
            output.write(contents)
            output.flush()
            os.fsync(output.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main(argv):
    if len(argv) != 2:
        print("usage: patch_probe_offsets.py PATH", file=sys.stderr)
        return 2
    path = os.path.realpath(os.path.expanduser(argv[1]))
    try:
        with open(path, "r", encoding="utf-8", newline="") as source:
            contents = source.read()
        updated, changed = patch(contents)
        if changed:
            write_atomic(path, updated)
        if NEW not in updated or OLD in updated:
            raise ValueError("probe XY offset patch did not verify")
    except (OSError, ValueError) as exc:
        print("E: unable to enable probe XY offsets: %s" % exc, file=sys.stderr)
        return 1
    print("I: probe XY offsets are enabled")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
