import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("factory-reset-improved.sh")


class FactoryResetImprovedTests(unittest.TestCase):
    def setUp(self):
        self.shell = shutil.which("bash") or shutil.which("sh")
        if self.shell is None:
            git_for_windows_shell = Path(r"C:\Program Files\Git\bin\bash.exe")
            if git_for_windows_shell.is_file():
                self.shell = str(git_for_windows_shell)
        if self.shell is None:
            self.skipTest("sh is required")

    def _fixture_script(self, root: Path) -> Path:
        script = SCRIPT.read_text(encoding="utf-8")
        shell_root = root.as_posix()
        script = script.replace(
            "UDISK_ROOT=/mnt/UDISK", f"UDISK_ROOT='{shell_root}'", 1
        )
        script = script.replace(
            'if ! echo "all" | /usr/bin/nc -U /var/run/wipe.sock; then',
            "if ! true; then",
            1,
        )
        fixture = root.parent / "factory-reset-improved-fixture.sh"
        fixture.write_text(script, encoding="utf-8")
        return fixture

    def _run(self, fixture: Path, mode: str) -> subprocess.CompletedProcess:
        env = os.environ.copy()
        shell_tools = Path(self.shell).parent.parent / "usr" / "bin"
        if shell_tools.is_dir():
            env["PATH"] = f"{shell_tools}{os.pathsep}{env.get('PATH', '')}"
        return subprocess.run(
            [self.shell, str(fixture), mode],
            text=True,
            capture_output=True,
            check=False,
            env=env,
        )

    def test_dry_run_defers_live_creality_tree(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "UDISK"
            for name in ("root", "bin", "creality", "printer_data"):
                (root / name).mkdir(parents=True)
            (root / "creality/userdata/log").mkdir(parents=True)
            (root / "creality/userdata/log/app-server.log").write_text("active")
            fixture = self._fixture_script(root)

            result = self._run(fixture, "--dry-run")

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(f"DEFER:  {root.as_posix()}/creality", result.stdout)
            self.assertIn(f"REMOVE: {root.as_posix()}/printer_data", result.stdout)
            self.assertTrue((root / "creality/userdata/log/app-server.log").is_file())

    def test_run_preserves_stock_paths_and_removes_third_party_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "UDISK"
            for name in ("root", "bin", "creality", "printer_data", "ai_image"):
                (root / name).mkdir(parents=True)
            (root / "creality/userdata/log").mkdir(parents=True)
            (root / "creality/userdata/log/web-server.log").write_text("active")
            fixture = self._fixture_script(root)

            result = self._run(fixture, "--run")

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(f"Deferring: {root.as_posix()}/creality", result.stdout)
            self.assertTrue((root / "root").is_dir())
            self.assertTrue((root / "bin").is_dir())
            self.assertTrue((root / "creality/userdata/log/web-server.log").is_file())
            self.assertFalse((root / "printer_data").exists())
            self.assertFalse((root / "ai_image").exists())


if __name__ == "__main__":
    unittest.main()
