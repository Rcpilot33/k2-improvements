#!/usr/bin/env python3

import importlib.util
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("preserve_kamp_settings.py")
SPEC = importlib.util.spec_from_file_location("preserve_kamp_settings", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class PreserveKampSettingsTests(unittest.TestCase):
    def test_legacy_values_are_written(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            legacy = root / "kamp_settings.cfg"
            overrides = root / "overrides.cfg"
            legacy.write_text(
                "[gcode_macro _KAMP_Settings]\n"
                "variable_mesh_margin: 0\n"
                "variable_probe_dock_enable: False\n"
                "variable_purge_margin: 9\n"
                "variable_purge_amount: 26\n"
                "variable_flow_rate: 11\n"
                "variable_smart_park_height: 10\n",
                encoding="utf-8",
            )
            MODULE.update_overrides(overrides, MODULE.legacy_user_values(legacy))
            values = MODULE.section_values(overrides)
            self.assertEqual(values["variable_purge_margin"], "9")
            self.assertEqual(values["variable_purge_amount"], "26")
            self.assertEqual(values["variable_flow_rate"], "11")
            self.assertNotIn("variable_mesh_margin", values)
            self.assertNotIn("variable_probe_dock_enable", values)
            self.assertNotIn("variable_smart_park_height", values)

    def test_existing_overrides_take_precedence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            overrides = root / "overrides.cfg"
            overrides.write_text(
                "[gcode_macro OTHER]\nvariable_x: 4\n\n"
                "[gcode_macro _KAMP_Settings]\nvariable_purge_margin: 10\n",
                encoding="utf-8",
            )
            MODULE.update_overrides(overrides, {"variable_purge_margin": "9"})
            text = overrides.read_text(encoding="utf-8")
            self.assertIn("variable_x: 4", text)
            self.assertEqual(MODULE.section_values(overrides)["variable_purge_margin"], "10")

    def test_updater_owned_section_removes_previous_overimport(self):
        with tempfile.TemporaryDirectory() as directory:
            overrides = Path(directory) / "overrides.cfg"
            overrides.write_text(
                MODULE.MARKER + "\n"
                "[gcode_macro _KAMP_Settings]\n"
                "variable_mesh_margin: 0\n"
                "variable_purge_margin: 9\n"
                "variable_purge_amount: 26\n"
                "variable_flow_rate: 11\n"
                "variable_smart_park_height: 10\n",
                encoding="utf-8",
            )
            MODULE.update_overrides(overrides, {"variable_purge_margin": "9"})
            values = MODULE.section_values(overrides)
            self.assertEqual(values["variable_purge_margin"], "9")
            self.assertNotIn("variable_mesh_margin", values)
            self.assertNotIn("variable_smart_park_height", values)

    def test_unmarked_section_is_not_pruned(self):
        with tempfile.TemporaryDirectory() as directory:
            overrides = Path(directory) / "overrides.cfg"
            overrides.write_text(
                "[gcode_macro _KAMP_Settings]\n"
                "variable_mesh_margin: 3\n"
                "variable_purge_margin: 9\n",
                encoding="utf-8",
            )
            MODULE.update_overrides(overrides, {"variable_purge_margin": "9"})
            self.assertEqual(
                MODULE.section_values(overrides)["variable_mesh_margin"], "3"
            )


if __name__ == "__main__":
    unittest.main()
