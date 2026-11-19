#!/usr/bin/env python3

import importlib.util
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS

try:
    import jinja2
except ImportError:
    jinja2 = None


MODULE_PATH = Path(__file__).with_name("patch_line_purge.py")
SPEC = importlib.util.spec_from_file_location("patch_line_purge", MODULE_PATH)
PATCHER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PATCHER)


UPSTREAM_SAMPLE = """[gcode_macro LINE_PURGE]
description: representative upstream KAMP macro
gcode:
    {% set cross_section = printer.configfile.settings.extruder.max_extrude_cross_section | float %}
    {% set RETRACT = G10 | string %}
    {% set UNRETRACT = G11 | string %}
    # Calculate purge origins and centers from objects
    {% set purge_x_origin = 0 %}
    # Calculate purge speed
    {% set purge_move_speed = 1 %}
    {% if cross_section < 5 %}
        G0 X1  # Rapid move to break string
        G0 Y1  # Rapid move to break string
    {% endif %}
"""


class LinePurgePatchTests(unittest.TestCase):
    def patch(self, text=UPSTREAM_SAMPLE):
        text = PATCHER.quote_firmware_commands(text)
        text = PATCHER.harden_boundaries(text)
        text = PATCHER.add_balancing_unretracts(text)
        return PATCHER.add_prime_tower_wait_wrapper(text)

    def test_complete_path_is_constrained_to_active_mesh_and_machine(self):
        result = self.patch()

        self.assertEqual(result.count(PATCHER.BOUNDARY_MARKER), 1)
        self.assertIn("path_length = purge_amount + 10.0", result)
        self.assertIn("printer.toolhead.axis_minimum.x", result)
        self.assertIn("printer.toolhead.axis_maximum.y", result)
        self.assertIn("printer.bed_mesh.mesh_min[0]", result)
        self.assertIn("printer.bed_mesh.mesh_max[1]", result)
        self.assertIn("boundary_inset = 0.5", result)
        self.assertIn("purge_margin > 0", result)
        self.assertIn("printer.prime_tower.polygon", result)
        self.assertIn("object_points + footprint_points", result)
        self.assertNotIn("object_points | length > 0 and", result)
        self.assertNotIn("G0 X1", result)

    def test_selector_checks_all_four_sides_and_has_safe_skip(self):
        result = self.patch()

        for side in ("front_fits", "left_fits", "rear_fits", "right_fits"):
            self.assertIn(side, result)
        self.assertIn("purge_side == 'none'", result)
        self.assertIn("_KAMP_FRONT_CENTER_PURGE FLOW={flow_rate}", result)
        self.assertIn("no exclude-object geometry is available", result)
        self.assertIn("one or more purge settings are invalid", result)

    def test_stock_fallback_is_opt_in_and_only_handles_missing_geometry(self):
        result = self.patch()

        self.assertIn("stock_purge_fallback | int", result)
        self.assertIn("stock_purge_fallback == 1 and stock_path_fits_machine", result)
        self.assertIn("WARNING: No exclude-object geometry is available", result)
        self.assertIn("stock purge fallback is disabled", result)
        self.assertIn("G1 X0 Y0 E9 F2400", result)
        self.assertIn("G1 X150 Y0 E9 F2400", result)
        self.assertIn(
            "footprint_points = printer.prime_tower.polygon if printer.prime_tower is defined",
            result,
        )
        self.assertLess(
            result.index("{% elif all_points | length == 0 %}"),
            result.index("{% elif cross_section < 5 %}"),
        )
        no_corridor = result[result.index("{% elif purge_side == 'none' %}") :]
        self.assertNotIn("KAMP_Stock_Fallback_State", no_corridor)

    def test_string_break_motion_and_retraction_are_balanced(self):
        result = self.patch()

        self.assertEqual(result.count("Rapid move to break string"), 2)
        self.assertEqual(result.count(PATCHER.MARKER), 2)
        self.assertIn("G0 X{break_end_x}", result)
        self.assertIn("G0 Y{break_end_y}", result)

    def test_cfs_exit_precedes_purge_without_feed_only_move(self):
        result = self.patch()

        self.assertNotIn("G0 F{travel_speed}", result)
        self.assertIn("{% set pos = printer.toolhead.position %}", result)
        self.assertIn("G0 Y{axis_y_max - 2.0} F{travel_speed}", result)
        self.assertIn("G0 Y{axis_y_min + 2.0} F{travel_speed}", result)
        self.assertIn(
            "G0 X{purge_start_x} Y{purge_start_y} F{travel_speed}", result
        )
        self.assertLess(result.index("G90\n        {% if pos.y > axis_y_max %}"),
                        result.index("G0 Y{axis_y_max - 2.0}"))
        self.assertLess(result.index("G0 Y{axis_y_max - 2.0}"),
                        result.index("G0 X{purge_start_x} Y{purge_start_y}"))

    def test_patch_is_idempotent(self):
        once = self.patch()
        twice = PATCHER.add_prime_tower_wait_wrapper(
            PATCHER.add_balancing_unretracts(PATCHER.harden_boundaries(once)))
        self.assertEqual(twice, once)

    def test_waits_before_rendering_internal_purge_macro(self):
        result = self.patch()

        self.assertEqual(result.count(PATCHER.WAIT_MARKER), 1)
        self.assertIn("[gcode_macro LINE_PURGE]", result)
        self.assertIn("[gcode_macro _KAMP_LINE_PURGE]", result)
        self.assertLess(result.index("PRIME_TOWER_WAIT"),
                        result.index("_KAMP_LINE_PURGE {rawparams}"))

    def test_unrecognized_upstream_layout_is_rejected(self):
        with self.assertRaises(SystemExit):
            PATCHER.harden_boundaries(UPSTREAM_SAMPLE.replace(
                "    # Calculate purge speed\n", "    # upstream changed this marker\n"
            ))

        with self.assertRaises(SystemExit):
            PATCHER.harden_boundaries(UPSTREAM_SAMPLE.replace(
                "        G0 Y1  # Rapid move to break string\n", ""
            ))

    def test_main_writes_a_regular_patched_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir, "Line_Purge.cfg")
            destination = Path(temp_dir, "installed.cfg")
            source.write_text(UPSTREAM_SAMPLE, encoding="utf-8")

            old_argv = PATCHER.sys.argv
            try:
                PATCHER.sys.argv = [str(MODULE_PATH), str(source), str(destination)]
                PATCHER.main()
            finally:
                PATCHER.sys.argv = old_argv

            self.assertTrue(destination.is_file())
            self.assertFalse(destination.is_symlink())
            installed = destination.read_text(encoding="utf-8")
            self.assertIn(PATCHER.BOUNDARY_MARKER, installed)
            self.assertEqual(installed.count(PATCHER.MARKER), 2)
            self.assertEqual(installed.count(PATCHER.WAIT_MARKER), 1)


