"""Exercise the local OTA review without connecting to a printer."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile


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

    def test_review_repairs_nozzle_protection_after_core_and_resumes_after_back(self):
        original = b"firmware=1.1.6.4\nsetup=cartographer\noption=nozzle-usb-cartographer\n"
        self.snapshot.write_bytes(original)
        script = """
has_cartographer_configuration() { return 0; }
extra_line() { :; }
ota_component_ready() {
    case "$1" in
        cartographer|nozzle-usb-cartographer) test -f "$MIGRATION_STATE_DIR/$1" ;;
        *) return 0 ;;
    esac
}
migration_apply_components() {
    [ "$(cat "$1")" = cartographer ] && touch "$MIGRATION_STATE_DIR/cartographer"
}
sh() {
    [ "$1" = "$INSTALLER_DIR/installer/extras/nozzle-usb-cartographer/install.sh" ] &&
    [ "$2" = --ota-repair ] && [ "$K2_DEFER_FIRMWARE_RESTART" = 0 ] &&
    ota_component_ready cartographer || return 1
    echo 'wiring prompt'
    [ "$CHOICE" = back ] && return 2
    [ "$CHOICE" = failed ] || touch "$MIGRATION_STATE_DIR/nozzle-usb-cartographer"
}
migration_mark_component_current() { echo "record $1"; }
ota_review
"""
        for choice in ("back", "failed"):
            result = self.shell(script, "y\n", CHOICE=choice)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("wiring prompt", result.stdout)
            self.assertNotIn("record nozzle-usb-cartographer", result.stdout)
            self.assertEqual(self.snapshot.read_bytes(), original)
        result = self.shell(script, CHOICE="apply")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("record nozzle-usb-cartographer", result.stdout)
        self.assertIn("Verified cartographer on firmware 1.1.8.0", result.stdout)
        self.assertIn("option=nozzle-usb-cartographer", self.snapshot.read_text())
        self.assertNotIn("wiring prompt", self.shell(script, CHOICE="back").stdout)

    def test_nested_idle_check_during_ota_repair(self):
        harness = """
. scripts/stock_nozzle_camera.sh
python3() { "$TEST_PYTHON" "$@"; }
stock_nozzle_camera_curl() {
    if [ -e "$MIGRATION_STATE_DIR/queried" ]; then echo "$SECOND"; else echo "$FIRST"; fi
    touch "$MIGRATION_STATE_DIR/queried"
}
stock_nozzle_camera_require_idle "$ACTION"
"""
        def response(state):
            return json.dumps({"result": {"status": {"print_stats": {"state": state}}}})

        unknown = '{"error":{"message":"Klippy not ready"}}'
        for first, second, ota, action, answer, success, prompted in (
            (response("standby"), unknown, "1", "repair", "", True, False),
            (response("printing"), unknown, "1", "repair", "y", False, False),
            (response("paused"), unknown, "1", "repair", "y", False, False),
            (unknown, unknown, "0", "repair", "y", False, False),
            (unknown, unknown, "1", "", "y", False, False),
            (unknown, unknown, "1", "repair", "", False, True),
            (unknown, unknown, "1", "repair", "n", False, True),
            (unknown, unknown, "1", "repair", "y", True, True),
            (unknown, response("printing"), "1", "repair", "y", False, True),
            (unknown, response("paused"), "1", "repair", "y", False, True),
        ):
            with self.subTest(first=first, second=second, ota=ota, action=action, answer=answer):
                (self.state / "queried").unlink(missing_ok=True)
                result = self.shell(harness, answer + "\n", FIRST=first, SECOND=second,
                                    K2_OTA_ACTIVITY_CONFIRM=ota, ACTION=action,
                                    TEST_PYTHON=Path(sys.executable).as_posix())
                self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr)
                self.assertEqual("Continue?" in result.stdout, prompted)

    def test_moonraker_recovery_owns_restart_when_both_repairs_are_queued(self):
        script = """
