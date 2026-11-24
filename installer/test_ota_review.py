"""Exercise the local OTA review without connecting to a printer."""
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
BASH = shutil.which("bash") or "C:/Program Files/Git/bin/bash.exe"
SPEC = importlib.util.spec_from_file_location("verify_ota_runtime",
                                              ROOT / "installer/migrations/verify_ota_runtime.py")
runtime = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runtime)


class RuntimeTests(unittest.TestCase):
    def test_only_accepts_registered_macros_and_updaters_for_selected_setup(self):
        api = {"/printer/info": {"state": "ready"},
               "/printer/gcode/help": dict.fromkeys(("start_print", "bed_assist")),
               "/machine/update/status?refresh=false": {"version_info": {"fluidd": {}}}}
        runtime.verify("stock-probe", request=api.__getitem__)
        with self.assertRaisesRegex(ValueError, "MATERIAL_Z_OFFSETS"):
            runtime.verify("stock-probe", ["material-z-offsets"], api.__getitem__)
        with self.assertRaisesRegex(ValueError, "A63_CARTO_INFO"):
            runtime.verify("cartographer", request=api.__getitem__)
        api["/printer/gcode/help"].update(dict.fromkeys(("A63_CARTO_INFO", "A62_CARTO_LIST_MODELS")))
        with self.assertRaisesRegex(ValueError, "missing Moonraker updaters: cartographer"):
            runtime.verify("cartographer", request=api.__getitem__)
        api["/printer/info"]["state"] = "error"
        with self.assertRaisesRegex(ValueError, "Ready"):
            runtime.verify("stock-probe", request=api.__getitem__)


@unittest.skipUnless(Path(BASH).is_file(), "requires Bash")
class ReviewTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.state = Path(directory.name)
        self.snapshot = self.state / "verified-setup"
        self.snapshot.write_text("firmware=1.1.5.5\nmodel=K2 Plus\nsetup=stock-probe\noption=kamp-adaptive-purge\n")

    def shell(self, script, stdin="", **env):
        setup = """
set -u
. installer/lib/common.sh
. installer/menus/update.sh
. installer/menus/ota_review.sh
detect_installed_firmware() { echo "$FW"; }
ota_bootstrap_check() { return 0; }
has_cartographer_configuration() { return 1; }
is_start_print_fast_stop_eligible() { return 1; }
ota_component_ready() { return 0; }
python3() { return "$RUNTIME_STATUS"; }
"""
        environment = dict(os.environ, MIGRATION_STATE_DIR=self.state.as_posix(),
                           FW="1.1.8.0", RUNTIME_STATUS="0")
        environment.update(env)
        result = subprocess.run([BASH, "-c", setup + script], cwd=ROOT, env=environment,
                                input=stdin.encode(), capture_output=True, timeout=15)
        result.stdout = result.stdout.decode()
        result.stderr = result.stderr.decode()
        return result

    def test_retry_only_advances_snapshot_after_success(self):
        original = self.snapshot.read_bytes()
        for settings in ({"RUNTIME_STATUS": "1"}, {"FW": ""}):
            with self.subTest(settings=settings):
                result = self.shell("ota_review", **settings)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(self.snapshot.read_bytes(), original)
        result = self.shell("ota_review")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("firmware=1.1.8.0", self.snapshot.read_text())
        self.assertIn("option=kamp-adaptive-purge", self.snapshot.read_text())

    def test_erased_option_stays_in_repair_plan_after_failure(self):
        original = self.snapshot.read_bytes()
        result = self.shell("""
ota_component_ready() { [ "$1" != kamp-adaptive-purge ]; }
extra_line() { :; }
confirm() { return 0; }
migration_apply_components() { cat "$1"; return 1; }
ota_review
""")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Missing or incomplete components:\nkamp-adaptive-purge", result.stdout)
        self.assertEqual(original, self.snapshot.read_bytes())

    def test_changed_firmware_and_manual_review_do_not_pull(self):
        dispatch = """
clear() { :; }
press_enter() { :; }
run_logged_install() { echo "ACTION $1"; }
migration_pull_installer() { echo "ACTION pull"; }
bootstrap_home_ready() { return 1; }
menu_update_installer
"""
        for choice, fw, action in (("1", "1.1.8.0", "ota-review"),
                                   ("1", "1.1.5.5", "pull"), ("4", "1.1.5.5", "ota-review")):
            with self.subTest(choice=choice, fw=fw):
                result = self.shell(dispatch, choice + "\n0\n", FW=fw)
                self.assertEqual(result.returncode, 0, result.stderr)
                actions = [line.split("ACTION ")[1] for line in result.stdout.splitlines() if "ACTION " in line]
                self.assertEqual(actions, [action])

    def test_preflight_rechecks_repair_and_denies_changes_during_print(self):
        script = """
ota_bootstrap_check() { [ -e "$MIGRATION_STATE_DIR/repaired" ]; }
migration_require_idle() { [ "$ACTIVITY" = idle ]; }
confirm() { return 0; }
run_logged_install() { [ "$1" = bootstrap-repair ] && touch "$MIGRATION_STATE_DIR/repaired"; }
ota_bootstrap_preflight
echo "pending=$bootstrap_needs_review"
"""
        self.assertIn("pending=1", self.shell(script, ACTIVITY="printing").stdout)
        self.assertFalse((self.state / "repaired").exists())
        self.assertIn("pending=0", self.shell(script, ACTIVITY="idle").stdout)
        self.assertTrue((self.state / "repaired").exists())

    def test_first_review_adopts_previously_installed_extras(self):
        self.snapshot.unlink()
        result = self.shell("ota_detect_options() { :; }; ota_review", "1\nmaterial-z-offsets\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("option=material-z-offsets", self.snapshot.read_text())

    def test_missing_fluidd_grouping_can_be_restored_after_runtime_is_ready(self):
        script = """
python3() { case "$1" in */verify_fluidd_layout.py) return 1 ;; *) return 0 ;; esac; }
confirm() { [ "$CONSENT" = yes ]; }
migration_reconcile_fluidd_layout() { echo "Restored group $1"; }
ota_review
"""
        original = self.snapshot.read_bytes()
        self.assertNotEqual(self.shell(script, CONSENT="no").returncode, 0)
        self.assertEqual(self.snapshot.read_bytes(), original)
        result = self.shell(script, CONSENT="yes")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Restored group macros", result.stdout)


if __name__ == "__main__":
    unittest.main()
