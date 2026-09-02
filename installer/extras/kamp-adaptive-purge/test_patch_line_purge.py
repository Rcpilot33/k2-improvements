#!/usr/bin/env python3

import importlib.util
import tempfile
import unittest
from pathlib import Path


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
        self.assertIn("object_points + tower_points", result)
        self.assertIn("object_points | length > 0", result)
        self.assertNotIn("G0 X1", result)

    def test_selector_checks_all_four_sides_and_has_safe_skip(self):
        result = self.patch()

        for side in ("front_fits", "left_fits", "rear_fits", "right_fits"):
            self.assertIn(side, result)
        self.assertIn("purge_side == 'none'", result)
        self.assertIn("no safe purge corridor exists", result)
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
            "tower_points = printer.prime_tower.polygon if object_points | length > 0",
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


if __name__ == "__main__":
    unittest.main()
