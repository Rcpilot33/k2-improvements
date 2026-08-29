# Prime-tower footprint discovery for adaptive mesh and purge placement.
#
# Creality Print does not emit EXCLUDE_OBJECT_DEFINE geometry for its prime
# tower.  The tower is, however, identified by ;TYPE:Prime tower blocks in
# the selected G-code file.  This module scans those actual motion blocks and
# publishes one conservative rectangular footprint for other Klipper
# components to consume before printing begins.
#
# This file may be distributed under the terms of the GNU GPLv3 license.

import logging
import math
import os
import re
import threading


_NUMBER = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"
_PARAM_RE = re.compile(r"(?:^|\s)([XY])\s*(%s)" % _NUMBER, re.IGNORECASE)
_E_PARAM_RE = re.compile(r"(?:^|\s)E\s*(%s)" % _NUMBER, re.IGNORECASE)
_COMMAND_RE = re.compile(r"^\s*([GMT]\d+)\b", re.IGNORECASE)
_TYPE_RE = re.compile(r"^\s*;\s*TYPE\s*:\s*(.*?)\s*$", re.IGNORECASE)
_TOWER_END_RE = re.compile(
    r"^\s*;\s*WIPE_TOWER_END\b", re.IGNORECASE)
_TOWER_MARKER_BYTES_RE = re.compile(
    br"(?im)^[ \t]*;[ \t]*TYPE[ \t]*:[ \t]*Prime[ \t]+tower[ \t]*\r?$"
)
_NO_SPARSE_BYTES_RE = re.compile(
    br"(?im)^[ \t]*;[ \t]*wipe_tower_no_sparse_layers[ \t]*="
    br"[ \t]*(?:1|true)[ \t]*(?:;[^\r\n]*)?\r*$"
)
_TOWER_ENABLED_BYTES_RE = re.compile(
    br"(?im)^[ \t]*;[ \t]*enable_prime_tower[ \t]*="
    br"[ \t]*(?:1|true)[ \t]*(?:;[^\r\n]*)?\r*$"
)
_MARKER_SCAN_CHUNK = 1024 * 1024
_MARKER_SCAN_OVERLAP = 512
_METADATA_TAIL_SIZE = 1024 * 1024
_DETAILED_CANCEL_INTERVAL = 4096
_START_PRINT_PREFIX_SIZE = 1024 * 1024
_START_PRINT_LINE_RE = re.compile(
    r"(?im)^[ \t]*START_PRINT\b([^\r\n;]*)")
_START_PRINT_PARAM_RE = re.compile(
    r"(?:^|\s)(BED_TEMP|CHAMBER_TEMP)\s*=\s*(%s)" % _NUMBER,
    re.IGNORECASE)

_NO_SPARSE_BLOCK_REASON = (
    "Prime-tower safety: Creality Print 'No sparse layers (beta)' is "
    "enabled. On the K2 Plus, a delayed tower can raise a partially "
    "printed model into the toolhead or X rail. Disable that setting, "
    "reslice, and resend this file."
)


class _ScanCancelled(Exception):
    pass


class _UnsupportedPrimeTower(Exception):
    pass


class _ScanJob:
    def __init__(self, cache_key, path, started_at, timeout):
        self.cache_key = cache_key
        self.path = path
        self.started_at = started_at
        self.deadline = started_at + timeout
        self.cancel_event = threading.Event()
        self.done_event = threading.Event()
        self.status = None
        self.error = None
        self.block_reason = None


def _check_cancel(cancel_event):
    if cancel_event is not None and cancel_event.is_set():
        raise _ScanCancelled()


def _finite_point(point):
    return point[0] is not None and point[1] is not None \
        and math.isfinite(point[0]) and math.isfinite(point[1])


