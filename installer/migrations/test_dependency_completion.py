"""Execute migration bookkeeping without touching printer state."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
BASH = shutil.which("bash") or "C:/Program Files/Git/bin/bash.exe"


@unittest.skipUnless(Path(BASH).exists(), "bash required")
class DependencyCompletionTests(unittest.TestCase):
    def run_mark(self, failed="", parent="cartographer"):
        with tempfile.TemporaryDirectory(prefix="k2-migration-test-") as directory:
            env = os.environ.copy()
            env.update(MIGRATION_STATE_DIR=Path(directory).as_posix(),
                       UPDATE_SCRIPT=(ROOT / "installer/menus/update.sh").as_posix(),
                       FAILED_COMPONENT=failed, PARENT_COMPONENT=parent)
            script = '''
. "$UPDATE_SCRIPT"
migration_catalog() {
    printf '%s\\n' 'carto|cartographer|check|reason' 'save|save-config-restart|check|reason' 'guard|virtual-sdcard-guard|check|reason' 'macro|macros|check|reason'
}
migration_component_installed() { [ "$1" != "$FAILED_COMPONENT" ]; }
warn() { printf '%s\\n' "$*" >&2; }
migration_mark_component_current "$PARENT_COMPONENT"
'''
            result = subprocess.run([BASH, "-c", script], env=env, capture_output=True, text=True)
            state = Path(directory) / "completed-migrations"
            completed = state.read_text().splitlines() if state.exists() else []
            return result, completed

    def test_cartographer_records_verified_dependencies(self):
        result, completed = self.run_mark()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(set(completed), {"carto", "save", "guard"})

    def test_missing_dependency_stays_pending(self):
        for name, missing in (("save-config-restart", "save"), ("virtual-sdcard-guard", "guard")):
            with self.subTest(name=name):
                result, completed = self.run_mark(failed=name)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("carto", completed)
                self.assertNotIn(missing, completed)
                self.assertIn("still appears incomplete", result.stderr)

    def test_failed_parent_does_not_acknowledge_dependencies(self):
        result, completed = self.run_mark(failed="cartographer")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(completed, [])

    def test_unrelated_component_does_not_acknowledge_dependencies(self):
        result, completed = self.run_mark(parent="macros")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(completed, ["macro"])


if __name__ == "__main__":
    unittest.main()
