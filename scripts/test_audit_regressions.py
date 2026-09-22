#!/usr/bin/env python3
"""Regression tests for utility defects found during the repository audit."""

import importlib.util
import pathlib
import tempfile
import unittest
from unittest import mock


ROOT = pathlib.Path(__file__).resolve().parents[1]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AuditRegressionTests(unittest.TestCase):
    def test_fix_venv_replaces_plain_so_suffix(self):
        module = load_module("fix_venv_test", ROOT / "scripts/fix_venv.py")
        expected_suffix = ".cpython-39-arm-linux-gnueabihf.so"
        with tempfile.TemporaryDirectory() as temp_dir:
            extension = pathlib.Path(temp_dir, "example.so")
            extension.write_bytes(b"test")
            with mock.patch.object(
                module.sysconfig,
                "get_config_var",
                return_value=expected_suffix,
            ):
                self.assertEqual(module.update_so_files(temp_dir), 0)
            self.assertTrue(
                pathlib.Path(temp_dir, "example" + expected_suffix).exists()
            )
            self.assertFalse(
                pathlib.Path(temp_dir, "example.so" + expected_suffix).exists()
            )

    def test_patch_webhooks_does_not_exit_when_called_as_a_function(self):
        module = load_module(
            "patch_webhooks_test",
            ROOT / "features/abort_homing/patch_webhooks.py",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            target = pathlib.Path(temp_dir, "webhooks.py")
            target.write_text(
                "force_stop_homing\ncan_force_stop_homing\n",
                encoding="utf-8",
            )
            self.assertIsNone(module.patch_webhooks(target))

    def test_restore_path_rejects_broad_and_persistent_targets(self):
        source = (ROOT / "scripts/restore-path.sh").read_text(encoding="utf-8")
        self.assertIn('[ "$#" -eq 1 ]', source)
        self.assertIn('/|/overlay|/overlay/*|/mnt|/mnt/*)', source)
        self.assertIn('rm -fr "$FULLPATH"', source)
        self.assertIn('rm -fr "$OVERLAY_PATH"', source)

    def test_installers_use_portable_commands_and_relative_helpers(self):
        moonraker = (ROOT / "features/moonraker/install.sh").read_text(
            encoding="utf-8"
        )
        fluidd = (ROOT / "features/fluidd/install.sh").read_text(
            encoding="utf-8"
        )
        cartographer = (ROOT / "features/cartographer/install.sh").read_text(
            encoding="utf-8"
        )
        toggle = (ROOT / "features/cartographer/cartographer.sh").read_text(
            encoding="utf-8"
        )
        delete_camera = (ROOT / "scripts/delete-camera").read_text(
            encoding="utf-8"
        )
        combined = "\n".join(
            (
                moonraker,
                fluidd,
                cartographer,
                toggle,
                delete_camera,
            )
        )
        self.assertNotIn("type -p", combined)
        self.assertNotIn(" source /etc/profile.d/entware.sh", combined)
        self.assertNotIn("~/k2-improvements/", combined)

        stale_fallbacks = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (
                ROOT / "installer/lib/common.sh",
                ROOT / "installer/extras/global-touch-offsets/install.sh",
                ROOT / "installer/extras/material-z-offsets/install.sh",
            )
        )
        self.assertNotIn("/mnt/UDISK/k2-improvements", stale_fallbacks)

    def test_screws_status_always_exposes_a_mapping(self):
        source = (
            ROOT / "features/screws_tilt_adjust/screws_tilt_adjust.py"
        ).read_text(encoding="utf-8")
        self.assertGreaterEqual(source.count("self.results = {}"), 2)
        self.assertNotIn("self.results = []", source)


if __name__ == "__main__":
    unittest.main()
