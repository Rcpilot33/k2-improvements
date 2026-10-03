#!/usr/bin/env python3

import unittest
from pathlib import Path


CONFIG = Path(__file__).with_name("cartographer_macros.cfg")


class CartographerMacroTests(unittest.TestCase):
    def test_load_selected_only_requires_touch_model_in_touch_mode(self):
        text = CONFIG.read_text(encoding="utf-8")
        body = text.split("[gcode_macro A23_CARTO_LOAD_SELECTED]", 1)[1]
        body = body.split("[gcode_macro A61_CARTO_TOUCH_HOME]", 1)[0]

        self.assertIn('carto_final_z_mode|default("touch")|string|lower', body)
        self.assertIn('final_z_mode not in ["touch", "scan"]', body)
        scan_load = body.index("CARTOGRAPHER_SCAN_MODEL LOAD={surface}")
        touch_guard = body.index('{% if final_z_mode == "touch" %}')
        touch_load = body.index("CARTOGRAPHER_TOUCH_MODEL LOAD={surface}")
        touch_guard_end = body.index("{% endif %}", touch_guard)
        self.assertLess(scan_load, touch_guard)
        self.assertLess(touch_guard, touch_load)
        self.assertLess(touch_load, touch_guard_end)
        self.assertEqual(body.count("CARTOGRAPHER_TOUCH_MODEL LOAD="), 1)


if __name__ == "__main__":
    unittest.main()
