#!/usr/bin/env python3
"""Preserve PR Touch status while releasing its conflicting ATC object name."""

import pathlib
import shutil
import sys


DEFAULT_TARGET = pathlib.Path(
    "/usr/share/klipper/klippy/extras/prtouch_v3.py"
)
REGISTRATION = (
    "    config.get_printer().add_object"
    "('axis_twist_compensation', prtouch)"
)
LEGACY_REGISTRATION = (
    "    # K2-Improvements supplies the full axis-twist object when this "
    "optional feature is installed."
)
PATCHED_REGISTRATION = (
    "    config.get_printer().add_object"
    "('k2_prtouch_axis_twist_status', prtouch)"
)


def patch_file(target):
    target = pathlib.Path(target)
    source = target.read_text(encoding="utf-8")

    if (source.count(PATCHED_REGISTRATION) == 1
            and REGISTRATION not in source and LEGACY_REGISTRATION not in source):
        return False
    registration = (LEGACY_REGISTRATION if LEGACY_REGISTRATION in source
                    else REGISTRATION)
    if (source.count(registration) != 1
            or PATCHED_REGISTRATION in source
            or (registration == LEGACY_REGISTRATION and REGISTRATION in source)):
        raise RuntimeError(
            "expected exactly one prtouch_v3 axis-twist registration in %s"
            % (target,)
        )

    backup = target.with_name(target.name + ".k2-axis-twist.bak")
    if not backup.exists():
        if registration == LEGACY_REGISTRATION:
            # An old install may have lost its backup. Reconstruct only the
            # registration we previously removed, preserving all other code.
            backup.write_text(source.replace(registration, REGISTRATION),
                              encoding="utf-8")
        else:
            shutil.copy2(str(target), str(backup))

    target.write_text(
        source.replace(registration, PATCHED_REGISTRATION),
        encoding="utf-8",
    )
    return True


def main():
    target = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_TARGET
    changed = patch_file(target)
    state = "patched" if changed else "already patched"
    print("prtouch_v3 axis-twist registration: %s" % (state,))


if __name__ == "__main__":
    main()
