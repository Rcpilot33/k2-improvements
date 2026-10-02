#!/usr/bin/env python3
"""Set the Moonraker web updater identity for an installed Fluidd build."""

import argparse
import json
import os
import pathlib
import tempfile


def update_release_source(path, owner, project):
    path = pathlib.Path(path)
    with path.open("r", encoding="utf-8") as source:
        release = json.load(source)

    if not isinstance(release, dict):
        raise ValueError("release_info.json must contain a JSON object")
    if not release.get("version"):
        raise ValueError("release_info.json is missing its version")

    release["project_name"] = project
    release["project_owner"] = owner

    mode = path.stat().st_mode
    descriptor, temporary = tempfile.mkstemp(
        prefix=".release_info.", suffix=".json", dir=str(path.parent)
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as target:
            json.dump(release, target, separators=(",", ":"))
            target.write("\n")
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("release_info")
    parser.add_argument("owner")
    parser.add_argument("project")
    args = parser.parse_args()
    update_release_source(args.release_info, args.owner, args.project)


if __name__ == "__main__":
    main()
