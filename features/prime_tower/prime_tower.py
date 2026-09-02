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


def _comment_type(line):
    """Return a normalized TYPE value for a standalone byte comment."""
    comment = line.lstrip()
    if not comment.startswith(b";"):
        return None
    comment = comment[1:].strip().lower()
    if not comment.startswith(b"type"):
        return None
    value = comment[4:].lstrip()
    if not value.startswith(b":"):
        return None
    return value[1:].strip()


def _is_tower_end(line):
    """Recognize WIPE_TOWER_END without a regex on every G-code line."""
    comment = line.lstrip()
    if not comment.startswith(b";"):
        return False
    comment = comment[1:].lstrip().lower()
    marker = b"wipe_tower_end"
    if not comment.startswith(marker):
        return False
    suffix = comment[len(marker):len(marker) + 1]
    return not suffix or not (suffix.isalnum() or suffix == b"_")


def _command_number(code):
    """Return (command letter, number, parameter offset), if supported."""
    if not code:
        return None
    command_letter = code[:1].upper()
    if command_letter not in (b"G", b"M"):
        return None
    index = 1
    while index < len(code) and 48 <= code[index] <= 57:
        index += 1
    if index == 1:
        return None
    # Preserve the old regex's word-boundary behavior for malformed input.
    if index < len(code) and code[index] not in b" \t;\r\n":
        return None
    return command_letter, int(code[1:index]), index


