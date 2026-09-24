"""Regression tests for the K2 Cartographer SAFE_MOVE_Z compatibility."""

import importlib.util
import pathlib
import unittest


MODULE_PATH = pathlib.Path(__file__).with_name("k2_safe_move_z.py")
SPEC = importlib.util.spec_from_file_location("k2_safe_move_z", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class FakeReactor:
    def monotonic(self):
        return 1.0


class FakeToolhead:
    def __init__(self, z, recorded_z):
        self.position = [225.0, 345.0, z, 0.0]
        self.z_pos = recorded_z
        self.moves = []
        self.wait_count = 0

    def get_status(self, eventtime):
        del eventtime
        return {"homed_axes": "xyz"}

    def get_position(self):
        return self.position[:]

    def move(self, target, speed):
        self.moves.append((target[:], speed))
        self.position = target[:]

    def manual_move(self, coordinates, speed):
        target = self.position[:]
        for axis, coordinate in enumerate(coordinates):
            if coordinate is not None:
                target[axis] = coordinate
        self.move(target, speed)

    def wait_moves(self):
        self.wait_count += 1


class FakeVirtualSD:
    def __init__(self):
        self.run_dis = 99.0


class FakePrinter:
    def __init__(self, toolhead, virtual_sd):
        self.toolhead = toolhead
        self.virtual_sd = virtual_sd

    def get_reactor(self):
        return FakeReactor()

    def lookup_object(self, name, default=None):
        objects = {
            "toolhead": self.toolhead,
            "virtual_sdcard": self.virtual_sd,
        }
        return objects.get(name, default)


class FakeGcmd:
    def __init__(self, distance, speed=6.0):
        self.values = {"STA": 1, "DIS": distance, "SPD": speed}
        self.responses = []

    def get_int(self, name, default=None):
        return int(self.values.get(name, default))

    def get_float(self, name, default=None):
        return float(self.values.get(name, default))

    def error(self, message):
        return RuntimeError(message)

    def respond_info(self, message):
        self.responses.append(message)


class SafeMoveClassificationTests(unittest.TestCase):
    def setUp(self):
        self.safe_move = object.__new__(MODULE.K2SafeMoveZ)
        self.safe_move.position_max = 360.0

    def test_normal_between_print_move_is_not_artificial(self):
        self.assertFalse(self.safe_move._is_artificial_z_reference(
            173.013, 20.0, 173.013))

    def test_tall_but_genuinely_recorded_move_is_not_artificial(self):
        self.assertFalse(self.safe_move._is_artificial_z_reference(
            360.0, 20.0, 358.0))

    def test_post_zdown_set_position_is_artificial(self):
        self.assertTrue(self.safe_move._is_artificial_z_reference(
            360.0, 20.0, 338.425))

    def test_missing_recorded_position_is_not_assumed_artificial(self):
        self.assertFalse(self.safe_move._is_artificial_z_reference(
            360.0, 20.0, None))


class GuardedMoveOutcomeTests(unittest.TestCase):
    def setUp(self):
        self.safe_move = object.__new__(MODULE.K2SafeMoveZ)
        self.safe_move.position_max = 360.0

    def test_artificial_move_stops_at_clearance_target(self):
        start_z = 360.0
        requested_target = 20.0
        recorded_z = 338.425
        backup_target = max(
            requested_target,
            self.safe_move.ARTIFICIAL_CLEARANCE_TARGET,
            start_z - max(
                0.0,
                recorded_z - self.safe_move.ARTIFICIAL_BACKUP_CLEARANCE))
        self.assertAlmostEqual(backup_target, 30.0)

    def test_normal_move_keeps_requested_endpoint(self):
        start_z = 173.013
        requested_target = 20.0
        recorded_z = 173.013
        artificial = self.safe_move._is_artificial_z_reference(
            start_z, requested_target, recorded_z)
        guarded_target = requested_target
        if artificial:
            guarded_target = max(
                requested_target,
                self.safe_move.ARTIFICIAL_CLEARANCE_TARGET,
                start_z - max(
                    0.0,
                    recorded_z - self.safe_move.ARTIFICIAL_BACKUP_CLEARANCE))
        self.assertEqual(guarded_target, requested_target)


class McuCompatibilityTests(unittest.TestCase):
    class HostMcu:
        def __init__(self, disconnected=False):
            self.non_critical_disconnected = disconnected

    class CurrentMcu:
        def __init__(self, disconnected=False):
            self.host_mcu = McuCompatibilityTests.HostMcu()
            self.disconnected = disconnected

        def is_disconnected(self):
            return self.disconnected

    class LegacyMcu:
        def __init__(self, disconnected=False):
            self.klipper_mcu = McuCompatibilityTests.HostMcu(disconnected)

    class HostMcuFallback:
        def __init__(self, disconnected=False):
            self.host_mcu = McuCompatibilityTests.HostMcu(disconnected)

    def test_current_mcu_api_accepts_connected_sensor(self):
        mcu = self.CurrentMcu(False)
        self.assertFalse(MODULE.K2SafeMoveZ._is_mcu_disconnected(mcu))

    def test_current_mcu_api_rejects_disconnected_sensor(self):
        mcu = self.CurrentMcu(True)
        self.assertTrue(MODULE.K2SafeMoveZ._is_mcu_disconnected(mcu))

    def test_legacy_mcu_api_remains_supported(self):
        self.assertFalse(MODULE.K2SafeMoveZ._is_mcu_disconnected(
            self.LegacyMcu(False)))
        self.assertTrue(MODULE.K2SafeMoveZ._is_mcu_disconnected(
            self.LegacyMcu(True)))

    def test_host_mcu_fallback_is_supported(self):
        self.assertFalse(MODULE.K2SafeMoveZ._is_mcu_disconnected(
            self.HostMcuFallback(False)))
        self.assertTrue(MODULE.K2SafeMoveZ._is_mcu_disconnected(
            self.HostMcuFallback(True)))

    def test_missing_or_unknown_mcu_fails_closed(self):
        self.assertTrue(MODULE.K2SafeMoveZ._is_mcu_disconnected(None))
        self.assertTrue(MODULE.K2SafeMoveZ._is_mcu_disconnected(object()))


class SafeMoveCommandTests(unittest.TestCase):
    def make_safe_move(self, start_z, recorded_z, stopped_z, triggered):
        toolhead = FakeToolhead(start_z, recorded_z)
        virtual_sd = FakeVirtualSD()
        safe_move = object.__new__(MODULE.K2SafeMoveZ)
        safe_move.position_min = -10.0
        safe_move.position_max = 360.0
        safe_move.max_z_velocity = 30.0
        safe_move.printer = FakePrinter(toolhead, virtual_sd)
        safe_move._require_idle = lambda gcmd: None

        def guarded_move(gcmd, active_toolhead, target_z, speed):
            del gcmd, target_z, speed
            active_toolhead.position[2] = stopped_z
            return stopped_z, triggered

        safe_move._guarded_move = guarded_move
        return safe_move, virtual_sd, toolhead

    def test_normal_move_reaches_z20_and_reports_completion(self):
        safe_move, virtual_sd, toolhead = self.make_safe_move(
            173.013, 173.013, 20.0, False)
        safe_move.cmd_SAFE_MOVE_Z(FakeGcmd(-153.013))
        self.assertAlmostEqual(virtual_sd.run_dis, -153.013)
        self.assertEqual(toolhead.moves, [])

    def test_normal_move_rejects_unexpected_cartographer_trigger(self):
        safe_move, virtual_sd, toolhead = self.make_safe_move(
            173.013, 173.013, 42.0, True)
        with self.assertRaisesRegex(RuntimeError, "unexpectedly"):
            safe_move.cmd_SAFE_MOVE_Z(FakeGcmd(-153.013))
        self.assertEqual(virtual_sd.run_dis, 0.0)
        self.assertEqual(toolhead.moves, [])

    def test_artificial_move_accepts_cartographer_trigger(self):
        safe_move, virtual_sd, toolhead = self.make_safe_move(
            360.0, 338.425, 42.0, True)
        gcmd = FakeGcmd(-340.0)
        safe_move.cmd_SAFE_MOVE_Z(gcmd)
        self.assertEqual(toolhead.moves, [([225.0, 345.0, 52.0, 0.0], 6.0)])
        self.assertEqual(toolhead.wait_count, 1)
        self.assertAlmostEqual(virtual_sd.run_dis, -340.0)
        self.assertTrue(any("retreated 10.000mm" in r for r in gcmd.responses))
        self.assertTrue(any("10mm retreat" in r for r in gcmd.responses))

    def test_artificial_move_stops_at_z30_without_unneeded_retreat(self):
        safe_move, virtual_sd, toolhead = self.make_safe_move(
            360.0, 338.425, 30.0, False)
        gcmd = FakeGcmd(-340.0)
        safe_move.cmd_SAFE_MOVE_Z(gcmd)
        self.assertEqual(toolhead.moves, [])
        self.assertEqual(toolhead.wait_count, 0)
        self.assertAlmostEqual(virtual_sd.run_dis, -340.0)
        self.assertTrue(any(
            "guarded clearance stop; no Cartographer trigger" in response
            for response in gcmd.responses))
        self.assertTrue(any(
            "actual travel=-330.000" in response
            for response in gcmd.responses))


if __name__ == "__main__":
    unittest.main()
