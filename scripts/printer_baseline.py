#!/usr/bin/env python3
"""Read the K2 hardware identity and compare saved and running travel limits."""

import json
import re
import subprocess
from pathlib import Path
from urllib.request import urlopen


def hardware_field(name):
    try:
        return subprocess.check_output(
            ["get_sn_mac.sh", name], text=True, stderr=subprocess.DEVNULL, timeout=5
        ).strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def printer_model(model_id):
    return {"F008": "K2 Plus", "F012": "K2 Pro"}.get(model_id, "unknown")


def saved_axis_limits(path):
    # Read just the main file. Includes and SAVE_CONFIG can affect the loaded settings.
    axes = {}
    axis = None
    for line in path.read_text(errors="replace").splitlines():
        line = re.split(r"[#;]", line, maxsplit=1)[0].strip()
        if line.startswith("["):
            stepper = re.fullmatch(r"\[stepper_([xyz])\]", line)
            axis = stepper[1] if stepper else None
        elif axis:
            match = re.fullmatch(r"(position_min|position_max)\s*[:=]\s*(\S+)", line)
            if match:
                axes.setdefault(axis, {})[match[1]] = float(match[2])
    return axes


def running_state():
    fields = ("toolhead=axis_minimum,axis_maximum,homed_axes&motor_control=motor_ready"
              "&print_stats=state&configfile=settings")
    with urlopen("http://127.0.0.1:7125/printer/objects/query?" + fields, timeout=5) as response:
        status = json.load(response)["result"]["status"]
    settings = status.get("configfile", {}).get("settings", {})
    axes = {}
    for axis in "xyz":
        config = settings.get("stepper_" + axis, {})
        axes[axis] = {key: config.get(key) for key in ("position_min", "position_max")}
    return {
        "loaded_axis_limits": axes,
        "printer_param_max_y": settings.get("gcode_macro printer_param", {}).get("variable_max_y_position"),
        "toolhead": status.get("toolhead"),
        "motor_ready": status.get("motor_control", {}).get("motor_ready"),
        "print_state": status.get("print_stats", {}).get("state"),
    }


def main():
    model_id = hardware_field("model")
    report = {"model_id": model_id, "model": printer_model(model_id), "board": hardware_field("board")}
    try:
        report["printer_cfg_axis_limits"] = saved_axis_limits(
            Path("/mnt/UDISK/printer_data/config/printer.cfg")
        )
    except (OSError, ValueError) as error:
        report["printer_cfg_error"] = str(error)
    try:
        report.update(running_state())
    except (OSError, ValueError, KeyError) as error:
        report["moonraker_error"] = str(error)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
