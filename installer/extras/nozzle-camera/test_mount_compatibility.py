"""Exercise stock-camera lockout, removal, mount selection and migrations."""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[3]
BASH = shutil.which("bash") or "C:/Program Files/Git/bin/bash.exe"


@unittest.skipUnless(Path(BASH).exists(), "bash required")
class CameraMountCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="k2-camera-mount-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        paths = ["scripts/stock_nozzle_camera.sh",
                 "installer/extras/cartographer-offset-setup/install.sh"]
        paths += ["installer/extras/nozzle-camera/" + name for name in
                  ("install.sh", "uninstall.sh", "nozzle-camera.sh", "nozzle_camera.cfg")]
        for name in paths:
            dest = self.base / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text((ROOT / name).read_text(), newline="\n")
        (self.base / "scripts/firmware_restart.sh").write_text(
            'echo restart >> "$TEST_EVENTS"\n', newline="\n")
        self.camera = self.base / "installer/extras/nozzle-camera"
        self.custom = self.base / "config/custom"
        self.custom.mkdir(parents=True)
        (self.custom.parent / "printer.cfg").write_text(
            "[stepper_y]\nposition_endstop: -6.2\nposition_min: -6.2\n")
        (self.custom / "cartographer.cfg").write_text(
            "[cartographer]\nx_offset: 0\ny_offset: -15\n"
            "[bed_mesh]\nmesh_min: 10, 5\nmesh_max: 340, 330\n"
            "[stepper_y]\nposition_endstop: -0.4\nposition_min: -0.4\n")
        self.overrides = self.custom / "overrides.cfg"
        self.set_mount(12)
        self.bin = self.base / "bin"
        self.bin.mkdir()
        self.events = self.base / "events"
        self.curl = self.base / "fake-curl"
        self.curl.write_text('''#!/bin/sh
case "$*" in
    *objects/query*) echo '{"result":{"status":{"print_stats":{"state":"'"$TEST_STATE"'"}}}}' ;;
    *objects/list*) echo '{"result":{"objects":["delayed_gcode _NOZZLE_CAMERA_AUTO_OFF"]}}' ;;
    *gcode/script*) echo cancel-timer >> "$TEST_EVENTS"; printf '%s\n' "$TEST_CANCEL_REPLY" ;;
esac
''', newline="\n")
        subprocess.run([BASH, "-c", 'chmod +x "$1"', "test", self.curl.as_posix()], check=True)

    def set_mount(self, y, custom=False):
        marker = "custom mount" if custom else "JimmyV test mount"
        self.overrides.write_text(
            f"[cartographer]\n# cartographer-offset-setup: {marker}\ny_offset: {y}\n")

    def install_camera_fixture(self):
        shutil.copyfile(self.camera / "nozzle_camera.cfg", self.custom / "nozzle_camera.cfg")
        shutil.copyfile(self.camera / "nozzle-camera.sh", self.bin / "nozzle-camera.sh")
        (self.custom / "main.cfg").write_text(
            "# unrelated settings\n[include start_print.cfg]\n[include nozzle_camera.cfg]\n")

    def run_shell(self, script, input_text="", **extra):
        env = dict(os.environ, INSTALLER_DIR=self.base.as_posix(),
                   PRINTER_CFG_DIR=self.custom.parent.as_posix(),
                   K2_BIN_DIR=self.bin.as_posix(), K2_CURL=self.curl.as_posix(),
                   NOZZLE_CAM_PIDFILE=(self.base / "camera.pid").as_posix(),
                   TEST_EVENTS=self.events.as_posix(), TEST_STATE="standby",
                   TEST_CANCEL_REPLY='{"result":"ok"}', K2_DEFER_FIRMWARE_RESTART="0",
                   REPO_ROOT=ROOT.as_posix(),
                   MIGRATION_STATE_DIR=(self.base / "state").as_posix())
        env.update(extra)
        result = subprocess.run([BASH, "-c", script], input=input_text.encode(),
                                capture_output=True, env=env, timeout=20)
        result.stdout = result.stdout.decode()
        result.stderr = result.stderr.decode()
        return result

    def remove(self, **extra):
        return self.run_shell('sh "$INSTALLER_DIR/installer/extras/nozzle-camera/uninstall.sh"', **extra)

    def test_all_jimmyv_profiles_are_blocked(self):
        for y in (12, 17, 36):
            self.set_mount(y)
            result = self.run_shell('. "$INSTALLER_DIR/scripts/stock_nozzle_camera.sh"; stock_nozzle_camera_available')
            self.assertEqual(result.returncode, 1)

    def test_jamin_and_explicit_custom_mounts_remain_available(self):
        for value in ("", "[cartographer]\n# cartographer-offset-setup: custom mount\ny_offset: 12\n"):
            self.overrides.write_text(value)
            result = self.run_shell('. "$INSTALLER_DIR/scripts/stock_nozzle_camera.sh"; stock_nozzle_camera_available')
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_older_offset_only_profiles_are_recognized(self):
        self.overrides.write_text("[cartographer]\ny_offset: 17.0\n")
        result = self.run_shell('. "$INSTALLER_DIR/scripts/stock_nozzle_camera.sh"; stock_nozzle_camera_available')
        self.assertEqual(result.returncode, 1)

    def test_menu_blocks_even_an_installed_camera(self):
        result = self.run_shell('''
. "$REPO_ROOT/installer/detect/features.sh"
. "$REPO_ROOT/installer/menus/extras.sh"
c_yellow() { printf '%s' "$*"; }
is_nozzle_camera() { return 0; }
extra_state nozzle-camera
''')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "UNAVAILABLE (JIMMYV MOUNT)")

    def test_direct_install_and_stale_power_commands_are_blocked(self):
        for command in ("install.sh", "nozzle-camera.sh on", "nozzle-camera.sh off"):
            result = self.run_shell('sh "$INSTALLER_DIR/installer/extras/nozzle-camera/"' + command)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("JimmyV mounts replace", result.stderr)
            self.assertFalse((self.custom / "nozzle_camera.cfg").exists())

    def test_removal_preserves_power_and_unrelated_settings_and_is_repeatable(self):
        self.install_camera_fixture()
        result = self.remove()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("USB rail power unchanged", result.stdout)
        self.assertFalse((self.custom / "nozzle_camera.cfg").exists())
        self.assertFalse((self.bin / "nozzle-camera.sh").exists())
        self.assertEqual((self.custom / "main.cfg").read_text(),
                         "# unrelated settings\n[include start_print.cfg]\n")
        self.assertEqual(self.events.read_text().splitlines(), ["cancel-timer", "restart"])
        self.assertEqual(len(list(self.custom.glob("nozzle_camera.cfg.before-*"))), 1)
        self.assertEqual(len(list(self.bin.glob("nozzle-camera.sh.before-*"))), 1)
        result = self.remove()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.events.read_text().splitlines(), ["cancel-timer", "restart"])

    def test_busy_printer_and_failed_timer_cancel_prevent_removal(self):
        self.install_camera_fixture()
        for extra in ({"TEST_STATE": "printing"}, {"TEST_STATE": "paused"},
                      {"TEST_STATE": "unknown"}, {"TEST_CANCEL_REPLY": '{"error":"failed"}'}):
            result = self.remove(**extra)
            self.assertNotEqual(result.returncode, 0)
            self.assertTrue((self.custom / "nozzle_camera.cfg").exists())
            self.assertIn("[include nozzle_camera.cfg]", (self.custom / "main.cfg").read_text())

    def test_modified_user_camera_file_is_preserved(self):
        self.install_camera_fixture()
        (self.custom / "nozzle_camera.cfg").write_text("# user replacement\n")
        result = self.remove()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("refusing to remove modified", result.stderr)
        self.assertEqual((self.custom / "nozzle_camera.cfg").read_text(), "# user replacement\n")
        self.assertFalse(self.events.exists())

    def test_mount_selection_cleans_existing_camera_with_one_restart(self):
        self.install_camera_fixture()
        self.overrides.write_text("")
        picker = 'sh "$INSTALLER_DIR/installer/extras/cartographer-offset-setup/install.sh"'
        result = self.run_shell(picker, "3\n")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("y_offset: 12", self.overrides.read_text())
        self.assertFalse((self.custom / "nozzle_camera.cfg").exists())
        self.assertEqual(self.events.read_text().splitlines(), ["cancel-timer", "restart"])
        # Reapplying the same mount must still remove a conflicting old extra.
        self.install_camera_fixture()
        result = self.run_shell(picker, "3\n")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse((self.custom / "nozzle_camera.cfg").exists())
        self.assertEqual(self.events.read_text().splitlines(),
                         ["cancel-timer", "restart", "cancel-timer", "restart"])

    def test_failed_camera_cleanup_does_not_commit_mount_changes(self):
        self.install_camera_fixture()
        self.overrides.write_text("")
        result = self.run_shell('sh "$INSTALLER_DIR/installer/extras/cartographer-offset-setup/install.sh"',
                                "3\n", TEST_CANCEL_REPLY='{"error":"failed"}')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.overrides.read_text(), "")

    def test_migration_is_only_offered_for_an_actual_conflict(self):
        shell = '''
. "$REPO_ROOT/installer/detect/features.sh"
. "$REPO_ROOT/installer/menus/update.sh"
migration_component_applicable nozzle-camera-mount-compatibility
'''
        self.assertEqual(self.run_shell(shell).returncode, 1)
        self.install_camera_fixture()
        self.assertEqual(self.run_shell(shell).returncode, 0)
        self.overrides.write_text("")
        self.assertEqual(self.run_shell(shell).returncode, 1)

    def test_migration_cleanup_defers_restart_and_verifies_absence(self):
        self.install_camera_fixture()
        result = self.run_shell('''
. "$REPO_ROOT/installer/detect/features.sh"
. "$REPO_ROOT/installer/menus/update.sh"
migration_repair_component nozzle-camera-mount-compatibility &&
migration_component_installed nozzle-camera-mount-compatibility
''')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.events.read_text().splitlines(), ["cancel-timer"])


if __name__ == "__main__":
    unittest.main()
