#!/usr/bin/env python3

import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
INSTALLERS = (
    ROOT / "features" / "entware" / "install.sh",
    ROOT / "bootstrap" / "entware" / "install.sh",
)


class EntwareInstallSafetyTests(unittest.TestCase):
    def test_existing_opkg_preserves_entware_root(self):
        for installer in INSTALLERS:
            with self.subTest(installer=installer):
                source = installer.read_text(encoding="utf-8")
                guard = source.index('if [ -x "$ENTWARE_ROOT/bin/opkg" ]')
                preserve = source.index("Preserving the existing Entware", guard)
                removal = source.index('rm -rf "$ENTWARE_ROOT"', preserve)
                self.assertLess(guard, preserve)
                self.assertLess(preserve, removal)

    def test_never_recursively_removes_opt_mountpoint(self):
        for installer in INSTALLERS:
            with self.subTest(installer=installer):
                source = installer.read_text(encoding="utf-8")
                self.assertNotIn("rm -rf /opt", source)
                self.assertNotIn("rm -rf /mnt/UDISK/opt", source)

    def test_refuses_to_replace_unrelated_opt(self):
        for installer in INSTALLERS:
            with self.subTest(installer=installer):
                source = installer.read_text(encoding="utf-8")
                self.assertIn("/opt exists and is not the Entware symlink", source)
                self.assertIn("/opt points outside", source)


if __name__ == "__main__":
    unittest.main()
