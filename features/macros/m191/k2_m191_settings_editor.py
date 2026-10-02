"""Live Fluidd editor for the configurable M191 chamber-heating settings."""

import hashlib
import os
import re
import tempfile


SECTION_NAME = "gcode_macro _M191_VARS"
START_PRINT_SECTION_NAME = "gcode_macro _START_PRINT_VARS"
SECTION_RE = re.compile(r"^[ \t]*\[([^]]+)\][ \t]*(?:#.*)?(?:\r?\n)?$")
NUMBER = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)"

# key, label, minimum, maximum, unit, kind, exclusive minimum
SETTINGS = (
    ("bed_assist_enabled", "Bed Assist", 0.0, 1.0, "", "boolean", False),
    ("bed_assist_trigger_delta", "Assist Trigger Delta", 0.0, 20.0, "C", "number", False),
    ("bed_assist_bed_target", "Fixed Bed Target", 0.0, 120.0, "C", "number", True),
    ("bed_assist_degrees_above_commanded", "Bed Target Increase", 0.0, 120.0, "C", "number", False),
    ("bed_assist_z_height", "Bed Z Height", 30.0, 330.0, "mm", "number", False),
    ("circulation_fan_speed", "Low Circulation Fan Speed", 0.0, 100.0, "%", "number", False),
    ("circulation_fan_high_speed", "High Circulation Fan Speed", 0.0, 100.0, "%", "number", False),
    ("circulation_fan_low_seconds", "Low Fan Duration", 0.0, 600.0, "sec", "number", True),
    ("circulation_fan_high_seconds", "High Fan Duration", 0.0, 600.0, "sec", "number", True),
    ("bed_restore_z_height", "Bed Return Z Height", 30.0, 330.0, "mm", "number", False),
    ("bed_restore_side_fan_speed", "Bed Return Side Fan Speed", 0.0, 100.0, "%", "number", False),
    ("chamber_fan_margin", "Chamber Fan Margin", 0.0, 10.0, "C", "number", False),
    ("bed_restore_tolerance", "Bed Restore Tolerance", 0.0, 20.0, "C", "number", True),
    ("chamber_wait_max_delta", "Chamber Wait Maximum Delta", 0.0, 20.0, "C", "number", True),
    ("heat_soak", "Machine Heat Soak", 0.0, 120.0, "min", "number", False),
)
SETTING_BY_KEY = {setting[0]: setting for setting in SETTINGS}


def section_for_key(key):
    if key == "heat_soak":
        return START_PRINT_SECTION_NAME
    return SECTION_NAME


def _variable_re(key):
    return re.compile(
        r"^([ \t]*variable_" + re.escape(key) + r"[ \t]*:[ \t]*)"
        r"(" + NUMBER + r")([ \t]*(?:#.*)?(?:\r?\n)?)$",
        re.IGNORECASE,
    )


VARIABLE_PATTERNS = {key: _variable_re(key) for key in SETTING_BY_KEY}


def validate_settings(values):
    for key in SETTING_BY_KEY:
        validate_value(key, values[key])
    if values["circulation_fan_high_speed"] < values["circulation_fan_speed"]:
        raise ValueError(
            "circulation_fan_high_speed must be at least circulation_fan_speed"
        )
    return values


def format_value(key, value):
    if key == "bed_assist_enabled":
        return str(int(round(float(value))))
    value = round(float(value), 3)
    if value == 0:
        value = 0.0
    formatted = ("%.3f" % value).rstrip("0").rstrip(".")
    return formatted if "." in formatted else formatted + ".0"


def validate_value(key, value):
    if key not in SETTING_BY_KEY:
        raise ValueError("unknown M191 setting: %s" % key)
    _, _, minimum, maximum, _, kind, exclusive_minimum = SETTING_BY_KEY[key]
    value = float(value)
    if kind == "boolean" and value not in (0.0, 1.0):
        raise ValueError("%s must be 0 or 1" % key)
    if value < minimum or value > maximum or (exclusive_minimum and value <= minimum):
        qualifier = "above %s through %s" if exclusive_minimum else "%s through %s"
        raise ValueError(("%s must be " + qualifier) % (key, minimum, maximum))
    return value


