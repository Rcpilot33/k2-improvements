#!/usr/bin/env python3

import importlib.util
import pathlib
import unittest
from collections import namedtuple


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
        if handler is None:
            return self.commands.pop(name, None)
        self.commands[name] = handler

    def run_script_from_command(self, script):
        self.scripts.append(script)

    def respond_info(self, message):
        self.messages.append(message)


class FakeToolhead:
    def __init__(self):
        self.recalculated = 0
        self.kin = FakeKinematics()
        self.position = [175., 175., 3., 0.]
        self.moves = []
        self.waits = 0

    def get_kinematics(self):
        return self.kin

    def wait_moves(self):
        self.waits += 1

    def get_position(self):
        return self.position

    def manual_move(self, coords, speed):
        self.moves.append((coords, speed))
        self.position[1] = coords[1]

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

    config_error = ValueError


class FakeConfig:
    def __init__(self, profile="none", travel=0., offset=12., x=0.):
        self.printer = FakePrinter()
        self.values = {"mount_profile": profile, "mesh_front_travel": travel,
                       "y_offset": offset, "x_offset": x}

    def get_printer(self):
        return self.printer

    def get(self, name, default=None):
        return self.values.get(name, default)

    def getfloat(self, name, default=None, minval=None, maxval=None):
        value = float(self.values.get(name, default))
        if (minval is not None and value < minval) or (maxval is not None and value > maxval):
            raise ValueError(name)
        return value

    def getsection(self, _name):
        return self

    error = ValueError


class FakeCommand:
    def __init__(self, active=0, method="scan"):
        self.active = active
        self.method = method
        self.messages = []

    def get_int(self, _name, minval=None, maxval=None):
        return self.active

    def get(self, _name, default=None):
        return self.method

    def respond_info(self, message):
        self.messages.append(message)

    error = ValueError


Coord = namedtuple("Coord", "x y z e")


class FakeRail:
    def get_range(self):
        return (-6.2, 400.)


class FakeKinematics:
    def __init__(self):
        self.limits = [(0., 350.), (0., 350.), (-5., 350.)]
        self.axes_min = Coord(0., -6.2, -5., 0.)
        self.rails = [FakeRail(), FakeRail(), FakeRail()]
        self.native_updates = []

    def set_limits(self, x_min, x_max, y_min, y_max):
        self.limits[0] = (x_min, x_max)
        self.limits[1] = (y_min, y_max)
        self.native_updates.append(tuple(self.limits))


