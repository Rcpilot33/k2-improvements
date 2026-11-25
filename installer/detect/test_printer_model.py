import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
BASH = shutil.which("bash") or "C:/Program Files/Git/bin/bash.exe"
ENTRIES = ("bootstrap.sh", "bootstrap/bootstrap.sh", "menu.sh", "no-carto.sh", "gimme-the-jamin.sh")


@unittest.skipUnless(Path(BASH).is_file(), "bash required")
class ModelRoutingTests(unittest.TestCase):
    def run_entry(self, entry, model, tools, *args, branch=""):
        # Stop at the first install operation. Exercise the real entry script,
        # including its relative paths, without running an install on this host.
        harness = """
        PATH="$(cd "$TOOLS" && pwd):/usr/bin:$PATH"
        get_sn_mac.sh() {
            if [ "$1" = model ]; then printf '%s\\n' "$MODEL"; else echo test-board; fi
        }
        exec 3>&2
        stop_install() { echo "reached-install ${BRANCH:-}" >&3; exit 73; }
        mkdir() { stop_install; }
        rm() { stop_install; }
        mktemp() { stop_install; }
        sh() { stop_install; }
        . "$0"
        """
        return subprocess.run(
            [BASH, "-c", harness, (ROOT / entry).as_posix(), *args],
            env=dict(os.environ, MODEL=model, TOOLS=tools.as_posix(), K2_BRANCH=branch),
            capture_output=True, text=True, timeout=10, cwd=ROOT,
        )

    def test_public_entry_points(self):
        with tempfile.TemporaryDirectory() as tmp:
            tools = Path(tmp)
            for entry in ENTRIES:
                for model in ("F008", "F012", "F021", ""):
                    with self.subTest(entry=entry, model=model):
                        result = self.run_entry(entry, model, tools)
                        if model == "F008":
                            self.assertIn("reached-install", result.stderr)
                            self.assertEqual(result.returncode, 73)
                        elif model == "F012" and entry in ("bootstrap.sh", "bootstrap/bootstrap.sh"):
                            self.assertIn("reached-install integration-testing", result.stderr)
                            self.assertEqual(result.returncode, 73)
                        elif model == "F012" and entry == "menu.sh":
                            # Both models proceed to the normal menu lock.
                            self.assertEqual(result.returncode, 73, result.stderr)
                        else:
                            self.assertEqual(result.returncode, 1, result.stderr)
                            self.assertNotIn("reached-install", result.stderr)
                            self.assertIn(model or "unknown", result.stdout + result.stderr)

    def test_pro_menu_browse_diagnostics_and_exit(self):
        # Run the entry point with its lock and state confined to the fixture.
        menu = (ROOT / "menu.sh").read_text().replace(
            "INSTALLER_LOCK=/tmp/k2-improvements-installer.lock",
            'INSTALLER_LOCK="$FIXTURE/menu.lock"',
        )
        with tempfile.TemporaryDirectory() as tmp:
            harness = """
            get_sn_mac.sh() { echo F012; }
            id() { echo 0; }
            clear() { :; }
            python3() {
                if [ "$1" = -B ] && [ "$2" = "$INSTALLER_DIR/scripts/printer_baseline.py" ]; then
                    echo baseline-report
                else
                    return 1
                fi
            }
            """
            result = subprocess.run(
                [BASH, "-c", harness + menu, (ROOT / "menu.sh").as_posix()],
                input=b"n\n2\n0\n1\n\n0\n", capture_output=True, timeout=30,
                env=dict(os.environ, FIXTURE=Path(tmp).as_posix(), HOME=Path(tmp).as_posix(),
                         MIGRATION_STATE_DIR=(Path(tmp) / "updates").as_posix()),
            )
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        output = result.stdout.decode()
        self.assertLess(output.index("K2 PRO DEVELOPMENT INSTALLER"), output.index("INSTALL OR CHANGE SETUP"))
        status = output.split("SYSTEM STATUS AND DIAGNOSTICS", 1)[1]
        self.assertNotIn("baseline-report", status)
        self.assertLess(status.index("Setup profile"), status.index("K2 PRO DEVELOPMENT INSTALLER"))

    def test_pro_bootstrap_branch_selection(self):
        with tempfile.TemporaryDirectory() as tmp:
            for entry in ("bootstrap.sh", "bootstrap/bootstrap.sh"):
                for requested in ("main", "integration-testing", "k2-pro-support"):
                    for args, env_branch in ((("--branch", requested), ""), ((), requested)):
                        with self.subTest(entry=entry, args=args, env_branch=env_branch):
                            result = self.run_entry(entry, "F012", Path(tmp), *args, branch=env_branch)
                            if requested in ("integration-testing", "k2-pro-support"):
                                self.assertEqual(result.returncode, 73)
                            else:
                                self.assertEqual(result.returncode, 1)
                                self.assertNotIn("reached-install", result.stderr)

    def test_pro_conversion_reselects_installed_macros(self):
        with tempfile.TemporaryDirectory() as tmp:
            custom = Path(tmp) / "custom"
            custom.mkdir()
            (Path(tmp) / "printer.cfg").write_text("[include custom/main.cfg]\n", newline="\n")
            configs = ("start_print", "start_print_pro", "m191", "bed_mesh", "overrides")
            for name in configs:
                (custom / (name + ".cfg")).touch()
            includes = "".join("[include %s.cfg]\n" % name for name in configs)
            main = custom / "main.cfg"
            main.write_text(includes + "[include k2_prtouch_safe_xy.cfg]\n", newline="\n")
            def check():
                return subprocess.run(
                    [BASH, "-c", '. "$1/installer/detect/features.sh"; is_macros',
                     "test", ROOT.as_posix()], env=dict(os.environ, K2_PRINTER_MODEL="F012",
                                                       PRINTER_CFG_DIR=Path(tmp).as_posix()),
                    timeout=10).returncode
            self.assertEqual(check(), 0)
            (custom / "cartographer.cfg").touch()
            self.assertEqual(check(), 1)
            main.write_text(includes + "#[include k2_prtouch_safe_xy.cfg]\n", newline="\n")
            self.assertEqual(check(), 0)
