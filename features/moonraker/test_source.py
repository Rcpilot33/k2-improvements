"""Disposable local Git repositories: no network or printer access."""
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("moonraker_source", Path(__file__).with_name("source.py"))
source = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(source)
META = '''BASE_CONFIG: dict = {"moonraker": {
    "origin": "https://github.com/Rcpilot33/moonraker.git",
    "primary_branch": "k2", "channel": "dev"}}
'''


class SourceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="k2-moonraker-test-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.repo = self.base / "installed"
        self.remote = self.base / "fork"
        self.backups = self.base / "recovery"
        hooks = self.base / "empty-hooks"
        hooks.mkdir()
        for repo in (self.repo, self.remote):
            subprocess.run(["git", "-c", f"core.hooksPath={hooks.as_posix()}",
                            "init", "-b", "k2", str(repo)], check=True, capture_output=True)
            source.git(repo, "config", "core.hooksPath", hooks.as_posix())
            source.git(repo, "config", "user.name", "K2 source test")
            source.git(repo, "config", "user.email", "test@example.invalid")
        self.common = Path("moonraker/components/update_manager/common.py")
        self.write_commit(self.repo, self.common, META.replace("Rcpilot33", "arksine"))
        self.original = source.git(self.repo, "rev-parse", "HEAD")
        source.git(self.remote, "fetch", str(self.repo), "k2")
        source.git(self.remote, "reset", "--hard", "FETCH_HEAD")
        self.write_commit(self.remote, self.common, META)
        source.git(self.repo, "remote", "add", "origin", "https://github.com/Jacob10383/moonraker.git")
        original_git = source.git

        def offline_git(repo, *args):
            args = tuple(str(self.remote) if x == source.ORIGIN else x for x in args) if args[0] == "fetch" else args
            return original_git(repo, *args)
        self.mock = patch.object(source, "git", side_effect=offline_git)
        self.mock.start()
        self.addCleanup(self.mock.stop)

    def write_commit(self, repo, path, content):
        target = repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        source.git(repo, "add", str(path))
        source.git(repo, "commit", "-m", "Test fixture")

    def migrate(self):
        source.select_source(self.repo, self.backups, migrate=True)

    def assert_untouched(self):
        self.assertEqual(source.git(self.repo, "rev-parse", "HEAD"), self.original)
        self.assertIn("Jacob10383", source.git(self.repo, "remote", "get-url", "origin"))

    def test_migrates_fast_forward_and_preserves_external_configuration(self):
        config = self.base / "moonraker.conf"
        config.write_bytes(b"[server]\n# keep my configuration\n")
        self.migrate()
        self.assertTrue(source.current(self.repo))
        self.assertEqual(config.read_bytes(), b"[server]\n# keep my configuration\n")
        self.assertEqual(len(list(self.backups.glob("*/receipt.json"))), 1)
        self.migrate()
        self.assertTrue(source.current(self.repo))

    def test_dirty_checkout_refused(self):
        (self.repo / self.common).write_text("local edit")
        with self.assertRaisesRegex(RuntimeError, "local changes"):
            self.migrate()
        self.assert_untouched()

    def test_untracked_files_refused(self):
        (self.repo / "custom.py").write_text("keep")
        with self.assertRaisesRegex(RuntimeError, "untracked"):
            self.migrate()
        self.assert_untouched()

    def test_unknown_origin_refused(self):
        source.git(self.repo, "remote", "set-url", "origin", "https://example.invalid/moonraker")
        with self.assertRaisesRegex(RuntimeError, "Unrecognized"):
            self.migrate()
        self.assertEqual(source.git(self.repo, "rev-parse", "HEAD"), self.original)

    def test_wrong_branch_refused(self):
        source.git(self.repo, "checkout", "-b", "master")
        with self.assertRaisesRegex(RuntimeError, "not on k2"):
            self.migrate()
        self.assert_untouched()

    def test_diverged_checkout_refused(self):
        self.write_commit(self.repo, Path("custom.py"), "local commit")
        head = source.git(self.repo, "rev-parse", "HEAD")
        with self.assertRaises(subprocess.CalledProcessError):
            self.migrate()
        self.assertEqual(source.git(self.repo, "rev-parse", "HEAD"), head)
        self.assertIn("Jacob10383", source.git(self.repo, "remote", "get-url", "origin"))

    def test_unpublished_metadata_refused(self):
        self.write_commit(self.remote, self.common, META.replace("Rcpilot33", "arksine"))
        with self.assertRaisesRegex(RuntimeError, "publish"):
            self.migrate()
        self.assert_untouched()

    def test_dependency_upgrade_refused_in_migration(self):
        self.write_commit(self.remote, Path("scripts/moonraker-requirements.txt"), "new-dependency")
        with self.assertRaisesRegex(RuntimeError, "dependencies"):
            self.migrate()
        self.assert_untouched()

    def test_stock_install_not_migrated(self):
        with self.assertRaisesRegex(RuntimeError, "stock"):
            source.select_source(self.base / "stock", self.backups, migrate=True)

    def test_origin_validation_is_exact(self):
        self.assertTrue(source.known_origin("git@github.com:Rcpilot33/moonraker.git"))
        self.assertFalse(source.known_origin("https://example.com/Jacob10383/moonraker"))
        self.assertFalse(source.known_origin("https://github.com/Jacob10383/moonraker-other.git"))


if __name__ == "__main__":
    unittest.main()