INSTALLER_DIR=$PWD
OTA_REVIEW_ACTIVE=1
migration_require_idle() { return 0; }
migration_reconcile_fluidd_layout() { return 0; }
migration_mark_component_current() { echo "current $1"; }
sh() {
    echo "run ${1##*/features/} ${2:-}"
    case "$1" in */moonraker/install.sh) return "$SERVICE_STATUS" ;; *) return 0 ;; esac
}
migration_apply_components "$MIGRATION_STATE_DIR/plan"
"""
        plan = self.state / "plan"
        plan.write_bytes(b"better-init\n")
        standalone = self.shell(script, SERVICE_STATUS="0")
        self.assertEqual(standalone.returncode, 0, standalone.stderr)
        self.assertNotIn("--defer-moonraker-service", standalone.stdout)
        plan.write_bytes(b"better-init\nmoonraker-service\n")
        for status in (0, 1):
            with self.subTest(status=status):
                result = self.shell(script, SERVICE_STATUS=str(status))
                self.assertIn("run better-init/install.sh --defer-moonraker-service", result.stdout)
                self.assertIn("run moonraker/install.sh --restore-service", result.stdout)
                self.assertEqual(result.returncode, status, result.stderr)
                self.assertEqual("current better-init" in result.stdout, status == 0)
                self.assertEqual("Final protected restart" in result.stdout, status == 0)

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

    def test_first_update_opens_setup_review_on_reload(self):
        self.snapshot.unlink()
        marker = self.state / "review-after-reload"
        dispatch = """
is_macros() { return 0; }
has_cartographer_configuration() { return 0; }
bootstrap_home_ready() { return 1; }
press_enter() { :; }
run_logged_install() { shift; "$@"; }
ota_detect_options() { :; }
ota_settings() { if [ "$1" = save ]; then touch "$MIGRATION_STATE_DIR/settings-$2.zip"; fi; }
menu_update_results() { echo UPDATE_RESULTS; }
migration_offer_on_startup
"""
        self.assertEqual(self.shell(dispatch).stdout, "")
        marker.touch()
        cancelled = self.shell(dispatch, "0\n")
        self.assertIn("Select the previously installed setup", cancelled.stdout)
        self.assertNotIn("UPDATE_RESULTS", cancelled.stdout)
        self.assertFalse(marker.exists())
        self.assertFalse(self.snapshot.exists())
        marker.touch()
        reviewed = self.shell(dispatch, "2\n\n")
        self.assertEqual(reviewed.returncode, 0, reviewed.stderr)
        self.assertIn("Verified cartographer", reviewed.stdout + reviewed.stderr)
        self.assertIn("UPDATE_RESULTS", reviewed.stdout)
        self.assertIn("setup=cartographer", self.snapshot.read_text())
        marker.touch()
        self.assertEqual(self.shell(dispatch).stdout.strip(), "UPDATE_RESULTS")

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

    def test_saved_settings_survive_review_and_retry_without_changing_printer_cfg(self):
        cfg = self.state / "config"
        custom = cfg / "custom"
        custom.mkdir(parents=True)
        native = cfg / "printer.cfg"
        native.write_bytes(b"#*# SAVE_CONFIG\n#*# z_offset = 0.025\n")
        overrides = custom / "overrides.cfg"
        table = custom / "prtouch_global_z.json"
        overrides.write_bytes(b"variable_offset_PETG: 0.012\n")
        table.write_bytes(b'{"version":1,"offsets":{"default":0.0}}\n')
        archive = self.state / "settings-stock-probe.zip"
        harness = """
INSTALLER_DIR=$PWD
python3() {
    case "$1" in */ota_settings.py) "$TEST_PYTHON" "$@" ;; *) return 0 ;; esac
}
ota_detect_options() { echo global-prtouch-offsets; }
migration_require_idle() { [ "$ACTIVITY" = idle ]; }
sh() { echo "protected restart" >> "$MIGRATION_STATE_DIR/restarts"; }
"""
        def run(command, answers="", fw="1.1.8.0", activity="idle"):
            return self.shell(harness + command, answers, FW=fw, ACTIVITY=activity,
                              PRINTER_CFG_DIR=cfg.as_posix(), TEST_PYTHON=Path(sys.executable).as_posix())

        (self.state / "review-after-reload").touch()
        saved = run("""