def parse_settings(text):
    values = {}
    current_section = None
    found_sections = set()
    for line in text.splitlines(True):
        section = SECTION_RE.match(line)
        if section:
            current_section = section.group(1).strip().casefold()
            if current_section in (
                SECTION_NAME.casefold(), START_PRINT_SECTION_NAME.casefold()
            ):
                found_sections.add(current_section)
            continue
        if current_section not in found_sections:
            continue
        for key, pattern in VARIABLE_PATTERNS.items():
            if current_section != section_for_key(key).casefold():
                continue
            match = pattern.match(line)
            if match and key not in values:
                values[key] = validate_value(key, match.group(2))
                break
    for required_section in (SECTION_NAME, START_PRINT_SECTION_NAME):
        if required_section.casefold() not in found_sections:
            raise ValueError("[%s] was not found" % required_section)
    missing = [key for key in SETTING_BY_KEY if key not in values]
    if missing:
        raise ValueError("missing M191 settings: %s" % ", ".join(missing))
    return validate_settings(values)


def rewrite_settings(text, values):
    validate_settings(values)
    lines = text.splitlines(True)
    current_section = None
    replaced = set()
    output = []
    for line in lines:
        section = SECTION_RE.match(line)
        if section:
            current_section = section.group(1).strip().casefold()
            output.append(line)
            continue
        if current_section in (
            SECTION_NAME.casefold(), START_PRINT_SECTION_NAME.casefold()
        ):
            for key, pattern in VARIABLE_PATTERNS.items():
                if current_section != section_for_key(key).casefold():
                    continue
                match = pattern.match(line)
                if match:
                    if key in replaced:
                        raise ValueError("duplicate variable_%s" % key)
                    output.append(match.group(1) + format_value(key, values[key]) + match.group(3))
                    replaced.add(key)
                    break
            else:
                output.append(line)
            continue
        output.append(line)
    missing = [key for key in SETTING_BY_KEY if key not in replaced]
    if missing:
        raise ValueError("could not rewrite M191 settings: %s" % ", ".join(missing))
    return "".join(output)


