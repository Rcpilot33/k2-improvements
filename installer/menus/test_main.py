"""Exercise manual update checks with local fixtures, never GitHub or a printer."""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
BASH = shutil.which("bash") or "C:/Program Files/Git/bin/bash.exe"


@unittest.skipUnless(Path(BASH).exists(), "bash required")
class MainMenuTests(unittest.TestCase):
    def run_menu(self, choices, results=("current",), pending=0, change=""):
        with tempfile.TemporaryDirectory(prefix="k2-main-menu-") as directory:
            base = Path(directory)
            for name, contents in (("branch", "integration-testing\n"),
                                   ("commit", "abc1234\n"),
                                   ("results", "\n".join(results) + "\n"), ("calls", "")):
                (base / name).write_text(contents, newline="\n")
            script = '''
set -eu
. "$COMMON_SCRIPT"
. "$MAIN_SCRIPT"
clear() { :; }
c_red() { printf '%s' "$1"; }
c_green() { printf '%s' "$1"; }
c_yellow() { printf '%s' "$1"; }
c_cyan() { printf '%s' "$1"; }
c_dim() { printf '%s' "$1"; }
ui_rule() { :; }
ui_menu_item() { printf 'MENU:%s:%s:%s\\n' "$1" "$2" "${3:-}"; }
detect_printer_fw() { echo 1.1.7.0; }
detect_carto_hw() { echo V4; }
detect_carto_fw() { echo '6.2.0 (Full)'; }
detect_install_profile() { echo 'stock probe / no-Cartographer'; }
is_cartographer() { return 1; }
detect_installer_branch() { cat "$FIXTURES/branch"; }
detect_installer_commit() { cat "$FIXTURES/commit"; }
migration_pending_component_count() { echo "$PENDING"; }
detect_remote_commit_state() {
    echo query >> "$FIXTURES/calls"
    local number
    number=$(wc -l < "$FIXTURES/calls")
    sed -n "${number}p" "$FIXTURES/results"
}
show_status() { :; }
menu_install_paths() { echo another-branch > "$FIXTURES/branch"; }
menu_cartographer_tools() { :; }
menu_extras() { :; }
menu_maintenance() { :; }
menu_update_installer() {
    if [ "$CHANGE" = commit ]; then
        echo def5678 > "$FIXTURES/commit"
    fi
}
main_menu
'''
            result = subprocess.run(
                # Preserve terminal LF input on Windows; text-mode stdin would
                # translate it to CRLF and make shell choices contain a CR.
                [BASH, "-c", script], input=choices.encode(), capture_output=True,
                timeout=10, env=dict(os.environ,
                    COMMON_SCRIPT=(ROOT / "installer/lib/common.sh").as_posix(),
                    MAIN_SCRIPT=(ROOT / "installer/menus/main.sh").as_posix(),
                    FIXTURES=base.as_posix(), PENDING=str(pending), CHANGE=change),
            )
            output = result.stdout.decode()
            self.assertEqual(result.returncode, 0, result.stderr.decode())
            states = [line.split(":", 3)[3] for line in output.splitlines()
                      if line.startswith("MENU:6:")]
            return states, (base / "calls").read_text().splitlines(), output

    def test_startup_and_ordinary_navigation_do_not_query_remote(self):
        states, calls, output = self.run_menu("1\n3\n4\n5\n0\n")
        self.assertEqual(states, ["NOT CHECKED"] * 5)
        self.assertEqual(calls, [])
        self.assertIn("MENU:7:Check for installer updates:", output)
        self.assertIn("Select [0-7]:", output)

    def test_manual_check_updates_option_six_without_hiding_pending_actions(self):
        for pending in (0, 2):
            for result, label in (("current", "INSTALLER UP TO DATE"),
                                  ("available", "INSTALLER UPDATE AVAILABLE"),
                                  ("unavailable", "CHECK FAILED")):
                with self.subTest(pending=pending, result=result):
                    states, calls, output = self.run_menu("7\n0\n", (result,), pending)
                    prefix = f"{pending} ACTION(S) PENDING | " if pending else ""
                    self.assertEqual(states, [prefix + "NOT CHECKED", prefix + label])
                    self.assertEqual(calls, ["query"])
                    self.assertIn("Checking installer updates for integration-testing", output)

    def test_failed_check_can_be_retried(self):
        states, calls, _ = self.run_menu("7\n7\n0\n", ("unavailable", "available"))
        self.assertEqual(states, ["NOT CHECKED", "CHECK FAILED", "INSTALLER UPDATE AVAILABLE"])
        self.assertEqual(calls, ["query", "query"])

    def test_result_survives_navigation_without_additional_queries(self):
        states, calls, _ = self.run_menu("7\n1\n3\n0\n")
        self.assertEqual(states, ["NOT CHECKED"] + ["INSTALLER UP TO DATE"] * 3)
        self.assertEqual(calls, ["query"])

    def test_branch_or_commit_change_invalidates_result_without_querying(self):
        for choice, change in (("2", ""), ("6", "commit")):
            with self.subTest(choice=choice):
                states, calls, _ = self.run_menu(f"7\n{choice}\n0\n", change=change)
                self.assertEqual(states, ["NOT CHECKED", "INSTALLER UP TO DATE", "NOT CHECKED"])
                self.assertEqual(calls, ["query"])


