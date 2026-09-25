#!/usr/bin/env python3

import importlib.util
import pathlib
import tempfile
import unittest


SCRIPT = pathlib.Path(__file__).with_name("alter_config.py")
INSTALLER = pathlib.Path(__file__).with_name("install.sh")
SPEC = importlib.util.spec_from_file_location("alter_config", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class AlterConfigTests(unittest.TestCase):
    def test_save_config_block_is_never_moved(self):
        original = (
            "[printer]\nkinematics: cartesian\n\n"
            "[prtouch_v3]\npr_version: 2\n"
            "#*# <---------------------- SAVE_CONFIG ---------------------->\n"
            "#*# [probe]\n#*# z_offset = 1.25\n"
        )
        kept, removed, found = MODULE.split_section(original, "prtouch_v3")
        self.assertTrue(found)
        self.assertEqual(removed, "[prtouch_v3]\npr_version: 2\n")
        self.assertIn("#*# <---------------------- SAVE_CONFIG", kept)
        self.assertIn("#*# z_offset = 1.25", kept)

    def test_real_following_section_ends_removed_section(self):
        original = "[prtouch_v3]\na: 1\n[next]\nb: 2\n"
        kept, removed, found = MODULE.split_section(original, "prtouch_v3")
        self.assertTrue(found)
        self.assertEqual(removed, "[prtouch_v3]\na: 1\n")
        self.assertEqual(kept, "[next]\nb: 2\n")

    def test_file_update_creates_original_and_section_backups(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            printer = root / "printer.cfg"
            custom = root / "custom"
            original = "[prtouch_v3]\na: 1\n#*# saved\n#*# a = 2\n"
            printer.write_text(original, encoding="utf-8")
            success, _message = MODULE.remove_section_from_ini(
                str(printer), "prtouch_v3", str(custom)
            )
            self.assertTrue(success)
            self.assertEqual(printer.read_text(encoding="utf-8"), "#*# saved\n#*# a = 2\n")
            self.assertEqual(
                (custom / "prtouch_v3.cfg").read_text(encoding="utf-8"),
                "[prtouch_v3]\na: 1\n",
            )
            self.assertEqual(
                pathlib.Path(str(printer) + ".before-cartographer.bak").read_text(
                    encoding="utf-8"
                ),
                original,
            )

    def test_missing_section_returns_failure_without_rewriting(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            printer = root / "printer.cfg"
            printer.write_text("[printer]\n", encoding="utf-8")
            success, _message = MODULE.remove_section_from_ini(
                str(printer), "prtouch_v3", str(root / "custom")
            )
            self.assertFalse(success)
            self.assertEqual(printer.read_text(encoding="utf-8"), "[printer]\n")

    def test_installer_skips_already_removed_section_but_not_real_failures(self):
        installer = INSTALLER.read_text(encoding="utf-8")
        self.assertIn("grep -q", installer)
        self.assertIn("[prtouch_v3", installer)
        self.assertIn('python3 "${SCRIPT_DIR}/alter_config.py"', installer)
        self.assertNotIn("alter_config.py ||", installer)


if __name__ == "__main__":
    unittest.main()
