#!/usr/bin/env python3

import importlib.util
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("prime_tower.py")
SPEC = importlib.util.spec_from_file_location("prime_tower", MODULE_PATH)
PRIME_TOWER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PRIME_TOWER)


class PrimeTowerParserTests(unittest.TestCase):
    def parse(self, gcode, padding=0.5):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir, "test.gcode")
            path.write_text(gcode, encoding="utf-8")
            return PRIME_TOWER.parse_prime_tower(str(path), padding)

    def test_no_tower_is_unchanged(self):
        result = self.parse("G90\nG1 X10 Y20\n;TYPE:Outer wall\n")
        self.assertFalse(result["detected"])
        self.assertEqual(result["polygon"], [])

    def test_uses_actual_rotated_and_resized_motion(self):
        result = self.parse("""G90
G1 X125 Y132
;TYPE:Prime tower
G1 X83 Y90 E2.6
G1 X86 Y87 E.2
G1 X128 Y129 E2.6
; WIPE_TOWER_END
G1 X300 Y300
""")
        self.assertTrue(result["detected"])
        self.assertEqual(result["blocks"], 1)
        self.assertEqual(result["bounds"], [82.5, 86.5, 128.5, 132.5])

    def test_relative_xy_and_late_tower_are_supported(self):
        result = self.parse("""G90
G1 X20 Y30
;TYPE:Outer wall
G1 X200 Y200
G91
M83
;TYPE:Prime tower
G1 X10 Y-5 E1
G1 X5 Y20 E1
; WIPE_TOWER_END
""", padding=0)
        self.assertEqual(result["bounds"], [200.0, 195.0, 215.0, 215.0])

    def test_unions_multiple_tower_blocks(self):
        result = self.parse("""G90
M83
G1 X10 Y20
;TYPE:Prime tower
G1 X20 Y30 E1
; WIPE_TOWER_END
G1 X100 Y110
;TYPE:Prime tower
G1 X120 Y130 E1
; WIPE_TOWER_END
""", padding=0)
        self.assertEqual(result["blocks"], 2)
        self.assertEqual(result["bounds"], [10.0, 20.0, 120.0, 130.0])

    def test_g92_updates_modal_xy(self):
        result = self.parse("""G90
M83
G92 X5 Y7
;TYPE:Prime tower
G1 X8 E1
G1 Y12 E1
; WIPE_TOWER_END
""", padding=0)
        self.assertEqual(result["bounds"], [5.0, 7.0, 8.0, 12.0])

    def test_ignores_toolchange_travel_inside_tower_block(self):
        result = self.parse("""G90
M83
G1 X183 Y143
;TYPE:Prime tower
G1 X0 Y245 F30000
G1 X205 Y345 F20000
G1 X183 Y143 F30000
G1 X166 Y143 E1
G1 Y129 E1
; WIPE_TOWER_END
""", padding=0)
        self.assertEqual(result["bounds"], [166.0, 129.0, 183.0, 143.0])


if __name__ == "__main__":
    unittest.main()
