"""Execute the menu's migration scan without touching printer state."""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
BASH = shutil.which("bash") or "C:/Program Files/Git/bin/bash.exe"


@unittest.skipUnless(Path(BASH).exists(), "bash required")
class PendingScanTests(unittest.TestCase):
    def run_scan(self, catalog, completed=None, installed=(), present=(),
                 snapshot=(), eligible=False, script="migration_pending_entries"):
        with tempfile.TemporaryDirectory(prefix="k2-pending-scan-") as directory:
            base = Path(directory)
            (base / "catalog").write_text("\n".join(catalog) + "\n", newline="\n")
            if completed is not None:
                (base / "completed-migrations").write_text(
                    "\n".join(completed) + "\n", newline="\n"
                )
            for name, values in (("installed", installed), ("present", present),
                                 ("installed-before-update", snapshot)):
                (base / name).write_text("\n".join(values) + "\n", newline="\n")
            calls = base / "calls"
            calls.touch()
            shell = '''
set -eu
. "$UPDATE_SCRIPT"
migration_catalog() { cat "$MIGRATION_STATE_DIR/catalog"; }
migration_component_installed() {
    printf 'installed:%s\\n' "$1" >> "$CALLS"
    grep -qxF "$1" "$MIGRATION_STATE_DIR/installed"
}
migration_component_present() {
    printf 'present:%s\\n' "$1" >> "$CALLS"
    grep -qxF "$1" "$MIGRATION_STATE_DIR/present"
}
is_start_print_fast_stop_eligible() {
    printf 'eligible\\n' >> "$CALLS"
    [ "$ELIGIBLE" = 1 ]
}
# The scan must not reopen the completion list through this per-id helper.
migration_is_complete() {
    printf 'per-id-completion\\n' >> "$CALLS"
    return 1
}
''' + script
            result = subprocess.run(
                [BASH, "-c", shell], capture_output=True, text=True, timeout=15,
                env=dict(os.environ,
                         UPDATE_SCRIPT=(ROOT / "installer/menus/update.sh").as_posix(),
                         MIGRATION_STATE_DIR=base.as_posix(), CALLS=calls.as_posix(),
                         ELIGIBLE="1" if eligible else "0"),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            return result.stdout.splitlines(), calls.read_text().splitlines()

    def test_current_installation_does_not_probe_completed_components(self):
        catalog = [f"done-{i}|macros|check|reason" for i in range(160)]
        output, calls = self.run_scan(
            catalog, completed=[f"done-{i}" for i in range(160)],
            installed=("macros",), script="migration_pending_component_count",
        )
        self.assertEqual(output, ["0"])
        self.assertEqual(calls, [])

    def test_each_uncompleted_component_is_probed_once_including_absent_ones(self):
        catalog = ["done|cartographer|check|done"] + [
            f"new-{i}|{component}|check|reason"
            for i, component in enumerate(("macros", "fluidd", "macros", "fluidd"))
        ]
        output, calls = self.run_scan(catalog, completed=("done",), installed=("macros",))
        self.assertEqual(output, ["new-0|macros|reason", "new-2|macros|reason"])
        self.assertEqual(calls, ["installed:macros", "installed:fluidd", "present:fluidd"])

    def test_missing_or_empty_completion_file_keeps_all_uncompleted_entries(self):
        for completed in (None, ()):
            with self.subTest(completed=completed):
                output, calls = self.run_scan(
                    ["a|macros|check|first", "b|macros|check|second|detail"],
                    completed=completed, installed=("macros",),
                )
                self.assertEqual(output, ["a|macros|first", "b|macros|second|detail"])
                self.assertEqual(calls, ["installed:macros"])

    def test_partial_install_and_pre_update_snapshot_still_offer_repairs(self):
        output, calls = self.run_scan(
            ["partial|macros|check|repair", "snapshot|cartographer|check|repair"],
            present=("macros",), snapshot=("cartographer",),
        )
        self.assertEqual(output, ["partial|macros|repair", "snapshot|cartographer|repair"])
        self.assertEqual(calls, ["installed:macros", "present:macros",
                                 "installed:cartographer", "present:cartographer"])

    def test_snapshot_cannot_bypass_fast_stop_firmware_gate(self):
        for eligible in (False, True):
            with self.subTest(eligible=eligible):
                output, calls = self.run_scan(
                    ["a|start-print-fast-stop|check|first",
                     "b|start-print-fast-stop|check|second"],
                    snapshot=("start-print-fast-stop",), eligible=eligible,
                )
                self.assertEqual(output, ["a|start-print-fast-stop|first",
                                          "b|start-print-fast-stop|second"] if eligible else [])
                self.assertEqual(calls, ["eligible"])

    def test_component_order_and_unique_count_stay_unchanged(self):
        catalog = ["f|fluidd|check|reason", "m|macros|check|reason",
                   "c|cartographer|check|reason", "m2|macros|check|reason"]
        for command, expected in (
            ("migration_pending_components", ["cartographer", "macros", "fluidd"]),
            ("migration_pending_component_count", ["3"]),
        ):
            with self.subTest(command=command):
                output, calls = self.run_scan(
                    catalog, installed=("fluidd", "macros", "cartographer"), script=command,
                )
                self.assertEqual(output, expected)
                self.assertEqual(calls, ["installed:fluidd", "installed:macros",
                                         "installed:cartographer"])

    def test_applicability_and_completion_are_refreshed_on_every_scan(self):
        output, calls = self.run_scan(
            ["a|macros|check|reason"], script='''
migration_pending_component_count
printf 'macros\\n' > "$MIGRATION_STATE_DIR/installed"
migration_pending_component_count
printf 'a\\n' > "$MIGRATION_COMPLETED"
migration_pending_component_count
''',
        )
        self.assertEqual(output, ["0", "1", "0"])
        self.assertEqual(calls, ["installed:macros", "present:macros", "installed:macros"])

    def test_real_catalog_pending_results_match_previous_selection_rules(self):
        catalog = [
            line for line in (ROOT / "installer/migrations/catalog.sh").read_text().splitlines()
            if line.count("|") >= 3 and not line.startswith("#")
        ]
        ids = {line.split("|", 1)[0] for line in catalog}
        installed = ("macros", "cartographer", "fluidd", "kamp-adaptive-purge")
        for completed in (None, (), tuple(sorted(ids)[::2]), tuple(ids)):
            with self.subTest(completed_count=None if completed is None else len(completed)):
                expected = []
                for line in catalog:
                    migration_id, component, _detector, reason = line.split("|", 3)
                    if component in installed and migration_id not in (completed or ()):
                        expected.append(f"{migration_id}|{component}|{reason}")
                output, calls = self.run_scan(catalog, completed=completed, installed=installed)
                self.assertEqual(output, expected)
                probed = [call for call in calls if call.startswith("installed:")]
                self.assertEqual(len(probed), len(set(probed)))

    def test_firmware_eligibility_is_not_cached_between_scans(self):
        output, calls = self.run_scan(
            ["a|start-print-fast-stop|check|reason"], script='''
migration_pending_component_count
ELIGIBLE=1
migration_pending_component_count
''',
        )
        self.assertEqual(output, ["0", "1"])
        self.assertEqual(calls, ["eligible", "eligible"])


if __name__ == "__main__":
    unittest.main()
