"""Temporary, observational tracing of Creality's native PR Touch Z offsets.

Never sends G-code, changes offsets, or writes printer configuration. Hooks
delegate to the original handlers once, with unchanged arguments and results.
"""

import datetime
import json
import logging
from logging.handlers import RotatingFileHandler
import math
import os
import re
import traceback


COMMANDS = (
    "G28", "_HOME_Z", "SAFE_MOVE_Z", "Z_TILT_ADJUST",
    "PROBE_CALIBRATE", "Z_OFFSET_APPLY_PROBE", "SET_GCODE_OFFSET",
    "SAVE_CONFIG", "CXSAVE_CONFIG", "START_PRINT", "BOX_START_PRINT",
    "BOX_NOZZLE_CLEAN", "SAVE_ENDPRINT", "END_PRINT", "CANCEL_PRINT",
    "RESTORE_GCODE_STATE", "SET_KINEMATIC_POSITION", "G92",
)
NATIVE_FIELDS = ("z_offset", "z_offset_calibrate", "z_offset_change_flag",
                 "G28_temp", "bst_zoft")


class TraceLogHandler(RotatingFileHandler):
    def handleError(self, record):
        # Default logging swallows disk-write errors. Surface them to _emit's
        # fail-open handler so status/klippy.log can report missing evidence.
        raise


def scalar(value):
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float) and math.isfinite(value):
        return value
    return None


def saved_offsets(text):
    """Keep normal and SAVE_CONFIG entries distinct; absence is not zero."""
    result = {"normal": [], "save_config": []}
    sections = {"normal": None, "save_config": None}
    for line in text.splitlines():
        source = "save_config" if line.startswith("#*#") else "normal"
        line = (line[3:] if source == "save_config" else line).strip()
        if not line or line.startswith(("#", ";")):
            continue
        section = re.match(r"^\[([^]]+)\]", line)
        if section:
            sections[source] = section.group(1).strip().lower()
            continue
        match = re.match(r"^z_offset\s*[:=]\s*([^#;]+)", line, re.I)
        if sections[source] == "prtouch_v3" and match:
            result[source].append(match.group(1).strip())
    return result


