"""Stock plate picker preferences and preservation during installer refreshes."""

import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("stock_plate_slicers", HERE / "configure_slicers.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
BASH = shutil.which("bash") or "C:/Program Files/Git/bin/bash.exe"


class SlicerPreferenceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.config = Path(temporary.name)
        self.custom = self.config / "custom"
        self.custom.mkdir()
        self.path = self.custom / m.PREFERENCE

    def test_missing_legacy_choice_keeps_both_and_preflight_writes_nothing(self):
        self.assertEqual(m.configure(self.config, check_only=True), "both")
        self.assertFalse(self.path.exists())
        self.assertEqual(m.configure(self.config), "both")
        self.assertEqual(json.loads(self.path.read_text()), {"slicers": "both"})

    def test_all_choices_are_persistent_and_updates_do_not_replace_choice(self):
        for choice in m.CHOICES:
            m.configure(self.config, choice)
            before = self.path.read_bytes()
            with patch.object(m.os, "replace") as replace:
                self.assertEqual(m.configure(self.config), choice)
                replace.assert_not_called()
            self.assertEqual(self.path.read_bytes(), before)

    def test_atomic_failure_preserves_old_choice_and_no_temporary_files(self):
        m.configure(self.config, "creality")
        before = self.path.read_bytes()
        with patch.object(m.os, "replace", side_effect=OSError("disk failure")):
            with self.assertRaises(OSError):
                m.configure(self.config, "orca")
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(list(self.custom.glob(".plate-workflow-slicers-*")), [])

    def test_invalid_saved_choice_or_requested_choice_is_not_silently_reset(self):
        for saved in ([], {"slicers": "unknown"}, {}):
            self.path.write_text(json.dumps(saved))
            before = self.path.read_bytes()
            with self.assertRaises(ValueError):
                m.configure(self.config)
            self.assertEqual(self.path.read_bytes(), before)
        self.path.unlink()
        with self.assertRaises(ValueError):
            m.configure(self.config, "unknown")
        self.assertFalse(self.path.exists())

    def test_preference_contract_matches_cartographer(self):
        spec = importlib.util.spec_from_file_location(
            "carto_slicer_layout", HERE.parent / "cartographer-macros/configure_fluidd_layout.py")
        carto = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(carto)
        m.configure(self.config, "orca")
        with patch.dict(os.environ, {"PRINTER_CFG_DIR": str(self.config)}):
            self.assertEqual(carto.preference_path(), self.path)
            self.assertEqual(carto.read_plate_slicers(), "orca")

    def install_fixture(self):
        (self.config / "printer.cfg").write_text(
            "[prtouch_v3]\nz_offset: 0\n#*# [bed_mesh textured_pei_70.0c_0.0c]\n"
            "#*# points =\n#*#   0.010, -0.020, 0.030\n")
        for name in ("start_print.cfg", "bed_mesh.cfg"):
            (self.custom / name).write_text("# _PLATE_AWARE_MESH\n")
        (self.custom / "main.cfg").write_text("# user includes\n")
        overrides = self.custom / "overrides.cfg"
        overrides.write_text("[gcode_macro _START_PRINT_VARS]\nvariable_bed_mesh_soak: 0\ngcode:\n")
        offsets = self.custom / "prtouch_global_z.json"
        offsets.write_text('{"version":1,"offsets":{"default":-0.13,"epoxy":-0.1}}\n')
        return overrides, offsets

    @unittest.skipUnless(Path(BASH).is_file(), "bash required")
    def test_installer_choice_and_refresh_preserve_meshes_offsets_and_soak(self):
        overrides, offsets = self.install_fixture()
        original = {path: path.read_bytes() for path in (overrides, offsets, self.config / "printer.cfg")}
        env = dict(os.environ, PRINTER_CFG_DIR=self.config.as_posix(), K2_PYTHON=Path(sys.executable).as_posix(),
                   K2_PLATE_SLICERS="orca")
        for choice in ("orca", ""):
            env["K2_PLATE_SLICERS"] = choice
            result = subprocess.run([BASH, str(HERE / "install.sh"), "--no-restart"],
                                    capture_output=True, env=env, timeout=20)
            self.assertEqual(result.returncode, 0, result.stderr.decode())
            self.assertEqual(m.read_choice(self.path), "orca")
            for path, contents in original.items():
                self.assertEqual(path.read_bytes(), contents)
            self.assertEqual((self.custom / "main.cfg").read_text().count("[include plate_aware_mesh.cfg]"), 1)

    @unittest.skipUnless(Path(BASH).is_file(), "bash required")
    def test_invalid_choice_or_cartographer_preflight_changes_no_files(self):
        self.install_fixture()
        for carto, choice in ((False, "unknown"), (True, "orca")):
            (self.config / "printer.cfg").write_text("[cartographer]\n" if carto else "[prtouch_v3]\n")
            before = {path: path.read_bytes() for path in self.config.rglob("*") if path.is_file()}
            result = subprocess.run([BASH, str(HERE / "install.sh"), "--no-restart"],
                                    capture_output=True, timeout=20,
                                    env=dict(os.environ, PRINTER_CFG_DIR=self.config.as_posix(),
                                             K2_PYTHON=Path(sys.executable).as_posix(), K2_PLATE_SLICERS=choice))
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(self.path.exists())
            self.assertFalse((self.custom / "plate_aware_mesh.cfg").exists())
            self.assertEqual({path: path.read_bytes() for path in self.config.rglob("*") if path.is_file()}, before)


if __name__ == "__main__":
    unittest.main()
