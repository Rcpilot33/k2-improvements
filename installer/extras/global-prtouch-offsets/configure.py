"""Install the opt-in no-Carto global editor and its required compatibility."""

import argparse
import json
from pathlib import Path
import sys
import urllib.request

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from ensure_included import add_include

CONFIG = "global_prtouch_offsets.cfg"


def query(url):
    with urllib.request.urlopen(url.rstrip("/") +
            "/printer/objects/query?print_stats=state&configfile=config", timeout=5) as response:
        return json.load(response)["result"]["status"]


def configure(config_dir, klipper_dir, status, remove=False):
    custom, extras = Path(config_dir) / "custom", Path(klipper_dir) / "klippy/extras"
    main = custom / "main.cfg"
    if not main.is_file() or not extras.is_dir():
        raise ValueError("existing custom/main.cfg and Klipper extras are required")
    if status.get("print_stats", {}).get("state") not in ("standby", "complete", "cancelled", "error"):
        raise ValueError("printer must be idle; printing, paused, or unknown state is refused")
    loaded = status.get("configfile", {}).get("config", {})
    if not remove and ("prtouch_v3" not in loaded or "cartographer" in loaded):
        raise ValueError("install requires loaded no-Carto [prtouch_v3]")
    links = [(HERE / CONFIG, custom / CONFIG),
             (HERE / "k2_prtouch_global_z.py", extras / "k2_prtouch_global_z.py")]
    if not remove:
        compat = ROOT / "features/prtouch-touchscreen"
        links += [(compat / "prtouch_touchscreen.cfg", custom / "prtouch_touchscreen.cfg"),
                  (compat / "k2_prtouch_touchscreen.py", extras / "k2_prtouch_touchscreen.py"),
                  (ROOT / "features/macros/start_print/start_print.cfg", custom / "start_print.cfg")]
        if not (custom / "start_print.cfg").exists():
            raise ValueError("install managed START_PRINT macros first")
    for source, target in links:
        if not source.is_file():
            raise ValueError("missing source: %s" % source)
        if target.is_symlink():
            if target.resolve() != source.resolve():
                raise ValueError("refusing unfamiliar link: %s; update managed macros first" % target)
        elif target.exists():
            raise ValueError("refusing existing file: %s; update managed macros first" % target)
    if remove:
        add_include(str(main), CONFIG, commented=True)
        for source, target in links:
            if target.is_symlink():
                target.unlink()
    else:
        created = []
        try:
            for source, target in links:
                if not target.is_symlink():
                    target.symlink_to(source)
                    created.append(target)
        except OSError:
            for target in reversed(created):
                target.unlink()
            raise
        add_include(str(main), "prtouch_touchscreen.cfg")
        add_include(str(main), CONFIG)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--remove", action="store_true")
    parser.add_argument("--config-dir", required=True)
    parser.add_argument("--klipper-dir", required=True)
    parser.add_argument("--moonraker-url", required=True)
    args = parser.parse_args()
    try:
        configure(args.config_dir, args.klipper_dir, query(args.moonraker_url), args.remove)
    except Exception as exc:
        print("ERROR: Global PR Touch installation was not completed: %s" % exc, file=sys.stderr)
        return 1
    print("Global No-Carto Z Offsets %s. Existing calibration and offset data preserved." %
          ("removed" if args.remove else "installed"))
    print("Power-cycle while idle; wait for full startup. No restart or motion was sent.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
