#!/usr/bin/env python3

import importlib.util
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock


MODULE_PATH = Path(__file__).with_name("prime_tower.py")
START_PRINT_PATH = MODULE_PATH.parent.parent / "macros" / "start_print" / \
    "start_print.cfg"
SPEC = importlib.util.spec_from_file_location("prime_tower", MODULE_PATH)
PRIME_TOWER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PRIME_TOWER)


class PrimeTowerParserTests(unittest.TestCase):
    def parse(self, gcode, padding=0.5):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir, "test.gcode")
            path.write_text(gcode, encoding="utf-8")
            return PRIME_TOWER.parse_prime_tower(str(path), padding)

    def test_no_tower_is_unchanged(self):
        result = self.parse("G90\nG1 X10 Y20\n;TYPE:Outer wall\n")
        self.assertFalse(result["detected"])
        self.assertEqual(result["polygon"], [])

    def test_no_sparse_setting_without_actual_tower_is_not_blocked(self):
        result = self.parse(
            "G90\n;TYPE:Outer wall\nG1 X10 Y20 E1\n"
            "; enable_prime_tower = 0\n"
            "; wipe_tower_no_sparse_layers = 1\n")
        self.assertFalse(result["detected"])

    def test_footer_blocks_before_searching_for_late_marker(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir, "huge-delayed-tower.gcode")
            path.write_text(
                "; enable_prime_tower = 1\n"
                "; wipe_tower_no_sparse_layers = 1\n",
                encoding="utf-8")
            with mock.patch.object(
                    PRIME_TOWER, "_file_contains_prime_tower",
                    side_effect=AssertionError("marker scan must not run")):
                with self.assertRaises(PRIME_TOWER._UnsupportedPrimeTower):
                    PRIME_TOWER.parse_prime_tower(str(path))

    def test_no_sparse_setting_with_actual_tower_is_blocked(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir, "delayed-tower.gcode")
            path.write_bytes(
                b"G90\r\nM83\r\n; TYPE: Prime tower\r\n"
                b"G1 X10 Y20 E1\r\n; WIPE_TOWER_END\r\n"
                b";   wipe_tower_no_sparse_layers = TRUE   \r\n")
            with self.assertRaises(
                    PRIME_TOWER._UnsupportedPrimeTower) as raised:
                PRIME_TOWER.parse_prime_tower(str(path))
        self.assertIn("No sparse layers", str(raised.exception))

    def test_normal_prime_tower_setting_still_parses(self):
        result = self.parse(
            "G90\nM83\nG1 X10 Y20\n;TYPE:Prime tower\n"
            "G1 X20 Y30 E1\n; WIPE_TOWER_END\n"
            "; enable_prime_tower = 1\n"
            "; wipe_tower_no_sparse_layers = 0\n")
        self.assertTrue(result["detected"])
        self.assertEqual(result["bounds"], [9.5, 19.5, 20.5, 30.5])

    def test_no_tower_skips_detailed_text_scan(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir, "large-single-color.gcode")
            path.write_bytes(
                (b"G1 X10 Y20 E1\n;TYPE:Outer wall\n" * 10000)
            )
            real_open = open

            def reject_text_scan(filename, mode="r", *args, **kwargs):
                if "b" not in mode:
                    raise AssertionError("entered detailed G-code parser")
                return real_open(filename, mode, *args, **kwargs)

            with mock.patch.object(PRIME_TOWER, "open", reject_text_scan,
                                   create=True):
                result = PRIME_TOWER.parse_prime_tower(str(path))

        self.assertFalse(result["detected"])
        self.assertEqual(result["blocks"], 0)

    def test_marker_split_across_scan_chunks_is_detected(self):
        prefix = b"X" * (PRIME_TOWER._MARKER_SCAN_CHUNK - 8) + b"\n"
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir, "split-marker.gcode")
            path.write_bytes(prefix + b"; TYPE: Prime tower\r\n")
            self.assertTrue(
                PRIME_TOWER._file_contains_prime_tower(str(path)))

    def test_cancelled_scan_stops_before_parsing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir, "tower.gcode")
            path.write_text(";TYPE:Prime tower\nG1 X10 Y20 E1\n",
                            encoding="utf-8")
            cancel_event = PRIME_TOWER.threading.Event()
            cancel_event.set()
            with self.assertRaises(PRIME_TOWER._ScanCancelled):
                PRIME_TOWER.parse_prime_tower(
                    str(path), cancel_event=cancel_event)

    def test_uses_actual_rotated_and_resized_motion(self):
        result = self.parse("""G90
G1 X125 Y132
;TYPE:Prime tower
G1 X83 Y90 E2.6
G1 X86 Y87 E.2
G1 X128 Y129 E2.6
; WIPE_TOWER_END
G1 X300 Y300
""")
        self.assertTrue(result["detected"])
        self.assertEqual(result["blocks"], 1)
        self.assertEqual(result["bounds"], [82.5, 86.5, 128.5, 132.5])

    def test_relative_xy_and_late_tower_are_supported(self):
        result = self.parse("""G90
G1 X20 Y30
;TYPE:Outer wall
G1 X200 Y200
G91
M83
;TYPE:Prime tower
G1 X10 Y-5 E1
G1 X5 Y20 E1
; WIPE_TOWER_END
""", padding=0)
        self.assertEqual(result["bounds"], [200.0, 195.0, 215.0, 215.0])

    def test_unions_multiple_tower_blocks(self):
        result = self.parse("""G90
M83
G1 X10 Y20
;TYPE:Prime tower
G1 X20 Y30 E1
; WIPE_TOWER_END
G1 X100 Y110
;TYPE:Prime tower
G1 X120 Y130 E1
; WIPE_TOWER_END
""", padding=0)
        self.assertEqual(result["blocks"], 2)
        self.assertEqual(result["bounds"], [10.0, 20.0, 120.0, 130.0])

    def test_g92_updates_modal_xy(self):
        result = self.parse("""G90
M83
G92 X5 Y7
;TYPE:Prime tower
G1 X8 E1
G1 Y12 E1
; WIPE_TOWER_END
""", padding=0)
        self.assertEqual(result["bounds"], [5.0, 7.0, 8.0, 12.0])

    def test_ignores_toolchange_travel_inside_tower_block(self):
        result = self.parse("""G90
M83
G1 X183 Y143
;TYPE:Prime tower
G1 X0 Y245 F30000
G1 X205 Y345 F20000
G1 X183 Y143 F30000
G1 X166 Y143 E1
G1 Y129 E1
; WIPE_TOWER_END
""", padding=0)
        self.assertEqual(result["bounds"], [166.0, 129.0, 183.0, 143.0])


