"""Hardware-free regressions for native mesh sample-boundary cancellation."""

import unittest

from test_fast_stop import MODULE, FakeConfig, FakePrinter, FakeTemplate, SupportedGCode


class CancelError(Exception):
    pass


class MeshGCode(SupportedGCode):
    cancel_error = CancelError

    def __init__(self):
        super().__init__()
        self.commands = {}
        self.scripts = []

    def register_command(self, name, handler, **kwargs):
        original = self.commands.pop(name, None)
        if handler is not None:
            self.commands[name] = handler
        return original

    def run_script_from_command(self, script):
        # Native cancellation cleanup deliberately uses the non-cancelable
        # command path to restore limits while cancel_pending is still set.
        self.scripts.append(script)


class Toolhead:
    square_corner_velocity = 7.

    def __init__(self):
        self.kin = self
        self.z_velocity, self.z_accel = 18., 400.
        self.waits = 0

    def get_max_accel(self): return 3500.
    def get_max_accel_to_decel(self): return 1750.
    def get_max_velocity_only(self): return 240.
    def get_max_z_velocity(self): return self.z_velocity
    def get_max_z_accel(self): return self.z_accel
    def set_max_z_velocity(self, value): self.z_velocity = value
    def set_max_z_accel(self, value): self.z_accel = value
    def wait_moves(self): self.waits += 1


class Native:
    def __init__(self):
        self.isCalibrateFlg = False
        self.g29_stat = False
        self.disturbance = []

    def disturb_ctl(self, value):
        self.disturbance.append(value)


