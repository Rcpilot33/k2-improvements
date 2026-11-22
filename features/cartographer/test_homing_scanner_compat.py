"""Regression tests for Cartographer connection checks during K2 homing."""

import importlib.util
import pathlib
import sys
import types
import unittest
from unittest.mock import Mock


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

    def test_single_z_recovery_has_no_tilt_adjustment(self):
        self.make_homing(None).resume_adjustment()

    def test_loaded_scan_model_allows_homing(self):
        self.make_homing(
            Scanner(CurrentMcu(False), scan_ready=True)
        )._check_scanner_model_ready()

    def test_no_cartographer_allows_other_probe_model_check(self):
        self.make_homing(None)._check_scanner_model_ready()

    def test_optical_home_policy(self):
        # Each tuple gives (calibration active, explicit request, optical expected).
        for dual_z, carto, sequence in (
            (False, True, [(False, 0, False), (True, 0, True), (True, 1, True),
                           (True, 0, False), (False, 0, False)]),
            (False, True, [(False, 1, True), (False, 0, False)]),
            (False, True, [(True, 1, True), (True, 0, False)]),
            (True, True, [(False, 0, True), (False, 0, False), (False, 1, True)]),
            (False, False, [(False, 0, True), (False, 0, False)]),
        ):
            scanner = Scanner(CurrentMcu()) if carto else None
            homing = self.make_homing(scanner)
            homing.config = Mock()
            sections = {'z_align'}
            if dual_z:
                sections.add('stepper_z1')
            if carto:
                sections.add('cartographer')
            homing.config.has_section.side_effect = sections.__contains__
            homing.probe_type = ''
            homing.z_move = 0
            homing.run_G28_two_Z = Mock(return_value=0)
            homing.write_real_zmax = Mock()
            homing.run_gcmd = Mock()
            toolhead = Mock()
            toolhead.get_status.return_value = {'homed_axes': 'xy'}
            align = types.SimpleNamespace(is_already_zodwn=False, zdown_switch_enable=0)
            box = Mock()
            box.has_flushing_sign.return_value = False
            gcode = Mock()
            objects = dict(toolhead=toolhead, box=box, gcode=gcode, z_align=align,
                           cartographer=scanner, gcode_move=Mock())
            homing.printer.lookup_object = objects.get
            homing.printer.get_reactor = Mock()
            for calibration, request, optical in sequence:
                with self.subTest(dual_z=dual_z, carto=carto, calibration=calibration,
                                  request=request, already_aligned=align.is_already_zodwn):
                    if request:
                        align.zdown_switch_enable = request
                    toolhead.G29_flag = calibration
                    was_aligned = align.is_already_zodwn
                    homing.cmd_G28({'Z': ''})
                    self.assertEqual(homing.run_G28_two_Z.call_count, int(optical))
                    self.assertEqual(align.is_already_zodwn, was_aligned or optical)
                    self.assertEqual(align.zdown_switch_enable, 0)
                    self.assertEqual(homing.write_real_zmax.called, calibration and optical)
                    toolhead.get_kinematics.return_value.home.assert_called_once()
                    gcode.run_script_from_command.assert_called_with('SET_Z_LIMIT')
                    homing.run_G28_two_Z.reset_mock()
                    homing.write_real_zmax.reset_mock()
                    toolhead.get_kinematics.return_value.home.reset_mock()


if __name__ == "__main__":
    unittest.main()
