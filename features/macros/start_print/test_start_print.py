#!/usr/bin/env python3
"""Static checks for the managed START_PRINT configuration."""

import pathlib
import unittest


CONFIG = pathlib.Path(__file__).with_name("start_print.cfg")
MACROS_INSTALLER = CONFIG.parent.parent / "install.sh"


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
        original = section.index("_K2_ORIGINAL_BOX_NOZZLE_CLEAN {rawparams}")
        release_before = section.index("_RELEASE_PREPRINT_CASE_FAN")
        release_after = section.index("_RELEASE_PREPRINT_CASE_FAN", original)
        self.assertLess(release_before, original)
        self.assertLess(original, release_after)
        self.assertEqual(section.count("_RELEASE_PREPRINT_CASE_FAN"), 2)

    def test_case_fan_release_wraps_deformation_calibration_preflight(self):
        section = self.config.split(
            "[gcode_macro SET_CHAMBER_FAN]", 1
        )[1].split("[gcode_macro BOX_NOZZLE_CLEAN]", 1)[0]
        self.assertIn(
            "rename_existing: _K2_ORIGINAL_SET_CHAMBER_FAN", section
        )
        original = section.index("_K2_ORIGINAL_SET_CHAMBER_FAN {rawparams}")
        release = section.index("_RELEASE_PREPRINT_CASE_FAN", original)
        self.assertLess(original, release)

    def test_case_fan_release_runs_immediately_after_box_start_print(self):
        section = self.config.split(
            "[gcode_macro START_PRINT]", 1
        )[1]
        box_start = section.index("BOX_START_PRINT")
        release = section.index("_RELEASE_PREPRINT_CASE_FAN", box_start)
        absolute_mode = section.index("G90", release)
        self.assertLess(box_start, release)
        self.assertLess(release, absolute_mode)

    def test_case_fan_release_applies_to_both_probe_paths(self):
        section = self.config.split(
            "[gcode_macro _RELEASE_PREPRINT_CASE_FAN]", 1
        )[1].split("[gcode_macro BOX_NOZZLE_CLEAN]", 1)[0]
        self.assertIn("DIRECT_CASE_FAN > 0.0", section)
        self.assertNotIn("'cartographer' not in printer", section)

    def test_case_fan_release_accepts_any_nonzero_direct_request(self):
        section = self.config.split(
            "[gcode_macro _RELEASE_PREPRINT_CASE_FAN]", 1
        )[1].split("[gcode_macro BOX_NOZZLE_CLEAN]", 1)[0]
        self.assertIn('printer["output_pin fan1"].value', section)
        self.assertIn("DIRECT_CASE_FAN > 0.0", section)
        self.assertNotIn("DIRECT_CASE_FAN >= 0.999", section)

    def test_case_fan_release_is_not_blocked_by_temporary_chamber_cooling(self):
        section = self.config.split(
            "[gcode_macro _RELEASE_PREPRINT_CASE_FAN]", 1
        )[1].split("[gcode_macro BOX_NOZZLE_CLEAN]", 1)[0]
        self.assertNotIn('printer["temperature_fan chamber_fan"].speed', section)
        self.assertNotIn("CHAMBER_COOLING", section)

    def test_case_fan_release_is_runtime_state_gated(self):
        section = self.config.split(
            "[gcode_macro _RELEASE_PREPRINT_CASE_FAN]", 1
        )[1].split("[gcode_macro BOX_NOZZLE_CLEAN]", 1)[0]
        self.assertNotIn("_FIRMWARE_COMPAT_K2", section)
        self.assertNotIn("RELEASE_CASE_FAN", section)
        self.assertNotIn("variable_release_stock_case_fan:", self.config)

    def test_obsolete_probe_switch_is_not_advertised(self):
        self.assertNotIn("variable_offset_PROBE:", self.config)

    def test_case_fan_is_not_continuously_enforced(self):
        self.assertEqual(self.config.count("M107 P1"), 1)
        self.assertNotIn("[delayed_gcode", self.config)

    def test_active_chamber_wait_uses_creality_35c_boundary(self):
        self.assertIn("{% if CHAMBER_TEMP > 35 %}", self.config)
        self.assertNotIn("{% if CHAMBER_TEMP > 40 %}", self.config)

    def test_preheat_restores_chamber_fan_policy_after_creality_preparation(self):
        self.assertIn(
            'printer["gcode_macro _M191_VARS"].chamber_fan_margin',
            self.config,
        )
        self.assertIn(
            "SET_TEMPERATURE_FAN_TARGET TEMPERATURE_FAN=chamber_fan TARGET=35",
            self.config,
        )
        self.assertIn(
            "SET_TEMPERATURE_FAN_TARGET TEMPERATURE_FAN=chamber_fan "
            "TARGET={CHAMBER_TEMP + CHAMBER_FAN_MARGIN}",
            self.config,
        )
        active = self.config.index("{% if CHAMBER_TEMP > 35 %}")
        active_fan_target = self.config.index(
            "SET_TEMPERATURE_FAN_TARGET TEMPERATURE_FAN=chamber_fan "
            "TARGET={CHAMBER_TEMP + CHAMBER_FAN_MARGIN}",
            active,
        )
        passive = self.config.index(
            "{% elif CHAMBER_TEMP > 0 %}", active_fan_target
        )
        baseline = self.config.index("{% else %}", passive)
        self.assertLess(active, active_fan_target)
        self.assertLess(active_fan_target, passive)
        self.assertLess(passive, baseline)
        self.assertNotIn(
            "SET_TEMPERATURE_FAN_TARGET TEMPERATURE_FAN=chamber_fan TARGET=0",
            self.config,
        )
        self.assertNotIn("M141 S{CHAMBER_TEMP}", self.config)

    def test_shared_fan_margin_is_validated(self):
        self.assertIn(
            "CHAMBER_FAN_MARGIN < 0.0 or CHAMBER_FAN_MARGIN > 10.0",
            self.config,
        )

    def test_machine_heat_soak_is_configurable_and_validated(self):
        self.assertIn(
            'printer["gcode_macro _START_PRINT_VARS"].heat_soak',
            self.config,
        )
        self.assertIn("SOAK_TIME < 0.0 or SOAK_TIME > 120.0", self.config)

    def test_machine_heat_soak_runs_after_active_chamber_wait(self):
        bed_wait = self.config.index(
            "TEMPERATURE_WAIT SENSOR=heater_bed MINIMUM={BED_TEMP - 0.5}"
        )
        chamber_wait = self.config.index("M191 S{CHAMBER_TEMP}", bed_wait)
        soak = self.config.index("Machine heat soaking:", chamber_wait)
        rehome = self.config.index("G28 Z", soak)
        self.assertLess(bed_wait, chamber_wait)
        self.assertLess(chamber_wait, soak)
        self.assertLess(soak, rehome)

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

    def test_optional_material_editor_owns_offset_application(self):
        self.assertIn('"k2_material_z_offset_editor" in printer', self.config)
        self.assertIn('K2_MATERIAL_Z_APPLY MATERIAL="{MATERIAL}"', self.config)
        self.assertEqual(self.config.count("SET_GCODE_OFFSET Z={OFFSET}"), 1)

    def test_material_defaults_start_at_point_zero_five(self):
        for material in ("PLA", "PETG", "ABS", "ASA", "DEFAULT"):
            self.assertIn("variable_offset_%s: 0.05" % material, self.config)

    def test_macro_repair_preserves_plate_surface_wrapper(self):
        installer = MACROS_INSTALLER.read_text(encoding="utf-8")
        capture = installer.index("HAD_SURFACE_WRAPPER=1")
        refresh = installer.index("for sub in start_print m191 bed_mesh overrides")
        restore = installer.index("surface-selection-wrapper/install.sh")
        self.assertLess(capture, refresh)
        self.assertLess(refresh, restore)


if __name__ == "__main__":
    unittest.main()
