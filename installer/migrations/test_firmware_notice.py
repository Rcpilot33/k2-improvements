"""Installer-only firmware updates must be visible without repair actions."""
import os
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]
BASH = shutil.which("bash") or "C:/Program Files/Git/bin/bash.exe"


@unittest.skipUnless(Path(BASH).exists(), "bash required")
class FirmwareNoticeTests(unittest.TestCase):
    def run_notice(self, changed="image.bin", new="new", failed="0"):
        script = '''
. "$UPDATE_SCRIPT"
git() { printf '%s' "$CHANGED"; return "$FAILED"; }
migration_print_firmware_notice old "$NEW"
'''
        return subprocess.run(
            [BASH, "-c", script], capture_output=True, text=True,
            env=dict(os.environ, UPDATE_SCRIPT=(ROOT / "installer/menus/update.sh").as_posix(),
                     CHANGED=changed, NEW=new, FAILED=failed),
        )

    def test_changed_bundle_reports_manual_action_only(self):
        result = self.run_notice()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("V4 6.2.0 and V3 6.1.0 Full / Lite", result.stdout)
        self.assertIn("V4 6.0.0 and V3 5.1.0", result.stdout)
        self.assertIn("No automatic flash or printer restart", result.stdout)
        self.assertIn("Scan and Touch calibration", result.stdout)

    def test_unrelated_noop_and_missing_history_are_quiet(self):
        for options in ({"changed": ""}, {"new": "old"}, {"failed": "1"}):
            with self.subTest(options=options):
                result = self.run_notice(**options)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, "")


if __name__ == "__main__":
    unittest.main()
