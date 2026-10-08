#!/usr/bin/env python3
"""Tests for releasing prtouch_v3's conflicting Axis Twist alias."""

import pathlib
import tempfile
import unittest

try:
    from .patch_prtouch_registration import (
        PATCHED_REGISTRATION,
        LEGACY_REGISTRATION,
        REGISTRATION,
        patch_file,
    )
except ImportError:
    from patch_prtouch_registration import (
        PATCHED_REGISTRATION,
        LEGACY_REGISTRATION,
        REGISTRATION,
        patch_file,
    )


STOCK_SOURCE = """from . import prtouch_v3_wrapper
from . import probe as probes

def load_config(config):
    prtouch = prtouch_v3_wrapper.PRTouchEndstopWrapper(config)
    config.get_printer().add_object('axis_twist_compensation', prtouch)
    config.get_printer().add_object('probe', probes.PrinterProbe(config, prtouch))
    return prtouch
"""


class PRTouchRegistrationPatchTests(unittest.TestCase):
    def make_target(self, directory, source=STOCK_SOURCE):
        target = pathlib.Path(directory) / "prtouch_v3.py"
        target.write_text(source, encoding="utf-8")
        return target

    def test_releases_only_axis_twist_alias_and_keeps_probe_registration(self):
        with tempfile.TemporaryDirectory() as directory:
            target = self.make_target(directory)

            self.assertTrue(patch_file(target))

            patched = target.read_text(encoding="utf-8")
            self.assertNotIn(REGISTRATION, patched)
            self.assertIn(PATCHED_REGISTRATION, patched)
            self.assertIn("add_object('probe'", patched)
            backup = target.with_name(target.name + ".k2-axis-twist.bak")
            self.assertEqual(backup.read_text(encoding="utf-8"), STOCK_SOURCE)

    def test_patch_is_idempotent_and_preserves_original_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            target = self.make_target(directory)
            self.assertTrue(patch_file(target))
            self.assertFalse(patch_file(target))
            backup = target.with_name(target.name + ".k2-axis-twist.bak")
            self.assertEqual(backup.read_text(encoding="utf-8"), STOCK_SOURCE)

    def test_unknown_source_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            target = self.make_target(directory, "def load_config(config):\n    pass\n")
            with self.assertRaises(RuntimeError):
                patch_file(target)

    def test_upgrade_old_patch_preserves_stock_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            target = self.make_target(
                directory, STOCK_SOURCE.replace(REGISTRATION, LEGACY_REGISTRATION))
            backup = target.with_name(target.name + ".k2-axis-twist.bak")
            backup.write_text(STOCK_SOURCE, encoding="utf-8")
            self.assertTrue(patch_file(target))
            self.assertIn(PATCHED_REGISTRATION, target.read_text(encoding="utf-8"))
            self.assertEqual(backup.read_text(encoding="utf-8"), STOCK_SOURCE)
            self.assertFalse(patch_file(target))

    def test_upgrade_without_backup_reconstructs_stock_registration(self):
        with tempfile.TemporaryDirectory() as directory:
            target = self.make_target(
                directory, STOCK_SOURCE.replace(REGISTRATION, LEGACY_REGISTRATION))
            self.assertTrue(patch_file(target))
            backup = target.with_name(target.name + ".k2-axis-twist.bak")
            self.assertEqual(backup.read_text(encoding="utf-8"), STOCK_SOURCE)

    def test_patched_loader_registers_the_same_native_instance(self):
        with tempfile.TemporaryDirectory() as directory:
            target = self.make_target(directory)
            patch_file(target)
            objects = {}
            native = object()
            class Printer:
                def add_object(self, name, value):
                    objects[name] = value
            class Config:
                def get_printer(self):
                    return Printer()
            class Wrapper:
                @staticmethod
                def PRTouchEndstopWrapper(config):
                    return native
            class Probes:
                @staticmethod
                def PrinterProbe(config, endstop):
                    return endstop
            namespace = {'prtouch_v3_wrapper': Wrapper, 'probes': Probes}
            source = target.read_text(encoding="utf-8")
            exec(source[source.index('def load_config'):], namespace)
            self.assertIs(namespace['load_config'](Config()), native)
            self.assertIs(objects['k2_prtouch_axis_twist_status'], native)
            self.assertIs(objects['probe'], native)
            self.assertNotIn('axis_twist_compensation', objects)


if __name__ == "__main__":
    unittest.main()