def _file_contains_prime_tower(path, cancel_event=None):
    """Quickly reject files without a prime-tower type marker.

    This scan operates on large byte chunks so a normal single-color G-code
    does not pay the cost of decoding and applying several regular
    expressions to every motion line.  The overlap preserves markers split
    across read boundaries; a false positive only falls back to the detailed
    parser and is therefore safe.
    """
    overlap = b""
    with open(path, "rb") as handle:
        while True:
            _check_cancel(cancel_event)
            chunk = handle.read(_MARKER_SCAN_CHUNK)
            if not chunk:
                return False
            data = overlap + chunk
            if _TOWER_MARKER_BYTES_RE.search(data) is not None:
                return True
            overlap = data[-_MARKER_SCAN_OVERLAP:]


def _read_prime_tower_footer(path, cancel_event=None):
    """Read Creality Print's effective per-job tower settings."""
    _check_cancel(cancel_event)
    with open(path, "rb") as handle:
        handle.seek(0, os.SEEK_END)
        file_size = handle.tell()
        handle.seek(max(0, file_size - _METADATA_TAIL_SIZE), os.SEEK_SET)
        metadata = handle.read()
    _check_cancel(cancel_event)
    return {
        "enabled": _TOWER_ENABLED_BYTES_RE.search(metadata) is not None,
        "no_sparse": _NO_SPARSE_BYTES_RE.search(metadata) is not None,
    }


def _uses_no_sparse_prime_tower(path, cancel_event=None):
    return _read_prime_tower_footer(path, cancel_event)["no_sparse"]


def _read_start_print_temperatures(path):
    """Read the sliced bed/chamber targets without scanning the whole file."""
    with open(path, "rb") as handle:
        prefix = handle.read(_START_PRINT_PREFIX_SIZE)
    text = prefix.decode("utf-8", errors="replace")
    line_match = _START_PRINT_LINE_RE.search(text)
    if line_match is None:
        return None
    temperatures = {}
    for name, raw_value in _START_PRINT_PARAM_RE.findall(
            line_match.group(1)):
        value = float(raw_value)
        if math.isfinite(value) and value >= 0.0:
            temperatures[name.upper()] = value
    if "BED_TEMP" not in temperatures:
        return None
    return temperatures


