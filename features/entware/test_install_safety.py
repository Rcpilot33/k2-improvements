#!/usr/bin/env python3

import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
INSTALLER = ROOT / "bootstrap" / "entware" / "install.sh"


class EntwareInstallSafetyTests(unittest.TestCase):
    def test_existing_opkg_preserves_entware_root(self):
        source = INSTALLER.read_text(encoding="utf-8")
        self.assertIn('if [ -x "$ENTWARE_ROOT/bin/opkg" ]', source)
        self.assertNotIn('rm -rf "$ENTWARE_ROOT"', source)

    def test_never_recursively_removes_opt_mountpoint(self):
        source = INSTALLER.read_text(encoding="utf-8")
        self.assertNotIn("rm -rf /opt", source)
        self.assertNotIn("rm -rf /mnt/UDISK/opt", source)

    def test_refuses_to_replace_unrelated_opt(self):
        source = INSTALLER.read_text(encoding="utf-8")
        self.assertIn("/opt exists and is not the Entware symlink", source)
        self.assertIn("/opt points outside", source)


if __name__ == "__main__":
    unittest.main()
