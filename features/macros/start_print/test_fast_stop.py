#!/usr/bin/env python3
"""Regression tests for the firmware-gated START_PRINT Fast Stop helper."""

import importlib.util
import pathlib
import unittest


MODULE_PATH = pathlib.Path(__file__).with_name("k2_start_print_fast_stop.py")
SPEC = importlib.util.spec_from_file_location("k2_start_print_fast_stop", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class FakeTemplate:
    def __init__(self):
        self.original_calls = []
        self.script = "FIRST\nSECOND\n"

    def render(self, context=None):
        return self.script

    def run_gcode_from_command(self, context=None):
        self.original_calls.append(context)


class SupportedGCode:
    def __init__(self):
        self.cancel_pending = False
        self.calls = []
        self.executed = []
        self.handlers = {}
        self.messages = []

    def _process_commands(self, commands, need_ack=True, check_cancel=False):
        self.calls.append((commands, need_ack, check_cancel))
        for line in commands:
            if check_cancel and self.cancel_pending:
                return
            self.executed.append(line)
            handler = self.handlers.get(line)
            if handler is not None:
                handler()

    def respond_info(self, message):
        self.messages.append(message)


class FakeReactor:
    def __init__(self):
        self.now = 0.
        self.pauses = []
        self.on_pause = lambda: None

    def monotonic(self):
        return self.now

    def pause(self, until):
        self.pauses.append(until)
        self.now = until
        self.on_pause()
        return self.now


class FakeToolhead:
    def __init__(self):
        self.waits = 0

    def wait_moves(self):
        self.waits += 1


class UnsupportedGCode:
    def _process_commands(self, commands, need_ack=True):
        raise AssertionError("unsupported command loop must not be used")


class FakePrinter:
    def __init__(self, gcode, start_print, m191=None):
        self.objects = {
            "gcode": gcode,
            "gcode_macro START_PRINT": start_print,
        }
        if m191 is not None:
            self.objects["gcode_macro M191"] = m191
        self.handlers = {}
        self.reactor = FakeReactor()
        self.shutdown = False
        self.objects["toolhead"] = FakeToolhead()

    def get_reactor(self):
        return self.reactor

    def is_shutdown(self):
        return self.shutdown

    def get_start_args(self):
        return {}

    def lookup_object(self, name, default=None):
        return self.objects.get(name, default)

    def register_event_handler(self, event, handler):
        self.handlers[event] = handler

    def config_error(self, message):
        return RuntimeError(message)


class FakeConfig:
    def __init__(self, printer):
        self.printer = printer

    def get_printer(self):
        return self.printer


class StartPrintFastStopTests(unittest.TestCase):
    def make_helper(self, gcode):
        start_print = type("Macro", (), {"template": FakeTemplate()})()
        m191 = type("Macro", (), {"template": FakeTemplate()})()
        printer = FakePrinter(gcode, start_print, m191)
        helper = MODULE.K2StartPrintFastStop(FakeConfig(printer))
        return helper, printer, start_print, m191

    def test_supported_api_makes_start_print_and_nested_m191_cancel_aware(self):
        helper, printer, start_print, m191 = self.make_helper(SupportedGCode())
        other_template = FakeTemplate()

        printer.handlers["klippy:ready"]()
        start_print.template.run_gcode_from_command({"params": {}})
        m191.template.run_gcode_from_command({"params": {"S": "45"}})

        self.assertTrue(helper.active)
        self.assertEqual(
            printer.objects["gcode"].calls,
            [
                (["FIRST", "SECOND", ""], False, True),
                (["FIRST", "SECOND", ""], False, True),
            ],
        )
        other_template.run_gcode_from_command({"other": True})
        self.assertEqual(other_template.original_calls, [{"other": True}])

    def test_missing_creality_cancel_api_leaves_start_print_unchanged(self):
        helper, printer, start_print, m191 = self.make_helper(UnsupportedGCode())
        original_start = start_print.template.run_gcode_from_command
        original_m191 = m191.template.run_gcode_from_command

        printer.handlers["klippy:ready"]()

        self.assertFalse(helper.active)
        self.assertEqual(
            start_print.template.run_gcode_from_command.__func__,
            original_start.__func__,
        )
        self.assertEqual(
            m191.template.run_gcode_from_command.__func__, original_m191.__func__
        )

    def test_ready_handler_is_idempotent(self):
        helper, printer, start_print, m191 = self.make_helper(SupportedGCode())
        printer.handlers["klippy:ready"]()
        installed_start = start_print.template.run_gcode_from_command
        installed_m191 = m191.template.run_gcode_from_command

        printer.handlers["klippy:ready"]()

        self.assertIs(start_print.template.run_gcode_from_command, installed_start)
        self.assertIs(m191.template.run_gcode_from_command, installed_m191)

    def test_missing_m191_still_enables_start_print(self):
        gcode = SupportedGCode()
        start_print = type("Macro", (), {"template": FakeTemplate()})()
        printer = FakePrinter(gcode, start_print)
        helper = MODULE.K2StartPrintFastStop(FakeConfig(printer))

        printer.handlers["klippy:ready"]()
        start_print.template.run_gcode_from_command({"params": {}})

        self.assertTrue(helper.active)
        self.assertEqual(
            gcode.calls,
            [(["FIRST", "SECOND", ""], False, True)],
        )

    def test_cancel_state_is_exposed_only_after_firmware_gate_activates(self):
        gcode = SupportedGCode()
        gcode.cancel_pending = True
        helper, printer, _start_print, _m191 = self.make_helper(gcode)

        self.assertFalse(helper.is_cancel_pending())
        printer.handlers["klippy:ready"]()
        self.assertTrue(helper.is_cancel_pending())

    def make_stock_helper(self):
        gcode = SupportedGCode()
        helper, printer, start_print, m191 = self.make_helper(gcode)
        printer.objects["prtouch_v3"] = object()
        mesh = type("Macro", (), {"template": FakeTemplate()})()
        create = type("Macro", (), {"template": FakeTemplate()})()
        printer.objects["gcode_macro MESH_IF_NEEDED"] = mesh
        printer.objects["gcode_macro _CREATE_MESH"] = create
        return helper, printer, gcode, start_print, m191, mesh, create

    def test_stock_machine_and_mesh_soaks_cancel_within_one_second(self):
        for macro_name in ("START_PRINT", "_CREATE_MESH"):
            with self.subTest(macro=macro_name):
                helper, printer, gcode, *_ = self.make_stock_helper()
                template = printer.objects["gcode_macro " + macro_name].template
                template.script = "BEFORE\nG4 P300000 # x minute heat soak\nAFTER"
                printer.reactor.on_pause = lambda: setattr(gcode, "cancel_pending", True)
                printer.handlers["klippy:ready"]()
                template.run_gcode_from_command()
                self.assertEqual(gcode.executed, ["BEFORE"])
                self.assertEqual(printer.reactor.pauses, [1.])
                self.assertEqual(printer.objects["toolhead"].waits, 1)
                self.assertIn("Heat soak stopped by print cancellation", gcode.messages)

    def test_stock_successful_soak_waits_full_duration_before_continuing(self):
        helper, printer, gcode, start_print, *_ = self.make_stock_helper()
        start_print.template.script = "BEFORE\nG4 P2500.0\nAFTER"
        printer.handlers["klippy:ready"]()
        start_print.template.run_gcode_from_command()
        self.assertEqual(printer.reactor.pauses, [1., 2., 2.5])
        self.assertEqual(gcode.executed, ["BEFORE", "AFTER"])

    def test_cancel_before_soak_never_enters_wait_or_runs_afterward(self):
        helper, printer, gcode, start_print, *_ = self.make_stock_helper()
        start_print.template.script = "BEFORE\nG4 P60000\nAFTER"
        printer.handlers["klippy:ready"]()
        gcode.cancel_pending = True
        start_print.template.run_gcode_from_command()
        self.assertEqual(gcode.executed, [])
        self.assertEqual(printer.reactor.pauses, [])
        self.assertEqual(printer.objects["toolhead"].waits, 0)

    def test_stock_shutdown_ends_soak_without_running_following_commands(self):
        helper, printer, gcode, start_print, *_ = self.make_stock_helper()
        start_print.template.script = "BEFORE\nG4 P60000\nAFTER"
        printer.reactor.on_pause = lambda: setattr(printer, "shutdown", True)
        printer.handlers["klippy:ready"]()
        start_print.template.run_gcode_from_command()
        self.assertEqual(gcode.executed, ["BEFORE"])
        self.assertEqual(printer.reactor.pauses, [1.])

    def test_canceled_nested_m191_unwinds_stock_mesh_and_start_print(self):
        helper, printer, gcode, start_print, m191, mesh, create = self.make_stock_helper()
        start_print.template.script = "MESH_IF_NEEDED\nLOAD_MESH\nSTART_EXTRUDING"
        mesh.template.script = "_CREATE_MESH\nMESH_DONE"
        create.template.script = "M191\nG4 P300000\nZ_TILT_ADJUST\nBED_MESH_CALIBRATE"
        m191.template.script = "WAIT_CHAMBER\nRESTORE_BED"
        gcode.handlers["WAIT_CHAMBER"] = lambda: setattr(gcode, "cancel_pending", True)
        printer.handlers["klippy:ready"]()
        # Resolve installed wrappers at dispatch, as Klipper's macros do.
        for name in ("MESH_IF_NEEDED", "_CREATE_MESH", "M191"):
            gcode.handlers[name] = (
                printer.objects["gcode_macro " + name].template.run_gcode_from_command
            )
        start_print.template.run_gcode_from_command()
        self.assertEqual(
            gcode.executed,
            ["MESH_IF_NEEDED", "_CREATE_MESH", "M191", "WAIT_CHAMBER"],
        )
        self.assertEqual(printer.reactor.pauses, [])

    def test_stock_soak_can_run_again_after_cancel_cleanup(self):
        helper, printer, gcode, start_print, *_ = self.make_stock_helper()
        start_print.template.script = "G4 P2000\nAFTER"
        printer.reactor.on_pause = lambda: setattr(gcode, "cancel_pending", True)
        printer.handlers["klippy:ready"]()
        start_print.template.run_gcode_from_command()
        self.assertEqual(gcode.executed, [])
        # Creality clears cancel_pending during its existing end-print handoff.
        gcode.cancel_pending = False
        printer.reactor.on_pause = lambda: None
        start_print.template.run_gcode_from_command()
        self.assertEqual(gcode.executed, ["AFTER"])
        self.assertEqual(printer.reactor.now, 3.)

    def test_stock_ready_is_idempotent_and_end_print_is_not_wrapped(self):
        helper, printer, gcode, start_print, m191, mesh, create = self.make_stock_helper()
        end_print = FakeTemplate()
        printer.objects["gcode_macro END_PRINT"] = type(
            "Macro", (), {"template": end_print}
        )()
        printer.handlers["klippy:ready"]()
        templates = (start_print.template, m191.template, mesh.template, create.template)
        installed = [template.run_gcode_from_command for template in templates]
        printer.handlers["klippy:ready"]()
        for template, original in zip(templates, installed):
            self.assertIs(template.run_gcode_from_command, original)
        self.assertFalse(getattr(end_print, "k2_fast_stop_active", False))

    def test_cartographer_keeps_native_dwells_and_mesh_macros_unchanged(self):
        helper, printer, gcode, start_print, m191, mesh, create = self.make_stock_helper()
        printer.objects["cartographer"] = object()
        start_print.template.script = "G4 P60000\nAFTER"
        printer.handlers["klippy:ready"]()
        start_print.template.run_gcode_from_command()
        self.assertEqual(gcode.executed, ["G4 P60000", "AFTER"])
        self.assertEqual(printer.reactor.pauses, [])
        self.assertFalse(getattr(mesh.template, "k2_fast_stop_active", False))
        self.assertFalse(getattr(create.template, "k2_fast_stop_active", False))

    def test_stock_native_probe_and_unrecognized_dwells_are_not_rewritten(self):
        helper, printer, gcode, start_print, *_ = self.make_stock_helper()
        start_print.template.script = "BED_MESH_CALIBRATE\nG4 S60\nG4 Pbad"
        printer.handlers["klippy:ready"]()
        start_print.template.run_gcode_from_command()
        self.assertEqual(gcode.executed, ["BED_MESH_CALIBRATE", "G4 S60", "G4 Pbad"])
        self.assertEqual(printer.reactor.pauses, [])

    def test_unsupported_stock_firmware_leaves_mesh_templates_unchanged(self):
        helper, printer, _gcode, _start, _m191, mesh, create = self.make_stock_helper()
        helper.gcode = UnsupportedGCode()
        printer.handlers["klippy:ready"]()
        self.assertFalse(helper.active)
        self.assertFalse(getattr(mesh.template, "k2_fast_stop_active", False))
        self.assertFalse(getattr(create.template, "k2_fast_stop_active", False))


if __name__ == "__main__":
    unittest.main()
