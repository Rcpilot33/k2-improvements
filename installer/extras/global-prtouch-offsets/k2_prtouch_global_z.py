"""Explicit no-Carto global Z editor and a separate, baseline-relative transform."""

import hashlib
import json
import math
import os
import re
import tempfile


SURFACES = ("default", "epoxy", "high_temp", "textured_pei", "custom",
            "orca_cool_plate", "orca_engineering", "orca_textured_cool", "orca_supertack")
NAME = re.compile(r"^[a-z0-9_]{1,64}$")
MESH_NAME = re.compile(r"^(.+)_-?\d+(?:\.\d+)?c_-?\d+(?:\.\d+)?c$")
RECOVERY_KEY = "K2_PRTOUCH_GLOBAL_Z"
INITIAL_DEFAULT_Z_OFFSET = -.080


def offset(value):
    if isinstance(value, bool):
        raise ValueError("global Z offset cannot be a boolean")
    value = float(value)
    if not math.isfinite(value) or not -5 <= value <= 5:
        raise ValueError("global Z offset must be finite and from -5 to 5 mm")
    return round(value, 3)


def surface(value):
    value = str(value).strip().lower() or "default"
    if not NAME.fullmatch(value):
        raise ValueError("SURFACE must be 1-64 lowercase letters, digits, or underscores")
    return value


def read_table(path, baseline):
    if not os.path.exists(path):
        offset(baseline)  # validate, but do not round/change a native baseline
        return {"default": INITIAL_DEFAULT_Z_OFFSET}, None
    with open(path, "rb") as source:
        data = source.read()
    table = json.loads(data)
    if not isinstance(table, dict) or table.get("version") != 1:
        raise ValueError("unsupported global Z table version")
    values = table.get("offsets")
    if not isinstance(values, dict) or "default" not in values:
        raise ValueError("global Z table requires a default offset")
    if any(surface(key) != key for key in values):
        raise ValueError("global Z table has a noncanonical surface name")
    return {key: offset(value) for key, value in values.items()}, hashlib.sha256(data).hexdigest()


