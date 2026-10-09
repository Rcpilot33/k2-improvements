"""Local temporary-file tests: never connect to or mutate a printer."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import configure
from k2_nozzle_camera_guard import CAMERA_FLAGS, K2NozzleCameraGuard, disable_camera_preferences

BASH = shutil.which("bash") or "C:/Program Files/Git/bin/bash.exe"


class ProtectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="k2-nozzle-protection-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        if os.name == "nt":
            # Windows cannot create native links without extra privileges.
            # Emulate file links for install/ownership checks; Linux uses real
            # symlinks and exercises the actual filesystem behavior.
            links = {}
            real_resolve, real_is_link, real_unlink = Path.resolve, Path.is_symlink, Path.unlink
            def create_link(path, target, *args, **kwargs):
                shutil.copyfile(target, path)
                links[path] = Path(target)
            def resolve(path, *args, **kwargs):
                return real_resolve(links.get(path, path), *args, **kwargs)
            def is_link(path):
                return path in links or real_is_link(path)
            def unlink(path, *args, **kwargs):
                links.pop(path, None)
                return real_unlink(path, *args, **kwargs)
            for method, replacement in (("symlink_to", create_link), ("resolve", resolve),
                                        ("is_symlink", is_link), ("unlink", unlink)):
                patched = patch.object(Path, method, replacement)
                patched.start()
                self.addCleanup(patched.stop)
        self.config = self.base / "config"
        self.custom = self.config / "custom"
        self.custom.mkdir(parents=True)
        self.klipper = self.base / "klipper"
        self.extras = self.klipper / "klippy/extras"
        self.extras.mkdir(parents=True)
        methods = ("execute_toolhead_ai_waste_management", "execute_ai_waste_detection",
                   "nozzle_cam_power_on", "nozzle_cam_power_off", "ai_capture",
                   "cmd_LOAD_AI_SET_AI_CONTROL_PREFER")
        (self.extras / "load_ai.py").write_text("class AI:\n" + "".join(
            "    def %s(self): pass\n" % name for name in methods))
        self.system = self.base / "system"
        self.power = self.system / "usr/bin/nozzle_cam_power.sh"
        self.power.parent.mkdir(parents=True)
        (self.system / "etc/init.d").mkdir(parents=True)
        (self.system / "etc/init.d/board_init").write_text("START=20\n")
        (self.system / "etc/init.d/klipper").write_text("START=55\n")
        self.factory_text = ('#!/bin/sh\nUSB_P_EN3=162\n'
                             'echo 0 > /sys/class/gpio/gpio$USB_P_EN3/value\n'
                             'echo 1 > /sys/class/gpio/gpio$USB_P_EN3/value\n')
        self.power.write_text(self.factory_text)
        (self.custom / "main.cfg").write_text("[include overrides.cfg]\n# other settings\n", newline="\n")
        self.preferences = self.base / "preferences.json"
        self.original = {"ai_control": {"switch": 1, "wasteSwitch": 1,
                         "flowDetect": 1, "flowEmDetect": 1, "firstFloor": 1},
                         "delay_image": {"switch": 1}, "unknown": [1, 2]}
        self.preferences.write_text(json.dumps(self.original))

    def apply(self, mode):
        configure.configure(self.config, self.klipper, self.system, self.preferences, mode)

    def test_preferences_disable_only_three_camera_flags(self):
        self.assertTrue(disable_camera_preferences(str(self.preferences)))
        expected = json.loads(json.dumps(self.original))
        expected["ai_control"].update({key: 0 for key in CAMERA_FLAGS})
        self.assertEqual(json.loads(self.preferences.read_text()), expected)
        before = self.preferences.stat().st_mtime_ns
        self.assertFalse(disable_camera_preferences(str(self.preferences)))
        self.assertEqual(self.preferences.stat().st_mtime_ns, before)

    def test_unknown_preferences_refused_without_writes(self):
        self.preferences.write_text('{"ai_control":{"switch":1}}')
        with self.assertRaises(ValueError):
            self.apply("power")
        self.assertEqual(self.power.read_text(), self.factory_text)
        self.assertFalse((self.custom / "k2_nozzle_camera_guard.cfg").exists())

    def test_unknown_factory_ai_api_refused_without_writes(self):
        (self.extras / "load_ai.py").write_text("class Unknown: pass\n")
        with self.assertRaises(ValueError):
            self.apply("power")
        self.assertEqual(json.loads(self.preferences.read_text()), self.original)

    def test_wrong_boot_order_refused_without_writes(self):
        (self.system / "etc/init.d/klipper").write_text("START=52\n")
        with self.assertRaises(ValueError):
            self.apply("power")
        self.assertEqual(self.power.read_text(), self.factory_text)
        self.assertEqual(json.loads(self.preferences.read_text()), self.original)

    def test_ai_only_does_not_touch_power_and_refresh_preserves_mode(self):
        self.apply("ai-only")
        self.apply("refresh")
        self.assertEqual(self.power.read_text(), self.factory_text)
        self.assertFalse((self.system / "etc/init.d/k2-nozzle-usb").exists())
        self.assertIn("# usb_power_hold: 0", (self.custom / "k2_nozzle_camera_guard.cfg").read_text())

    def test_power_installs_early_boot_hook_and_refresh_preserves_mode(self):
        self.apply("power")
        self.apply("refresh")
        self.assertIn(configure.POWER_MARKER, self.power.read_text())
        self.assertEqual(Path(str(self.power) + ".k2-factory").read_text(), self.factory_text)
        boot = self.system / "etc/rc.d/S53k2-nozzle-usb"
        self.assertTrue(boot.is_symlink())
        self.assertIn("START=53", boot.read_text())
        self.assertIn("# usb_power_hold: 1", (self.custom / "k2_nozzle_camera_guard.cfg").read_text())

    def test_power_script_modified_after_install_is_not_overwritten_on_refresh(self):
        self.apply("power")
        self.power.write_text("# new firmware power script\n")
        with self.assertRaises(ValueError):
            self.apply("refresh")
        self.assertEqual(self.power.read_text(), "# new firmware power script\n")

    def test_remove_restores_only_camera_flags_and_factory_script(self):
        self.apply("power")
        data = json.loads(self.preferences.read_text())
        data["ai_control"]["switch"] = 0
        data["unknown"].append(3)
        self.preferences.write_text(json.dumps(data))
        self.apply("remove")
        self.assertEqual(self.power.read_text(), self.factory_text)
        restored = json.loads(self.preferences.read_text())
        self.assertEqual(restored["ai_control"]["switch"], 0)
        self.assertEqual(restored["unknown"], [1, 2, 3])
        self.assertTrue(all(restored["ai_control"][key] == 1 for key in CAMERA_FLAGS))
        self.assertFalse((self.system / "etc/rc.d/S53k2-nozzle-usb").exists())
        self.assertFalse((self.custom / "k2_nozzle_camera_guard.cfg").exists())
        self.apply("remove")  # Idempotent cleanup.

    def test_switch_to_ai_only_restores_power_management_without_power_command(self):
        self.apply("power")
        self.apply("ai-only")
        self.assertEqual(self.power.read_text(), self.factory_text)
        self.assertTrue((self.custom / "k2_nozzle_camera_guard.cfg").exists())

    @unittest.skipUnless(Path(BASH).exists(), "bash required")
    def test_power_off_is_mapped_to_power_on(self):
        script = self.base / "wrapper.sh"
        script.write_text((HERE / "nozzle-power.sh").read_text(), newline="\n")
        factory = self.base / "factory.sh"
        # MSYS shell scripts use explicit chmod; never touch real sysfs.
        factory.write_text('#!/bin/sh\nprintf "%s" "$1"\n', newline="\n")
        subprocess.run([BASH, "-c", 'chmod +x "$1"', "test", factory.as_posix()], check=True)
        for request in ("on", "off"):
            result = subprocess.run([BASH, script.as_posix(), request], capture_output=True,
                                    env=dict(os.environ, K2_FACTORY_NOZZLE_POWER=factory.as_posix()))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, b"on")

    def test_runtime_clamps_waste_switch_but_preserves_general_ai(self):
        ai = Mock()
        ai.ai_switch = 0
        ai.ai_waste_switch = 1
        ai.cx_ai_engine_status = {}
        def original(gcmd):
            ai.ai_switch = gcmd.get_int("SWITCH", default=ai.ai_switch)
            ai.ai_waste_switch = gcmd.get_int("WASTE_SWITCH", default=ai.ai_waste_switch)
        ai.cmd_LOAD_AI_SET_AI_CONTROL_PREFER = original
        gcode = Mock()
        printer = Mock()
        printer.lookup_object.side_effect = lambda name, *args: {"gcode": gcode, "load_ai": ai}[name]
        config = Mock()
        config.get_printer.return_value = printer
        config.get.return_value = str(self.preferences)
        guard = K2NozzleCameraGuard(config)
        guard.connect()
        command = Mock()
        command.get_int.side_effect = lambda name, *args, **kwargs: 1
        ai.cmd_LOAD_AI_SET_AI_CONTROL_PREFER(command)
        self.assertEqual(ai.ai_switch, 1)
        self.assertEqual(ai.ai_waste_switch, 0)
        self.assertEqual(ai.cx_ai_engine_status["ai_waste_switch"], 0)
        ai.cmd_LOAD_AI_GET_STATUS(command)
        self.assertEqual(json.loads(command.respond_info.call_args.args[0]),
                         {"ai_switch": 1, "ai_waste_switch": 0})
        self.assertEqual(ai.ai_switch, 1)
        self.assertIsNone(ai.execute_toolhead_ai_waste_management())
        self.assertIsNone(ai.execute_ai_waste_detection())
        self.assertIsNone(ai.nozzle_cam_power_off())
        self.assertTrue(guard.active)
        registered = [call.args[0] for call in gcode.register_command.call_args_list]
        self.assertIn("LOAD_AI_T_CMD_TEST", registered)
        self.assertIn("LOAD_AI_DEAL", registered)

    @unittest.skipUnless(Path(BASH).exists(), "bash required")
    def test_shell_cancellation_and_busy_printer_make_no_changes(self):
        script_dir = self.base / "repo/installer/extras/nozzle-usb-cartographer"
        script_dir.mkdir(parents=True)
        script = script_dir / "install.sh"
        script.write_text((HERE / "install.sh").read_text(), newline="\n")
        helpers = self.base / "repo/scripts"
        helpers.mkdir()
        (helpers / "stock_nozzle_camera.sh").write_text(
            'stock_nozzle_camera_is_jimmyv() { return 0; }\n'
            'stock_nozzle_camera_require_idle() { return 1; }\n', newline="\n")
        cancelled = subprocess.run([BASH, script.as_posix()], input=b"2\nn\n", capture_output=True)
        self.assertEqual(cancelled.returncode, 2)
        busy = subprocess.run([BASH, script.as_posix(), "--power"], capture_output=True)
        self.assertEqual(busy.returncode, 1)
        self.assertIn(b"confirmed idle", busy.stderr)
        self.assertEqual(self.power.read_text(), self.factory_text)

    @unittest.skipUnless(Path(BASH).exists(), "bash required")
    def test_detector_and_migration_do_not_offer_feature_to_uninstalled_users(self):
        root = HERE.parents[2]
        env = dict(os.environ, PRINTER_CFG_DIR=self.config.as_posix(),
                   KLIPPER_DIR=self.klipper.as_posix(), K2_SYSTEM_ROOT=self.system.as_posix(),
                   INSTALLER_DIR=root.as_posix(), MIGRATION_STATE_DIR=(self.base / "state").as_posix())
        command = '. "$INSTALLER_DIR/installer/detect/features.sh"; . "$INSTALLER_DIR/installer/menus/update.sh"; migration_component_applicable nozzle-usb-cartographer'
        result = subprocess.run([BASH, "-c", command], env=env, capture_output=True)
        self.assertEqual(result.returncode, 1)
        self.apply("ai-only")
        result = subprocess.run([BASH, "-c", command], env=env, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        (self.custom / "k2_nozzle_camera_guard.cfg").write_text(configure.MARKER + "\n# usb_power_hold: 1\n", newline="\n")
        detector = '. "$INSTALLER_DIR/installer/detect/features.sh"; is_nozzle_usb_cartographer'
        result = subprocess.run([BASH, "-c", detector], env=env, capture_output=True)
        self.assertEqual(result.returncode, 1)  # Config alone is not rail protection.


if __name__ == "__main__":
    unittest.main()
