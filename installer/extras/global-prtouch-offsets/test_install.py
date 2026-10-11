import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("global_prtouch_install", HERE / "configure.py")
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)
layout_spec = importlib.util.spec_from_file_location("global_prtouch_layout", HERE / "configure_fluidd_layout.py")
layout = importlib.util.module_from_spec(layout_spec)
layout_spec.loader.exec_module(layout)


class Tests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        self.cfg, self.klipper = root / "config", root / "klipper"
        self.custom = self.cfg / "custom"
        self.custom.mkdir(parents=True)
        self.extras = self.klipper / "klippy/extras"
        self.extras.mkdir(parents=True)
        self.main = self.custom / "main.cfg"
        self.initial = "[include start_print.cfg]\n[include overrides.cfg]\n"
        self.main.write_text(self.initial)
        self.native = self.cfg / "printer.cfg"
        self.native.write_text("#*# [prtouch_v3]\n#*# z_offset = -0.020\n")
        self.table = self.custom / "prtouch_global_z.json"
        self.table.write_text('{"version":1,"offsets":{"default":-0.02}}')
        self.status = {"print_stats": {"state": "standby"},
                       "configfile": {"config": {"prtouch_v3": {"z_offset": "-.020"}}}}
        if sys.platform == "win32":
            links = {}
            original_resolve, original_unlink, original_exists = Path.resolve, Path.unlink, Path.exists

            def unlink(path, *args, **kwargs):
                if path in links:
                    del links[path]
                else:
                    original_unlink(path, *args, **kwargs)

            for name, function in (
                    ("symlink_to", lambda path, source: links.update({path: Path(source)})),
                    ("is_symlink", lambda path: path in links),
                    ("resolve", lambda path, *args, **kwargs: original_resolve(links.get(path, path), *args, **kwargs)),
                    ("exists", lambda path: original_exists(links.get(path, path))),
                    ("unlink", unlink)):
                mock = patch.object(Path, name, function)
                mock.start()
                self.addCleanup(mock.stop)
        (self.custom / "start_print.cfg").symlink_to(c.ROOT / "features/macros/start_print/start_print.cfg")

    def install(self, remove=False):
        c.configure(self.cfg, self.klipper, self.status, remove)

    def test_install_idempotent_remove_preserves_offsets_calibration_and_compat(self):
        before = self.native.read_bytes(), self.table.read_bytes()
        self.install()
        self.install()
        self.assertEqual(self.main.read_text().count("[include global_prtouch_offsets.cfg]"), 1)
        self.assertTrue((self.extras / "k2_prtouch_global_z.py").is_symlink())
        self.install(True)
        self.install(True)
        self.assertFalse((self.extras / "k2_prtouch_global_z.py").is_symlink())
        self.assertTrue((self.extras / "k2_prtouch_touchscreen.py").is_symlink())
        self.assertIn("[include prtouch_touchscreen.cfg]", self.main.read_text())
        self.assertEqual(before, (self.native.read_bytes(), self.table.read_bytes()))

    def test_preflight_checks_before_overlay_without_creating_links_or_includes(self):
        before = self.main.read_bytes(), self.native.read_bytes(), self.table.read_bytes()
        c.configure(self.cfg, self.klipper, self.status, check_only=True)
        self.assertEqual(before, (self.main.read_bytes(), self.native.read_bytes(), self.table.read_bytes()))
        self.assertFalse((self.custom / c.CONFIG).is_symlink())
        self.assertFalse((self.extras / "k2_prtouch_global_z.py").is_symlink())
        self.status["print_stats"]["state"] = "printing"
        with self.assertRaises(ValueError):
            c.configure(self.cfg, self.klipper, self.status, check_only=True)

    def test_installer_preflights_before_installing_shared_compact_ui(self):
        script = (HERE / "install.sh").read_text()
        self.assertLess(script.index('configure_feature --check-only'), script.index('../fluidd-ui-overlay/install.sh'))
        self.assertLess(script.index('../fluidd-ui-overlay/install.sh'), script.index('configure_feature "$@"'))
        detector = (c.ROOT / "installer/detect/features.sh").read_text()
        body = detector.split('is_global_prtouch_offsets() {', 1)[1].split('\n}', 1)[0]
        self.assertIn('has_settings_ui_overlay 8', body)

    def test_printing_paused_unknown_cartographer_or_missing_native_refused(self):
        for state in ("printing", "paused", "unknown", None):
            self.status["print_stats"]["state"] = state
            for remove in (False, True):
                with self.assertRaises(ValueError):
                    self.install(remove)
        self.status["print_stats"]["state"] = "standby"
        self.status["configfile"]["config"]["cartographer"] = {}
        with self.assertRaises(ValueError):
            self.install()
        self.status["configfile"]["config"] = {}
        with self.assertRaises(ValueError):
            self.install()
        self.assertEqual(self.main.read_text(), self.initial)

    def test_foreign_config_or_unmanaged_start_is_preserved(self):
        target = self.custom / c.CONFIG
        target.write_text("user config")
        with self.assertRaises(ValueError):
            self.install()
        self.assertEqual(target.read_text(), "user config")
        self.assertFalse((self.extras / "k2_prtouch_touchscreen.py").is_symlink())
        target.unlink()
        start = self.custom / "start_print.cfg"
        start.unlink()
        start.write_text("user START_PRINT")
        with self.assertRaises(ValueError):
            self.install()
        self.assertEqual(start.read_text(), "user START_PRINT")

    def test_failed_dependency_link_rolls_back_new_global_links(self):
        original = Path.symlink_to

        def fail(path, source):
            if path.name == "k2_prtouch_touchscreen.py":
                raise OSError("link failed")
            return original(path, source)

        with patch.object(Path, "symlink_to", fail):
            with self.assertRaises(OSError):
                self.install()
        self.assertFalse((self.custom / c.CONFIG).is_symlink())
        self.assertFalse((self.extras / "k2_prtouch_global_z.py").is_symlink())
        self.assertEqual(self.main.read_text(), self.initial)

    def test_remove_after_switch_to_cartographer_is_allowed(self):
        self.install()
        self.status["configfile"]["config"]["cartographer"] = {}
        self.install(True)
        self.assertFalse((self.extras / "k2_prtouch_global_z.py").is_symlink())

    def test_layout_preserves_carto_material_and_other_database_items(self):
        existing = {"other": "keep", "macros": {
            "categories": [{"id": "z", "name": "Z Offsets"}],
            "stored": [{"name": "GLOBAL_Z_OFFSETS_CARTO", "visible": False},
                       {"name": "MATERIAL_Z_OFFSETS", "alias": "Material", "categoryId": "z"}]}}
        result = layout.merge_layout(existing)
        self.assertEqual(result["other"], "keep")
        self.assertEqual(result["macros"]["stored"][:2], existing["macros"]["stored"])
        new = result["macros"]["stored"][-1]
        self.assertEqual(new["name"], "GLOBAL_Z_OFFSETS_NO_CARTO")
        self.assertEqual(new["categoryId"], "z")
        self.assertTrue(new["disabledWhilePrinting"])
        self.assertEqual(layout.merge_layout(result), result)

    def test_start_print_and_menu_gates_preserve_carto_and_reset_plate(self):
        start = (c.ROOT / "features/macros/start_print/start_print.cfg").read_text()
        self.assertIn("'cartographer' not in printer and 'k2_prtouch_global_z' in printer", start)
        self.assertLess(start.index("K2_PRTOUCH_GLOBAL_Z_RESET"), start.index("  BOX_START_PRINT"))
        self.assertLess(start.index("BED_MESH_PROFILE LOAD={mesh_name}"), start.index("K2_PRTOUCH_GLOBAL_Z_APPLY"))
        extras = (c.ROOT / "installer/menus/extras.sh").read_text()
        self.assertIn("ui_menu_item 6 'Global No-Carto Z Offsets'", extras)
        self.assertIn("global-prtouch-offsets/install.sh|is_stock_probe", extras)
        self.assertIn("ui_menu_item 6 'Global Carto Z Offsets'", extras)


if __name__ == "__main__":
    unittest.main()