class _FakeReactor:
    def __init__(self):
        self.callbacks = []

    def register_async_callback(self, callback):
        self.callbacks.append(callback)

    def monotonic(self):
        return 1.0

    def pause(self, waketime):
        deadline = time.monotonic() + 1.0
        while not self.callbacks and time.monotonic() < deadline:
            time.sleep(0.001)
        callbacks, self.callbacks = self.callbacks, []
        for callback in callbacks:
            callback(waketime)
        return waketime


class _AdvancingReactor(_FakeReactor):
    def pause(self, waketime):
        return waketime


class _RejectingReactor(_AdvancingReactor):
    def register_async_callback(self, callback):
        raise RuntimeError("reactor is stopping")


class _FakeVirtualSDCard:
    def __init__(self, path):
        self.path = path

    def get_status(self, eventtime):
        return {"file_path": self.path}


class _FakeGCode:
    def __init__(self):
        self.commands = {}
        self.messages = []
        self.scripts = []

    def register_command(self, name, callback, desc=None):
        self.commands[name] = callback

    def respond_info(self, message):
        self.messages.append(message)

    def run_script_from_command(self, script):
        self.scripts.append(script)


class _FakeCommand:
    def __init__(self):
        self.messages = []

    def error(self, message):
        return RuntimeError(message)

    def respond_info(self, message):
        self.messages.append(message)


class _FakePrinter:
    def __init__(self, path, reactor=None):
        self.reactor = reactor or _FakeReactor()
        self.virtual_sdcard = _FakeVirtualSDCard(path)
        self.gcode = _FakeGCode()

    def get_reactor(self):
        return self.reactor

    def lookup_object(self, name, default=None):
        if name == "virtual_sdcard":
            return self.virtual_sdcard
        if name == "gcode":
            return self.gcode
        return default


class _FakeConfig:
    def __init__(self, path, reactor=None, scan_timeout=None):
        self.printer = _FakePrinter(path, reactor)
        self.scan_timeout = scan_timeout

    def get_printer(self):
        return self.printer

    def getfloat(self, name, default, minval=None):
        if name == "scan_timeout" and self.scan_timeout is not None:
            return self.scan_timeout
        return default


class _DeferredThread:
    created = []

    def __init__(self, target, args, name):
        self.target = target
        self.args = args
        self.name = name
        self.daemon = False
        self.__class__.created.append(self)

    def start(self):
        pass


