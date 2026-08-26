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
_MARKER_SCAN_CHUNK = 1024 * 1024
_MARKER_SCAN_OVERLAP = 512


def _finite_point(point):
    return point[0] is not None and point[1] is not None \
        and math.isfinite(point[0]) and math.isfinite(point[1])


def _file_contains_prime_tower(path):
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
            chunk = handle.read(_MARKER_SCAN_CHUNK)
            if not chunk:
                return False
            data = overlap + chunk
            if _TOWER_MARKER_BYTES_RE.search(data) is not None:
                return True
            overlap = data[-_MARKER_SCAN_OVERLAP:]


def parse_prime_tower(path, padding=0.5):
    """Return a rectangular polygon around all prime-tower motion blocks.

    The parser follows modal absolute/relative XY positioning and records the
    actual path endpoints between ``;TYPE:Prime tower`` and
    ``; WIPE_TOWER_END``.  It deliberately uses motion rather than slicer
    metadata so rotation, resizing, sparse layers, and late-starting towers
    are handled without slicer-specific geometry calculations.
    """
    if not _file_contains_prime_tower(path):
        return {
            "detected": False,
            "polygon": [],
            "bounds": [],
            "blocks": 0,
        }

    absolute_xy = True
    absolute_e = True
    x_pos = None
    y_pos = None
    e_pos = 0.0
    in_tower = False
    tower_blocks = 0
    points = []

    with open(path, "r", encoding="utf-8", errors="replace") as handle:
        for raw_line in handle:
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
        self._cache_key = None
        self._status = self._empty_status()
        self.gcode.register_command(
            "PRIME_TOWER_WAIT", self.cmd_PRIME_TOWER_WAIT,
            desc="Wait cooperatively for prime-tower footprint discovery")

    @staticmethod
    def _empty_status(source=None, error=None, ready=True):
        return {
            "detected": False,
            "polygon": [],
            "bounds": [],
            "blocks": 0,
            "source": source,
            "error": error,
            "ready": ready,
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

    def _finish_scan(self, eventtime, cache_key, path, status, error):
        if cache_key != self._cache_key:
            return
        if error is not None:
            logging.error("prime_tower: scan failed for %s: %s", path, error)
            self._status = self._empty_status(path, error)
            return
        status["source"] = path
        status["error"] = None
        status["ready"] = True
        self._status = status
        if status["detected"]:
            logging.info(
                "prime_tower: detected %d blocks at "
                "X[%.3f, %.3f] Y[%.3f, %.3f] in %s",
                status["blocks"], status["bounds"][0],
                status["bounds"][2], status["bounds"][1],
                status["bounds"][3], path)

    def _scan_worker(self, cache_key, path):
        status = None
        error = None
        try:
            status = parse_prime_tower(path, self.padding)
        except Exception as err:
            error = str(err)
        try:
            self.reactor.register_async_callback(
                lambda eventtime: self._finish_scan(
                    eventtime, cache_key, path, status, error))
        except Exception:
            logging.exception(
                "prime_tower: unable to publish scan result for %s", path)

    def _start_scan(self, cache_key, path):
        self._cache_key = cache_key
        self._status = self._empty_status(path, ready=False)
        worker = threading.Thread(
            target=self._scan_worker,
            args=(cache_key, path),
            name="prime-tower-scan")
        worker.daemon = True
        worker.start()

    def get_status(self, eventtime):
        path = self._selected_path(eventtime)
        if not path:
            self._cache_key = None
            self._status = self._empty_status()
            return dict(self._status)
        try:
            stat_result = os.stat(path)
            cache_key = (path, stat_result.st_size, stat_result.st_mtime)
        except OSError as err:
            cache_key = (path, None, None)
            if cache_key != self._cache_key:
                logging.warning("prime_tower: cannot inspect %s: %s", path, err)
                self._cache_key = cache_key
                self._status = self._empty_status(path, str(err))
            return dict(self._status)

        if cache_key != self._cache_key:
            self._start_scan(cache_key, path)
        return dict(self._status)

    def wait_for_scan(self, eventtime):
        """Wait for the selected-file scan while continuing reactor service."""
        status = self.get_status(eventtime)
        while not status.get("ready", True):
            eventtime = self.reactor.pause(eventtime + 0.050)
            status = self.get_status(eventtime)
        return status

    def cmd_PRIME_TOWER_WAIT(self, gcmd):
        status = self.wait_for_scan(self.reactor.monotonic())
        if status.get("error"):
            gcmd.respond_info(
                "prime_tower: footprint scan failed; continuing without "
                "tower geometry: %s" % (status["error"],))


def load_config(config):
    return PrimeTower(config)
