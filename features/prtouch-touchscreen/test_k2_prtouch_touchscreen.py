"""Exercise the real native Python probe methods without loading MCU code."""

import ast
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


compat_module = load(HERE / "k2_prtouch_touchscreen.py", "prtouch_display_module")
carto_module = load(ROOT / "features/cartographer/k2_cartographer_touchscreen.py",
                    "carto_display_module")
# Use the repository's Creality PrinterProbe implementations, not a rewritten
# approximation of the calibration arithmetic being tested. Exclude hardware
# imports/constructor and the print-recovery file writer from this harness.
native_path = ROOT / "features/axis_twist_compensation/probe.py"
native_tree = ast.parse(native_path.read_text())
native_class = next(n for n in native_tree.body
                    if isinstance(n, ast.ClassDef) and n.name == "PrinterProbe")
native_methods = {}
exec(compile(ast.Module(body=[n for n in native_class.body
     if isinstance(n, ast.FunctionDef) and n.name in
     ("get_offsets", "get_status", "cmd_Z_OFFSET_APPLY_PROBE")], type_ignores=[]),
     str(native_path), "exec"), native_methods)


class GCode:
    def __init__(self):
        self.commands = {}
        self.messages = []

    def register_command(self, name, handler, desc=None):
        self.commands[name] = handler

    def respond_info(self, message):
        self.messages.append(message)

    def run_script(self, script):
        raise AssertionError("compatibility must not send G-code: " + script)


class Move:
    def __init__(self):
        self.offset = 0.0

    def get_status(self, eventtime=0):
        return {"homing_origin": SimpleNamespace(z=self.offset)}


class ConfigFile:
    def __init__(self):
        self.pending = {}

    def set(self, section, option, value):
        self.pending[(section, option)] = value


class NativeProbe:
    get_offsets = native_methods["get_offsets"]
    get_status = native_methods["get_status"]
    cmd_Z_OFFSET_APPLY_PROBE = native_methods["cmd_Z_OFFSET_APPLY_PROBE"]

    def __init__(self, printer, offset):
        self.printer = printer
        self.gcode = printer.objects["gcode"]
        self.gcode_move = printer.objects["gcode_move"]
        self.name = "prtouch_v3"
        self.z_offset = offset
        self.x_offset = self.y_offset = 0.0
        self.z_offset_calibrate = 0.0
        self.z_offset_change_flag = False
        self.last_state = False
        self.last_z_result = 1.962
        self.record_calls = 0
        self.gcode.commands["Z_OFFSET_APPLY_PROBE"] = self.cmd_Z_OFFSET_APPLY_PROBE

    def record_gcode_offset_when_printing(self):
        self.record_calls += 1


class Printer:
    def __init__(self):
        self.objects = {"gcode": GCode(), "gcode_move": Move(),
                        "configfile": ConfigFile(), "prtouch_v3": object()}
        self.handlers = {}

    def lookup_object(self, name, default=None):
        return self.objects.get(name, default)

    def register_event_handler(self, event, callback):
        self.handlers.setdefault(event, []).append(callback)

    def ready(self):
        for callback in self.handlers["klippy:ready"]:
            callback()