class Probe:
    def __init__(self, native, gcode):
        self.mcu_probe, self.gcode = native, gcode
        self.calls, self.ends = [], 0
        self.cancel_after = None
        self.multi_probe_pending = False

    def run_probe(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        # Simulate Cancel arriving while a synchronous probe is executing.
        # The original sample must return normally before the guard unwinds.
        if len(self.calls) == self.cancel_after:
            self.gcode.cancel_pending = True
        return [20., 20., .01]

    def multi_probe_end(self):
        self.ends += 1
        self.multi_probe_pending = False
        self.mcu_probe.g29_stat = False


class Command:
    def __init__(self): self.messages = []
    def respond_info(self, message): self.messages.append(message)


class PRTouchMeshCancelTests(unittest.TestCase):
    def setUp(self):
        self.gcode, self.native, self.toolhead = MeshGCode(), Native(), Toolhead()
        self.probe = Probe(self.native, self.gcode)
        start = type("Macro", (), {"template": FakeTemplate()})()
        self.printer = FakePrinter(self.gcode, start)
        self.printer.objects.update({"prtouch_v3": self.native, "probe": self.probe,
                                     "toolhead": self.toolhead})
        self.shutdowns = []
        self.printer.invoke_shutdown = self.shutdowns.append
        self.helper = MODULE.K2StartPrintFastStop(FakeConfig(self.printer))
        self.helper.active = True
        self.guard = MODULE.PRTouchMeshCancel(self.helper)
        self.finalized = False
        self.profiles = {"existing": "untouched"}
        self.command = Command()
        self.gcode.commands["BED_MESH_CALIBRATE"] = self.native_mesh

    def native_mesh(self, gcmd):
        self.native.isCalibrateFlg = self.native.g29_stat = True
        self.native.disturb_ctl(True)
        self.toolhead.z_velocity, self.toolhead.z_accel = 5., 200.
        self.probe.multi_probe_pending = True
        for _ in range(9):
            self.probe.run_probe(gcmd, sample="original")
        self.finalized = True
        self.profiles["candidate"] = "complete"
        self.probe.multi_probe_end()
        self.native.isCalibrateFlg = False
        return "native result"

    def test_cancel_after_third_complete_sample_unwinds_without_partial_profile(self):
        self.guard.install()
        self.probe.cancel_after = 3
        with self.assertRaises(CancelError):
            self.gcode.commands["BED_MESH_CALIBRATE"](self.command)
        self.assertEqual(len(self.probe.calls), 3)
        self.assertFalse(self.finalized)
        self.assertEqual(self.profiles, {"existing": "untouched"})
        self.assertFalse(self.probe.multi_probe_pending)
        self.assertFalse(self.native.g29_stat)
        self.assertFalse(self.native.isCalibrateFlg)
        self.assertEqual(self.native.disturbance, [True, False])
        self.assertEqual((self.toolhead.z_velocity, self.toolhead.z_accel), (18., 400.))
        self.assertEqual(self.toolhead.waits, 1)
        self.assertEqual(self.guard.mesh_depth, 0)
        self.assertEqual(self.gcode.scripts, [
            "SET_VELOCITY_LIMIT ACCEL=3500.000000000 ACCEL_TO_DECEL=1750.000000000 "
            "VELOCITY=240.000000000 SQUARE_CORNER_VELOCITY=7.000000000"
        ])
        self.assertIn("partial mesh not saved", self.command.messages[0])
        self.assertEqual(self.shutdowns, [])

    def test_cancel_during_last_sample_does_not_finalize(self):
        self.guard.install()
        self.probe.cancel_after = 9
        with self.assertRaises(CancelError): self.guard.cmd_mesh(self.command)
        self.assertEqual(len(self.probe.calls), 9)
        self.assertFalse(self.finalized)
        self.assertNotIn("candidate", self.profiles)

    def test_cancel_before_command_does_not_touch_probe_or_existing_mesh(self):
        self.guard.install()
        self.gcode.cancel_pending = True
        with self.assertRaises(CancelError): self.guard.cmd_mesh(self.command)
        self.assertEqual(self.probe.calls, [])
        self.assertEqual(self.probe.ends, 0)
        self.assertEqual(self.native.disturbance, [])
        self.assertEqual(self.gcode.scripts, [])
        self.assertEqual(self.profiles, {"existing": "untouched"})

    def test_success_delegates_native_mesh_and_preserves_arguments_and_result(self):
        self.guard.install()
        self.assertEqual(self.guard.cmd_mesh(self.command), "native result")
        self.assertEqual(len(self.probe.calls), 9)
        self.assertEqual(self.probe.calls[0], ((self.command,), {"sample": "original"}))
        self.assertTrue(self.finalized)
        self.assertEqual(self.gcode.scripts, [])
        self.assertEqual(self.guard.mesh_depth, 0)

    def test_pending_cancel_does_not_change_homing_tilt_or_standalone_probe(self):
        self.guard.install()
        self.gcode.cancel_pending = True
        self.assertEqual(self.probe.run_probe("standalone", speed=5), [20., 20., .01])
        self.assertEqual(len(self.probe.calls), 1)
        self.assertEqual(self.probe.ends, 0)

    def test_next_mesh_works_after_native_cancel_handoff_clears_flag(self):
        self.guard.install()
        self.probe.cancel_after = 3
        with self.assertRaises(CancelError): self.guard.cmd_mesh(self.command)
        self.gcode.cancel_pending = False
        self.probe.cancel_after = None
        self.assertEqual(self.guard.cmd_mesh(self.command), "native result")
        self.assertTrue(self.finalized)
        self.assertFalse(self.native.isCalibrateFlg)

    def test_other_errors_propagate_without_being_labeled_cancellation(self):
        def fail(gcmd): raise ValueError("native failure")
        self.gcode.commands["BED_MESH_CALIBRATE"] = fail
        self.guard.install()
        with self.assertRaisesRegex(ValueError, "native failure"):
            self.guard.cmd_mesh(self.command)
        self.assertEqual(self.guard.mesh_depth, 0)
        self.assertEqual(self.probe.ends, 0)
        self.assertEqual(self.gcode.scripts, [])

    def test_failed_cleanup_requests_shutdown_instead_of_silent_handoff(self):
        def fail(): raise RuntimeError("cleanup failed")
        self.probe.multi_probe_end = fail
        self.guard.install()
        self.probe.cancel_after = 1
        with self.assertLogs(level="ERROR"):
            with self.assertRaisesRegex(RuntimeError, "cleanup failed"):
                self.guard.cmd_mesh(self.command)
        self.assertEqual(self.shutdowns, ["PR Touch mesh cancellation cleanup failed"])
        self.assertFalse(self.finalized)
        self.assertEqual(self.guard.mesh_depth, 0)

    def test_unsupported_probe_and_limits_are_not_modified(self):
        for missing in ("probe_identity", "cancel_api", "limits_api", "calibration_flag"):
            with self.subTest(missing=missing):
                self.setUp()
                if missing == "probe_identity": self.probe.mcu_probe = object()
                elif missing == "cancel_api": self.gcode.cancel_error = None
                elif missing == "limits_api": self.toolhead.get_max_accel = None
                else: del self.native.isCalibrateFlg
                original_probe, original_mesh = self.probe.run_probe, self.native_mesh
                with self.assertLogs(level="WARNING"): self.guard.install()
                self.assertFalse(self.guard.installed)
                self.assertEqual(self.probe.run_probe, original_probe)
                self.assertEqual(self.gcode.commands["BED_MESH_CALIBRATE"], original_mesh)

    def test_missing_mesh_command_leaves_probe_unchanged(self):
        self.gcode.commands.clear()
        original_probe = self.probe.run_probe
        with self.assertLogs(level="WARNING"): self.guard.install()
        self.assertFalse(self.guard.installed)
        self.assertEqual(self.probe.run_probe, original_probe)

    def test_helper_activates_and_reports_guard_only_on_native_probe_path(self):
        for cartographer in (False, True):
            with self.subTest(cartographer=cartographer):
                self.setUp()
                self.helper.active = False
                if cartographer: self.printer.objects["cartographer"] = object()
                self.helper._handle_ready()
                self.assertEqual(self.helper.get_status(0)["stock_mesh_cancel"], not cartographer)


if __name__ == "__main__":
    unittest.main()
