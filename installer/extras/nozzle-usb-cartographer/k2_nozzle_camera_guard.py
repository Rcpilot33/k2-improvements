"""Disable factory nozzle-camera AI, preserving enclosure-camera preferences."""

import json
import logging
import os
import tempfile


CAMERA_FLAGS = ("wasteSwitch", "flowDetect", "flowEmDetect")


def disable_camera_preferences(path):
    """Change only known nozzle-camera flags; never invent or reset AI settings."""
    with open(path, encoding="utf-8") as source:
        data = json.load(source)
    control = data.get("ai_control")
    if not isinstance(control, dict) or any(key not in control for key in CAMERA_FLAGS):
        raise ValueError("Unsupported factory ai_control preferences")
    if all(control[key] == 0 for key in CAMERA_FLAGS):
        return False
    for key in CAMERA_FLAGS:
        control[key] = 0
    mode = os.stat(path).st_mode & 0o777
    descriptor, temporary = tempfile.mkstemp(prefix=".k2-camera-", dir=os.path.dirname(path))
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as target:
            json.dump(data, target, indent=2)
            target.write("\n")
            target.flush()
            os.fsync(target.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return True


class CameraPreferenceCommand:
    def __init__(self, original):
        self.original = original

    def __getattr__(self, name):
        return getattr(self.original, name)

    def get_int(self, name, *args, **kwargs):
        # Validate the supplied parameter normally, then clamp only waste AI.
        value = self.original.get_int(name, *args, **kwargs)
        return 0 if name == "WASTE_SWITCH" else value


class K2NozzleCameraGuard:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.gcode = self.printer.lookup_object("gcode")
        self.preferences = config.get(
            "preferences_path", "/mnt/UDISK/creality/userdata/config/user_print_refer.json")
        self.active = False
        self.printer.register_event_handler("klippy:connect", self.connect)

    def connect(self):
        if self.active:
            return
        ai = self.printer.lookup_object("load_ai", None)
        required = ("execute_toolhead_ai_waste_management", "execute_ai_waste_detection",
                    "nozzle_cam_power_on", "nozzle_cam_power_off", "ai_capture",
                    "cmd_LOAD_AI_SET_AI_CONTROL_PREFER")
        if ai is None or any(not callable(getattr(ai, name, None)) for name in required):
            raise self.printer.config_error("Unsupported factory nozzle-camera AI API")
        try:
            disable_camera_preferences(self.preferences)
        except (OSError, ValueError) as error:
            raise self.printer.config_error("Cannot disable nozzle-camera preferences: %s" % error)
        original = ai.cmd_LOAD_AI_SET_AI_CONTROL_PREFER

        def set_preferences(gcmd):
            # Creality sends this at print start. Re-clamp persisted settings too.
            try:
                disable_camera_preferences(self.preferences)
            except (OSError, ValueError) as error:
                raise gcmd.error("Cannot enforce nozzle-camera preferences: %s" % error)
            original(CameraPreferenceCommand(gcmd))
            ai.ai_waste_switch = 0
            ai.cx_ai_engine_status["ai_waste_switch"] = 0

        def report_status(gcmd):
            # The factory command populates synthetic test results, including
            # waste AI enabled. Report actual switches without running it.
            gcmd.respond_info(json.dumps({"ai_switch": ai.ai_switch,
                                          "ai_waste_switch": 0}))

        ai.ai_waste_switch = 0
        ai.cx_ai_engine_status["ai_waste_switch"] = 0
        for name in required[:-1]:
            setattr(ai, name, self.no_camera)
        ai.cmd_LOAD_AI_SET_AI_CONTROL_PREFER = set_preferences
        self.gcode.register_command("LOAD_AI_SET_AI_CONTROL_PREFER", None)
        self.gcode.register_command("LOAD_AI_SET_AI_CONTROL_PREFER", set_preferences)
        # Direct commands must not perform camera-dependent movement/capture.
        for command in ("LOAD_AI_DEAL", "LOAD_AI_DETECT_WASTE", "LOAD_AI_T_CMD_TEST"):
            self.gcode.register_command(command, None)
            self.gcode.register_command(command, self.disabled_command)
        ai.cmd_LOAD_AI_GET_STATUS = report_status
        self.gcode.register_command("LOAD_AI_GET_STATUS", None)
        self.gcode.register_command("LOAD_AI_GET_STATUS", report_status)
        self.active = True
        logging.info("Factory nozzle-camera AI disabled; enclosure AI preserved")

    def no_camera(self, *args, **kwargs):
        return None

    def disabled_command(self, gcmd):
        gcmd.respond_info("Factory nozzle camera removed: camera AI command skipped")

    def get_status(self, eventtime):
        return {"active": self.active, "nozzle_camera_available": False}


def load_config(config):
    return K2NozzleCameraGuard(config)
