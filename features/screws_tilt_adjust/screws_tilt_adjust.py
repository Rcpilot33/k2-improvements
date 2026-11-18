# Helper script to adjust bed screws tilt using Z probe
#
# Copyright (C) 2019  Rui Caridade <rui.mcbc@gmail.com>
# Copyright (C) 2021  Matthew Lloyd <github@matthewlloyd.net>
#
# This file may be distributed under the terms of the GNU GPLv3 license.
import math
from . import probe


PROBE_BOUNDARY_MARGIN = .5
ADJUSTMENT_ACCESS_BED_DROP = 200.
ADJUSTMENT_ACCESS_SPEED = 20.


def calculate_safe_probe_coordinate(requested, axis_minimum, axis_maximum,
                                    probe_offset,
                                    margin=PROBE_BOUNDARY_MARGIN):
    """Return the closest bed coordinate reachable by nozzle and probe."""
    if axis_minimum >= axis_maximum:
        raise ValueError("axis minimum must be less than axis maximum")
    if margin < 0.:
        raise ValueError("probe boundary margin cannot be negative")

    safe_minimum = max(axis_minimum + margin,
                       axis_minimum + probe_offset + margin)
    safe_maximum = min(axis_maximum - margin,
                       axis_maximum + probe_offset - margin)
    if safe_minimum > safe_maximum:
        raise ValueError("active probe has no reachable range")
    return min(max(requested, safe_minimum), safe_maximum)


def calculate_bed_access_z(current_z, axis_maximum,
                           distance=ADJUSTMENT_ACCESS_BED_DROP,
                           margin=PROBE_BOUNDARY_MARGIN):
    """Return a safe absolute Z that lowers the bed after probing."""
    if distance < 0.:
        raise ValueError("bed access distance cannot be negative")
    if margin < 0.:
        raise ValueError("bed access boundary margin cannot be negative")
    return min(current_z + distance, axis_maximum - margin)


