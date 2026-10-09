"""Exercise mount selection with mocked Moonraker and protected restart."""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[3]
BASH = shutil.which("bash") or "C:/Program Files/Git/bin/bash.exe"


@unittest.skipUnless(Path(BASH).exists(), "bash required")
class MountActivationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="k2-mount-activation-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.picker = self.base / "installer/extras/cartographer-offset-setup/install.sh"
        self.picker.parent.mkdir(parents=True)
        self.picker.write_text(
            (ROOT / "installer/extras/cartographer-offset-setup/install.sh").read_text(),
            newline="\n",
        )
        scripts = self.base / "scripts"
        scripts.mkdir()
        shutil.copyfile(ROOT / "scripts/stock_nozzle_camera.sh", scripts / "stock_nozzle_camera.sh")
        (scripts / "firmware_restart.sh").write_text(
            'if [ "${K2_DEFER_FIRMWARE_RESTART:-0}" = 1 ]; then\n'
            ' echo "I: deferring FIRMWARE_RESTART until the full setup is complete"\n'
            ' exit 0\nfi\n'
            'echo restart >> "$TEST_RESTART_LOG"\n'
            'exit "${TEST_RESTART_STATUS:-0}"\n', newline="\n",
        )
        self.custom = self.base / "config/custom"
        self.custom.mkdir(parents=True)
        (self.custom.parent / "printer.cfg").write_text(
            "[stepper_y]\nposition_endstop: -6.2\nposition_min: -6.2\n"
        )
        self.baseline = (
            "[cartographer]\nx_offset: 0\ny_offset: -15\n"
            "[bed_mesh]\nmesh_min: 10, 5\nmesh_max: 340, 330\n"
            "[stepper_y]\nposition_endstop: -0.4\nposition_min: -0.4\n"
        )
        (self.custom / "cartographer.cfg").write_text(self.baseline)
        self.overrides = self.custom / "overrides.cfg"
        self.original = "[bed_mesh]\nprobe_count: 15, 15\n[extruder]\npressure_advance: 0.05\n"
        self.overrides.write_text(self.original)
        self.restart_log = self.base / "restart.log"
        self.query_log = self.base / "query.log"
        self.curl = self.base / "fake-curl"
        self.curl.write_text(
            '#!/bin/sh\necho query >> "$TEST_QUERY_LOG"\n'
            'printf "%s\\n" "$TEST_ACTIVITY_JSON"\n'
            'exit "${TEST_QUERY_STATUS:-0}"\n', newline="\n",
        )
        subprocess.run([BASH, "-c", 'chmod +x "$1"', "test", self.curl.as_posix()], check=True)

    def run_picker(self, choice="3\n", state="standby", **extra_env):
        env = dict(
            os.environ, PRINTER_CFG_DIR=self.custom.parent.as_posix(),
            K2_CURL=self.curl.as_posix(), K2_DEFER_FIRMWARE_RESTART="0",
            TEST_RESTART_LOG=self.restart_log.as_posix(),
            TEST_QUERY_LOG=self.query_log.as_posix(),
            TEST_ACTIVITY_JSON='{"result":{"status":{"print_stats":{"state":"' + state + '"}}}}',
        )
        env.update(extra_env)
        result = subprocess.run(
            [BASH, self.picker.as_posix()], input=choice.encode(), env=env,
            capture_output=True, timeout=15,
        )
        result.stdout = result.stdout.decode()
        result.stderr = result.stderr.decode()
        return result

    def test_changed_profile_restarts_once_and_preserves_other_settings(self):
        result = self.run_picker()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.restart_log.read_text().splitlines(), ["restart"])
        self.assertIn("mount settings are active", result.stdout)
        saved = self.overrides.read_text()
        for setting in ("y_offset: 12", "mesh_min: 5, 12", "position_min: -6.2",
                        "probe_count: 15, 15", "pressure_advance: 0.05"):
            self.assertIn(setting, saved)
        self.assertEqual((self.custom / "cartographer.cfg").read_text(), self.baseline)
        self.assertEqual(len(list(self.custom.glob("overrides.cfg.before-cartographer-offset-*"))), 1)

    def test_cancel_does_not_query_write_or_restart(self):
        result = self.run_picker("b\n")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(self.overrides.read_text(), self.original)
        self.assertFalse(self.query_log.exists())
        self.assertFalse(self.restart_log.exists())

    def test_unchanged_selection_does_not_restart(self):
        self.assertEqual(self.run_picker().returncode, 0)
        self.restart_log.unlink()
        self.query_log.unlink()
        result = self.run_picker()
        self.assertEqual(result.returncode, 0)
        self.assertIn("already configured - no change", result.stdout)
        self.assertFalse(self.query_log.exists())
        self.assertFalse(self.restart_log.exists())

    def test_full_setup_defers_activation_without_idle_query(self):
        result = self.run_picker(K2_DEFER_FIRMWARE_RESTART="1", TEST_ACTIVITY_JSON="")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("deferring FIRMWARE_RESTART", result.stdout)
        self.assertNotIn("mount settings are active", result.stdout)
        self.assertIn("y_offset: 12", self.overrides.read_text())
        self.assertFalse(self.query_log.exists())
        self.assertFalse(self.restart_log.exists())

    def test_busy_and_unknown_activity_leave_config_unchanged(self):
        for state in ("printing", "paused", "unknown"):
            with self.subTest(state=state):
                result = self.run_picker(state=state)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(self.overrides.read_text(), self.original)
                self.assertFalse(self.restart_log.exists())
                self.assertEqual(list(self.custom.glob("overrides.cfg.before-*")), [])

    def test_query_failure_does_not_accept_even_an_idle_response(self):
        result = self.run_picker(TEST_QUERY_STATUS="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.overrides.read_text(), self.original)
        self.assertFalse(self.restart_log.exists())

    def test_restart_failure_keeps_saved_settings_and_reports_inactive(self):
        result = self.run_picker(TEST_RESTART_STATUS="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("y_offset: 12", self.overrides.read_text())
        self.assertIn("power-cycle before homing", result.stderr)
        self.assertNotIn("mount settings are active", result.stdout)

    def test_full_setup_picker_invocation_has_deferral_flag(self):
        source = (ROOT / "installer/menus/install_all.sh").read_text()
        invocation = source.index('sh "$INSTALLER_DIR/installer/extras/cartographer-offset-setup/install.sh"')
        self.assertIn("K2_DEFER_FIRMWARE_RESTART=1", source[invocation - 100:invocation])


if __name__ == "__main__":
    unittest.main()
