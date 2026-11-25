#!/usr/bin/env python3

import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("ensure_m191_settings.py")
INSTALLER = Path(__file__).with_name("install.sh")
OVERRIDES = Path(__file__).with_name("overrides.cfg")
SPEC = importlib.util.spec_from_file_location("ensure_m191_settings", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class EnsureM191SettingsTests(unittest.TestCase):
    def test_seeds_native_bed_drop_once_and_keeps_user_setting(self):
        for original in ("[bed_mesh]\nprobe_count: 5,5\n",
                         "[screws_tilt_adjust]\r\nscrew_thread: CW-M4\r\n",
                         "[screws_tilt_adjust]"):
            seeded = MODULE.ensure_stc_bed_drop(original)
            self.assertEqual(seeded.count("[screws_tilt_adjust]"), 1)
            self.assertIn("bed_drop_distance: 200", seeded)
            custom = seeded.replace("bed_drop_distance: 200", "bed_drop_distance = 0 # disabled")
            self.assertEqual(MODULE.ensure_stc_bed_drop(custom), custom)

    def test_installer_runs_m191_settings_migration(self):
        self.assertIn(
            'python3 "${SCRIPT_DIR}/ensure_m191_settings.py"',
            INSTALLER.read_text(encoding="utf-8"),
        )

    def test_migration_defaults_match_new_install_template(self):
        template = OVERRIDES.read_text(encoding="utf-8")
        for name, value in MODULE.DEFAULTS:
            self.assertIn("variable_%s: %s" % (name, value), template)

    def test_adds_complete_section_when_missing(self):
        updated = MODULE.update("[virtual_sdcard]\nforced_leveling: false\n")
        self.assertIn("[gcode_macro _M191_VARS]", updated)
        for name, value in MODULE.DEFAULTS:
            self.assertIn("variable_%s: %s" % (name, value), updated)
        self.assertIn("gcode:\n", updated)

    def test_preserves_existing_values_and_adds_only_missing_values(self):
        original = (
            "[gcode_macro _M191_VARS]\n"
            "variable_bed_assist_bed_target: 92.0 # chosen by user\n"
            "gcode:\n"
        )
        updated = MODULE.update(original)
        self.assertIn(
            "variable_bed_assist_bed_target: 92.0 # chosen by user", updated
        )
        self.assertNotIn("variable_bed_assist_bed_target: 105.0", updated)
        self.assertIn("variable_bed_assist_z_height: 195.0", updated)

    def test_updates_unmodified_legacy_low_fan_default(self):
        original = (
            "[gcode_macro _M191_VARS]\n"
            "variable_circulation_fan_speed: 25.0\n"
            "gcode:\n"
        )
        updated = MODULE.update(original)
        self.assertIn("variable_circulation_fan_speed: 15.0\n", updated)
        self.assertNotIn("variable_circulation_fan_speed: 25.0\n", updated)

    def test_preserves_commented_legacy_fan_selection(self):
        original = (
            "[gcode_macro _M191_VARS]\n"
            "variable_circulation_fan_speed: 25.0 # chosen by user\n"
            "gcode:\n"
        )
        updated = MODULE.update(original)
        self.assertIn(
            "variable_circulation_fan_speed: 25.0 # chosen by user", updated
        )

    def test_second_update_is_idempotent(self):
        once = MODULE.update("[virtual_sdcard]\nforced_leveling: false\n")
        self.assertEqual(MODULE.update(once), once)

    def test_rejects_duplicate_sections(self):
        contents = (
            "[gcode_macro _M191_VARS]\ngcode:\n"
            "[gcode_macro _M191_VARS]\ngcode:\n"
        )
        with self.assertRaisesRegex(ValueError, "multiple"):
            MODULE.update(contents)

    def test_rejects_section_without_gcode_line(self):
        with self.assertRaisesRegex(ValueError, "no gcode"):
            MODULE.update("[gcode_macro _M191_VARS]\nvariable_x: 1\n")


if __name__ == "__main__":
    unittest.main()
