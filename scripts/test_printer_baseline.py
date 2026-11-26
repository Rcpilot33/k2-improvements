import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import printer_baseline as baseline


class PrinterBaselineTests(unittest.TestCase):
    def test_hardware_identity(self):
        for model_id, expected in (("F008", "K2 Plus"), ("F012", "K2 Pro"),
                                   ("F021", "unknown"), (None, "unknown")):
            self.assertEqual(baseline.printer_model(model_id), expected)

    def test_main_cfg_limits_exclude_other_steppers_and_saved_comments(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "printer.cfg"
            path.write_text("[stepper_y]\nposition_min: -6.5\nposition_max: 332 # mm\n"
                            "[stepper_z1]\nposition_max: 350\n#*# position_max: 999\n")
            self.assertEqual(baseline.saved_axis_limits(path),
                             {"y": {"position_min": -6.5, "position_max": 332}})

    def test_unhomed_ready_controller_and_distinct_limits(self):
        status = {"motor_control": {"motor_ready": True},
                  "toolhead": {"homed_axes": "", "axis_maximum": [302, 302, 303, 0]},
                  "configfile": {"settings": {"stepper_y": {"position_max": 332}}}}
        reply = io.BytesIO(json.dumps({"result": {"status": status}}).encode())
        with patch.object(baseline, "urlopen", return_value=reply):
            report = baseline.running_state()
        self.assertIs(report["motor_ready"], True)
        self.assertEqual(report["toolhead"]["homed_axes"], "")
        self.assertEqual(report["toolhead"]["axis_maximum"][1], 302)
        self.assertEqual(report["loaded_axis_limits"]["y"]["position_max"], 332)