class _ImmediateThread(_DeferredThread):
    def start(self):
        self.target(*self.args)


class _FailingThread(_DeferredThread):
    def start(self):
        raise RuntimeError("thread unavailable")


class PrimeTowerStatusTests(unittest.TestCase):
    def test_start_print_preflight_precedes_printer_preparation(self):
        config = START_PRINT_PATH.read_text(encoding="utf-8")
        start_print = config.split("[gcode_macro START_PRINT]", 1)[1]
        start_print = start_print.split("[gcode_macro", 1)[0]
        self.assertLess(
            start_print.index("PRIME_TOWER_WAIT"),
            start_print.index("BOX_START_PRINT"))

    def test_unsupported_tower_is_ready_and_hard_blocked(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir, "delayed-tower.gcode")
            path.write_text(
                "START_PRINT BED_TEMP=70 CHAMBER_TEMP=0\n"
                "G90\nM83\n;TYPE:Prime tower\nG1 X20 Y30 E1\n"
                "; WIPE_TOWER_END\n"
                "; wipe_tower_no_sparse_layers = 1\n",
                encoding="utf-8")
            scanner = PRIME_TOWER.PrimeTower(_FakeConfig(str(path)))
            result = scanner.wait_for_scan(1.0)

            self.assertTrue(result["ready"])
            self.assertTrue(result["blocked"])
            self.assertFalse(result["detected"])
            self.assertIsNone(result["error"])
            self.assertIn("No sparse layers", result["block_reason"])

            with self.assertRaises(RuntimeError) as raised:
                scanner.cmd_PRIME_TOWER_WAIT(_FakeCommand())

        self.assertIn("No sparse layers", str(raised.exception))
        self.assertEqual(scanner.gcode.scripts[-1], "TURN_OFF_HEATERS")

    def test_scan_reports_status_and_holds_sliced_preheat_targets(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir, "tower.gcode")
            path.write_text(
                "; generated file\n"
                "START_PRINT EXTRUDER_TEMP=245 BED_TEMP=70 "
                "CHAMBER_TEMP=45 MATERIAL=PETG\n"
                "G90\n;TYPE:Prime tower\nG1 X20 Y30 E1\n",
                encoding="utf-8")
            scanner = PRIME_TOWER.PrimeTower(_FakeConfig(str(path)))
            scanner.wait_for_scan(1.0)

        self.assertIn("scanning selected G-code", scanner.gcode.messages[0])
        self.assertEqual(
            scanner.gcode.scripts[0],
            "M104 S140\nM140 S70.000\nM141 S45.000")

    def test_scan_without_start_print_target_leaves_heaters_unchanged(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir, "tower.gcode")
            path.write_text(
                "G90\n;TYPE:Prime tower\nG1 X20 Y30 E1\n",
                encoding="utf-8")
            with mock.patch.object(PRIME_TOWER.logging, "warning"):
                scanner = PRIME_TOWER.PrimeTower(_FakeConfig(str(path)))
                scanner.wait_for_scan(1.0)

        self.assertEqual(scanner.gcode.scripts, [])

    def test_successful_scan_does_not_turn_heaters_off(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir, "tower.gcode")
            path.write_text(
                "START_PRINT BED_TEMP=70 CHAMBER_TEMP=0\n"
                "G90\n;TYPE:Prime tower\nG1 X20 Y30 E1\n",
                encoding="utf-8")
            scanner = PRIME_TOWER.PrimeTower(_FakeConfig(str(path)))
            scanner.wait_for_scan(1.0)

        self.assertNotIn("TURN_OFF_HEATERS", scanner.gcode.scripts)

    def test_status_scan_runs_in_worker_and_cooperative_wait_finishes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir, "tower.gcode")
            path.write_text(
                "G90\nM83\nG1 X10 Y20\n;TYPE:Prime tower\n"
                "G1 X20 Y30 E1\n; WIPE_TOWER_END\n",
                encoding="utf-8")
            scanner = PRIME_TOWER.PrimeTower(_FakeConfig(str(path)))
            initial = scanner.get_status(1.0)
            result = scanner.wait_for_scan(1.0)

        self.assertFalse(initial["ready"])
        self.assertTrue(result["ready"])
        self.assertTrue(result["detected"])
        self.assertEqual(result["bounds"], [9.5, 19.5, 20.5, 30.5])
        self.assertIn("PRIME_TOWER_WAIT", scanner.gcode.commands)

    def test_wait_times_out_and_rejects_late_worker_result(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir, "tower.gcode")
            path.write_text(
                "G90\nM83\nG1 X10 Y20\n;TYPE:Prime tower\n"
                "G1 X20 Y30 E1\n; WIPE_TOWER_END\n",
                encoding="utf-8")
            reactor = _AdvancingReactor()
            _DeferredThread.created = []
            with mock.patch.object(
                    PRIME_TOWER.threading, "Thread", _DeferredThread), \
                    mock.patch.object(PRIME_TOWER.logging, "error"):
                scanner = PRIME_TOWER.PrimeTower(
                    _FakeConfig(str(path), reactor, scan_timeout=0.1))
                result = scanner.wait_for_scan(1.0)

            self.assertTrue(result["ready"])
            self.assertFalse(result["detected"])
            self.assertIn("timed out", result["error"])

            # The parser receives a cooperative cancellation request. Even
            # a misbehaving late job cannot replace the fail-open result.
            worker = _DeferredThread.created[0]
            job = worker.args[0]
            self.assertTrue(job.cancel_event.is_set())
            job.status = {
                "detected": True,
                "polygon": [[0.0, 0.0]],
                "bounds": [0.0, 0.0, 0.0, 0.0],
                "blocks": 1,
            }
            job.done_event.set()
            scanner._finish_scan(2.0, job)
            self.assertIn("timed out", scanner._status["error"])
            self.assertFalse(scanner._status["detected"])

    def test_callback_publication_failure_is_recovered_by_polling(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir, "tower.gcode")
            path.write_text(
                "G90\nM83\nG1 X10 Y20\n;TYPE:Prime tower\n"
                "G1 X20 Y30 E1\n; WIPE_TOWER_END\n",
                encoding="utf-8")
            reactor = _RejectingReactor()
            with mock.patch.object(
                    PRIME_TOWER.threading, "Thread", _ImmediateThread), \
                    mock.patch.object(PRIME_TOWER.logging, "exception"):
                scanner = PRIME_TOWER.PrimeTower(
                    _FakeConfig(str(path), reactor, scan_timeout=0.1))
                result = scanner.wait_for_scan(1.0)

        self.assertTrue(result["ready"])
        self.assertTrue(result["detected"])
        self.assertIsNone(result["error"])
        self.assertEqual(result["bounds"], [9.5, 19.5, 20.5, 30.5])

    def test_new_selection_cancels_old_job_and_gets_full_timeout(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            first_path = Path(temp_dir, "first.gcode")
            second_path = Path(temp_dir, "second.gcode")
            first_path.write_text("G90\n", encoding="utf-8")
            second_path.write_text(
                "G90\nM83\nG1 X10 Y20\n;TYPE:Prime tower\n"
                "G1 X20 Y30 E1\n; WIPE_TOWER_END\n",
                encoding="utf-8")
            reactor = _AdvancingReactor()
            _DeferredThread.created = []
            with mock.patch.object(
                    PRIME_TOWER.threading, "Thread", _DeferredThread):
                scanner = PRIME_TOWER.PrimeTower(
                    _FakeConfig(
                        str(first_path), reactor, scan_timeout=10.0))
                scanner.get_status(1.0)
                first_job = scanner._active_job
                scanner.printer.virtual_sdcard.path = str(second_path)
                scanner.get_status(9.0)
                second_job = scanner._active_job

            self.assertTrue(first_job.cancel_event.is_set())
            self.assertIsNot(first_job, second_job)
            self.assertEqual(second_job.started_at, 9.0)
            self.assertEqual(second_job.deadline, 19.0)

            second_worker = _DeferredThread.created[1]
            second_worker.target(*second_worker.args)
            for callback in reactor.callbacks:
                callback(9.1)
            result = scanner.get_status(9.1)
            self.assertTrue(result["detected"])
            self.assertIsNone(result["error"])

    def test_worker_start_failure_fails_open_without_waiting(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir, "tower.gcode")
            path.write_text(";TYPE:Prime tower\nG1 X10 Y20 E1\n",
                            encoding="utf-8")
            with mock.patch.object(
                    PRIME_TOWER.threading, "Thread", _FailingThread), \
                    mock.patch.object(PRIME_TOWER.logging, "exception"):
                scanner = PRIME_TOWER.PrimeTower(_FakeConfig(str(path)))
                result = scanner.wait_for_scan(1.0)

        self.assertTrue(result["ready"])
        self.assertFalse(result["detected"])
        self.assertIn("unable to start scan worker", result["error"])


if __name__ == "__main__":
    unittest.main()