class ScrewsTiltAdjust:
    def __init__(self, config):
        self.config = config
        self.printer = config.get_printer()
        self.screws = []
        self.results = {}
        self.max_diff = None
        self.max_diff_error = False
        # Read config
        self.bed_drop_distance = config.getfloat(
            'bed_drop_distance', ADJUSTMENT_ACCESS_BED_DROP, minval=0.)
        if not math.isfinite(self.bed_drop_distance):
            raise config.error('bed_drop_distance must be finite')
        for i in range(99):
            prefix = "screw%d" % (i + 1,)
            if config.get(prefix, None) is None:
                break
            screw_coord = config.getfloatlist(prefix, count=2)
            screw_name = "screw at %.3f,%.3f" % screw_coord
            screw_name = config.get(prefix + "_name", screw_name)
            self.screws.append((screw_coord, screw_name))
        if len(self.screws) < 3:
            raise config.error("screws_tilt_adjust: Must have "
                               "at least three screws")
        self.threads = {'CW-M3': 0, 'CCW-M3': 1, 'CW-M4': 2, 'CCW-M4': 3,
                        'CW-M5': 4, 'CCW-M5': 5, 'CW-M6': 6, 'CCW-M6': 7}
        self.thread = config.getchoice('screw_thread', self.threads,
                                       default='CW-M3')
        # Initialize ProbePointsHelper
        points = [coord for coord, name in self.screws]
        self.probe_helper = probe.ProbePointsHelper(self.config,
                                                    self.probe_finalize,
                                                    default_points=points)
        self.probe_helper.minimum_points(3)
        # screwN values describe physical bed locations. Convert them to
        # toolhead coordinates with the active probe's live X/Y offsets.
        self.probe_helper.use_xy_offsets(True)
        self.active_probe_points = points
        # Register command
        self.gcode = self.printer.lookup_object('gcode')
        self.gcode.register_command("SCREWS_TILT_CALCULATE",
                                    self.cmd_SCREWS_TILT_CALCULATE,
                                    desc=self.cmd_SCREWS_TILT_CALCULATE_help)
    cmd_SCREWS_TILT_CALCULATE_help = "Tool to help adjust bed leveling " \
                                     "screws by calculating the number " \
                                     "of turns to level it."

    @staticmethod
    def _coord_value(coord, index, name):
        try:
            return float(coord[index])
        except (IndexError, KeyError, TypeError):
            return float(getattr(coord, name))

    def _prepare_safe_probe_points(self, gcmd):
        active_probe = self.printer.lookup_object('probe', None)
        if active_probe is None:
            raise gcmd.error(
                "SCREWS_TILT_CALCULATE requires an active probe")
        offsets = active_probe.get_offsets()
        x_offset, y_offset = float(offsets[0]), float(offsets[1])

        toolhead = self.printer.lookup_object('toolhead')
        eventtime = self.printer.get_reactor().monotonic()
        status = toolhead.get_status(eventtime)
        minimum = status['axis_minimum']
        maximum = status['axis_maximum']
        axis_minimum = (
            self._coord_value(minimum, 0, 'x'),
            self._coord_value(minimum, 1, 'y'))
        axis_maximum = (
            self._coord_value(maximum, 0, 'x'),
            self._coord_value(maximum, 1, 'y'))

        safe_points = []
        try:
            for coord, _name in self.screws:
                safe_x = calculate_safe_probe_coordinate(
                    coord[0], axis_minimum[0], axis_maximum[0], x_offset)
                safe_y = calculate_safe_probe_coordinate(
                    coord[1], axis_minimum[1], axis_maximum[1], y_offset)
                safe_points.append((safe_x, safe_y))
        except ValueError as err:
            raise gcmd.error("SCREWS_TILT_CALCULATE: %s" % (err,))

        # Preflight every offset-adjusted toolhead target before probing.
        for safe_x, safe_y in safe_points:
            toolhead_x = safe_x - x_offset
            toolhead_y = safe_y - y_offset
            if not (axis_minimum[0] <= toolhead_x <= axis_maximum[0] and
                    axis_minimum[1] <= toolhead_y <= axis_maximum[1]):
                raise gcmd.error(
                    "SCREWS_TILT_CALCULATE: calculated toolhead target "
                    "X=%.3f Y=%.3f is outside the motion range" %
                    (toolhead_x, toolhead_y))

        self.active_probe_points = safe_points
        self.probe_helper.update_probe_points(safe_points, 3)

        safe_min_x = calculate_safe_probe_coordinate(
            axis_minimum[0], axis_minimum[0], axis_maximum[0], x_offset)
        safe_max_x = calculate_safe_probe_coordinate(
            axis_maximum[0], axis_minimum[0], axis_maximum[0], x_offset)
        safe_min_y = calculate_safe_probe_coordinate(
            axis_minimum[1], axis_minimum[1], axis_maximum[1], y_offset)
        safe_max_y = calculate_safe_probe_coordinate(
            axis_maximum[1], axis_minimum[1], axis_maximum[1], y_offset)
        gcmd.respond_info(
            "SCREWS_TILT_CALCULATE: active probe offsets X=%.3f Y=%.3f; "
            "safe physical probe range X=%.3f..%.3f Y=%.3f..%.3f" % (
                x_offset, y_offset, safe_min_x, safe_max_x,
                safe_min_y, safe_max_y))

        for (requested, name), actual in zip(self.screws, safe_points):
            toolhead_x = actual[0] - x_offset
            toolhead_y = actual[1] - y_offset
            suffix = ""
            if (abs(actual[0] - requested[0]) > .0005 or
                    abs(actual[1] - requested[1]) > .0005):
                suffix = " (closest safely reachable point)"
            gcmd.respond_info(
                "%s: probe X=%.3f Y=%.3f; toolhead X=%.3f Y=%.3f%s" %
                (name, actual[0], actual[1], toolhead_x, toolhead_y,
                 suffix))

    def cmd_SCREWS_TILT_CALCULATE(self, gcmd):
        self._prepare_safe_probe_points(gcmd)
        self.max_diff = gcmd.get_float("MAX_DEVIATION", None)
        # Option to force all turns to be in the given direction (CW or CCW)
        direction = gcmd.get("DIRECTION", default=None)
        if direction is not None:
            direction = direction.upper()
            if direction not in ('CW', 'CCW'):
                raise gcmd.error(
                    "Error on '%s': DIRECTION must be either CW or CCW" % (
                        gcmd.get_commandline(),))
        self.direction = direction
        self.probe_helper.start_probe(gcmd)
        self._lower_bed_for_adjustment(gcmd)

    def _lower_bed_for_adjustment(self, gcmd):
        toolhead = self.printer.lookup_object('toolhead')
        eventtime = self.printer.get_reactor().monotonic()
        maximum = toolhead.get_status(eventtime)['axis_maximum']
        axis_maximum_z = self._coord_value(maximum, 2, 'z')
        current_z = float(toolhead.get_position()[2])
        if self.bed_drop_distance == 0.:
            return
        target_z = calculate_bed_access_z(
            current_z, axis_maximum_z, distance=self.bed_drop_distance)
        if target_z <= current_z:
            gcmd.respond_info(
                "SCREWS_TILT_CALCULATE: bed is already at its safe "
                "adjustment-access limit")
            return
        gcmd.respond_info(
            "SCREWS_TILT_CALCULATE: lowering bed %.1f mm to Z=%.1f "
            "for adjustment access" % (target_z - current_z, target_z))
        toolhead.manual_move([None, None, target_z], ADJUSTMENT_ACCESS_SPEED)
        toolhead.wait_moves()

    def get_status(self, eventtime):
        return {'error': self.max_diff_error,
            'max_deviation': self.max_diff,
            'results': self.results}

    def probe_finalize(self, offsets, positions):
        self.results = {}
        self.max_diff_error = False
        # Factors used for CW-M3, CCW-M3, CW-M4, CCW-M4, CW-M5, CCW-M5, CW-M6
        #and CCW-M6
        threads_factor = {0: 0.5, 1: 0.5, 2: 0.7, 3: 0.7, 4: 0.8, 5: 0.8,
        6: 1.0, 7: 1.0}
        is_clockwise_thread = (self.thread & 1) == 0
        screw_diff = []
        # Process the read Z values
        if self.direction is not None:
            # Lowest or highest screw is the base position used for comparison
            use_max = ((is_clockwise_thread and self.direction == 'CW')
                    or (not is_clockwise_thread and self.direction == 'CCW'))
            min_or_max = max if use_max else min
            i_base, z_base = min_or_max(
                enumerate([pos[2] for pos in positions]), key=lambda v: v[1])
        else:
            # First screw is the base position used for comparison
            i_base, z_base = 0, positions[0][2]
        # Provide the user some information on how to read the results
        self.gcode.respond_info("01:20 means 1 full turn and 20 minutes, "
                                "CW=clockwise, CCW=counter-clockwise")
        for i, screw in enumerate(self.screws):
            z = positions[i][2]
            _configured_coord, name = screw
            coord = self.active_probe_points[i]
            if i == i_base:
                # Show the results
                self.gcode.respond_info(
                    "%s : x=%.1f, y=%.1f, z=%.5f" %
                    (name + ' (base)', coord[0], coord[1], z))
                sign = "CW" if is_clockwise_thread else "CCW"
                self.results["screw%d" % (i + 1,)] = {'z': z, 'sign': sign,
                    'adjust': '00:00', 'is_base': True}
            else:
                # Calculate how knob must be adjusted for other positions
                diff = z_base - z
                screw_diff.append(abs(diff))
                if abs(diff) < 0.001:
                    adjust = 0
                else:
                    adjust = diff / threads_factor.get(self.thread, 0.5)
                if is_clockwise_thread:
                    sign = "CW" if adjust >= 0 else "CCW"
                else:
                    sign = "CCW" if adjust >= 0 else "CW"
                adjust = abs(adjust)
                full_turns = math.trunc(adjust)
                decimal_part = adjust - full_turns
                minutes = round(decimal_part * 60, 0)
                # Show the results
                self.gcode.respond_info(
                    "%s : x=%.1f, y=%.1f, z=%.5f : adjust %s %02d:%02d" %
                    (name, coord[0], coord[1], z, sign, full_turns, minutes))
                self.results["screw%d" % (i + 1,)] = {'z': z, 'sign': sign,
                    'adjust':"%02d:%02d" % (full_turns, minutes),
                    'is_base': False}
        if self.max_diff and any((d > self.max_diff) for d in screw_diff):
            self.max_diff_error = True
            raise self.gcode.error(
                "bed level exceeds configured limits ({}mm)! " \
                "Adjust screws and restart print.".format(self.max_diff))

def load_config(config):
    return ScrewsTiltAdjust(config)
