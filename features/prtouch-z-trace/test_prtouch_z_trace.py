"""Hardware-free checks for passive tracing and narrowly scoped installation."""

import importlib.util
import json
import pathlib
import sys
import tempfile
import types
import unittest
from unittest.mock import patch


HERE = pathlib.Path(__file__).resolve().parent


def load(name):
    spec = importlib.util.spec_from_file_location(name, HERE / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


trace = load("k2_prtouch_z_trace")
configure = load("configure")


class GCode:
    def __init__(self):
        self.handlers = {}

    def register_command(self, name, handler, desc=None):
        if handler is None:
            return self.handlers.pop(name, None)
        self.handlers[name] = handler


class ConfigFile:
    def __init__(self):
        self.status = {"config": {"prtouch_v3": {"z_offset": "0.120"}},
                       "save_config_pending_items": {}, "save_config_pending": False}
        self.calls = []

    def get_status(self, eventtime):
        return self.status

    def set(self, section, option, value):
        self.calls.append((section, option, value))
        self.status["save_config_pending_items"].setdefault(section, {})[option] = str(value)
        self.status["save_config_pending"] = True
        return "set-result"

    def remove_section(self, section):
        self.calls.append(("remove", section))
        return "remove-result"


class Command:
    def __init__(self, **params):
        self.params = params
        self.responses = []

    def get_command_parameters(self):
        return self.params

    def get(self, key, default):
        return self.params.get(key, default)

    def respond_info(self, message):
        self.responses.append(message)


class TraceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = pathlib.Path(self.temp.name)
        (self.root / "config").mkdir()
        self.cfg = self.root / "config" / "printer.cfg"
        self.cfg.write_text("[prtouch_v3]\n#z_offset: 0\n#*# [prtouch_v3]\n#*# z_offset = 0.120\n")
        self.configfile = ConfigFile()
        self.gcode = GCode()
        self.origin = [0, 0, .02, 0]
        self.probe = types.SimpleNamespace(
            name="prtouch_v3", z_offset=.12, z_offset_calibrate=0.,
            z_offset_change_flag=False,
            get_status=lambda eventtime: {"z_offset": .12})
        self.reactor = types.SimpleNamespace(monotonic=lambda: 10., NEVER=999999.,
                                             register_timer=lambda *args: None)
        self.objects = {"gcode": self.gcode, "configfile": self.configfile,
                        "probe": self.probe, "prtouch_v3": types.SimpleNamespace(z_offset=.12),
                        "gcode_move": types.SimpleNamespace(get_status=lambda t: {"homing_origin": self.origin}),
                        "print_stats": types.SimpleNamespace(get_status=lambda t: {"state": "standby"})}
        self.events = {}
        self.printer = types.SimpleNamespace(
            lookup_object=lambda key, default=None: self.objects.get(key, default),
            get_start_args=lambda: {"config_file": str(self.cfg)},
            get_reactor=lambda: self.reactor,
            register_event_handler=lambda key, fn: self.events.setdefault(key, fn))
        self.config = types.SimpleNamespace(
            get_printer=lambda: self.printer,
            get=lambda key, default: str(self.root / "trace.log"),
            getfloat=lambda key, default, **kwargs: default)
        self.helper = trace.load_config(self.config)
        self.addCleanup(self.helper._disconnect)

    def records(self):
        path = pathlib.Path(self.helper.log_path)
        return [json.loads(line) for line in path.read_text().splitlines()]

    def test_distinguishes_loaded_live_pending_and_saved(self):
        self.helper._ready()
        self.assertEqual(self.configfile.set("prtouch_v3", "z_offset", 0), "set-result")
        record = self.records()[-1]
        state = record["state"]
        self.assertEqual(record["event"], "config_set_after")
        self.assertEqual(state["pending_save_offset"], "0")
        self.assertEqual(state["loaded_config_offset"], "0.120")
        self.assertEqual(state["probe_loaded_offset"], .12)
        self.assertEqual(state["homing_origin_z"], .02)
        self.assertEqual(state["file"]["entries"]["save_config"], ["0.120"])
        before = self.records()[-2]
        self.assertEqual(before["requested_value"], "0")
        self.assertTrue(any("test_distinguishes" in s for s in before["caller_stack"]))
        self.assertEqual(self.configfile.calls, [("prtouch_v3", "z_offset", 0)])

    def test_original_command_called_once_with_same_object_and_return(self):
        cmd = Command(Z_ADJUST="0.02")
        seen = []
        value = object()
        self.gcode.handlers["SET_GCODE_OFFSET"] = lambda gcmd: seen.append(gcmd) or value
        self.helper._ready()
        result = self.gcode.handlers["SET_GCODE_OFFSET"](cmd)
        self.assertIs(result, value)
        self.assertEqual(seen, [cmd])
        self.assertEqual([r["event"] for r in self.records()],
                         ["ready", "command_before", "command_after"])
        self.assertEqual(self.helper.command_stack, [])

    def test_native_exception_preserved_and_stack_unwinds(self):
        error = RuntimeError("native error")
        def original(gcmd):
            raise error
        self.gcode.handlers["G28"] = original
        self.helper._ready()
        with self.assertRaises(RuntimeError) as caught:
            self.gcode.handlers["G28"](Command())
        self.assertIs(caught.exception, error)
        self.assertEqual(self.helper.command_stack, [])
        self.assertEqual(self.records()[-1]["event"], "command_error")

    def test_config_writer_error_is_not_masked(self):
        error = RuntimeError("writer error")
        self.helper.original_set = lambda *args: (_ for _ in ()).throw(error)
        with self.assertRaises(RuntimeError) as caught:
            self.configfile.set("prtouch_v3", "z_offset", .15)
        self.assertIs(caught.exception, error)

    def test_observation_errors_do_not_stop_native_calls(self):
        self.helper._writer_details = lambda: (_ for _ in ()).throw(OSError("stack unavailable"))
        self.helper._state = lambda *args: (_ for _ in ()).throw(RuntimeError("read failed"))
        self.assertEqual(self.configfile.set("prtouch_v3", "z_offset", .15), "set-result")
        seen = []
        cmd = types.SimpleNamespace(get_command_parameters=lambda: (_ for _ in ()).throw(ValueError()))
        self.helper._command("G28", lambda gcmd: seen.append(gcmd))(cmd)
        self.assertEqual(seen, [cmd])

    def test_log_open_error_does_not_stop_native_calls(self):
        self.helper.log_path = str(self.root)  # directory, not a writable log file
        self.assertEqual(self.configfile.set("prtouch_v3", "z_offset", .15), "set-result")
        self.assertIsNotNone(self.helper.log_error)

    def test_log_write_error_is_reported_without_stopping_native_calls(self):
        self.helper._ready()
        with patch.object(self.helper.handler, "shouldRollover", side_effect=OSError("disk full")):
            self.assertEqual(self.configfile.set("prtouch_v3", "z_offset", .15), "set-result")
        self.assertIn("disk full", self.helper.log_error)

    def test_log_rotation_is_bounded(self):
        self.helper._ready()
        for index in range(5):
            self.helper._emit("rotation_test", payload="x" * 600000)
        files = list(pathlib.Path(self.helper.log_path).parent.glob("prtouch-z-trace.log*"))
        self.assertEqual(len(files), 3)
        self.assertTrue(all(path.stat().st_size < 1024 * 1024 for path in files))

    def test_unchanged_poll_is_quiet_but_external_file_change_is_seen(self):
        self.helper._ready()
        self.helper._poll(11.)
        self.assertEqual(len(self.records()), 1)
        self.cfg.write_text("#*# [prtouch_v3]\n#*# z_offset = 0.000\n")
        self.helper._poll(12.)
        self.assertEqual(self.records()[-1]["event"], "state_changed")
        self.assertEqual(self.records()[-1]["state"]["file"]["entries"]["save_config"], ["0.000"])

    def test_snapshot_forces_read_when_file_signature_unchanged(self):
        self.helper._ready()
        stat = self.cfg.stat()
        self.cfg.write_text(self.cfg.read_text().replace("0.120", "0.000"))
        import os
        os.utime(self.cfg, ns=(stat.st_atime_ns, stat.st_mtime_ns))
        self.helper.cmd_snapshot(Command(LABEL="after_edit"))
        self.assertEqual(self.records()[-1]["state"]["file"]["entries"]["save_config"], ["0.000"])

    def test_nested_command_context_and_no_new_motion(self):
        self.gcode.handlers["G28"] = lambda cmd: self.configfile.set("prtouch_v3", "z_offset", 0)
        self.gcode.handlers["START_PRINT"] = lambda cmd: self.gcode.handlers["G28"](cmd)
        self.helper._ready()
        self.gcode.handlers["START_PRINT"](Command())
        record = next(r for r in self.records() if r["event"] == "config_set_before")
        self.assertEqual(record["commands"], ["START_PRINT", "G28"])
        self.assertEqual(self.configfile.calls, [("prtouch_v3", "z_offset", 0)])
        self.assertEqual(set(self.gcode.handlers), {"START_PRINT", "G28", "K2_PRTOUCH_Z_TRACE_SNAPSHOT"})

    def test_wrong_probe_inactive_without_hooks(self):
        self.objects["cartographer"] = object()
        original = lambda cmd: None
        self.gcode.handlers["G28"] = original
        self.helper._ready()
        self.assertFalse(self.helper.active)
        self.assertIs(self.gcode.handlers["G28"], original)
        self.assertEqual(self.configfile.set, self.helper.original_set)

    def test_remove_and_unrelated_writes_delegate_once(self):
        self.assertEqual(self.configfile.remove_section("prtouch_v3"), "remove-result")
        self.configfile.set("bed_mesh default", "points", "1,2")
        self.assertEqual(self.configfile.calls, [("remove", "prtouch_v3"), ("bed_mesh default", "points", "1,2")])
        self.assertEqual([r["event"] for r in self.records()], ["config_remove_before", "config_remove_after"])

    def test_shutdown_stops_polling_and_files_unchanged(self):
        before = self.cfg.read_bytes()
        self.helper._ready()
        self.helper._shutdown()
        self.assertEqual(self.helper._poll(12), self.reactor.NEVER)
        self.assertEqual(self.cfg.read_bytes(), before)


class ParserTests(unittest.TestCase):
    def test_sections_and_missing_values(self):
        result = trace.saved_offsets("[prtouch_v3]\nz_offset: -.13 # note\n"
                                     "[other]\nz_offset: 9\n#*# [prtouch_v3]\n"
                                     "#*# z_offset = -.15\n#*# [bed_mesh default]\n#*# z_offset = 8")
        self.assertEqual(result, {"normal": ["-.13"], "save_config": ["-.15"]})
        self.assertEqual(trace.saved_offsets("[prtouch_v3]\n# z_offset: 0"),
                         {"normal": [], "save_config": []})


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = pathlib.Path(self.temp.name)
        self.cfg = root / "config"
        self.custom = self.cfg / "custom"
        self.custom.mkdir(parents=True)
        self.klipper = root / "klipper"
        self.extras = self.klipper / "klippy" / "extras"
        self.extras.mkdir(parents=True)
        self.main = self.custom / "main.cfg"
        self.main.write_text("[include overrides.cfg]\n")
        self.printer_cfg = self.cfg / "printer.cfg"
        self.printer_cfg.write_text("#*# [prtouch_v3]\n#*# z_offset = -.13\n")
        self.status = {"print_stats": {"state": "standby"},
                       "configfile": {"config": {"prtouch_v3": {"z_offset": "-.13"}}}}
        # Linux exercises real links. Windows often denies symlink creation
        # without administrator/developer-mode privileges; model only links
        # there while keeping config/file preservation checks on real files.
        if sys.platform == "win32":
            links = {}
            original_resolve = pathlib.Path.resolve
            original_unlink = pathlib.Path.unlink
            def symlink_to(path, source, target_is_directory=False):
                links[path] = pathlib.Path(source)
            def resolve(path, *args, **kwargs):
                return original_resolve(links.get(path, path), *args, **kwargs)
            def unlink(path, *args, **kwargs):
                if path in links:
                    del links[path]
                else:
                    original_unlink(path, *args, **kwargs)
            for name, fn in (("symlink_to", symlink_to),
                             ("is_symlink", lambda path: path in links),
                             ("resolve", resolve), ("unlink", unlink)):
                patcher = patch.object(pathlib.Path, name, fn)
                patcher.start()
                self.addCleanup(patcher.stop)

    def run_configure(self, remove=False):
        configure.configure(self.cfg, self.klipper, self.status, remove)

    def test_install_idempotent_and_remove_retains_offsets_and_unrelated(self):
        before = self.printer_cfg.read_bytes()
        self.run_configure()
        self.run_configure()
        self.assertEqual(self.main.read_text().count("[include prtouch_z_trace.cfg]"), 1)
        self.assertTrue((self.extras / "k2_prtouch_z_trace.py").is_symlink())
        self.assertTrue((self.custom / "prtouch_z_trace.cfg").is_symlink())
        self.run_configure(True)
        self.run_configure(True)
        self.assertIn("#[include prtouch_z_trace.cfg]", self.main.read_text())
        self.assertIn("[include overrides.cfg]", self.main.read_text())
        self.assertFalse((self.extras / "k2_prtouch_z_trace.py").exists())
        self.assertEqual(self.printer_cfg.read_bytes(), before)

    def test_printing_paused_unknown_and_carto_refused_before_writes(self):
        for state in ("printing", "paused", "unknown", None):
            self.status["print_stats"]["state"] = state
            with self.assertRaises(ValueError):
                self.run_configure()
            self.assertEqual(self.main.read_text(), "[include overrides.cfg]\n")
        self.status["print_stats"]["state"] = "standby"
        self.status["configfile"]["config"]["cartographer"] = {}
        with self.assertRaises(ValueError):
            self.run_configure()
        self.assertFalse((self.extras / "k2_prtouch_z_trace.py").exists())

    def test_unfamiliar_file_or_link_is_preserved(self):
        target = self.extras / "k2_prtouch_z_trace.py"
        target.write_text("user file")
        for remove in (False, True):
            with self.assertRaises(ValueError):
                self.run_configure(remove)
        self.assertEqual(target.read_text(), "user file")
        self.assertEqual(self.main.read_text(), "[include overrides.cfg]\n")

    def test_unfamiliar_symlink_is_preserved(self):
        target = self.custom / "prtouch_z_trace.cfg"
        target.symlink_to(self.printer_cfg)
        with self.assertRaises(ValueError):
            self.run_configure()
        self.assertEqual(target.resolve(), self.printer_cfg.resolve())


if __name__ == "__main__":
    unittest.main()