def _motion_parameters(code, offset):
    """Return X, Y, and E values using a cheap whitespace-token parser.

    Creality Print emits normal whitespace-delimited G-code. Supporting an
    axis letter separated from its value retains the flexibility of the old
    regular expressions without applying them to every motion line.
    """
    x_value = y_value = e_value = None
    pending_axis = None
    for token in code[offset:].split():
        if pending_axis is not None:
            try:
                value = float(token)
            except ValueError:
                pending_axis = None
            else:
                if pending_axis == b"X":
                    x_value = value
                elif pending_axis == b"Y":
                    y_value = value
                else:
                    e_value = value
                pending_axis = None
                continue

        axis = token[:1].upper()
        if axis not in (b"X", b"Y", b"E"):
            continue
        if len(token) == 1:
            pending_axis = axis
            continue
        try:
            value = float(token[1:])
        except ValueError:
            continue
        if axis == b"X":
            x_value = value
        elif axis == b"Y":
            y_value = value
        else:
            e_value = value
    return x_value, y_value, e_value


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
    # An enabled footer already tells us to expect tower toolpaths, so avoid
    # reading the file once for marker discovery and then again for geometry.
    # Older slicers may omit or misreport this footer; retain the quick byte
    # marker pass as a compatibility fallback for those files.
    if not footer["enabled"]:
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
    x_min = x_max = y_min = y_max = None

    with open(path, "rb") as handle:
        for line_number, raw_line in enumerate(handle):
            if line_number % _DETAILED_CANCEL_INTERVAL == 0:
                _check_cancel(cancel_event)
            line = raw_line.lstrip()
            if not line:
                continue
            if line.startswith(b";"):
                type_value = _comment_type(line)
                if type_value is not None:
                    in_tower = type_value == b"prime tower"
                    if in_tower:
                        tower_blocks += 1
                elif in_tower and _is_tower_end(line):
                    in_tower = False
                continue

            comment_offset = line.find(b";")
            code = (line if comment_offset < 0 else
                    line[:comment_offset]).rstrip()
            if not code:
                continue
            command_info = _command_number(code)
            if command_info is None:
                continue
            command_letter, command_number, parameter_offset = command_info
            if command_letter == b"G" and command_number == 90:
                absolute_xy = True
                continue
            if command_letter == b"G" and command_number == 91:
                absolute_xy = False
                continue
            if command_letter == b"M" and command_number == 82:
                absolute_e = True
                continue
            if command_letter == b"M" and command_number == 83:
                absolute_e = False
                continue

            if command_letter != b"G" or command_number not in \
                    (0, 1, 2, 3, 92):
                continue
            x_value, y_value, e_value = _motion_parameters(
                code, parameter_offset)
            if command_number == 92:
                if x_value is not None:
                    x_pos = x_value
                if y_value is not None:
                    y_pos = y_value
                if e_value is not None:
                    e_pos = e_value
                continue

            old_x, old_y = x_pos, y_pos
            new_x, new_y = x_pos, y_pos
            if x_value is not None:
                if absolute_xy or x_pos is None:
                    new_x = x_value
                else:
                    new_x = x_pos + x_value
            if y_value is not None:
                if absolute_xy or y_pos is None:
                    new_y = y_value
                else:
                    new_y = y_pos + y_value
            e_delta = 0.0
            if e_value is not None:
                e_delta = e_value - e_pos if absolute_e else e_value
                e_pos = e_value if absolute_e else e_pos + e_value
            x_pos, y_pos = new_x, new_y
            if in_tower and e_delta > 0.000001:
                if _finite_point((old_x, old_y)):
                    x_min = old_x if x_min is None else min(x_min, old_x)
                    x_max = old_x if x_max is None else max(x_max, old_x)
                    y_min = old_y if y_min is None else min(y_min, old_y)
                    y_max = old_y if y_max is None else max(y_max, old_y)
                if _finite_point((x_pos, y_pos)):
                    x_min = x_pos if x_min is None else min(x_min, x_pos)
                    x_max = x_pos if x_max is None else max(x_max, x_pos)
                    y_min = y_pos if y_min is None else min(y_min, y_pos)
                    y_max = y_pos if y_max is None else max(y_max, y_pos)

    if x_min is None:
        return {
            "detected": False,
            "polygon": [],
            "bounds": [],
            "blocks": tower_blocks,
        }

    padding = max(0.0, float(padding))
    x_min -= padding
    x_max += padding
    y_min -= padding
    y_max += padding
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
        self.scan_timeout_per_mb = config.getfloat(
            "scan_timeout_per_mb", 10.0, minval=0.0)
        self._cache_key = None
        self._active_job = None
        self._status = self._empty_status()
        self.gcode.register_command(
            "PRIME_TOWER_WAIT", self.cmd_PRIME_TOWER_WAIT,
            desc="Wait cooperatively for prime-tower footprint discovery")
        register_event_handler = getattr(
            self.printer, "register_event_handler", None)
        if register_event_handler is not None:
            register_event_handler(
                "klippy:connect", self._install_cartographer_mesh_hook)

    def _install_cartographer_mesh_hook(self, *args):
        """Add the detected tower to Cartographer's adaptive object list.

        Cartographer 3D owns BED_MESH_CALIBRATE when it is installed, so its
        adapter computes adaptive bounds without calling Klipper's native
        BedMeshCalibrate.set_adaptive_mesh().  Hook the adapter at connect
        time, after the Cartographer package is importable, while leaving the
        native bed_mesh integration in place for other probes.
        """
        try:
            from cartographer.adapters.klipper.bed_mesh import KlipperBedMesh
        except (ImportError, AttributeError):
            return
        if getattr(KlipperBedMesh, "_k2_prime_tower_hook", False):
            return

        original_get_objects = KlipperBedMesh.get_objects

        def get_objects_with_prime_tower(adapter):
            polygons = list(original_get_objects(adapter))
            tower = adapter.printer.lookup_object("prime_tower", None)
            if tower is None:
                return polygons
            eventtime = adapter.printer.get_reactor().monotonic()
            status = tower.wait_for_scan(eventtime)
            if status.get("blocked"):
                raise adapter.printer.command_error(status["block_reason"])
            if not status.get("detected"):
                return polygons
            polygon = [tuple(point) for point in status.get("polygon", [])]
            if polygon and polygon not in polygons:
                polygons.append(polygon)
                bounds = status.get("bounds", [])
                if len(bounds) == 4:
                    logging.info(
                        "prime_tower: Cartographer adaptive mesh includes "
                        "tower X[%.3f, %.3f] Y[%.3f, %.3f]",
                        bounds[0], bounds[2], bounds[1], bounds[3])
            return polygons

        KlipperBedMesh.get_objects = get_objects_with_prime_tower
        KlipperBedMesh._k2_prime_tower_hook = True
        logging.info(
            "prime_tower: installed Cartographer adaptive-mesh integration")

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
        file_size = cache_key[1]
        size_timeout = 0.0
        if file_size is not None:
            size_timeout = (file_size / float(1024 * 1024)) * \
                self.scan_timeout_per_mb
        timeout = max(self.scan_timeout, size_timeout)
        job = _ScanJob(cache_key, path, eventtime, timeout)
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
