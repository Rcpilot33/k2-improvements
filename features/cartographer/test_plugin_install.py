"""Exercise plugin migration against local Git repositories, never a printer."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
FEATURE = ROOT / "features/cartographer"
BRANCH = "k2-cartographer-upstream-integration"
URL = "https://github.com/Rcpilot33/cartographer3d-plugin.git"
BASH = shutil.which("bash") or "C:/Program Files/Git/bin/bash.exe"


@unittest.skipUnless(Path(BASH).exists() and shutil.which("git"), "Git and bash required")
class PluginInstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="cartographer-install-test-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.source = self.base / "source"
        self.dest = self.base / "plugin"
        self.env = os.environ.copy()
        self.env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=str(self.base / "gitconfig"))
        self.git("init", "-b", "main", str(self.source), cwd=self.base)
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "user.name", "Plugin test")
        self.git("config", "core.hooksPath", str(self.base / "no-hooks"))
        self.git("commit", "--allow-empty", "-m", "base")
        self.old = self.git("rev-parse", "HEAD").stdout.strip()
        self.git("checkout", "-b", BRANCH)
        self.git("commit", "--allow-empty", "-m", "integration")
        self.target = self.git("rev-parse", "HEAD").stdout.strip()
        self.git("config", "--global", "protocol.file.allow", "always")
        self.git("config", "--global", "url." + self.source.as_uri() + ".insteadOf", URL)

    def git(self, *args, cwd=None):
        return subprocess.run(["git", *args], cwd=cwd or self.source, env=self.env,
                              text=True, capture_output=True, check=True)

    def existing(self):
        self.git("clone", "--branch", "main", str(self.source), str(self.dest))
        self.git("remote", "set-url", "origin",
                 "https://github.com/Jacob10383/cartographer3d-plugin.git", cwd=self.dest)

    def install(self, success=True):
        result = subprocess.run([BASH, str(FEATURE / "install_plugin.sh"), self.dest.as_posix()],
                                env=self.env, capture_output=True, text=True)
        self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr)

    def test_fresh_clone(self):
        self.install()
        self.assertEqual(self.git("rev-parse", "HEAD", cwd=self.dest).stdout.strip(), self.target)
        self.assert_future_branch_visible()

    def assert_future_branch_visible(self):
        self.assertEqual(self.git("config", "--get", "remote.origin.fetch", cwd=self.dest).stdout.strip(),
                         "+refs/heads/*:refs/remotes/origin/*")
        self.git("branch", "release-fixture")
        self.git("fetch", "origin", cwd=self.dest)
        self.assertEqual(self.git("rev-parse", "origin/release-fixture", cwd=self.dest).stdout.strip(),
                         self.target)

    def test_lowercase_origin_and_narrow_refspec_migration(self):
        self.existing()
        self.git("remote", "set-url", "origin",
                 "https://github.com/jacob10383/cartographer3d-plugin.git", cwd=self.dest)
        self.git("config", "remote.origin.fetch", "+refs/heads/main:refs/remotes/origin/main", cwd=self.dest)
        self.install()
        self.assertEqual(self.git("config", "--get", "remote.origin.url", cwd=self.dest).stdout.strip(), URL)
        self.assert_future_branch_visible()

    def test_existing_migration_and_repeat(self):
        self.existing()
        self.install()
        self.install()
        self.assertEqual(self.git("rev-parse", "HEAD", cwd=self.dest).stdout.strip(), self.target)
        self.assertEqual(self.git("rev-parse", "main", cwd=self.dest).stdout.strip(), self.old)
        self.assertEqual(self.git("rev-parse", "--abbrev-ref", "@{upstream}", cwd=self.dest).stdout.strip(),
                         "origin/" + BRANCH)
        self.assertEqual(self.git("remote", "get-url", "origin", cwd=self.dest).stdout.strip(),
                         self.source.as_uri())

    def test_dirty_checkout_is_preserved(self):
        self.existing()
        (self.dest / "local.cfg").write_text("preserve me", encoding="utf-8")
        self.install(False)
        self.assertEqual((self.dest / "local.cfg").read_text(), "preserve me")
        self.assertEqual(self.git("rev-parse", "HEAD", cwd=self.dest).stdout.strip(), self.old)

    def test_divergent_commit_is_preserved(self):
        self.existing()
        self.git("-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                 "commit", "--allow-empty", "-m", "local", cwd=self.dest)
        before = self.git("rev-parse", "HEAD", cwd=self.dest).stdout
        self.install(False)
        self.assertEqual(self.git("rev-parse", "HEAD", cwd=self.dest).stdout, before)

    def test_non_repository_is_preserved(self):
        self.dest.mkdir()
        self.install(False)
        self.assertTrue(self.dest.is_dir())

    def test_unknown_origin_is_preserved(self):
        self.existing()
        self.git("remote", "set-url", "origin", "https://example.invalid/plugin.git", cwd=self.dest)
        self.install(False)
        self.assertEqual(self.git("rev-parse", "HEAD", cwd=self.dest).stdout.strip(), self.old)

    def test_divergent_destination_branch_is_preserved(self):
        self.existing()
        self.git("checkout", "-b", BRANCH, cwd=self.dest)
        self.git("-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                 "commit", "--allow-empty", "-m", "local branch", cwd=self.dest)
        before = self.git("rev-parse", "HEAD", cwd=self.dest).stdout
        self.git("checkout", "main", cwd=self.dest)
        self.install(False)
        self.assertEqual(self.git("rev-parse", BRANCH, cwd=self.dest).stdout, before)

if __name__ == "__main__":
    unittest.main()
