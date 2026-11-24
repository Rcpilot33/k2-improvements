"""Save and review K2 user settings across a no-wipe firmware update."""
import argparse
import difflib
import os
from pathlib import Path
import shutil
import sys
import tempfile
import zipfile


FILES = ("overrides.cfg", "cartographer.cfg", "prtouch_global_z.json",
         "plate-workflow-slicers.json", "kamp_settings.cfg")


def save(custom, archive, baseline):
    if not (custom / "overrides.cfg").is_file():
        raise ValueError("Missing custom/overrides.cfg. Review the installed setup before saving.")
    with tempfile.NamedTemporaryFile(dir=archive.parent, delete=False) as tmp:
        name = Path(tmp.name)
    try:
        with zipfile.ZipFile(name, "w", compression=zipfile.ZIP_DEFLATED) as backup:
            backup.write(baseline, "verified-setup")
            for filename in FILES:
                path = custom / filename
                if path.is_file():
                    backup.write(path, filename)
                    print("Saving custom/" + filename)
        # Retain the last explicit backup as well. An interrupted copy must
        # leave the current archive available until its replacement is ready.
        if archive.exists():
            previous = archive.with_suffix(".previous.zip")
            with tempfile.NamedTemporaryFile(dir=archive.parent, delete=False) as tmp:
                copy = Path(tmp.name)
            try:
                shutil.copyfile(archive, copy)
                os.replace(copy, previous)
            finally:
                if copy.exists():
                    copy.unlink()
        os.replace(name, archive)
        print("Settings saved to " + str(archive))
    finally:
        if name.exists():
            name.unlink()


def review(custom, archive, apply):
    with zipfile.ZipFile(archive) as backup:
        damaged = backup.testzip()
        if damaged or "overrides.cfg" not in backup.namelist():
            raise ValueError("Incomplete settings backup: " + str(archive))
        for filename in FILES:
            if filename not in backup.namelist():
                continue
            path = custom / filename
            saved = backup.read(filename)
            live = path.read_bytes() if path.exists() else None
            if live == saved:
                continue
            if not apply:
                return 3
            if live is None:
                print("Missing custom/" + filename)
            else:
                print("Changed custom/" + filename)
                before = live.decode("utf-8", "replace").splitlines()
                after = saved.decode("utf-8", "replace").splitlines()
                for line in difflib.unified_diff(before, after, "current", "saved", lineterm=""):
                    print(line)
            answer = input("Restore saved " + filename + "? [y=restore and restart after repairs / k=keep current / Enter=back] ").strip().lower()
            if answer == "k":
                continue
            if answer not in ("y", "yes"):
                return 1
            if custom.is_symlink() or path.is_symlink():
                raise ValueError("Review the linked settings path manually: " + str(path))
            if (path.read_bytes() if path.exists() else None) != live:
                raise ValueError("Settings changed during review. Review again: " + str(path))
            custom.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=custom, delete=False) as tmp:
                name = Path(tmp.name)
            try:
                name.write_bytes(saved)
                if live is not None:
                    shutil.copymode(path, name)
                else:
                    name.chmod((backup.getinfo(filename).external_attr >> 16) & 0o777 or 0o644)
                # A retry must still activate files written before an interruption.
                (archive.parent / "settings-restart-pending").touch()
                os.replace(name, path)
                print("Restored custom/" + filename)
            finally:
                if name.exists():
                    name.unlink()
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("save", "check", "restore"))
    parser.add_argument("custom", type=Path)
    parser.add_argument("archive", type=Path)
    parser.add_argument("baseline", type=Path, nargs="?")
    args = parser.parse_args()
    try:
        if args.action == "save":
            save(args.custom, args.archive, args.baseline)
            return 0
        return review(args.custom, args.archive, args.action == "restore")
    except (OSError, ValueError, EOFError, zipfile.BadZipFile) as error:
        print("Settings backup: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
