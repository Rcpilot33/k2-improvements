#!/usr/bin/env python3

import unittest
from pathlib import Path


MACRO = Path(__file__).with_name("m191.cfg").read_text(encoding="utf-8")


class M191WorkflowTests(unittest.TestCase):
    def test_assist_requires_chamber_below_requested_target(self):
        self.assertIn(
            "{% set USE_BED_ASSIST = S > 35.0 and CHAMBER_TEMP < S %}",
            MACRO,
        )

    def test_assist_lowers_bed_and_starts_both_fans_at_25_percent(self):
        assist = MACRO.index("{% if USE_BED_ASSIST %}")
        move = MACRO.index("G1 Z195 F600", assist)
        model_fan = MACRO.index("M106 S64", move)
        side_fan = MACRO.index("M106 P2 S64", model_fan)
        chamber_wait = MACRO.index(
            'TEMPERATURE_WAIT SENSOR="temperature_sensor chamber_temp"', side_fan
        )
        self.assertLess(move, model_fan)
        self.assertLess(model_fan, side_fan)
        self.assertLess(side_fan, chamber_wait)

    def test_fans_stop_before_bed_returns_to_original_target(self):
        chamber_wait = MACRO.index(
            'TEMPERATURE_WAIT SENSOR="temperature_sensor chamber_temp"'
        )
        model_fan_off = MACRO.index("M106 S0", chamber_wait)
        side_fan_off = MACRO.index("M106 P2 S0", model_fan_off)
        restore_target = MACRO.index(
            "SET_HEATER_TEMPERATURE HEATER=heater_bed TARGET={ORIGINAL_BED_TARGET}",
            side_fan_off,
        )
        bed_wait = MACRO.index(
            "TEMPERATURE_WAIT SENSOR=heater_bed MINIMUM={BED_WAIT_MINIMUM}",
            restore_target,
        )
        self.assertLess(model_fan_off, side_fan_off)
        self.assertLess(side_fan_off, restore_target)
        self.assertLess(restore_target, bed_wait)

    def test_zero_bed_target_does_not_wait_for_unreachable_temperature(self):
        self.assertIn("{% if ORIGINAL_BED_TARGET > 0.0 %}", MACRO)
        self.assertIn("Original bed target was off, skipping bed target wait", MACRO)

    def test_old_direct_fan2_override_is_removed(self):
        self.assertNotIn("SET_PIN PIN=fan2", MACRO)

    def test_respond_messages_do_not_contain_k2_comment_delimiter(self):
        for line in MACRO.splitlines():
            if "RESPOND MSG=" in line:
                self.assertNotIn(";", line, msg=line)


if __name__ == "__main__":
    unittest.main()
