#!/usr/bin/env python3

import re
import unittest
from pathlib import Path


MACRO = Path(__file__).with_name("m191.cfg").read_text(encoding="utf-8")
INSTALLER = Path(__file__).with_name("install.sh").read_text(encoding="utf-8")
OVERRIDES = (
    Path(__file__).parents[1] / "overrides" / "overrides.cfg"
).read_text(encoding="utf-8")

DEFAULTS = {
    "bed_assist_enabled": "1",
    "bed_assist_trigger_delta": "3.0",
    "bed_assist_bed_target": "105.0",
    "bed_assist_degrees_above_commanded": "0.0",
    "bed_assist_z_height": "195.0",
    "circulation_fan_speed": "15.0",
    "circulation_fan_high_speed": "100.0",
    "circulation_fan_low_seconds": "45.0",
    "circulation_fan_high_seconds": "20.0",
    "bed_restore_z_height": "30.0",
    "bed_restore_side_fan_speed": "100.0",
    "chamber_fan_margin": "2.0",
    "bed_restore_tolerance": "5.0",
    "chamber_wait_max_delta": "5.0",
}


def macro_defaults(text):
    section = text.split("[gcode_macro _M191_VARS]", 1)[1].split(
        "[gcode_macro", 1
    )[0]
    return dict(
        re.findall(r"^variable_([A-Za-z0-9_]+):\s*([^\s#]+)", section, re.M)
    )


