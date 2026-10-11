#!/usr/bin/env python3
"""Persist the stock plate workflow's Cartographer-compatible slicer choice."""

import argparse
import json
import os
from pathlib import Path
import sys
import tempfile


CHOICES = ("creality", "orca", "both")
PREFERENCE = "plate-workflow-slicers.json"


def read_choice(path):
    if not path.exists():
        return "both"  # Older stock installations showed all plate types.
    saved = json.loads(path.read_text())
    if not isinstance(saved, dict) or saved.get("slicers") not in CHOICES:
        raise ValueError("Invalid saved plate-workflow slicer selection")
    return saved["slicers"]


def configure(config_dir, choice=None, check_only=False):
    custom = Path(config_dir) / "custom"
    if not custom.is_dir():
        raise ValueError("custom configuration directory is missing; install macros first")
    path = custom / PREFERENCE
    selected = choice or read_choice(path)
    if selected not in CHOICES:
        raise ValueError("Slicers must be creality, orca, or both")
    if check_only:
        return selected
    if path.exists() and read_choice(path) == selected:
        return selected
    descriptor, temporary = tempfile.mkstemp(prefix=".plate-workflow-slicers-", dir=str(custom))
    try:
        with os.fdopen(descriptor, "w") as output:
            json.dump({"slicers": selected}, output)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        if path.exists():
            os.chmod(temporary, path.stat().st_mode)
        os.replace(temporary, str(path))
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return selected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config-dir", required=True)
    parser.add_argument("--slicers", choices=CHOICES)
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    try:
        selected = configure(args.config_dir, args.slicers, args.check_only)
    except (OSError, ValueError) as exc:
        print("ERROR: plate-workflow slicer selection was not changed: %s" % exc, file=sys.stderr)
        return 1
    print("I: plate-workflow slicers: %s%s" % (selected, " (preflight only)" if args.check_only else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
