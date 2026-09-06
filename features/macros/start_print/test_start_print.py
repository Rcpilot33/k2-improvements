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

    def test_preheat_applies_fan_margin_for_existing_mesh_path(self):
        self.assertIn(
            "SET_TEMPERATURE_FAN_TARGET TEMPERATURE_FAN=chamber_fan "
            "TARGET={CHAMBER_TEMP + 2.0}",
            self.config,
        )
        self.assertNotIn("M141 S{CHAMBER_TEMP}", self.config)

    def test_preheat_keeps_passive_chamber_heater_off(self):
        active_guard = self.config.index("{% if CHAMBER_TEMP > 35 %}")
        active_heater = self.config.index(
            "SET_HEATER_TEMPERATURE HEATER=chamber_heater "
            "TARGET={CHAMBER_TEMP}",
            active_guard,
        )
        passive_branch = self.config.index("{% else %}", active_heater)
        passive_heater = self.config.index(
            "SET_HEATER_TEMPERATURE HEATER=chamber_heater TARGET=0",
            passive_branch,
        )
        self.assertLess(active_heater, passive_branch)
        self.assertLess(passive_branch, passive_heater)


if __name__ == "__main__":
    unittest.main()
