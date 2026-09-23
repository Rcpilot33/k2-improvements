#!/usr/bin/env python3

import importlib.util
import pathlib
import unittest


HERE = pathlib.Path(__file__).resolve().parent
INSTALLER = (HERE / "install.sh").read_text(encoding="utf-8")
SPEC = importlib.util.spec_from_file_location(
    "k2_m141_guard", HERE / "k2_m141_guard.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class FakeStatus:
    def __init__(self, **status):
        self.status = status

    def get_status(self, eventtime):
        return dict(self.status)


class FakeReactor:
    def __init__(self):
        self.now = 123.0

    def monotonic(self):
        return self.now


class FakeCommand:
    def __init__(self, target=None, fan=None, speed=None):
        self.target = target
        self.fan = fan
        self.speed = speed
        self.responses = []

    def get_float(self, name, default=None):
        if name != "S":
            return default
        if self.speed is not None:
            return self.speed
        return self.target

    def get_int(self, name, default=None):
        return self.fan if name == "P" and self.fan is not None else default

    def error(self, message):
        return RuntimeError(message)

    def respond_info(self, message):
        self.responses.append(message)


class FakeGcode:
    def __init__(self):
        self.calls = []
        self.scripts = []
        self.handlers = {"M141": self.original, "M106": self.original_m106}

    def original(self, gcmd):
        self.calls.append(("original", gcmd.target))

    def original_m106(self, gcmd):
        self.calls.append(("original_m106", gcmd.fan, gcmd.speed))

    def register_command(self, name, handler, desc=None):
        if handler is None:
            return self.handlers.pop(name, None)
        if name in self.handlers:
            raise RuntimeError("duplicate command")
        self.handlers[name] = handler

    def run_script_from_command(self, script):
        self.scripts.append(script)
        self.calls.append(("restore", script))


class FakePrinter:
    def __init__(self, state="printing", margin=2.0):
        self.gcode = FakeGcode()
        self.objects = {
            "gcode": self.gcode,
            "print_stats": FakeStatus(state=state),
            "gcode_macro _M191_VARS": FakeStatus(chamber_fan_margin=margin),
        }
        self.reactor = FakeReactor()
        self.events = {}

    def lookup_object(self, name):
        return self.objects[name]

    def get_reactor(self):
        return self.reactor

    def register_event_handler(self, event, handler):
        self.events[event] = handler

    def config_error(self, message):
        return RuntimeError(message)


class FakeConfig:
    def __init__(self, printer):
        self.printer = printer

    def get_printer(self):
        return self.printer

    def error(self, message):
        return RuntimeError(message)


class M141GuardTests(unittest.TestCase):
    def make_guard(self, state="printing", margin=2.0):
        printer = FakePrinter(state=state, margin=margin)
        guard = MODULE.K2M141Guard(FakeConfig(printer))
        printer.events["klippy:ready"]()
        return guard, printer.gcode

    def test_active_heating_calls_original_then_restores_margin_target(self):
        guard, gcode = self.make_guard()
        command = FakeCommand(55.0)

        guard.cmd_M141(command)

        self.assertEqual(gcode.calls[0], ("original", 55.0))
        self.assertEqual(
            gcode.scripts,
            [
                "SET_TEMPERATURE_FAN_TARGET "
                "TEMPERATURE_FAN=chamber_fan TARGET=57.000000"
            ],
        )

    def test_s_zero_keeps_stock_end_print_behavior(self):
        guard, gcode = self.make_guard()
        command = FakeCommand(0.0)

        guard.cmd_M141(command)

        self.assertEqual(gcode.calls, [("original", 0.0)])
        self.assertEqual(gcode.scripts, [])

    def test_idle_heating_command_is_unchanged(self):
        guard, gcode = self.make_guard(state="standby")
        command = FakeCommand(55.0)

        guard.cmd_M141(command)

        self.assertEqual(gcode.calls, [("original", 55.0)])

    def test_low_temperature_command_is_unchanged(self):
        guard, gcode = self.make_guard()
        command = FakeCommand(35.0)

        guard.cmd_M141(command)

        self.assertEqual(gcode.calls, [("original", 35.0)])

    def test_missing_s_parameter_is_unchanged(self):
        guard, gcode = self.make_guard()
        command = FakeCommand()

        guard.cmd_M141(command)

        self.assertEqual(gcode.calls, [("original", None)])

    def test_idle_deformation_sequence_suppresses_case_fan_request(self):
        guard, gcode = self.make_guard(state="standby")
        guard.cmd_M141(FakeCommand(30.0))
        command = FakeCommand(fan=1, speed=255.0)

        guard.cmd_M106(command)

        self.assertEqual(
            gcode.calls,
            [
                ("original", 30.0),
                ("restore", "SET_PIN PIN=fan1 VALUE=0"),
            ],
        )
        self.assertEqual(gcode.scripts, ["SET_PIN PIN=fan1 VALUE=0"])
        self.assertIn("Suppressed Creality pre-file", command.responses[0])
        self.assertEqual(guard.pre_file_case_fan_deadline, 0.0)

    def test_deformation_window_expires_before_later_manual_case_fan(self):
        guard, gcode = self.make_guard(state="standby")
        guard.cmd_M141(FakeCommand(30.0))
        guard.reactor.now += guard.PREFILE_CASE_FAN_WINDOW + 0.1

        guard.cmd_M106(FakeCommand(fan=1, speed=255.0))

        self.assertEqual(
            gcode.calls,
            [("original", 30.0), ("original_m106", 1, 255.0)],
        )

    def test_non_case_fan_command_passes_through_during_window(self):
        guard, gcode = self.make_guard(state="standby")
        guard.cmd_M141(FakeCommand(30.0))

        guard.cmd_M106(FakeCommand(fan=0, speed=255.0))

        self.assertEqual(
            gcode.calls,
            [("original", 30.0), ("original_m106", 0, 255.0)],
        )

    def test_printing_m141_does_not_arm_case_fan_suppression(self):
        guard, gcode = self.make_guard(state="printing")
        guard.cmd_M141(FakeCommand(30.0))

        guard.cmd_M106(FakeCommand(fan=1, speed=255.0))

        self.assertEqual(
            gcode.calls,
            [("original", 30.0), ("original_m106", 1, 255.0)],
        )

    def test_case_fan_command_without_deformation_marker_passes_through(self):
        guard, gcode = self.make_guard(state="standby")

        guard.cmd_M106(FakeCommand(fan=1, speed=255.0))

        self.assertEqual(gcode.calls, [("original_m106", 1, 255.0)])

    def test_invalid_margin_stops_before_original_handler(self):
        guard, gcode = self.make_guard(margin=11.0)

        with self.assertRaisesRegex(RuntimeError, "must be from 0 to 10 C"):
            guard.cmd_M141(FakeCommand(55.0))

        self.assertEqual(gcode.calls, [])

    def test_installer_loads_guard_and_requests_code_restart(self):
        self.assertIn('k2_m141_guard.py"', INSTALLER)
        self.assertIn('k2_m141_guard.cfg"', INSTALLER)
        self.assertIn("touch /tmp/k2-klippy-code-restart-required", INSTALLER)
        self.assertIn("scripts/klippy_code_restart.sh", INSTALLER)

    def test_registration_waits_until_all_config_macros_are_loaded(self):
        printer = FakePrinter()
        guard = MODULE.K2M141Guard(FakeConfig(printer))

        self.assertIsNone(guard.original_m141)
        self.assertIsNone(guard.original_m106)
        self.assertEqual(printer.gcode.handlers["M141"], printer.gcode.original)
        self.assertEqual(
            printer.gcode.handlers["M106"], printer.gcode.original_m106
        )

        printer.events["klippy:ready"]()

        self.assertIsNotNone(guard.original_m141)
        self.assertIsNotNone(guard.original_m106)
        self.assertEqual(printer.gcode.handlers["M141"], guard.cmd_M141)
        self.assertEqual(printer.gcode.handlers["M106"], guard.cmd_M106)

    def test_missing_m106_restores_m141_before_reporting_config_error(self):
        printer = FakePrinter()
        del printer.gcode.handlers["M106"]
        MODULE.K2M141Guard(FakeConfig(printer))

        with self.assertRaisesRegex(RuntimeError, "original fan handlers"):
            printer.events["klippy:ready"]()

        self.assertEqual(printer.gcode.handlers["M141"], printer.gcode.original)


if __name__ == "__main__":
    unittest.main()