class ScanLimitGuardTests(unittest.TestCase):
    def enabled(self, handler=None):
        config = FakeConfig("jimmyv_final_12", 6.)
        guard = MODULE.K2CartographerScanGuard(config)
        config.printer.gcode.commands["BED_MESH_CALIBRATE_ORIG"] = handler or (lambda gcmd: None)
        guard._install_mesh_hook()
        return config.printer.toolhead, guard

    def test_opt_in_and_exact_jimmyv_offsets_required(self):
        for profile, offset in MODULE.K2CartographerScanGuard.MOUNT_OFFSETS.items():
            guard = MODULE.K2CartographerScanGuard(FakeConfig(profile, 6., offset))
            self.assertEqual(guard.front_travel, 6.)
        for config in (FakeConfig("none", 6.), FakeConfig("custom", 6.),
                       FakeConfig("jimmyv_final_12", 6., 17.),
                       FakeConfig("jimmyv_final_12", 6., 12., 1.),
                       FakeConfig("jimmyv_final_12", 7.),
                       FakeConfig("jimmyv_final_12", 1.)):
            with self.assertRaises(ValueError):
                MODULE.K2CartographerScanGuard(config)

    def test_disabled_has_no_hook_and_cannot_open_front(self):
        config = FakeConfig()
        guard = MODULE.K2CartographerScanGuard(config)
        guard._install_mesh_hook()
        self.assertIsNone(guard._mesh_handler)
        self.assertEqual(config.printer.toolhead.kin.native_updates, [])

    def test_success_opens_only_mesh_and_exits_before_restoring_exact_limits(self):
        toolhead, guard = self.enabled()
        kin = toolhead.kin
        old_limits = list(kin.limits)
        old_min = kin.axes_min
        def mesh(gcmd):
            self.assertEqual(kin.limits[1], (-6., 350.))
            self.assertEqual(kin.axes_min.y, -6.)
            self.assertTrue(guard.front_active)
            toolhead.position[1] = -6.
            return "mesh-saved"
        guard._mesh_handler = mesh
        self.assertEqual(guard._run_mesh(FakeCommand()), "mesh-saved")
        self.assertEqual(kin.limits, old_limits)
        self.assertEqual(kin.axes_min, old_min)
        self.assertEqual(toolhead.moves, [([None, 0., None], 50.)])
        self.assertEqual(toolhead.position, [175., 0., 3., 0.])
        self.assertFalse(guard.front_active)
        self.assertEqual(kin.native_updates[-1], tuple(old_limits))
        self.assertEqual(guard.get_status(None)['y_limits'], [0., 350.])

    def test_errors_disconnect_cancel_and_shutdown_restore_without_recovery_move(self):
        for error in (RuntimeError("scan failed"), ValueError("disconnected"),
                      KeyboardInterrupt("cancelled"), SystemExit("shutdown")):
            with self.subTest(error=error):
                toolhead, guard = self.enabled()
                old_limits = list(toolhead.kin.limits)
                def mesh(gcmd):
                    toolhead.position[1] = -6.
                    raise error
                guard._mesh_handler = mesh
                with self.assertRaises(type(error)):
                    guard._run_mesh(FakeCommand())
                self.assertEqual(toolhead.kin.limits, old_limits)
                self.assertEqual(toolhead.moves, [])
                self.assertFalse(guard.front_active)

    def test_motor_off_does_not_rehome_axes_in_cleanup(self):
        toolhead, guard = self.enabled()
        def mesh(gcmd):
            toolhead.kin.limits = [(1., -1.)] * 3
            raise RuntimeError("motor off")
        guard._mesh_handler = mesh
        with self.assertRaises(RuntimeError):
            guard._run_mesh(FakeCommand())
        self.assertEqual(toolhead.kin.limits, [(1., -1.)] * 3)

    def test_touch_fallback_never_gets_expanded_limits(self):
        toolhead, guard = self.enabled()
        guard._run_mesh(FakeCommand(method="touch"))
        self.assertEqual(toolhead.kin.native_updates, [])

    def test_unhomed_or_inadequate_physical_range_blocks_before_motion(self):
        for invalid in ("unhomed", "range", "setter"):
            with self.subTest(invalid=invalid):
                toolhead, guard = self.enabled()
                if invalid == "unhomed":
                    toolhead.kin.limits[1] = (1., -1.)
                elif invalid == "range":
                    toolhead.kin.rails[1].get_range = lambda: (-0.4, 400.)
                else:
                    toolhead.kin.set_limits = None
                with self.assertRaises(ValueError):
                    guard._run_mesh(FakeCommand())
                self.assertEqual(toolhead.moves, [])
                self.assertEqual(toolhead.kin.native_updates, [])

    def test_nondefault_limits_and_z_are_preserved(self):
        toolhead, guard = self.enabled()
        toolhead.kin.limits = [(5., 340.), (0., 345.), (-10., 330.)]
        captured = list(toolhead.kin.limits)
        guard._run_mesh(FakeCommand())
        self.assertEqual(toolhead.kin.native_updates[0],
                         ((5., 340.), (-6., 345.), (-10., 330.)))
        self.assertEqual(toolhead.kin.limits, captured)

    def test_exit_failure_still_closes_boundary(self):
        toolhead, guard = self.enabled()
        guard._mesh_handler = lambda gcmd: toolhead.position.__setitem__(1, -6.)
        def fail_exit(coords, speed):
            raise RuntimeError('exit failed')
        toolhead.manual_move = fail_exit
        with self.assertRaisesRegex(RuntimeError, 'exit failed'):
            guard._run_mesh(FakeCommand())
        self.assertEqual(toolhead.kin.limits[1], (0., 350.))
        self.assertFalse(guard.front_active)

    def test_manual_adaptive_and_if_needed_meshes_share_managed_entry(self):
        root = MODULE_PATH.resolve().parents[2]
        wrapper = (MODULE_PATH.parent / 'cartographer.cfg').read_text()
        self.assertIn('rename_existing: BED_MESH_CALIBRATE_ORIG', wrapper)
        self.assertIn('BED_MESH_CALIBRATE_ORIG {rawparams}', wrapper)
        self.assertIn('BED_MESH_CALIBRATE PROFILE={PROFILE_NAME}',
                      (root / 'features/macros/bed_mesh/bed_mesh.cfg').read_text())
        self.assertIn('BED_MESH_CALIBRATE PROFILE=adaptive ADAPTIVE=1',
                      (root / 'features/macros/start_print/start_print.cfg').read_text())

    def test_hook_is_idempotent_and_missing_managed_macro_is_rejected(self):
        toolhead, guard = self.enabled()
        handler = guard._mesh_handler
        guard._install_mesh_hook()
        self.assertIs(guard._mesh_handler, handler)
        guard = MODULE.K2CartographerScanGuard(FakeConfig("jimmyv_final_12", 6.))
        with self.assertRaises(ValueError):
            guard._install_mesh_hook()

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
