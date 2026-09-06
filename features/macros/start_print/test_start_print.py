#!/usr/bin/env python3
"""Static checks for the managed START_PRINT configuration."""

import pathlib
import unittest


CONFIG = pathlib.Path(__file__).with_name("start_print.cfg")


class StartPrintConfigTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = CONFIG.read_text(encoding="utf-8")

    def test_case_fan_release_wraps_native_nozzle_clean(self):
        section = self.config.split(
            "[gcode_macro BOX_NOZZLE_CLEAN]", 1
        )[1].split("[gcode_macro START_PRINT]", 1)[0]
        self.assertIn(
            "rename_existing: _K2_ORIGINAL_BOX_NOZZLE_CLEAN", section
        )
        self.assertIn("_K2_ORIGINAL_BOX_NOZZLE_CLEAN {rawparams}", section)
        self.assertIn("M107 P1", section)

    def test_case_fan_release_is_stock_probe_only(self):
        section = self.config.split(
            "[gcode_macro BOX_NOZZLE_CLEAN]", 1
        )[1].split("[gcode_macro START_PRINT]", 1)[0]
        self.assertIn("{% if 'cartographer' not in printer %}", section)

    def test_case_fan_is_not_continuously_enforced(self):
        self.assertEqual(self.config.count("M107 P1"), 1)
        self.assertNotIn("[delayed_gcode", self.config)

    def test_active_chamber_wait_uses_creality_35c_boundary(self):
        self.assertIn("{% if CHAMBER_TEMP > 35 %}", self.config)
        self.assertNotIn("{% if CHAMBER_TEMP > 40 %}", self.config)


if __name__ == "__main__":
    unittest.main()
