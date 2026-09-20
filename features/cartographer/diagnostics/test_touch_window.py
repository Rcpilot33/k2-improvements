"""Host-only checks; cannot establish real MCU stopping latency."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch


spec = importlib.util.spec_from_file_location(
    "touch_window_diagnostic", Path(__file__).with_name("carto_touch_window_test.py")
)
diagnostic = importlib.util.module_from_spec(spec)
spec.loader.exec_module(diagnostic)


class TouchWindowTests(unittest.TestCase):
    def setUp(self):
        self.position = [175.0, 175.0, 100.0, 0.0]
        self.status = {
            "homed_axes": "xyz", "axis_minimum": [0, 0, -5],
            "axis_maximum": [350, 350, 350],
        }
        self.toolhead = Mock()
        self.toolhead.get_status.return_value = self.status
        self.toolhead.get_position.side_effect = lambda: self.position[:]
        self.toolhead.get_max_accel.return_value = 5000.0
        self.toolhead.get_last_move_time.return_value = 10.0
        self.toolhead.get_extruder().get_heater().get_temp.return_value = (25.0, 0.0)
        self.toolhead.manual_move.side_effect = self.move
        self.carto = Mock()
        self.carto.touch_mode.get_model.return_value = SimpleNamespace(threshold=3708)
        self.carto.touch_mode.boundaries.is_within.return_value = True
        session = Mock()
        session.__enter__ = Mock(return_value=session)
        session.__exit__ = Mock(return_value=False)
        self.carto.mcu.start_session.return_value = session
        self.homing = Mock()
        self.gcode = Mock()
        self.stats = Mock()
        self.stats.get_status.return_value = {"state": "standby"}
        self.sd = Mock()
        self.sd.is_active.return_value = False
        objects = dict(toolhead=self.toolhead, cartographer=self.carto,
                       homing=self.homing, gcode=self.gcode,
                       print_stats=self.stats, virtual_sdcard=self.sd)
        self.printer = Mock()
        self.printer.is_shutdown.return_value = False
        self.printer.lookup_object.side_effect = lambda name, default=None: objects.get(name, default)
        config = Mock()
        config.get_printer.return_value = self.printer
        self.test = diagnostic.load_config(config)
        self.command = Mock()
        self.command.get.return_value = "CLEAR_WINDOW"
        self.command.error.side_effect = lambda message: RuntimeError(message)
        self.endstop = Mock()
        self.import_patch = patch.dict("sys.modules", {
            "cartographer.adapters.klipper.endstop": SimpleNamespace(KlipperEndstop=self.endstop),
        })
        self.import_patch.start()
        self.addCleanup(self.import_patch.stop)

    def move(self, coordinates, speed):
        self.position[2] = coordinates[2]

    def assert_rejected(self):
        with self.assertRaises(Exception):
            self.test.run(self.command)
        self.toolhead.manual_move.assert_not_called()
        self.homing.probing_move.assert_not_called()
        self.printer.invoke_shutdown.assert_not_called()

    def test_missing_confirmation(self):
        self.command.get.return_value = ""
        self.assert_rejected()

    def test_unhomed(self):
        self.status["homed_axes"] = "xy"
        self.assert_rejected()

    def test_printing_or_paused(self):
        for state in ("printing", "paused"):
            with self.subTest(state=state):
                self.stats.get_status.return_value = {"state": state}
                self.assert_rejected()

    def test_active_sd(self):
        self.sd.is_active.return_value = True
        self.assert_rejected()

    def test_shutdown(self):
        self.printer.is_shutdown.return_value = True
        self.assert_rejected()

    def test_nozzle_hot_or_target_active(self):
        for temperatures in ((51.0, 0.0), (25.0, 140.0), (float("nan"), 0.0)):
            with self.subTest(temperatures=temperatures):
                self.toolhead.get_extruder().get_heater().get_temp.return_value = temperatures
                self.assert_rejected()

    def test_disconnected_before_start(self):
        self.carto.mcu.ensure_connected.side_effect = RuntimeError("disconnected")
        self.assert_rejected()

    def test_no_touch_model(self):
        self.carto.touch_mode.get_model.side_effect = RuntimeError("no model")
        self.assert_rejected()

    def test_invalid_threshold(self):
        self.carto.touch_mode.get_model.return_value.threshold = 0
        self.assert_rejected()

    def test_outside_touch_bounds(self):
        self.carto.touch_mode.boundaries.is_within.return_value = False
        self.assert_rejected()

    def test_insufficient_initial_clearance(self):
        self.position[2] = 20.0
        self.assert_rejected()

    def test_invalid_coordinates(self):
        self.position[0] = float("nan")
        self.assert_rejected()

    def test_travel_limit(self):
        self.status["axis_maximum"][2] = 140.0
        self.assert_rejected()

    def test_exact_window_endstop_and_shutdown(self):
        self.test.run(self.command)
        self.toolhead.manual_move.assert_called_once_with([None, None, 150.0], speed=5.0)
        self.endstop.assert_called_once_with(self.carto.mcu, self.carto.touch_mode)
        self.homing.probing_move.assert_called_once_with(
            self.endstop.return_value, [175.0, 175.0, 50.0, 0.0], 2.0
        )
        self.gcode.run_script_from_command.assert_called_once_with("SET_VELOCITY_LIMIT ACCEL=100")
        self.printer.invoke_shutdown.assert_called_once()
        with self.assertRaisesRegex(RuntimeError, "already attempted"):
            self.test.run(self.command)
        self.homing.probing_move.assert_called_once()

    def test_disconnect_during_positioning_prevents_touch(self):
        self.carto.mcu.ensure_connected.side_effect = [None, RuntimeError("disconnected")]
        with self.assertRaisesRegex(RuntimeError, "disconnected"):
            self.test.run(self.command)
        self.homing.probing_move.assert_not_called()
        self.printer.invoke_shutdown.assert_called_once()

    def test_failed_start_position_prevents_touch(self):
        self.toolhead.manual_move.side_effect = None
        with self.assertRaisesRegex(RuntimeError, "start position"):
            self.test.run(self.command)
        self.homing.probing_move.assert_not_called()
        self.printer.invoke_shutdown.assert_called_once()

    def test_failure_never_retries_or_retracts(self):
        self.homing.probing_move.side_effect = RuntimeError("communication timeout")
        with self.assertRaisesRegex(RuntimeError, "communication timeout"):
            self.test.run(self.command)
        self.homing.probing_move.assert_called_once()
        self.toolhead.manual_move.assert_called_once()
        self.printer.invoke_shutdown.assert_called_once()


if __name__ == "__main__":
    unittest.main()