def parse_prime_tower(path, padding=0.5, cancel_event=None):
    """Return a rectangular polygon around all prime-tower motion blocks.

    The parser follows modal absolute/relative XY positioning and records the
    actual path endpoints between ``;TYPE:Prime tower`` and
    ``; WIPE_TOWER_END``.  It deliberately uses motion rather than slicer
    metadata so rotation, resizing, sparse layers, and late-starting towers
    are handled without slicer-specific geometry calculations.
    """
    footer = _read_prime_tower_footer(path, cancel_event)
    # Creality Print writes enable_prime_tower as an effective per-job value:
    # it is zero for a single-color job even when the saved profile retains
    # no-sparse=1.  Check this small footer first so an unsafe large file
    # cannot time out while its first tower marker is hundreds of MB away.
    if footer["enabled"] and footer["no_sparse"]:
        raise _UnsupportedPrimeTower(_NO_SPARSE_BLOCK_REASON)
    if not _file_contains_prime_tower(path, cancel_event):
        return {
            "detected": False,
            "polygon": [],
            "bounds": [],
            "blocks": 0,
        }
    # The real toolpath marker remains the authority and fallback for files
    # from slicer versions that omit or misreport enable_prime_tower.
    if footer["no_sparse"]:
        raise _UnsupportedPrimeTower(_NO_SPARSE_BLOCK_REASON)

    absolute_xy = True
    absolute_e = True
    x_pos = None
    y_pos = None
    e_pos = 0.0
    in_tower = False
    tower_blocks = 0
    points = []

    with open(path, "r", encoding="utf-8", errors="replace") as handle:
        for line_number, raw_line in enumerate(handle):
            if line_number % _DETAILED_CANCEL_INTERVAL == 0:
                _check_cancel(cancel_event)
            type_match = _TYPE_RE.match(raw_line)
            if type_match is not None:
                in_tower = type_match.group(1).strip().lower() == "prime tower"
                if in_tower:
                    tower_blocks += 1
                continue
            if in_tower and _TOWER_END_RE.match(raw_line):
                in_tower = False
                continue

            code = raw_line.split(";", 1)[0].strip()
            if not code:
                continue
            command_match = _COMMAND_RE.match(code)
            if command_match is None:
                continue
            command = command_match.group(1).upper()
            if command == "G90":
                absolute_xy = True
                continue
            if command == "G91":
                absolute_xy = False
                continue
            if command == "M82":
                absolute_e = True
                continue
            if command == "M83":
                absolute_e = False
                continue

            params = dict((axis.upper(), float(value))
                          for axis, value in _PARAM_RE.findall(code))
            e_match = _E_PARAM_RE.search(code)
            e_value = float(e_match.group(1)) if e_match is not None else None
            if command == "G92":
                if "X" in params:
                    x_pos = params["X"]
                if "Y" in params:
                    y_pos = params["Y"]
                if e_value is not None:
                    e_pos = e_value
                continue
            if command not in ("G0", "G1", "G2", "G3"):
                continue

            old_x, old_y = x_pos, y_pos
            new_x, new_y = x_pos, y_pos
            if "X" in params:
                if absolute_xy or x_pos is None:
                    new_x = params["X"]
                else:
                    new_x = x_pos + params["X"]
            if "Y" in params:
                if absolute_xy or y_pos is None:
                    new_y = params["Y"]
                else:
                    new_y = y_pos + params["Y"]
            e_delta = 0.0
            if e_value is not None:
                e_delta = e_value - e_pos if absolute_e else e_value
                e_pos = e_value if absolute_e else e_pos + e_value
            x_pos, y_pos = new_x, new_y
            if in_tower and e_delta > 0.000001:
                if _finite_point((old_x, old_y)):
                    points.append((old_x, old_y))
                if _finite_point((x_pos, y_pos)):
                    points.append((x_pos, y_pos))

    if not points:
        return {
            "detected": False,
            "polygon": [],
            "bounds": [],
            "blocks": tower_blocks,
        }

    padding = max(0.0, float(padding))
    x_min = min(point[0] for point in points) - padding
    x_max = max(point[0] for point in points) + padding
    y_min = min(point[1] for point in points) - padding
    y_max = max(point[1] for point in points) + padding
    bounds = [x_min, y_min, x_max, y_max]
    return {
        "detected": True,
        "polygon": [
            [x_min, y_min], [x_max, y_min],
            [x_max, y_max], [x_min, y_max],
        ],
        "bounds": bounds,
        "blocks": tower_blocks,
    }


