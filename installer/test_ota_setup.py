"""Exercise installer recovery against a preserved printer configuration."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
BASH = shutil.which("bash") or "C:/Program Files/Git/bin/bash.exe"


@unittest.skipUnless(Path(BASH).is_file(), "requires Bash")
class PreservedSetupTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        self.cfg = self.base / "printer_data/config"
        self.custom = self.cfg / "custom"
        self.custom.mkdir(parents=True)
        self.env = dict(os.environ, PRINTER_CFG_DIR=self.cfg.as_posix(),
                        KLIPPER_DIR=(self.base / "klipper").as_posix(),
                        TEST_PYTHON=Path(sys.executable).as_posix())

    def shell(self, script, stdin=""):
        return subprocess.run([BASH, "-c", script], cwd=ROOT, env=self.env,
                              input=stdin, capture_output=True, text=True, timeout=30)

    def test_install_log_shows_error_and_retains_status_and_input(self):
        result = self.shell("""
. installer/lib/common.sh
detect_printer_fw() { echo 1.1.8.0; }
detect_installer_commit() { echo abcdef; }
fixture() { read -r answer; echo "choice=$answer"; echo "missing overrides" >&2; return 7; }
run_logged_install cartographer fixture
""", "yes\n")
        self.assertEqual(result.returncode, 7, result.stderr)
        log = (self.cfg.parent / "logs/k2-installer.log").read_text()
        for expected in ("1.1.8.0", "abcdef", "choice=yes", "missing overrides", "exit code 7"):
            self.assertIn(expected, result.stdout)
            self.assertIn(expected, log)

    def test_surviving_configuration_with_missing_driver_is_incomplete(self):
        (self.custom / "cartographer.cfg").write_text("[cartographer]\n")
        result = self.shell("""
. installer/detect/features.sh
is_essentials_core() { return 0; }
detect_install_profile
""")
        self.assertEqual(result.stdout.strip(), "Cartographer (incomplete)")

    def test_fluidd_ui_survives_without_updater(self):
        script = """
. installer/menus/ota_review.sh
INSTALLER_DIR=$PWD
is_fluidd() { return 0; }
python3() { "$TEST_PYTHON" "$@"; }
ota_component_ready fluidd
"""
        config = self.cfg / "moonraker.conf"
        config.write_text("[include updates/fluidd.cfg]\n")
        self.assertNotEqual(self.shell(script).returncode, 0)
        (self.cfg / "updates").mkdir()
        shutil.copyfile(ROOT / "features/fluidd/update-manager.cfg", self.cfg / "updates/fluidd.cfg")
        self.assertEqual(self.shell(script).returncode, 0)
        config.write_text("# updater include lost\n")
        self.assertNotEqual(self.shell(script).returncode, 0)

    def test_repair_missing_includes_and_updater_and_retry_failed_layout(self):
        # Run the real installers with only the service and HTTP call replaced.
        repo = self.base / "checkout"
        for relative in ("features/cartographer/register.sh", "features/cartographer/update-manager.cfg",
                         "scripts/ensure_included.py", "installer/lib/common.sh",
                         "installer/detect/features.sh", "installer/extras/cartographer-macros/install.sh",
                         "installer/extras/cartographer-macros/cartographer_macros.cfg"):
            target = repo / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relative, target)
        with (repo / "installer/lib/common.sh").open("a", newline="\n") as f:
            f.write('\nrestart_moonraker_and_wait() { test -s "$PRINTER_CFG_DIR/updates/cartographer.cfg"; }\n')
        (repo / "installer/extras/cartographer-macros/configure_fluidd_layout.py").write_text(
            'import os, sys\nsys.exit(int(os.environ["LAYOUT_STATUS"]))\n')
        klippy = self.base / "klipper/klippy"
        (klippy / "extras").mkdir(parents=True)
        (klippy / "extras/cartographer.py").touch()
        (klippy / "mcu.py").write_text("class TriggerDispatch:\n")
        (self.cfg / "printer.cfg").write_text("# preserved\n")
        (self.cfg / "moonraker.conf").write_text("[include updates/cartographer.cfg]\n")
        (self.custom / "main.cfg").write_text("[include overrides.cfg]\n")
        offsets = b"[cartographer]\nx_offset: 11.5\n"
        (self.custom / "overrides.cfg").write_bytes(offsets)
        (self.custom / "cartographer.cfg").write_text("[cartographer]\n")
        self.env["CHECKOUT"] = repo.as_posix()
        # Use a PATH shim also visible to /bin/sh child scripts.
        shim = self.base / "bin"
        shim.mkdir()
        (shim / "python3").write_text('#!/bin/sh\nexec "$TEST_PYTHON" "$@"\n', newline="\n")
        (shim / "python3").chmod(0o755)
        self.env["SHIM"] = shim.as_posix()
        script = """
export PATH="$(cd "$SHIM" && pwd):$PATH"
cd "$CHECKOUT" && sh features/cartographer/register.sh
"""
        check = '. installer/detect/features.sh; is_cartographer_registered'
        self.assertNotEqual(self.shell(check).returncode, 0)
        self.env["LAYOUT_STATUS"] = "1"
        failed = self.shell(script)
        self.assertNotEqual(failed.returncode, 0)
        self.assertTrue((self.custom / ".cartographer-registration-pending").exists(), failed.stderr)
        self.assertNotEqual(self.shell(check).returncode, 0)
        self.env["LAYOUT_STATUS"] = "0"
        for attempt in range(2):
            result = self.shell(script)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(self.shell(check).returncode, 0)
        self.assertEqual((self.custom / "overrides.cfg").read_bytes(), offsets)
        includes = (self.custom / "main.cfg").read_text().splitlines()
        self.assertEqual(includes.count("[include cartographer_macros.cfg]"), 1)
        self.assertEqual(includes[-1], "[include overrides.cfg]")
        self.assertEqual((self.cfg / "moonraker.conf").read_text().count("[include"), 1)