press_enter() { :; }
bootstrap_home_ready() { return 1; }
run_logged_install() { shift; "$@"; }
menu_update_results() { :; }
migration_offer_on_startup
""", fw="1.1.5.5")
        self.assertEqual(saved.returncode, 0, saved.stderr)
        self.assertTrue(archive.is_file())
        self.assertEqual(run("ota_save_before_update", "y\n", fw="1.1.5.5").returncode, 0)
        with zipfile.ZipFile(archive) as z:
            self.assertIn(b"option=global-prtouch-offsets", z.read("verified-setup"))
            self.assertNotIn("printer.cfg", z.namelist())
        original = archive.read_bytes()
        table.unlink()
        overrides.write_bytes(b"variable_offset_PETG: 0.0\n")
        self.assertNotEqual(run("ota_review", activity="printing").returncode, 0)
        self.assertFalse(table.exists())
        cancelled = run("ota_review", "k\n\n")
        self.assertNotEqual(cancelled.returncode, 0)
        self.assertIn("-variable_offset_PETG: 0.0", cancelled.stdout)
        self.assertIn("+variable_offset_PETG: 0.012", cancelled.stdout)
        self.assertEqual(overrides.read_bytes(), b"variable_offset_PETG: 0.0\n")
        self.assertFalse(table.exists())
        self.assertNotEqual(run("ota_review", "y\n\n").returncode, 0)
        self.assertEqual(overrides.read_bytes(), b"variable_offset_PETG: 0.012\n")
        completed = run("ota_review", "y\n")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(table.read_bytes(), b'{"version":1,"offsets":{"default":0.0}}\n')
        self.assertEqual(native.read_bytes(), b"#*# SAVE_CONFIG\n#*# z_offset = 0.025\n")
        self.assertEqual(archive.read_bytes(), original)
        self.assertEqual((self.state / "restarts").read_text().splitlines(), ["protected restart"])
        self.assertFalse((self.state / "settings-restart-pending").exists())
        overrides.write_bytes(b"variable_offset_PETG: 0.017\n")
        self.assertEqual(run("ota_save_before_update", "y\n").returncode, 0)
        self.assertEqual(archive.with_suffix(".previous.zip").read_bytes(), original)
        with zipfile.ZipFile(archive) as z:
            self.assertEqual(z.read("overrides.cfg"), overrides.read_bytes())

    def test_cartographer_settings_restore_before_scan_after_custom_directory_loss(self):
        cfg = self.state / "config"
        custom = cfg / "custom"
        custom.mkdir(parents=True)
        files = {"overrides.cfg": "y_offset: 12\n", "cartographer.cfg": "[cartographer]\nserial: /dev/cartographer\n",
                 "plate-workflow-slicers.json": '{"slicers":["orca"]}\n', "kamp_settings.cfg": "variable_flow_rate: 12\n"}
        for name, value in files.items():
            (custom / name).write_text(value)
        self.snapshot.unlink()
        harness = """
INSTALLER_DIR=$PWD
python3() { case "$1" in */ota_settings.py) "$TEST_PYTHON" "$@" ;; *) return 0 ;; esac; }
ota_detect_options() { echo cartographer-plate-workflow; }
has_cartographer_configuration() { [ -s "$PRINTER_CFG_DIR/custom/cartographer.cfg" ]; }
migration_require_idle() { return 0; }
sh() { return 0; }
"""
        env = dict(PRINTER_CFG_DIR=cfg.as_posix(), TEST_PYTHON=Path(sys.executable).as_posix())
        historical = """
ota_component_ready() { case "$1" in moonraker-source|cartographer) return 1 ;; *) return 0 ;; esac; }
"""
        saved = self.shell(harness + historical + "ota_save_before_update", FW="1.1.6.4", **env)
        self.assertEqual(saved.returncode, 0, saved.stderr)
        baseline = self.snapshot.read_bytes()
        self.assertIn(b"state=captured", baseline)
        with zipfile.ZipFile(self.state / "settings-cartographer.zip") as backup:
            self.assertEqual(backup.read("verified-setup"), baseline)
            self.assertIn(b"option=cartographer-plate-workflow", baseline)
        check = self.shell(harness + historical + 'ota_setup_installed cartographer', FW="1.1.6.4", **env)
        self.assertNotEqual(check.returncode, 0)
        self.assertIn("moonraker-source\ncartographer", check.stdout + check.stderr)
        self.assertEqual(self.snapshot.read_bytes(), baseline)
        self.assertNotEqual(self.shell(harness + "ota_save_before_update", **env).returncode, 0)
        self.assertEqual(self.snapshot.read_bytes(), baseline)
        shutil.rmtree(custom)
        restored = self.shell(harness + "ota_review", "y\n" * len(files), **env)
        self.assertEqual(restored.returncode, 0, restored.stderr)
        self.assertIn("state=verified", self.snapshot.read_text())
        self.assertEqual({p.name: p.read_text() for p in custom.iterdir()}, files)


if __name__ == "__main__":
    unittest.main()
