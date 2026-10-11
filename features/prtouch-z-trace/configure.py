"""Install/remove only this temporary tracer, preserving native calibration."""

import argparse
import json
from pathlib import Path
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from ensure_included import add_include

HERE = Path(__file__).resolve().parent
LINKS = (("k2_prtouch_z_trace.py", "extras"), ("prtouch_z_trace.cfg", "custom"))


def query(url):
    with urllib.request.urlopen(url.rstrip("/") +
            "/printer/objects/query?print_stats=state&configfile=config", timeout=5) as response:
        return json.load(response)["result"]["status"]


def configure(config_dir, klipper_dir, status, remove=False):
    custom = Path(config_dir) / "custom"
    extras = Path(klipper_dir) / "klippy" / "extras"
    main = custom / "main.cfg"
    if not main.is_file() or not extras.is_dir():
        raise ValueError("existing custom/main.cfg and Klipper extras directory are required")
    if status.get("print_stats", {}).get("state") not in (
            "standby", "complete", "cancelled", "error"):
        raise ValueError("printer must be idle; printing, paused, or unknown state is refused")
    loaded = status.get("configfile", {}).get("config", {})
    if not remove and ("prtouch_v3" not in loaded or "cartographer" in loaded):
        raise ValueError("install requires the loaded no-Carto [prtouch_v3] configuration")
    targets = []
    for filename, location in LINKS:
        target = (extras if location == "extras" else custom) / filename
        source = HERE / filename
        if target.is_symlink():
            if target.resolve() != source.resolve():
                raise ValueError("refusing to replace an unfamiliar link: %s" % target)
        elif target.exists():
            raise ValueError("refusing to replace an existing file: %s" % target)
        targets.append((target, source))
    # Disable first on removal; install all links before enabling the include.
    # No printer.cfg edits, saved calibration writes, or automatic restart.
    if remove:
        add_include(str(main), "prtouch_z_trace.cfg", commented=True)
        for target, source in targets:
            if target.is_symlink():
                target.unlink()
    else:
        for target, source in targets:
            if not target.is_symlink():
                target.symlink_to(source)
        add_include(str(main), "prtouch_z_trace.cfg")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--remove", action="store_true")
    parser.add_argument("--config-dir", required=True)
    parser.add_argument("--klipper-dir", required=True)
    parser.add_argument("--moonraker-url", required=True)
    args = parser.parse_args()
    try:
        configure(args.config_dir, args.klipper_dir,
                  query(args.moonraker_url), args.remove)
    except Exception as exc:
        print("ERROR: PR Touch trace configuration was not completed: %s" % exc,
              file=sys.stderr)
        return 1
    print("PR Touch trace %s. No offsets were changed and no restart was sent."
          % ("removed" if args.remove else "installed"))
    print("Power-cycle while idle and wait for full K2 startup before homing.")
    print("Existing trace logs are retained in printer_data/logs.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
