"""Check preserved packages and individual OTA losses on a temporary filesystem."""
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest


HERE = Path(__file__).resolve().parent
BASH = shutil.which("bash") or "C:/Program Files/Git/bin/bash.exe"


@unittest.skipUnless(Path(BASH).is_file(), "requires Bash")
class BootstrapTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.base = Path(directory.name)
        self.fs = self.base / "fs"
        # Relocate the printer's absolute paths. Model link destinations as
        # text so this fixture also runs on Windows without symlink privileges.
        checker = (HERE / "prerequisites.sh").read_text()
        checker = re.sub(r'(?<![\w/.])/(etc|mnt|usr|opt)(?=[/" ])', r'./fs/\1', checker)
        (self.base / "check.sh").write_bytes(checker.encode("utf-8"))
        self.command = """
. ./check.sh
bootstrap_link_ready() {
    if [ "$1" = ./fs/opt ]; then [ "$2" = ./fs/mnt/UDISK/opt ]; return; fi
    [ "$(cat "$1" 2>/dev/null)" = "$2" ]
}
bootstrap_entware_ready .
"""
        packages = "entware-opt git git-http wget-ssl curl jq unzip openssh-sftp-server".split()
        self.put("opt/bin/opkg", "#!/bin/sh\nprintf '%s - 1.0\\n' " + " ".join(packages) + "\n")
        self.put("opt/etc/opkg.conf", "fixture")
        self.put("opt/bin/git", "#!/bin/sh\necho ./fs/git-helpers\n")
        for path in ("opt/bin/wget", "opt/bin/curl", "opt/bin/jq", "opt/bin/unzip", "git-helpers/git-remote-https",
                     "opt/libexec/sftp-server", "opt/etc/init.d/rc.unslung", "etc/init.d/unslung"):
            self.put(path)
        (self.base / "entware").mkdir()
        shutil.copyfile(self.fs / "etc/init.d/unslung", self.base / "entware/unslung.init")
        self.put("etc/profile.d/entware.sh", 'export PATH="./fs/opt/bin:./fs/opt/sbin:$PATH"')
        for path, target in (("usr/libexec/sftp-server", "opt/libexec/sftp-server"),
                             ("etc/rc.d/S99unslung", "etc/init.d/unslung"),
                             ("etc/rc.d/K01unslung", "etc/init.d/unslung")):
            self.put(path, "./fs/" + target)

    def put(self, path, content="#!/bin/sh\nexit 0\n"):
        target = self.fs / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content.encode("utf-8"))
        target.chmod(0o755)

    def check(self):
        return subprocess.run([BASH, "-c", self.command], cwd=self.base,
                              capture_output=True, text=True, timeout=10)

    def test_package_database_alone_cannot_hide_missing_tools_or_boot_links(self):
        result = self.check()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for path in ("opt/bin/jq", "git-helpers/git-remote-https", "etc/profile.d/entware.sh",
                     "usr/libexec/sftp-server", "etc/rc.d/S99unslung", "etc/rc.d/K01unslung"):
            with self.subTest(path=path):
                target = self.fs / path
                content = target.read_text()
                target.unlink()
                self.assertNotEqual(self.check().returncode, 0)
                self.put(path, content)
