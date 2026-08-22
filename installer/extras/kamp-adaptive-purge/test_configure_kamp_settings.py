#!/usr/bin/env python3

import tempfile
import unittest
from pathlib import Path

import configure_kamp_settings as settings


class ConfigureKampSettingsTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.overrides = Path(self.temporary.name) / "overrides.cfg"
        self.values = {
            "variable_verbose_enable": "True",
            "variable_purge_height": "0.4",
            "variable_tip_distance": "0",
            "variable_purge_margin": "10",
            "variable_purge_amount": "25",
            "variable_flow_rate": "12",
        }

    def test_creates_preserved_override_section(self):
        self.overrides.write_text("[bed_mesh]\nprobe_count: 19,19\n", encoding="utf-8")

        settings.update_overrides(self.overrides, self.values)

        contents = self.overrides.read_text(encoding="utf-8")
        self.assertIn("[bed_mesh]\nprobe_count: 19,19\n", contents)
        self.assertIn("[gcode_macro _KAMP_Settings]", contents)
        self.assertEqual(settings.section_values(self.overrides), self.values)

    def test_updates_known_values_and_preserves_other_content(self):
        self.overrides.write_text(
            "# user file\n"
            "[gcode_macro _KAMP_Settings]\n"
            "variable_purge_height: 0.6 # tuned\n"
            "variable_future_option: 99\n"
            "\n"
            "[cartographer touch]\n"
            "max_noisy_samples: 2\n",
            encoding="utf-8",
        )
        changed = dict(self.values)
        changed["variable_purge_height"] = "0.5"

        settings.update_overrides(self.overrides, changed)
        settings.update_overrides(self.overrides, changed)

        contents = self.overrides.read_text(encoding="utf-8")
        self.assertEqual(contents.count("[gcode_macro _KAMP_Settings]"), 1)
        self.assertEqual(contents.count("variable_flow_rate:"), 1)
        self.assertIn("variable_purge_height: 0.5 # tuned", contents)
        self.assertIn("variable_future_option: 99", contents)
        self.assertIn("[cartographer touch]\nmax_noisy_samples: 2", contents)
        self.assertEqual(settings.section_values(self.overrides), changed)

    def test_normalizes_and_validates_values(self):
        self.assertEqual(settings.normalized("variable_verbose_enable", "no"), "False")
        self.assertEqual(settings.normalized("variable_purge_height", "0.50"), "0.5")
        self.assertEqual(settings.normalized("variable_tip_distance", "0"), "0")
        with self.assertRaises(ValueError):
            settings.normalized("variable_purge_height", "0")
        with self.assertRaises(ValueError):
            settings.normalized("variable_purge_margin", "-1")
        with self.assertRaises(ValueError):
            settings.normalized("variable_flow_rate", "inf")


if __name__ == "__main__":
    unittest.main()