@unittest.skipIf(jinja2 is None, "Install Jinja2 to run macro rendering tests")
class FrontCenterRenderTests(unittest.TestCase):
    def setUp(self):
        self.env = jinja2.Environment(variable_start_string="{", variable_end_string="}")
        self.messages = []
        self.printer = {
            "toolhead": NS(axis_minimum=NS(x=0, y=-5, z=0),
                           axis_maximum=NS(x=350, y=350, z=350),
                           position=NS(x=133, y=378, z=3), homed_axes="xyz"),
            "extruder": NS(can_extrude=True),
            "configfile": NS(settings=NS(extruder=NS(max_extrude_cross_section=5))),
            "exclude_object": NS(objects=[NS(polygon=[[0, 0], [350, 0], [350, 350], [0, 350]])]),
            "gcode_macro _KAMP_Settings": NS(stock_purge_fallback=0),
        }

    def render(self, source, **values):
        return self.env.from_string(source).render(
            printer=self.printer, action_respond_info=lambda msg: self.messages.append(msg) or "",
            **values)

    def fallback(self):
        return self.render(PATCHER.FRONT_PURGE.split("gcode:\n", 1)[1],
                           params={"FLOW": 12, "TIP": 0, "OBJECT_MIN_Y": 0})

    def test_full_bed_selects_fallback_without_opt_in(self):
        result = self.render(PATCHER.BOUNDARY_CALCULATIONS + PATCHER.BOUNDARY_EXECUTION,
                             purge_amount=25, purge_margin=10, purge_height=.4,
                             flow_rate=12, tip_distance=0, cross_section=5,
                             verbose_enable=False, travel_speed=12000)
        self.assertIn("_KAMP_FRONT_CENTER_PURGE FLOW=12 TIP=0 OBJECT_MIN_Y=0.0", result)
        self.assertNotIn("SAVE_GCODE_STATE", result)

    def test_small_print_retains_adaptive_purge(self):
        self.printer["exclude_object"].objects = [NS(polygon=[[100, 100], [150, 150]])]
        result = self.render(PATCHER.BOUNDARY_CALCULATIONS + PATCHER.BOUNDARY_EXECUTION,
                             purge_amount=25, purge_margin=10, purge_height=.4,
                             flow_rate=12, tip_distance=0, cross_section=5,
                             verbose_enable=False, travel_speed=12000)
        self.assertNotIn("_KAMP_FRONT_CENTER_PURGE", result)
        self.assertIn("SAVE_GCODE_STATE NAME=Prepurge_State", result)

    def test_front_line_and_cfs_exit_restore_state(self):
        result = self.fallback()
        self.assertIn("G1 X150 Y-1", result)
        self.assertIn("G1 X200 E0.3742", result)
        self.assertLess(result.index("G0 Y348.0"), result.index("G1 Z3"))
        self.assertIn("RESTORE_GCODE_STATE NAME=KAMP_Front_Center_State MOVE=0", result)

    def test_unreachable_y_skips_all_motion_without_error(self):
        self.printer["toolhead"].axis_minimum.y = -0.4
        result = self.fallback()
        self.assertEqual(result.strip(), "")
        self.assertIn("purge skipped", self.messages[-1])

    def test_other_travel_limits_and_cold_nozzle_skip(self):
        for axis, value in (("x", 204), ("z", 2)):
            with self.subTest(axis=axis):
                setattr(self.printer["toolhead"].axis_maximum, axis, value)
                self.assertEqual(self.fallback().strip(), "")
                setattr(self.printer["toolhead"].axis_maximum, axis, 350)
        self.printer["extruder"].can_extrude = False
        self.assertEqual(self.fallback().strip(), "")


if __name__ == "__main__":
    unittest.main()