def write_json(path, value):
    """Atomic, flushed JSON replacement; a failed write leaves the old file intact."""
    descriptor, temporary = tempfile.mkstemp(prefix=".prtouch-global-z-", dir=os.path.dirname(path))
    try:
        with os.fdopen(descriptor, "w") as output:
            json.dump(value, output, indent=2, sort_keys=True, allow_nan=False)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        if os.path.exists(path):
            os.chmod(temporary, os.stat(path).st_mode)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class K2PRTouchGlobalZ:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.gcode = self.printer.lookup_object("gcode")
        self.path = config.get("offsets_path", "/mnt/UDISK/printer_data/config/custom/prtouch_global_z.json")
        self.installed = False
        self.baseline = None
        self.values = None
        self.next_transform = None
        self.gcode_move = None
        self.active_surface = "default"
        self.active_value = None
        self.delta = 0.0
        self.session = None
        self.names = []
        self.index = 0
        self.increment = .010
        self.recovery_path = None
        for name, handler in (
                ("OFFSETS", self.cmd_open), ("SELECT", self.cmd_select),
                ("STEP", self.cmd_step), ("ADJUST", self.cmd_adjust),
                ("STAGE", self.cmd_stage), ("INHERIT", self.cmd_inherit),
                ("SAVE", self.cmd_save), ("CANCEL", self.cmd_cancel),
                ("APPLY", self.cmd_apply), ("RESET", self.cmd_reset),
                ("STATUS", self.cmd_status)):
            self.gcode.register_command("K2_PRTOUCH_GLOBAL_Z_" + name, handler)
        self.printer.register_event_handler("klippy:ready", self._ready)

    def _ready(self):
        if self.installed or self.printer.lookup_object("cartographer", None) is not None:
            return
        compat = self.printer.lookup_object("k2_prtouch_touchscreen", None)
        probe = self.printer.lookup_object("probe", None)
        if (compat is None or not compat.get_status(0).get("transient_only")
                or getattr(probe, "name", None) != "prtouch_v3"):
            raise self.printer.config_error("Global PR Touch offsets require active transient-only touchscreen compatibility")
        try:
            self.baseline = float(probe.z_offset)
            offset(self.baseline)  # reject invalid native values before wrapping motion
            self.values, unused = read_table(self.path, self.baseline)
        except (OSError, ValueError, TypeError) as exc:
            raise self.printer.config_error("Invalid PR Touch global Z table: %s" % exc)
        self.gcode_move = self.printer.lookup_object("gcode_move")
        self.next_transform = self.gcode_move.set_move_transform(self, force=True)
        self.installed = True
        self._activate("default", self.values["default"])

    def _require_native(self, gcmd):
        if not self.installed or self.printer.lookup_object("cartographer", None) is not None:
            raise gcmd.error("Global PR Touch offsets are unavailable; Cartographer is never changed")

    def _state(self):
        stats = self.printer.lookup_object("print_stats", None)
        return stats.get_status(0).get("state") if stats is not None else None

    def _idle(self, gcmd):
        self._require_native(gcmd)
        if self._state() not in ("standby", "complete", "cancelled", "error"):
            raise gcmd.error("Global Z editing requires an idle printer; printing, paused, or unknown state is refused")

    def _plate_aware(self):
        return self.printer.lookup_object("gcode_macro _PLATE_AWARE_MESH", None) is not None

    def _activate(self, name, value):
        self.active_surface, self.active_value = name, value
        # Never add the full saved calibration again: Creality already uses
        # baseline. The display's homing_origin/material offset is untouched.
        self.delta = value - self.baseline
        self.gcode_move.reset_last_position()

    def get_position(self):
        self._restore_recovery(position_sync=True)
        pos = list(self.next_transform.get_position())
        pos[2] += self.delta
        return pos

    def move(self, pos, speed):
        self._restore_recovery()
        actual = list(pos)
        actual[2] -= self.delta
        self.next_transform.move(actual, speed)

    def _recovery_file(self):
        sd = self.printer.lookup_object("virtual_sdcard", None)
        return getattr(sd, "print_file_name_path", None)

    def _record_recovery(self, gcmd):
        path = self._recovery_file()
        self.recovery_path = path
        if self._state() != "printing" or not path or not os.path.isfile(path):
            return
        try:
            with open(path) as source:
                data = json.load(source)
            if not isinstance(data, dict):
                raise ValueError("recovery file is not an object")
            data[RECOVERY_KEY] = {"surface": self.active_surface,
                                  "offset": self.active_value, "baseline": self.baseline}
            write_json(path, data)
        except (OSError, ValueError, TypeError) as exc:
            raise gcmd.error("Could not record global Z print-recovery state: %s" % exc)

    def _restore_recovery(self, position_sync=False):
        path = self._recovery_file()
        if not path or path == self.recovery_path or self._state() != "printing":
            return
        try:
            with open(path) as source:
                data = json.load(source)
            if not isinstance(data, dict):
                raise ValueError("recovery file is not an object")
            entry = data.get(RECOVERY_KEY)
            if entry is not None:
                if not isinstance(entry, dict):
                    raise ValueError("global Z recovery entry is not an object")
                name, value = surface(entry["surface"]), offset(entry["offset"])
                if float(entry["baseline"]) != self.baseline:
                    raise ValueError("native baseline changed since the interrupted print")
                if name != "default" and not self._plate_aware():
                    raise ValueError("the interrupted print requires plate-aware meshes")
                if value - self.baseline != self.delta and not position_sync:
                    raise ValueError("resume must synchronize the homed position before moving with a restored global Z offset")
                # Before the first resumed move, reuse the frozen print value,
                # not a subsequently edited table or the last UI selection.
                self.active_surface, self.active_value = name, value
                self.delta = value - self.baseline
            self.recovery_path = path
        except (OSError, ValueError, TypeError, KeyError) as exc:
            raise self.printer.command_error("Cannot restore global Z recovery state: %s" % exc)

    def cmd_reset(self, gcmd):
        self._require_native(gcmd)
        self.recovery_path = self._recovery_file()
        self._activate("default", self.values["default"])

    def cmd_apply(self, gcmd):
        self._require_native(gcmd)
        try:
            name = surface(gcmd.get("SURFACE", "")) if self._plate_aware() else "default"
        except ValueError as exc:
            raise gcmd.error(str(exc))
        self.recovery_path = self._recovery_file()
        self._activate(name, self.values.get(name, self.values["default"]))
        self._record_recovery(gcmd)
        gcmd.respond_info("[PRTOUCH_GLOBAL_Z] SURFACE=%s global=%.3f baseline=%.3f delta=%.3f%s"
                          % (name, self.active_value, self.baseline, self.delta,
                             " (inherits DEFAULT)" if name not in self.values else ""))

    def get_status(self, eventtime):
        return {"installed": self.installed, "baseline": self.baseline,
                "active_surface": self.active_surface, "global_z_offset": self.active_value,
                "baseline_delta": self.delta, "plate_aware": self._plate_aware(),
                "offsets": dict(self.values or {}), "session_open": self.session is not None}

    def cmd_status(self, gcmd):
        gcmd.respond_info("[PRTOUCH_GLOBAL_Z] %s" % json.dumps(self.get_status(0), sort_keys=True))

    def _action(self, text):
        self.gcode.respond_raw("// action:" + text)

    def _session(self, gcmd):
        self._idle(gcmd)
        if self.session is None:
            raise gcmd.error("Open Global_Z_Offsets_No_Carto first")
        if self.session_plate_aware != self._plate_aware():
            raise gcmd.error("Plate workflow changed; cancel and reopen the editor")

    def _show(self):
        self._action("prtouch_global_offsets_begin %d|%.3f" % (self.index, self.increment))
        for index, name in enumerate(self.names):
            self._action("prtouch_global_offsets_surface %s|%.3f|%d|%d" %
                         (name.upper(), self._value(name), index, name not in self.session))
        self._action("prtouch_global_offsets_show")

    def _value(self, name):
        return self.session.get(name, self.session["default"])

    def cmd_open(self, gcmd):
        self._idle(gcmd)
        try:
            saved, self.digest = read_table(self.path, self.baseline)
        except (OSError, ValueError, TypeError) as exc:
            raise gcmd.error("Could not read global Z table: %s" % exc)
        if saved != self.values:
            raise gcmd.error("Global Z file changed outside this editor; restart before editing")
        self.session, self.original = dict(saved), dict(saved)
        self.session_plate_aware = self._plate_aware()
        names = set(SURFACES) | set(saved) if self.session_plate_aware else {"default"}
        if self.session_plate_aware:
            raw = self.printer.lookup_object("configfile").get_status(0).get("config", {})
            mesh = self.printer.lookup_object("bed_mesh", None)
            mesh_names = list(mesh.get_status(0).get("profiles", {})) if mesh is not None else []
            mesh_names += [section[len("bed_mesh "):] for section in raw if section.startswith("bed_mesh ")]
            for mesh_name in mesh_names:
                match = MESH_NAME.fullmatch(mesh_name)
                if match and NAME.fullmatch(match[1]):
                    names.add(match[1])
        self.names = [name for name in SURFACES if name in names] + sorted(names - set(SURFACES))
        self.index, self.increment = 0, .010
        self._action("prompt_end")  # dismiss a legacy stacked prompt after upgrading
        self._show()

    def cmd_select(self, gcmd):
        self._session(gcmd)
        self.index = gcmd.get_int("INDEX", minval=0, maxval=len(self.names) - 1)
        self._show()

    def cmd_step(self, gcmd):
        self._session(gcmd)
        value = gcmd.get_float("VALUE")
        if value not in (.005, .010, .025, .050):
            raise gcmd.error("Step must be 0.005, 0.010, 0.025, or 0.050")
        self.increment = value
        self._show()

    def cmd_adjust(self, gcmd):
        self._session(gcmd)
        direction = gcmd.get("DIRECTION")
        if direction not in ("up", "down"):
            raise gcmd.error("DIRECTION must be up or down")
        name = self.names[self.index]
        try:
            self.session[name] = offset(self._value(name) + (self.increment if direction == "up" else -self.increment))
        except ValueError as exc:
            raise gcmd.error(str(exc))
        self._show()

    def cmd_stage(self, gcmd):
        self._session(gcmd)
        index = gcmd.get_int("INDEX", minval=0, maxval=len(self.names) - 1)
        try:
            self.session[self.names[index]] = offset(gcmd.get_float("VALUE"))
        except ValueError as exc:
            raise gcmd.error(str(exc))
        self._show()

    def cmd_inherit(self, gcmd):
        self._session(gcmd)
        name = self.names[self.index]
        if name == "default":
            raise gcmd.error("DEFAULT cannot inherit itself")
        self.session.pop(name, None)
        self._show()

    def cmd_cancel(self, gcmd):
        self.session = None
        self._action("prtouch_global_offsets_end")
        gcmd.respond_info("Global No-Carto Z Offset changes cancelled")

    def cmd_save(self, gcmd):
        self._session(gcmd)
        try:
            unused, digest = read_table(self.path, self.baseline)
            if digest != self.digest:
                raise ValueError("global Z file changed; cancel and reopen")
            changed = self.session != self.original
            if changed:
                write_json(self.path, {"version": 1, "offsets": self.session})
        except (OSError, ValueError, TypeError) as exc:
            raise gcmd.error("Nothing activated; could not save global Z table: %s" % exc)
        self.values = dict(self.session)
        self._activate(self.active_surface, self.values.get(self.active_surface, self.values["default"]))
        self.session = None
        self._action("prtouch_global_offsets_end")
        gcmd.respond_info("Global No-Carto Z offsets %s; no motion, staging, or restart" %
                          ("saved and active" if changed else "unchanged"))


def load_config(config):
    return K2PRTouchGlobalZ(config)
