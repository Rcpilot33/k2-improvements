"""Regression tests for Cartographer connection checks during K2 homing."""

import importlib.util
import pathlib
import sys
import types
import unittest


MODULE_PATH = pathlib.Path(__file__).with_name("patches") / "homing.py"

# The K2 homing patch imports this firmware-specific constant at module load.
extras = types.ModuleType("extras")
z_align = types.ModuleType("extras.z_align")
z_align.MOTOR_PROTECT_ERROR = -1
extras.z_align = z_align
sys.modules.setdefault("extras", extras)
sys.modules.setdefault("extras.z_align", z_align)

SPEC = importlib.util.spec_from_file_location("k2_homing", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class FakePrinter:
    command_error = RuntimeError

    def __init__(self, scanner):
        self.scanner = scanner

    def lookup_object(self, name, default=None):
        if name == "cartographer":
            return self.scanner
        return default


class HostMcu:
    def __init__(self, disconnected=False):
        self.non_critical_disconnected = disconnected


class CurrentMcu:
    def __init__(self, disconnected=False):
        self.disconnected = disconnected

    def is_disconnected(self):
        return self.disconnected


class LegacyMcu:
    def __init__(self, disconnected=False):
        self.klipper_mcu = HostMcu(disconnected)


class Scanner:
    def __init__(self, mcu, scan_ready=True):
        self.mcu = mcu
        self.scan_mode = types.SimpleNamespace(is_ready=scan_ready)


class HomingScannerCompatibilityTests(unittest.TestCase):
    def make_homing(self, scanner):
        homing = object.__new__(MODULE.PrinterHoming)
        homing.printer = FakePrinter(scanner)
        return homing

    def test_no_cartographer_object_allows_other_probe_homing(self):
        self.make_homing(None)._check_scanner_connected()

    def test_current_connected_mcu_allows_homing(self):
        self.make_homing(Scanner(CurrentMcu(False)))._check_scanner_connected()

    def test_current_disconnected_mcu_stops_homing(self):
        with self.assertRaisesRegex(RuntimeError, "disconnected"):
            self.make_homing(
                Scanner(CurrentMcu(True)))._check_scanner_connected()

    def test_legacy_connected_mcu_allows_homing(self):
        self.make_homing(Scanner(LegacyMcu(False)))._check_scanner_connected()

    def test_legacy_disconnected_mcu_stops_homing(self):
        with self.assertRaisesRegex(RuntimeError, "disconnected"):
            self.make_homing(
                Scanner(LegacyMcu(True)))._check_scanner_connected()

    def test_unknown_cartographer_interface_fails_closed(self):
        with self.assertRaisesRegex(RuntimeError, "disconnected"):
            self.make_homing(object())._check_scanner_connected()

    def test_missing_scan_model_stops_homing(self):
        with self.assertRaisesRegex(RuntimeError, "scan model is not loaded"):
            self.make_homing(
                Scanner(CurrentMcu(False), scan_ready=False)
            )._check_scanner_model_ready()

    def test_loaded_scan_model_allows_homing(self):
        self.make_homing(
            Scanner(CurrentMcu(False), scan_ready=True)
        )._check_scanner_model_ready()

    def test_no_cartographer_allows_other_probe_model_check(self):
        self.make_homing(None)._check_scanner_model_ready()


if __name__ == "__main__":
    unittest.main()