class M191WorkflowTests(unittest.TestCase):
    def test_managed_and_override_defaults_match(self):
        self.assertEqual(macro_defaults(MACRO), DEFAULTS)
        self.assertEqual(macro_defaults(OVERRIDES), DEFAULTS)

    def test_active_heating_boundary_remains_fixed(self):
        self.assertIn("{% set WAIT_FOR_CHAMBER = S > 35.0 %}", MACRO)

    def test_m141_is_not_redefined_as_a_second_macro(self):
        self.assertNotIn("[gcode_macro M141]", MACRO)
        self.assertNotIn("rename_existing", MACRO)

    def test_nonzero_target_restores_configured_chamber_fan_margin(self):
        wait = MACRO.index("{% set WAIT_FOR_CHAMBER = S > 35.0 %}")
        target = MACRO.index(
            "{% set FAN_TARGET = S + CHAMBER_FAN_MARGIN %}",
            wait,
        )
        apply_target = MACRO.index(
            "SET_TEMPERATURE_FAN_TARGET TEMPERATURE_FAN=chamber_fan "
            "TARGET={FAN_TARGET}",
            target,
        )
        self.assertLess(wait, target)
        self.assertLess(target, apply_target)
        self.assertNotIn("0.0 if WAIT_FOR_CHAMBER", MACRO)

    def test_fixed_target_is_used_when_degrees_above_is_zero(self):
        relative = MACRO.index("{% if DEGREES_ABOVE_COMMANDED > 0.0 %}")
        relative_target = MACRO.index(
            "ORIGINAL_BED_TARGET + DEGREES_ABOVE_COMMANDED", relative
        )
        fixed_branch = MACRO.index("{% else %}", relative_target)
        fixed_target = MACRO.index(
            "{% set RAW_BED_ASSIST_TARGET = FIXED_BED_ASSIST_TARGET %}",
            fixed_branch,
        )
        self.assertLess(relative_target, fixed_branch)
        self.assertLess(fixed_branch, fixed_target)

    def test_calculated_assist_target_is_capped_at_120(self):
        self.assertIn(
            "{% set BED_ASSIST_TARGET = [RAW_BED_ASSIST_TARGET, 120.0]|min %}",
            MACRO,
        )
        self.assertIn(
            "[BED_ASSIST_HEATER_UNCAPPED, 120.0]|min",
            MACRO,
        )

    def test_assist_never_lowers_commanded_bed_target(self):
        self.assertIn("[ORIGINAL_BED_TARGET, BED_ASSIST_TARGET]|max", MACRO)
        self.assertIn("{% if BED_TARGET_WILL_BE_RAISED %}", MACRO)

    def test_assist_skips_when_calculated_target_is_not_above_actual_bed(self):
        self.assertIn("BED_ASSIST_TARGET > ACTUAL_BED_TEMP", MACRO)
        self.assertIn("BED_ASSIST_TARGET <= ACTUAL_BED_TEMP", MACRO)

    def test_assist_enable_and_chamber_delta_gate_entire_sequence(self):
        self.assertIn(
            "BED_ASSIST_ENABLED == 1.0 and WAIT_FOR_CHAMBER and "
            "CHAMBER_TEMP < BED_ASSIST_THRESHOLD and "
            "BED_ASSIST_TARGET > ACTUAL_BED_TEMP",
            MACRO,
        )
        assist = MACRO.index("{% if USE_BED_ASSIST %}")
        move = MACRO.index("G1 Z{BED_ASSIST_Z_HEIGHT} F600", assist)
        circulation = MACRO.index("K2_M191_CIRCULATION_WAIT", move)
        self.assertLess(move, circulation)

    def test_z_height_range_is_30_through_330(self):
        self.assertIn(
            "BED_ASSIST_Z_HEIGHT < 30.0 or BED_ASSIST_Z_HEIGHT > 330.0",
            MACRO,
        )

    def test_fan_percentages_are_validated_and_converted_to_pwm(self):
        self.assertIn(
            "CIRCULATION_FAN_LOW_PERCENT < 0.0 or CIRCULATION_FAN_LOW_PERCENT > 100.0",
            MACRO,
        )
        self.assertIn("CIRCULATION_FAN_HIGH_PERCENT < CIRCULATION_FAN_LOW_PERCENT", MACRO)
        self.assertIn("(CIRCULATION_FAN_LOW_PERCENT * 2.55)|round(0)|int", MACRO)
        self.assertIn("(CIRCULATION_FAN_HIGH_PERCENT * 2.55)|round(0)|int", MACRO)
        self.assertIn("LOW_PWM={CIRCULATION_FAN_LOW_PWM}", MACRO)
        self.assertIn("HIGH_PWM={CIRCULATION_FAN_HIGH_PWM}", MACRO)

    def test_circulation_wait_uses_configured_seconds(self):
        self.assertIn("[k2_m191_circulation]", MACRO)
        self.assertIn(
            'K2_M191_CIRCULATION_WAIT SENSOR="temperature_sensor chamber_temp"',
            MACRO,
        )
        self.assertIn("LOW_SECONDS={CIRCULATION_FAN_LOW_SECONDS}", MACRO)
        self.assertIn("HIGH_SECONDS={CIRCULATION_FAN_HIGH_SECONDS}", MACRO)
        self.assertIn("CYCLE_FANS=1 REPORT_ID=C REPORT_TARGET={S}", MACRO)
        self.assertNotIn("[delayed_gcode", MACRO)

    def test_all_chamber_waits_report_the_exact_sensor_as_c(self):
        waits = [
            line.strip()
            for line in MACRO.splitlines()
            if 'SENSOR="temperature_sensor chamber_temp"' in line
        ]
        self.assertEqual(len(waits), 3)
        for wait in waits:
            self.assertTrue(wait.startswith("K2_M191_CIRCULATION_WAIT"))
            self.assertIn("REPORT_ID=C", wait)
            self.assertIn("REPORT_TARGET={S}", wait)
        self.assertEqual(sum("CYCLE_FANS=1" in wait for wait in waits), 1)
        self.assertEqual(sum("CYCLE_FANS=0" in wait for wait in waits), 2)

    def test_bed_return_uses_side_fan_only_while_waiting(self):
        restore = MACRO.index(
            "SET_HEATER_TEMPERATURE HEATER=heater_bed TARGET={ORIGINAL_BED_TARGET}"
        )
        move = MACRO.index("G1 Z{BED_RESTORE_Z_HEIGHT} F600", restore)
        side_on = MACRO.index("M106 P2 S{BED_RESTORE_SIDE_FAN_PWM}", move)
        wait = MACRO.index("TEMPERATURE_WAIT SENSOR=heater_bed", side_on)
        side_off = MACRO.index("M106 P2 S0", wait)
        chamber_recheck = MACRO.index(
            'K2_M191_CIRCULATION_WAIT SENSOR="temperature_sensor chamber_temp"',
            side_off,
        )
        self.assertLess(restore, move)
        self.assertLess(move, side_on)
        self.assertLess(side_on, wait)
        self.assertLess(wait, side_off)
        self.assertLess(side_off, chamber_recheck)
        self.assertNotIn("M106 S{BED_RESTORE_SIDE_FAN_PWM}", MACRO)

    def test_installer_deploys_circulation_wait_module(self):
        self.assertIn(
            'ln -sfn "$SCRIPT_DIR/k2_m191_circulation.py"', INSTALLER
        )
        self.assertIn(
            '"$KLIPPER_EXTRAS/k2_m191_circulation.py"', INSTALLER
        )

    def test_configured_chamber_wait_and_bed_restore_tolerances_are_used(self):
        self.assertIn(
            'MINIMUM={S} MAXIMUM={S + CHAMBER_WAIT_MAX_DELTA}', MACRO
        )
        self.assertIn("ORIGINAL_BED_TARGET - BED_RESTORE_TOLERANCE", MACRO)
        self.assertIn(
            "MAXIMUM={ORIGINAL_BED_TARGET + BED_RESTORE_TOLERANCE}", MACRO
        )

    def test_zero_bed_target_does_not_wait_for_unreachable_temperature(self):
        self.assertIn("{% if ORIGINAL_BED_TARGET > 0.0 %}", MACRO)
        self.assertIn(
            "Original bed target was off, skipping bed target wait", MACRO
        )

    def test_s_zero_disables_only_chamber_heating(self):
        zero = MACRO.index("{% if S == 0 %}")
        branch_end = MACRO.index("{% else %}", zero)
        branch = MACRO[zero:branch_end]
        self.assertIn(
            "SET_HEATER_TEMPERATURE HEATER=chamber_heater TARGET=0", branch
        )
        self.assertIn(
            "SET_TEMPERATURE_FAN_TARGET TEMPERATURE_FAN=chamber_fan TARGET=35",
            branch,
        )
        self.assertNotIn("TURN_OFF_HEATERS", branch)
        self.assertNotIn("M107", branch)
        self.assertNotIn("M106 P2", branch)

    def test_old_direct_fan2_override_is_removed(self):
        self.assertNotIn("SET_PIN PIN=fan2", MACRO)

    def test_respond_messages_do_not_contain_k2_comment_delimiter(self):
        for line in MACRO.splitlines():
            if "RESPOND MSG=" in line:
                self.assertNotIn(";", line, msg=line)


if __name__ == "__main__":
    unittest.main()