class Tests(unittest.TestCase):
    def setup_probe(self, offset=-.020, activate=True):
        self.printer = Printer()
        self.move = self.printer.objects["gcode_move"]
        self.cfg = self.printer.objects["configfile"]
        self.probe = NativeProbe(self.printer, offset)
        self.printer.objects["probe"] = self.probe
        self.original_handler = self.probe.gcode.commands["Z_OFFSET_APPLY_PROBE"]
        self.compat = compat_module.load_config(SimpleNamespace(
            get_printer=lambda: self.printer))
        if activate:
            self.printer.ready()

    def apply(self):
        self.probe.gcode.commands["Z_OFFSET_APPLY_PROBE"](None)

    def cleanup(self):
        # Exact master-server pair captured on both printers. MOVE=0 changes
        # the coordinate offset, not physical motion, so model that separately.
        self.move.offset += self.probe.get_status(0)["z_offset"]
        self.apply()

    def test_only_status_changes_on_install_and_query(self):
        self.setup_probe()
        self.assertTrue(self.compat.installed)
        self.assertEqual(self.probe.get_status(2),
                         {"last_query": False, "last_z_result": 1.962, "z_offset": 0})
        self.assertEqual(self.probe.get_offsets(), (0, 0, -.020))
        self.assertEqual(self.probe.z_offset_calibrate, 0)
        self.assertFalse(self.probe.z_offset_change_flag)
        self.assertEqual(self.cfg.pending, {})
        self.assertIs(self.probe.gcode.commands["Z_OFFSET_APPLY_PROBE"],
                      self.original_handler)
        self.assertEqual(self.probe.record_calls, 0)

    def test_captured_no_carto_touchscreen_sequence_restores_baseline(self):
        self.setup_probe()
        # At preparation, master-server sees zero, not the loaded -.020.
        self.assertEqual(self.probe.get_status(0)["z_offset"], 0)
        self.move.offset = .100  # existing material SET_GCODE_OFFSET Z=0.100
        self.assertEqual(self.probe.get_status(0)["z_offset"], -.100)
        self.move.offset += .005  # normal touchscreen MOVE=1 adjustment
        self.apply()
        self.assertEqual(self.cfg.pending[("prtouch_v3", "z_offset")], "-0.125")
        self.assertEqual(self.probe.get_status(0)["z_offset"], -.105)
        self.assertAlmostEqual(self.compat.get_status(0)["native_reported_z_offset"], -.125)
        self.cleanup()
        self.assertAlmostEqual(self.move.offset, 0)
        self.assertEqual(self.cfg.pending[("prtouch_v3", "z_offset")], "-0.020")
        self.assertEqual(self.probe.get_offsets()[2], -.020)
        self.assertEqual(self.probe.record_calls, 2)

    def test_unadjusted_repeated_prints_and_both_offset_signs(self):
        for global_offset in (-.020, 0.0, .035):
            for material in (-.030, 0.0, .100):
                for adjustment in (-.010, 0.0, .005):
                    with self.subTest(global_offset=global_offset,
                                      material=material, adjustment=adjustment):
                        self.setup_probe(global_offset)
                        for _ in range(3):
                            self.move.offset = material
                            self.move.offset += adjustment
                            if adjustment:
                                self.apply()
                            self.cleanup()
                            self.assertAlmostEqual(self.move.offset, 0, places=6)
                            # Native formatting can preserve a negative zero
                            # from harmless floating-point cleanup residue.
                            self.assertAlmostEqual(
                                float(self.cfg.pending[("prtouch_v3", "z_offset")]),
                                global_offset, places=3)
                            self.assertEqual(self.probe.get_offsets()[2], global_offset)

    def test_direct_probe_apply_still_stages_the_native_calculation(self):
        self.setup_probe()
        self.move.offset = -.030
        self.apply()
        self.assertEqual(self.cfg.pending[("prtouch_v3", "z_offset")], "0.010")
        self.assertEqual(self.probe.get_status(0)["z_offset"], .030)
        self.assertEqual(self.probe.get_offsets()[2], -.020)

    def test_rounding_does_not_expose_float_residue(self):
        self.setup_probe()
        self.move.offset = .100 + .005
        self.assertEqual(self.probe.get_status(0)["z_offset"], -.105)

    def test_copies_original_status_and_preserves_all_other_fields(self):
        self.setup_probe(activate=False)
        original_status = {"z_offset": -.500, "last_query": True,
                           "last_z_result": 2.1, "future_native_field": "keep"}
        self.probe.get_status = lambda eventtime: original_status
        self.printer.ready()
        self.move.offset = -.030
        status = self.probe.get_status(5)
        self.assertEqual(status["z_offset"], .030)
        self.assertEqual(original_status["z_offset"], -.500)
        for field in ("last_query", "last_z_result", "future_native_field"):
            self.assertEqual(status[field], original_status[field])

    def test_pending_calibration_never_becomes_the_display_offset(self):
        self.setup_probe()
        self.probe.z_offset_calibrate = -.500
        self.probe.z_offset_change_flag = True
        self.move.offset = .035
        self.assertEqual(self.probe.get_status(0)["z_offset"], -.035)
        self.assertEqual(self.compat.get_status(0)["native_reported_z_offset"], -.500)
        self.assertEqual(self.probe.get_offsets()[2], -.020)

    def test_repeated_ready_does_not_wrap_again(self):
        self.setup_probe()
        original = self.compat.original_get_status
        self.printer.ready()
        self.assertIs(self.compat.original_get_status, original)
        self.assertEqual(self.probe.get_status(0)["z_offset"], 0)

    def test_missing_objects_or_wrong_probe_stays_inactive(self):
        for missing in ("prtouch_v3", "probe", "gcode_move"):
            self.setup_probe(activate=False)
            del self.printer.objects[missing]
            original = self.probe.get_status
            self.printer.ready()
            self.assertFalse(self.compat.installed)
            self.assertEqual(self.probe.get_status, original)
        self.setup_probe(activate=False)
        self.probe.name = "probe"
        self.printer.ready()
        self.assertFalse(self.compat.installed)

    def test_cartographer_display_is_untouched_even_with_dummy_native(self):
        for native_first in (True, False):
            with self.subTest(native_first=native_first):
                self.setup_probe(activate=False)
                self.printer.objects["cartographer"] = SimpleNamespace(
                    scan_mode=object(), touch_mode=object())
                carto = carto_module.load_config(SimpleNamespace(
                    get_printer=lambda: self.printer))
                self.printer.handlers["klippy:ready"] = (
                    [self.compat._handle_ready, carto._handle_ready] if native_first
                    else [carto._handle_ready, self.compat._handle_ready])
                self.printer.ready()
                self.assertFalse(self.compat.installed)
                self.assertTrue(carto.installed)
                self.move.offset = .035
                self.assertEqual(self.probe.get_status(0)["z_offset"], -.035)
                self.move.offset += .005
                self.assertEqual(self.probe.get_status(0)["z_offset"], -.040)
                self.assertEqual(self.probe.get_status.__self__, carto)

    def test_status_command_exposes_calibration_separately_without_writes(self):
        self.setup_probe()
        self.probe.gcode.commands["K2_PRTOUCH_TOUCHSCREEN_STATUS"](self.probe.gcode)
        message = self.probe.gcode.messages[-1]
        self.assertIn("installed=True", message)
        self.assertIn("loaded_z_offset=-0.02", message)
        self.assertIn("native_reported_z_offset=-0.02", message)
        self.assertEqual(self.cfg.pending, {})


if __name__ == "__main__":
    unittest.main()
