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
            shim = tools / "python3"
            shim.write_bytes(b'#!/bin/sh\n[ "$1" = -B ] && [ -f "$2" ] && '
                             b'[ "${2##*/}" = printer_baseline.py ] && echo baseline-report\n')
            shim.chmod(0o755)
            for entry in ENTRIES:
                for model in ("F008", "F012", "F021", ""):
                    with self.subTest(entry=entry, model=model):
                        result = self.run_entry(entry, model, tools)
                        if model == "F008":
                            self.assertIn("reached-install", result.stderr)
                            self.assertEqual(result.returncode, 73)
                        elif model == "F012" and entry in ("bootstrap.sh", "bootstrap/bootstrap.sh"):
                            self.assertIn("reached-install k2-pro-support", result.stderr)
                            self.assertEqual(result.returncode, 73)
                        elif model == "F012" and entry == "menu.sh":
                            self.assertEqual(result.returncode, 0, result.stderr)
                            self.assertIn("baseline-report", result.stdout)
                        else:
                            self.assertEqual(result.returncode, 1, result.stderr)
                            self.assertNotIn("reached-install", result.stderr)
                            self.assertIn(model or "unknown", result.stdout + result.stderr)

    def test_pro_bootstrap_branch_selection(self):
        with tempfile.TemporaryDirectory() as tmp:
            for entry in ("bootstrap.sh", "bootstrap/bootstrap.sh"):
                for requested in ("main", "integration-testing", "k2-pro-support"):
                    for args, env_branch in ((("--branch", requested), ""), ((), requested)):
                        with self.subTest(entry=entry, args=args, env_branch=env_branch):
                            result = self.run_entry(entry, "F012", Path(tmp), *args, branch=env_branch)
                            if requested == "k2-pro-support":
                                self.assertEqual(result.returncode, 73)
                            else:
                                self.assertEqual(result.returncode, 1)
                                self.assertNotIn("reached-install", result.stderr)
