"""Exercise batch orchestration without touching a printer."""
import os
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]
BASH = shutil.which("bash") or "C:/Program Files/Git/bin/bash.exe"


@unittest.skipUnless(Path(BASH).is_file(), "bash required")
class ExtrasBatchTests(unittest.TestCase):
    def run_batch(self, selection, **options):
        script = r'''
. "$INSTALLER_DIR/installer/menus/extras.sh"
ui_heading() { :; }
info() { echo "INFO:$*"; }
warn() { echo "WARN:$*"; }
press_enter() { :; }
confirm() { test "${DECLINE:-0}" = 0; }
read_prompt() { read -r "$1"; }
is_cartographer() { test "${CARTO:-0}" = 1; }
is_stock_probe() { test "${CARTO:-0}" = 0; }
is_macros() { return 0; }
is_stock_nozzle_camera_available() { return 0; }
migration_require_idle() { test "${BUSY:-0}" = 0; }
migration_mark_component_current() { echo "MARK:$1"; }
extras_batch_install() {
    echo "INSTALL:$1:defer=$K2_DEFER_FIRMWARE_RESTART:plates=$K2_PLATE_SLICERS"
    test "$1" != "${FAIL:-}"
}
sh() { echo "RESTART:$1:defer=$K2_DEFER_FIRMWARE_RESTART"; test "${RESTART_FAIL:-0}" = 0; }
run_extras_batch
result=$?
echo "OUTER_DEFER:${K2_DEFER_FIRMWARE_RESTART:-unset}"
exit "$result"
'''
        result = subprocess.run([BASH, "-c", script], input=selection.encode(),
                              capture_output=True, timeout=15,
                              env=dict(os.environ, INSTALLER_DIR=ROOT.as_posix(),
                                       **options))
        result.stdout = result.stdout.decode()
        result.stderr = result.stderr.decode()
        return result

    def test_order_deduplication_and_single_restart(self):
        result = self.run_batch("6 3 6\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        out = result.stdout
        self.assertEqual(out.count("INSTALL:"), 2)
        self.assertLess(out.index("INSTALL:kamp"), out.index("INSTALL:material"))
        self.assertEqual(out.count("RESTART:"), 1)
        self.assertIn("defer=1", out)
        self.assertIn("klippy_code_restart.sh:defer=0", out)
        self.assertLess(out.index("RESTART:"), out.index("MARK:"))
        self.assertIn("OUTER_DEFER:unset", out)

    def test_invalid_cancel_busy_and_declined_do_not_mutate(self):
        for selection, options in (("999\n", {}), ("1 bad\n", {}),
                                   ("\n", {}), ("0\n", {}), ("   \n", {}),
                                   ("3\n", {"BUSY": "1"}),
                                   ("3\n", {"DECLINE": "1"})):
            with self.subTest(selection=selection, options=options):
                out = self.run_batch(selection, **options).stdout
                self.assertNotIn("INSTALL:", out)
                self.assertNotIn("RESTART:", out)

    def test_failure_stops_remaining_and_restarts_partial_install(self):
        result = self.run_batch("3 5 6\n", FAIL="global-prtouch-offsets")
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("INSTALL:material", result.stdout)
        self.assertEqual(result.stdout.count("RESTART:"), 1)
        self.assertIn("MARK:kamp-adaptive-purge", result.stdout)
        self.assertNotIn("MARK:global-prtouch-offsets", result.stdout)

    def test_failed_restart_marks_nothing_current(self):
        result = self.run_batch("3\n", RESTART_FAIL="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("MARK:", result.stdout)

    def test_plate_workflow_for_each_probe_type(self):
        for carto, name in (("0", "plate-aware-mesh"),
                            ("1", "cartographer-plate-workflow")):
            result = self.run_batch("4 5\n3\n", CARTO=carto)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("INSTALL:%s:defer=1:plates=both" % name, result.stdout)
            self.assertNotIn("INSTALL:secure-auth", result.stdout)


if __name__ == "__main__":
    unittest.main()
