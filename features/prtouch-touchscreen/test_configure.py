import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("prtouch_display_configure", HERE / "configure.py")
configure = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(configure)


class Tests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        self.cfg = root / "config"
        self.custom = self.cfg / "custom"
        self.custom.mkdir(parents=True)
        self.klipper = root / "klipper"
        self.extras = self.klipper / "klippy/extras"
        self.extras.mkdir(parents=True)
        self.main = self.custom / "main.cfg"
        self.initial_main = "[include start_print.cfg]\n[include overrides.cfg]\n"
        self.main.write_text(self.initial_main)
        self.printer_cfg = self.cfg / "printer.cfg"
        self.printer_cfg.write_text("#*# [prtouch_v3]\n#*# z_offset = -0.020\n")
        self.status = {"print_stats": {"state": "standby"},
                       "configfile": {"config": {"prtouch_v3": {"z_offset": "-.020"}}}}
        self.module_target = self.extras / "k2_prtouch_touchscreen.py"
        self.config_target = self.custom / configure.CONFIG
        # Windows symlink privileges are not required to test installer logic.
        # Linux tests exercise real symlinks. All config/preservation reads and
        # writes still use real temporary files on both platforms.
        if sys.platform == "win32":
            links = {}
            original_resolve = Path.resolve
            original_unlink = Path.unlink

            def symlink_to(path, source, target_is_directory=False):
                links[path] = Path(source)

            def resolve(path, *args, **kwargs):
                return original_resolve(links.get(path, path), *args, **kwargs)

            def unlink(path, *args, **kwargs):
                if path in links:
                    del links[path]
                else:
                    original_unlink(path, *args, **kwargs)

            for name, function in (("symlink_to", symlink_to),
                                   ("is_symlink", lambda path: path in links),
                                   ("resolve", resolve), ("unlink", unlink)):
                patcher = patch.object(Path, name, function)
                patcher.start()
                self.addCleanup(patcher.stop)

    def run_configure(self, remove=False):
        configure.configure(self.cfg, self.klipper, self.status, remove)

    def test_install_idempotent_remove_preserves_calibration_and_other_includes(self):
        before = self.printer_cfg.read_bytes()
        self.run_configure()
        self.run_configure()
        main = self.main.read_text()
        self.assertEqual(main.count("[include prtouch_touchscreen.cfg]"), 1)
        self.assertLess(main.index("[include prtouch_touchscreen.cfg]"),
                        main.index("[include overrides.cfg]"))
        self.assertTrue(self.module_target.is_symlink())
        self.assertTrue(self.config_target.is_symlink())
        self.run_configure(True)
        self.run_configure(True)
        self.assertIn("#[include prtouch_touchscreen.cfg]", self.main.read_text())
        self.assertIn("[include start_print.cfg]", self.main.read_text())
        self.assertFalse(self.module_target.is_symlink())
        self.assertFalse(self.config_target.is_symlink())
        self.assertEqual(self.printer_cfg.read_bytes(), before)

    def test_printing_paused_or_unknown_refused_for_install_and_remove(self):
        for state in ("printing", "paused", "unknown", None):
            self.status["print_stats"]["state"] = state
            for remove in (False, True):
                with self.assertRaises(ValueError):
                    self.run_configure(remove)
                self.assertEqual(self.main.read_text(), self.initial_main)
                self.assertFalse(self.module_target.is_symlink())

    def test_carto_config_even_with_dummy_prtouch_is_refused(self):
        self.status["configfile"]["config"]["cartographer"] = {}
        with self.assertRaises(ValueError):
            self.run_configure()
        self.assertEqual(self.main.read_text(), self.initial_main)
        self.assertFalse(self.module_target.is_symlink())

    def test_missing_native_config_or_main_refused(self):
        del self.status["configfile"]["config"]["prtouch_v3"]
        with self.assertRaises(ValueError):
            self.run_configure()
        self.status["configfile"]["config"]["prtouch_v3"] = {}
        self.main.unlink()
        with self.assertRaises(ValueError):
            self.run_configure()
        self.assertFalse(self.module_target.is_symlink())

    def test_existing_second_target_is_checked_before_creating_first_link(self):
        self.config_target.write_text("user config")
        for remove in (False, True):
            with self.assertRaises(ValueError):
                self.run_configure(remove)
        self.assertEqual(self.config_target.read_text(), "user config")
        self.assertFalse(self.module_target.is_symlink())
        self.assertEqual(self.main.read_text(), self.initial_main)

    def test_foreign_symlink_preserved(self):
        self.config_target.symlink_to(self.printer_cfg)
        for remove in (False, True):
            with self.assertRaises(ValueError):
                self.run_configure(remove)
        self.assertEqual(self.config_target.resolve(), self.printer_cfg.resolve())
        self.assertFalse(self.module_target.is_symlink())

    def test_failed_second_symlink_rolls_back_first_without_enabling_include(self):
        original = Path.symlink_to

        def fail_second(path, source, *args, **kwargs):
            if path == self.config_target:
                raise OSError("simulated link failure")
            return original(path, source, *args, **kwargs)

        with patch.object(Path, "symlink_to", fail_second):
            with self.assertRaises(OSError):
                self.run_configure()
        self.assertFalse(self.module_target.is_symlink())
        self.assertEqual(self.main.read_text(), self.initial_main)

    def test_remove_allowed_after_switching_to_carto(self):
        self.run_configure()
        self.status["configfile"]["config"] = {"cartographer": {}}
        self.run_configure(True)
        self.assertFalse(self.module_target.is_symlink())

    def test_moonraker_query_is_bounded_and_read_only(self):
        with patch.object(configure.urllib.request, "urlopen") as request:
            request.return_value.__enter__.return_value.read.return_value = (
                '{"result":{"status":{"print_stats":{"state":"standby"}}}}')
            self.assertEqual(configure.query("http://127.0.0.1:7125/"),
                             {"print_stats": {"state": "standby"}})
            request.assert_called_once_with(
                "http://127.0.0.1:7125/printer/objects/query?print_stats=state&configfile=config",
                timeout=5)


if __name__ == "__main__":
    unittest.main()
