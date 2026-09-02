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
                "variable_purge_margin: 9\n"
                "variable_purge_amount: 26\n"
                "variable_flow_rate: 11\n",
                encoding="utf-8",
            )
            MODULE.update_overrides(overrides, MODULE.section_values(legacy))
            values = MODULE.section_values(overrides)
            self.assertEqual(values["variable_purge_margin"], "9")
            self.assertEqual(values["variable_purge_amount"], "26")
            self.assertEqual(values["variable_flow_rate"], "11")

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


if __name__ == "__main__":
    unittest.main()