def file_digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def write_atomic(path, text):
    directory = os.path.dirname(path)
    mode = os.stat(path).st_mode
    descriptor, temporary = tempfile.mkstemp(prefix=".m191-settings-", dir=directory)
    try:
        with os.fdopen(descriptor, "w") as output:
            output.write(text)
            output.flush()
            os.fsync(output.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


class K2M191SettingsEditor:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.gcode = self.printer.lookup_object("gcode")
        self.overrides_path = config.get(
            "overrides_path",
            "/mnt/UDISK/printer_data/config/custom/overrides.cfg",
        )
        self.settings = None
        self.session_digest = None
        self.gcode.register_command(
            "K2_M191_SETTINGS", self.cmd_open,
            desc="Edit M191 chamber-heating settings",
        )
        self.gcode.register_command("K2_M191_SETTINGS_STAGE", self.cmd_stage)
        self.gcode.register_command("K2_M191_SETTINGS_CANCEL", self.cmd_cancel)
        self.gcode.register_command("K2_M191_SETTINGS_SAVE", self.cmd_save)

    def get_status(self, eventtime):
        return {"session_open": self.settings is not None}

    def _read(self, gcmd):
        try:
            with open(self.overrides_path, "r") as source:
                return source.read()
        except OSError as exc:
            raise gcmd.error("Could not read overrides.cfg: %s" % exc)

    def _write(self, gcmd, text):
        try:
            write_atomic(self.overrides_path, text)
        except OSError as exc:
            raise gcmd.error("Could not save overrides.cfg: %s" % exc)

    def _printing_or_paused(self):
        print_stats = self.printer.lookup_object("print_stats", None)
        if print_stats is None:
            return False
        state = str(print_stats.get_status(0.0).get("state", "")).lower()
        return state in ("printing", "paused")

    def _action(self, message):
        self.gcode.respond_raw("// action:%s" % message)

    def _close(self):
        self._action("m191_settings_end")

    def _require_session(self, gcmd):
        if self.settings is None:
            raise gcmd.error("Open Bed_Assist before saving settings")

    def _live_variables(self, gcmd, section, keys):
        macro = self.printer.lookup_object(section, None)
        variables = getattr(macro, "variables", None)
        if not isinstance(variables, dict) or any(key not in variables for key in keys):
            raise gcmd.error("%s live variables are unavailable; nothing was saved" % section)
        return variables

    def cmd_open(self, gcmd):
        if self._printing_or_paused():
            raise gcmd.error("Bed Assist settings cannot be edited during a print")
        text = self._read(gcmd)
        try:
            values = parse_settings(text)
        except (TypeError, ValueError) as exc:
            raise gcmd.error("Could not parse M191 settings: %s" % exc)
        self.session_digest = file_digest(text)
        self.settings = [
            {"key": key, "original": values[key], "current": values[key]}
            for key in SETTING_BY_KEY
        ]
        self._action("m191_settings_begin")
        for index, setting in enumerate(self.settings):
            _, label, minimum, maximum, unit, kind, exclusive = SETTING_BY_KEY[setting["key"]]
            self._action(
                "m191_settings_setting %s|%s|%s|%s|%s|%s|%d|%s|%d"
                % (
                    setting["key"], label, format_value(setting["key"], setting["current"]),
                    minimum, maximum, unit, index, kind, 1 if exclusive else 0,
                )
            )
        self._action("m191_settings_show")

    def cmd_stage(self, gcmd):
        self._require_session(gcmd)
        index = gcmd.get_int("INDEX", minval=0, maxval=len(self.settings) - 1)
        value = gcmd.get_float("VALUE")
        key = self.settings[index]["key"]
        try:
            value = validate_value(key, value)
        except ValueError as exc:
            raise gcmd.error(str(exc))
        self.settings[index]["current"] = value

    def cmd_cancel(self, gcmd):
        self.settings = None
        self.session_digest = None
        self._close()
        gcmd.respond_info("Bed Assist setting changes cancelled")

    def cmd_save(self, gcmd):
        self._require_session(gcmd)
        if self._printing_or_paused():
            raise gcmd.error("Saving Bed Assist settings is not allowed during a print")
        text = self._read(gcmd)
        if file_digest(text) != self.session_digest:
            raise gcmd.error(
                "overrides.cfg changed while the editor was open; cancel and reopen it"
            )
        changed = [item for item in self.settings if item["current"] != item["original"]]
        if not changed:
            self.settings = None
            self.session_digest = None
            self._close()
            gcmd.respond_info("No Bed Assist setting changes to save")
            return
        values = {item["key"]: item["current"] for item in self.settings}
        try:
            updated = rewrite_settings(text, values)
        except (TypeError, ValueError) as exc:
            raise gcmd.error("Could not update M191 settings: %s" % exc)
        live_by_section = {}
        for section in (SECTION_NAME, START_PRINT_SECTION_NAME):
            keys = [item["key"] for item in changed if section_for_key(item["key"]) == section]
            if keys:
                live_by_section[section] = self._live_variables(gcmd, section, keys)
        self._write(gcmd, updated)
        for item in changed:
            live_by_section[section_for_key(item["key"])][item["key"]] = item["current"]
        self.settings = None
        self.session_digest = None
        self._close()
        gcmd.respond_info("Bed Assist settings saved and active; no restart needed")


def load_config(config):
    return K2M191SettingsEditor(config)
