"""Reuse the existing metadata merge without changing the Cartographer editor."""
import importlib.util
import os
from pathlib import Path
import sys
import uuid

SOURCE = Path(__file__).resolve().parent.parent / "global-touch-offsets/configure_fluidd_layout.py"
spec = importlib.util.spec_from_file_location("prtouch_layout_base", SOURCE)
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
base.MACRO_NAME = "GLOBAL_Z_OFFSETS_NO_CARTO"
base.MACRO_ALIAS = "Global_Z_Offsets_No_Carto"
base.CATEGORY_ID = str(uuid.uuid5(uuid.NAMESPACE_URL,
    "https://github.com/Rcpilot33/k2-improvements/fluidd/global-prtouch-offsets"))
merge_layout = base.merge_layout


def main():
    try:
        base.configure(os.environ.get("MOONRAKER_URL", "http://127.0.0.1:7125"))
    except base.LayoutError as exc:
        print("W: Global No-Carto Z Offsets category could not be configured: %s" % exc)
        return 1
    print("I: Global_Z_Offsets_No_Carto configured in Z Offsets; refresh Fluidd")
    return 0


if __name__ == "__main__":
    sys.exit(main())