class PrimeTower:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.reactor = self.printer.get_reactor()
        self.gcode = self.printer.lookup_object("gcode")
        self.padding = config.getfloat("padding", 0.5, minval=0.0)
        self.scan_timeout = config.getfloat(
            "scan_timeout", 120.0, minval=1.0)
        self._cache_key = None
        self._active_job = None
        self._status = self._empty_status()
        self.gcode.register_command(
            "PRIME_TOWER_WAIT", self.cmd_PRIME_TOWER_WAIT,
            desc="Wait cooperatively for prime-tower footprint discovery")

    @staticmethod
    def _empty_status(source=None, error=None, ready=True,
                      blocked=False, block_reason=None):
        return {
            "detected": False,
            "polygon": [],
            "bounds": [],
            "blocks": 0,
            "source": source,
            "error": error,
            "ready": ready,
            "blocked": blocked,
            "block_reason": block_reason,
        }

    def _selected_path(self, eventtime):
        virtual_sdcard = self.printer.lookup_object("virtual_sdcard", None)
        if virtual_sdcard is None:
            return None
        try:
            return virtual_sdcard.get_status(eventtime).get("file_path")
        except Exception:
            logging.exception("prime_tower: unable to query virtual_sdcard")
            return None

    def _cancel_active_job(self):
        job = self._active_job
        if job is not None:
            job.cancel_event.set()
            self._active_job = None

    def _finish_scan(self, eventtime, job):
        if job is not self._active_job or not job.done_event.is_set():
            return
        self._active_job = None
        if job.cancel_event.is_set():
            return
        if job.block_reason is not None:
            logging.error(
                "prime_tower: blocked unsafe file %s: %s",
                job.path, job.block_reason)
            self._status = self._empty_status(
                job.path, blocked=True, block_reason=job.block_reason)
            return
        if job.error is not None:
            logging.error(
                "prime_tower: scan failed for %s: %s", job.path, job.error)
            self._status = self._empty_status(job.path, job.error)
            return
        status = job.status
        if status is None:
            error = "scan worker completed without a result"
            logging.error("prime_tower: %s for %s", error, job.path)
            self._status = self._empty_status(job.path, error)
            return
        status["source"] = job.path
        status["error"] = None
        status["ready"] = True
        status["blocked"] = False
        status["block_reason"] = None
        self._status = status
        elapsed = max(0.0, eventtime - job.started_at)
        file_size = job.cache_key[1]
        if status["detected"]:
            logging.info(
                "prime_tower: detected %d blocks at "
                "X[%.3f, %.3f] Y[%.3f, %.3f] in %s "
                "(%s bytes, %.3fs)",
                status["blocks"], status["bounds"][0],
                status["bounds"][2], status["bounds"][1],
                status["bounds"][3], job.path, file_size, elapsed)
        else:
            logging.info(
                "prime_tower: no tower detected in %s (%s bytes, %.3fs)",
                job.path, file_size, elapsed)

    def _scan_worker(self, job):
        cancelled = False
        try:
            job.status = parse_prime_tower(
                job.path, self.padding, job.cancel_event)
        except _ScanCancelled:
            cancelled = True
        except _UnsupportedPrimeTower as err:
            job.block_reason = str(err)
        except Exception as err:
            job.error = str(err)
        finally:
            job.done_event.set()
        if cancelled or job.cancel_event.is_set():
            return
        try:
            self.reactor.register_async_callback(
                lambda eventtime: self._finish_scan(eventtime, job))
        except Exception:
            logging.exception(
                "prime_tower: unable to publish scan result for %s; "
                "the reactor poll will recover it", job.path)

    def _report_scan_status(self):
        message = (
            "Prime-tower/KAMP safety: scanning selected G-code for "
            "prime-tower geometry...")
        try:
            self.gcode.respond_info(message)
        except Exception:
            logging.exception("prime_tower: unable to report scan status")

    def _hold_scan_temperatures(self, path):
        try:
            temperatures = _read_start_print_temperatures(path)
        except Exception:
            logging.exception(
                "prime_tower: unable to read START_PRINT temperatures from %s",
                path)
            return
        if temperatures is None:
            logging.warning(
                "prime_tower: START_PRINT bed target was not found in the "
                "first %d bytes of %s; leaving heaters unchanged",
                _START_PRINT_PREFIX_SIZE, path)
            return
        commands = [
            "M104 S140",
            "M140 S%.3f" % (temperatures["BED_TEMP"],),
        ]
        chamber_temp = temperatures.get("CHAMBER_TEMP", 0.0)
        if chamber_temp > 0.0:
            commands.append("M141 S%.3f" % (chamber_temp,))
        try:
            self.gcode.run_script_from_command("\n".join(commands))
        except Exception:
            # Temperature holding is a convenience during a potentially long
            # scan. It must never weaken the fail-open parser behavior.
            logging.exception(
                "prime_tower: unable to hold preheat temperatures while "
                "scanning %s", path)

    def _start_scan(self, cache_key, path, eventtime):
        self._cancel_active_job()
        self._cache_key = cache_key
        job = _ScanJob(cache_key, path, eventtime, self.scan_timeout)
        self._active_job = job
        self._status = self._empty_status(path, ready=False)
        self._report_scan_status()
        worker = threading.Thread(
            target=self._scan_worker,
            args=(job,),
            name="prime-tower-scan")
        worker.daemon = True
        try:
            worker.start()
        except Exception as err:
            error = "unable to start scan worker: %s" % (err,)
            logging.exception("prime_tower: %s for %s", error, path)
            job.cancel_event.set()
            self._active_job = None
            self._status = self._empty_status(path, error)

    def get_status(self, eventtime):
        path = self._selected_path(eventtime)
        if not path:
            self._cancel_active_job()
            self._cache_key = None
            self._status = self._empty_status()
            return dict(self._status)
        try:
            stat_result = os.stat(path)
            modified = getattr(stat_result, "st_mtime_ns", None)
            if modified is None:
                modified = int(stat_result.st_mtime * 1000000000)
            cache_key = (path, stat_result.st_size, modified)
        except OSError as err:
            cache_key = (path, None, None)
            if cache_key != self._cache_key or self._active_job is not None:
                logging.warning("prime_tower: cannot inspect %s: %s", path, err)
                self._cancel_active_job()
                self._cache_key = cache_key
                self._status = self._empty_status(path, str(err))
            return dict(self._status)

        if cache_key != self._cache_key:
            self._start_scan(cache_key, path, eventtime)
        elif self._active_job is not None:
            # This polling path also publishes a completed worker result if
            # register_async_callback() was unavailable during shutdown or
            # resource pressure.
            self._finish_scan(eventtime, self._active_job)
        return dict(self._status)

    def wait_for_scan(self, eventtime):
        """Wait for the selected-file scan while continuing reactor service."""
        status = self.get_status(eventtime)
        while not status.get("ready", True):
            job = self._active_job
            if job is None:
                return status
            # Prefer a result that completed at the deadline over a timeout.
            # This also makes callback-publication failure recover without
            # waiting for the next 50 ms reactor pause.
            if job.done_event.is_set():
                self._finish_scan(eventtime, job)
                return dict(self._status)
            if eventtime >= job.deadline:
                elapsed = max(0.0, eventtime - job.started_at)
                timeout = job.deadline - job.started_at
                error = "scan timed out after %.1fs" % (timeout,)
                logging.error(
                    "prime_tower: %s for %s (%s bytes, %.3fs elapsed)",
                    error, job.path, job.cache_key[1], elapsed)
                # Cancel the parser and detach this job. A late callback is
                # rejected by object identity, while the same selected file
                # retains this fail-open result instead of relaunching work.
                job.cancel_event.set()
                self._active_job = None
                self._status = self._empty_status(job.path, error)
                return dict(self._status)
            waketime = min(eventtime + 0.050, job.deadline)
            eventtime = self.reactor.pause(waketime)
            status = self.get_status(eventtime)
        return status

    def cmd_PRIME_TOWER_WAIT(self, gcmd):
        eventtime = self.reactor.monotonic()
        status = self.get_status(eventtime)
        if not status.get("ready", True):
            # Creality Print begins the virtual-SD stream after file selection.
            # Its preamble resets the heater targets before START_PRINT invokes
            # this command, so apply the hold here, after those resets, rather
            # than when the background scan first starts.
            path = status.get("source")
            if path:
                self._hold_scan_temperatures(path)
            status = self.wait_for_scan(eventtime)
        if status.get("blocked"):
            try:
                self.gcode.run_script_from_command("TURN_OFF_HEATERS")
            except Exception:
                # Preserve the original hard-rejection reason even if the
                # printer's heater shutdown command itself reports a fault.
                logging.exception(
                    "prime_tower: unable to turn heaters off after rejecting "
                    "unsafe G-code")
            raise gcmd.error(status["block_reason"])
        if status.get("error"):
            gcmd.respond_info(
                "prime_tower: footprint scan failed; continuing without "
                "tower geometry: %s" % (status["error"],))


def load_config(config):
    return PrimeTower(config)
