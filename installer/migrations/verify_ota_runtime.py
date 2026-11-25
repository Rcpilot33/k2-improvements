"""Verify restored printer registrations through the local read-only API."""
import json
import sys
import urllib.request


def query(path):
    with urllib.request.urlopen("http://127.0.0.1:7125" + path, timeout=5) as response:
        return json.load(response)["result"]


OPTION_COMMANDS = {
    "global-touch-offsets": "GLOBAL_Z_OFFSETS_CARTO",
    "global-prtouch-offsets": "GLOBAL_Z_OFFSETS_NO_CARTO",
    "material-z-offsets": "MATERIAL_Z_OFFSETS",
    "kamp-adaptive-purge": "LINE_PURGE",
}


def verify(setup, options=(), request=query):
    if request("/printer/info").get("state") != "ready":
        raise ValueError("Klipper has not reached Ready")
    commands = {key.upper() for key in request("/printer/gcode/help")}
    required = {"START_PRINT", "BED_ASSIST"}
    required.update(OPTION_COMMANDS[option] for option in options if option in OPTION_COMMANDS)
    updaters = {"fluidd"}
    if setup == "cartographer":
        required.update(("A62_CARTO_LIST_MODELS", "A63_CARTO_INFO"))
        updaters.add("cartographer")
    missing = required - commands
    if missing:
        raise ValueError("missing Klipper macros: {}. Check the active includes and Klipper log."
                         .format(", ".join(sorted(missing))))
    versions = request("/machine/update/status?refresh=false")["version_info"]
    missing = updaters.difference(versions)
    if missing:
        raise ValueError("missing Moonraker updaters: {}. Check the updater includes and Moonraker log."
                         .format(", ".join(sorted(missing))))
    if setup == "cartographer":
        status = request("/printer/objects/query?k2_cartographer_touchscreen=installed&probe=z_offset")["status"]
        if (status.get("k2_cartographer_touchscreen", {}).get("installed") is not True
                or status.get("probe", {}).get("z_offset") is None):
            raise ValueError("Cartographer touchscreen live Z offset is unavailable. Check the active include and Klipper log.")


if __name__ == "__main__":
    try:
        verify(sys.argv[1], sys.argv[2:])
    except (OSError, KeyError, ValueError, TypeError) as error:
        sys.exit("Verification pending: {}".format(error))
