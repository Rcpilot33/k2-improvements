"""Structural checks for the post-Cartographer-flash restart workflow."""

import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]


class CartographerFirmwareRestartTests(unittest.TestCase):
    def test_successful_flash_runs_protected_restart(self):
        script = (ROOT / "installer/menus/carto_fw.sh").read_text(encoding="utf-8")
        success = script.index('if [ "$flash_status" -eq 0 ]')
        restart = script.index('sh "$INSTALLER_DIR/scripts/firmware_restart.sh"', success)
        cancelled = script.index('elif [ "$flash_status" -eq 2 ]', success)
        self.assertLess(restart, cancelled)

    def test_clean_abort_has_distinct_status(self):
        flasher = (ROOT / "features/cartographer/firmware/flash.py").read_text(encoding="utf-8")
        abort = flasher.index('if fw_path == "ABORT"')
        next_failure = flasher.index("if not fw_path:", abort)
        self.assertIn("return 2", flasher[abort:next_failure])

    def test_cancelled_flash_does_not_enter_failure_recovery(self):
        script = (ROOT / "installer/menus/carto_fw.sh").read_text(encoding="utf-8")
        self.assertIn('elif [ "$flash_status" -eq 2 ]', script)
        self.assertIn("Firmware flashing cancelled; no protected restart was requested.", script)


if __name__ == "__main__":
    unittest.main()
