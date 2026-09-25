#!/usr/bin/env python3

import importlib.util
import pathlib
import unittest


MODULE_PATH = pathlib.Path(__file__).with_name("k2_cartographer_scan_guard.py")
SPEC = importlib.util.spec_from_file_location("scan_guard", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class FakeGcode:
    def __init__(self):
        self.commands = {}
        self.scripts = []
        self.messages = []

    def register_command(self, name, handler):
        self.commands[name] = handler

    def run_script_from_command(self, script):
        self.scripts.append(script)

    def respond_info(self, message):
        self.messages.append(message)


class FakeToolhead:
    def __init__(self):
        self.recalculated = 0

    def _calc_junction_deviation(self):
        self.recalculated += 1


class FakeConfigFile:
    def get_status(self, _eventtime):
        return {"settings": {"printer": {
            "max_velocity": 500,
            "square_corner_velocity": 5,
            "max_accel": 6000,
            "max_accel_to_decel": 3000,
        }}}


class FakePrinter:
    def __init__(self):
        self.gcode = FakeGcode()
        self.toolhead = FakeToolhead()
        self.events = {}

    def lookup_object(self, name):
        if name == "gcode":
            return self.gcode
        if name == "toolhead":
            return self.toolhead
        return FakeConfigFile()

    def register_event_handler(self, name, handler):
        self.events[name] = handler


class FakeConfig:
    def __init__(self):
        self.printer = FakePrinter()

    def get_printer(self):
        return self.printer


class FakeCommand:
    def __init__(self, active):
        self.active = active

    def get_int(self, _name, minval=None, maxval=None):
        return self.active


class ScanLimitGuardTests(unittest.TestCase):
    def test_command_error_restores_configured_limits_once(self):
        config = FakeConfig()
        guard = MODULE.K2CartographerScanGuard(config)
        guard.cmd_guard(FakeCommand(1))
        guard._handle_command_error()
        guard._handle_command_error()
        toolhead = config.printer.toolhead
        self.assertEqual(toolhead.max_velocity, 500.0)
        self.assertEqual(toolhead.square_corner_velocity, 5.0)
        self.assertEqual(toolhead.max_accel, 6000.0)
        self.assertEqual(toolhead.max_accel_to_decel, 3000.0)
        self.assertEqual(toolhead.recalculated, 1)
        self.assertFalse(guard.active)

    def test_inactive_errors_do_not_change_limits(self):
        config = FakeConfig()
        guard = MODULE.K2CartographerScanGuard(config)
        guard._handle_command_error()
        self.assertEqual(config.printer.toolhead.recalculated, 0)


if __name__ == "__main__":
    unittest.main()