@unittest.skipUnless(Path(BASH).exists(), "bash required")
class RemoteCheckTests(unittest.TestCase):
    def run_check(self, mode, repository=True, branch="integration-testing"):
        with tempfile.TemporaryDirectory(prefix="k2-remote-check-") as directory:
            base = Path(directory)
            if repository:
                (base / ".git").mkdir()
            calls = base / "calls"
            calls.touch()
            script = '''
set -eu
. "$MAIN_SCRIPT"
git() {
    printf '%s\\n' "$*" >> "$CALLS"
    case "$*" in
        *symbolic-ref*) [ -n "$BRANCH" ] && echo "$BRANCH" ;;
        *rev-parse*) echo aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa ;;
        *ls-remote*)
            case "$MODE" in
                current|failure)
                    printf 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\\trefs/heads/%s\\n' "$BRANCH"
                    [ "$MODE" != failure ]
                    ;;
                available) printf 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb\\trefs/heads/%s\\n' "$BRANCH" ;;
                missing) echo 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb refs/heads/unrelated' ;;
                empty) : ;;
                timeout)
                    command sleep 30 &
                    local sleeper=$!
                    trap 'kill "$sleeper" 2>/dev/null || true; wait "$sleeper" 2>/dev/null || true; echo stopped >> "$CALLS"; exit 143' TERM
                    wait "$sleeper"
                    ;;
            esac
            ;;
        *) return 99 ;;
    esac
}
detect_remote_commit_state
'''
            result = subprocess.run(
                [BASH, "-c", script], capture_output=True, text=True, timeout=10,
                env=dict(os.environ,
                         MAIN_SCRIPT=(ROOT / "installer/menus/main.sh").as_posix(),
                         INSTALLER_DIR=base.as_posix(), MODE=mode,
                         CALLS=calls.as_posix(), BRANCH=branch),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            return result.stdout.strip(), calls.read_text().splitlines()

    def test_current_branch_query_is_read_only_and_uses_actual_git_exit_status(self):
        for mode, expected in (("current", "current"), ("available", "available"),
                               ("failure", "unavailable"), ("empty", "unavailable"),
                               ("missing", "unavailable")):
            with self.subTest(mode=mode):
                output, calls = self.run_check(mode)
                self.assertEqual(output, expected)
                self.assertTrue(any("ls-remote --heads origin refs/heads/integration-testing" in call
                                    for call in calls))
                self.assertFalse(any("fetch" in call or "pull" in call for call in calls))

    def test_missing_checkout_or_detached_head_does_not_query_remote(self):
        for repository, branch in ((False, "integration-testing"), (True, "")):
            with self.subTest(repository=repository, branch=branch):
                output, calls = self.run_check("current", repository, branch)
                self.assertEqual(output, "unavailable")
                self.assertFalse(any("ls-remote" in call for call in calls))

    def test_timeout_stops_query_and_reports_unavailable(self):
        output, calls = self.run_check("timeout")
        self.assertEqual(output, "unavailable")
        self.assertIn("stopped", calls)


if __name__ == "__main__":
    unittest.main()