class K2PRTouchZTrace:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.reactor = self.printer.get_reactor()
        self.gcode = self.printer.lookup_object("gcode")
        self.configfile = self.printer.lookup_object("configfile")
        self.config_path = os.path.abspath(
            self.printer.get_start_args()["config_file"])
        default_log = os.path.join(os.path.dirname(self.config_path), "..",
                                   "logs", "prtouch-z-trace.log")
        self.log_path = os.path.abspath(default_log)
        self.interval = config.getfloat("poll_interval", 1., minval=.5)
        self.active = False
        self.last_state = None
        self.file_signature = None
        self.file_state = None
        self.handler = None
        self.log_error = None
        self.sequence = 0
        self.command_stack = []
        self.hooked_commands = []
        self.original_set = self.configfile.set
        self.original_remove = self.configfile.remove_section
        self.configfile.set = self._set
        self.configfile.remove_section = self._remove_section
        self.gcode.register_command(
            "K2_PRTOUCH_Z_TRACE_SNAPSHOT", self.cmd_snapshot,
            desc="Record PR Touch offset state without changing it")
        self.printer.register_event_handler("klippy:ready", self._ready)
        self.printer.register_event_handler("klippy:shutdown", self._shutdown)
        self.printer.register_event_handler("klippy:disconnect", self._disconnect)

    def _emit(self, event, **data):
        # Observation failures must not turn a successful native command into
        # an error (or mask a native error). Keep diagnostics bounded on disk.
        try:
            if self.handler is None:
                os.makedirs(os.path.dirname(self.log_path), exist_ok=True)
                self.handler = TraceLogHandler(
                    self.log_path, maxBytes=1024 * 1024, backupCount=2,
                    encoding="utf-8")
                self.handler.setFormatter(logging.Formatter("%(message)s"))
            self.sequence += 1
            record = dict(event=event, seq=self.sequence, pid=os.getpid(),
                          utc=datetime.datetime.now(
                              datetime.timezone.utc).isoformat(),
                          monotonic=self.reactor.monotonic(),
                          commands=list(self.command_stack), **data)
            message = json.dumps(record, sort_keys=True, allow_nan=False)
            self.handler.handle(logging.LogRecord(
                "prtouch-z-trace", logging.INFO, __file__, 0, message, (), None))
        except Exception as exc:
            error = "%s: %s" % (type(exc).__name__, exc)
            if self.log_error != error:
                logging.warning("PR Touch Z trace could not record: %s", error)
            self.log_error = error

    def _read_file(self, force=False):
        try:
            stat = os.stat(self.config_path)
            signature = (stat.st_mtime_ns, stat.st_size, stat.st_ino)
            if force or signature != self.file_signature:
                if stat.st_size > 2 * 1024 * 1024:
                    raise ValueError("printer config exceeds diagnostic read limit")
                with open(self.config_path, encoding="utf-8", errors="replace") as f:
                    self.file_state = {"entries": saved_offsets(f.read()),
                                       "mtime_ns": stat.st_mtime_ns,
                                       "size": stat.st_size}
                self.file_signature = signature
            return self.file_state
        except (OSError, ValueError) as exc:
            self.file_signature = None
            return {"error": "%s: %s" % (type(exc).__name__, exc)}

    def _status(self, name):
        obj = self.printer.lookup_object(name, None)
        return obj.get_status(self.reactor.monotonic()) if obj else {}

    def _state(self, force_file=False):
        config_status = self.configfile.get_status(self.reactor.monotonic())
        probe = self.printer.lookup_object("probe", None)
        native = self.printer.lookup_object("prtouch_v3", None)
        probe_status = self._status("probe")
        move = self._status("gcode_move")
        origin = move.get("homing_origin")
        origin_z = scalar(origin[2]) if origin is not None else None
        stats = self._status("print_stats")
        return {
            "file": self._read_file(force_file),
            "loaded_config_offset": scalar(config_status.get("config", {}).get(
                "prtouch_v3", {}).get("z_offset")),
            "pending_save_offset": scalar(config_status.get(
                "save_config_pending_items", {}).get("prtouch_v3", {}).get("z_offset")),
            "save_config_pending": config_status.get("save_config_pending"),
            "probe_loaded_offset": scalar(getattr(probe, "z_offset", None)),
            "probe_reported_offset": scalar(probe_status.get("z_offset")),
            "probe_calibrate_offset": scalar(getattr(probe, "z_offset_calibrate", None)),
            "probe_change_flag": scalar(getattr(probe, "z_offset_change_flag", None)),
            "native_fields": {name: scalar(getattr(native, name, None))
                              for name in NATIVE_FIELDS},
            "homing_origin_z": origin_z,
            "print_state": scalar(stats.get("state")),
            "print_file": scalar(stats.get("filename")),
        }

    def _context(self):
        # Temperatures/positions are context only, not change triggers: don't
        # fill the log simply because a heater warms or the toolhead moves.
        context = {}
        for name in ("extruder", "heater_bed"):
            status = self._status(name)
            context[name] = {key: scalar(status.get(key))
                             for key in ("temperature", "target")}
        mesh = self._status("bed_mesh")
        context["mesh_profile"] = scalar(mesh.get("profile_name"))
        return context

    def _snapshot(self, event, force_file=False, **data):
        try:
            state = self._state(force_file)
            self._emit(event, state=state, context=self._context(), **data)
            self.last_state = state
        except Exception as exc:
            self._emit("observation_error", source=event,
                       error="%s: %s" % (type(exc).__name__, exc))

    def _writer_details(self):
        return {"caller_stack": ["%s:%s:%d" % (frame.filename, frame.name, frame.lineno)
                                  for frame in traceback.extract_stack(limit=14)[:-2]]}

    def _writer_snapshot(self, event, **data):
        try:
            self._snapshot(event, force_file=True, **data, **self._writer_details())
        except Exception as exc:
            self._emit("observation_error", source=event, error=str(exc))

    def _set(self, section, option, value):
        relevant = str(section).lower() == "prtouch_v3" and str(option).lower() == "z_offset"
        if relevant:
            self._writer_snapshot("config_set_before", requested_value=str(value))
        try:
            return self.original_set(section, option, value)
        finally:
            if relevant:
                self._snapshot("config_set_after", force_file=True)

    def _remove_section(self, section):
        relevant = str(section).lower() == "prtouch_v3"
        if relevant:
            self._writer_snapshot("config_remove_before")
        try:
            return self.original_remove(section)
        finally:
            if relevant:
                self._snapshot("config_remove_after", force_file=True)

    def _command(self, name, original):
        def observed(gcmd):
            self.command_stack.append(name)
            try:
                parameters = {str(k): str(v) for k, v in
                              gcmd.get_command_parameters().items()}
                self._snapshot("command_before", force_file=True, command=name,
                               parameters=parameters)
            except Exception as exc:
                self._emit("observation_error", source=name, error=str(exc))
            try:
                result = original(gcmd)
            except BaseException:
                self._snapshot("command_error", force_file=True, command=name)
                raise
            else:
                self._snapshot("command_after", force_file=True, command=name)
                return result
            finally:
                self.command_stack.pop()
        return observed

    def _ready(self):
        if self.active:
            return
        probe = self.printer.lookup_object("probe", None)
        if (self.printer.lookup_object("cartographer", None) is not None
                or self.printer.lookup_object("prtouch_v3", None) is None
                or getattr(probe, "name", None) != "prtouch_v3"):
            self._emit("inactive", reason="requires native PR Touch, no Cartographer")
            self.configfile.set = self.original_set
            self.configfile.remove_section = self.original_remove
            return
        for name in COMMANDS:
            original = self.gcode.register_command(name, None)
            if original is None:
                continue
            try:
                self.gcode.register_command(name, self._command(name, original))
            except Exception:
                self.gcode.register_command(name, None)
                self.gcode.register_command(name, original)
                self._emit("hook_unavailable", command=name)
                continue
            self.hooked_commands.append(name)
        self.active = True
        self._snapshot("ready", force_file=True,
                       hooked_commands=self.hooked_commands,
                       config_path=self.config_path)
        self.reactor.register_timer(self._poll, self.reactor.monotonic() + self.interval)
        logging.info("PR Touch Z trace active: %s", self.log_path)

    def _poll(self, eventtime):
        if not self.active:
            return self.reactor.NEVER
        try:
            state = self._state()
            if state != self.last_state:
                self._emit("state_changed", previous=self.last_state, state=state,
                           context=self._context())
                self.last_state = state
        except Exception as exc:
            self._emit("observation_error", source="poll", error=str(exc))
        return eventtime + self.interval

    def _shutdown(self):
        if self.active:
            self._snapshot("shutdown", force_file=True)
        self.active = False

    def _disconnect(self):
        if self.active:
            self._snapshot("disconnect", force_file=True)
        self.active = False
        if self.handler is not None:
            self.handler.close()
            self.handler = None

    def cmd_snapshot(self, gcmd):
        if not self.active:
            gcmd.respond_info("PR Touch Z trace is inactive (native no-Carto only)")
            return
        self._snapshot("manual", force_file=True, label=gcmd.get("LABEL", "manual"))
        gcmd.respond_info("PR Touch Z trace: %s%s" % (
            self.log_path, " (logging error: %s)" % self.log_error if self.log_error else ""))

    def get_status(self, eventtime):
        return {"active": self.active, "log_path": self.log_path,
                "logging_error": self.log_error, "hooked_commands": list(self.hooked_commands)}


def load_config(config):
    return K2PRTouchZTrace(config)
