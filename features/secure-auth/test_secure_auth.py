"""Exercise installation and recovery with a temporary Dropbear service."""

from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


HERE = Path(__file__).resolve().parent
BASH = shutil.which("bash") or "C:/Program Files/Git/bin/bash.exe"
ORIGINAL = "#!/bin/sh\necho original >> restarts\n"
MANAGED = "#!/bin/sh\n# k2-improvements: secure-auth installed\necho managed >> restarts\n"


@unittest.skipUnless(Path(BASH).is_file(), "requires Bash")
class SecureAuthTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        # Use relative paths so the shell fixture also runs under Git Bash.
        script = (HERE / "install.sh").read_text().replace("/rom/etc/", "./rom/etc/")
        script = script.replace("=/etc/", "=./etc/").replace(" -d /etc/", " -d ./etc/")
        self.put("install.sh", script)
        self.put("dropbear.init", MANAGED)
        self.service = self.put("etc/init.d/dropbear", ORIGINAL)
        self.key = self.put("etc/dropbear/authorized_keys", "ssh-ed25519 " + "A" * 48 + "\n")
        self.backup = self.root / "etc/dropbear/before-secure-auth.init"

    def put(self, name, content):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content.encode())
        path.chmod(0o755)
        return path

    def invoke(self, *args, success=True):
        result = subprocess.run(
            [BASH, "-c", 'pidof() { return 1; }; . ./install.sh "$@"', "install.sh", *args],
            cwd=self.root, capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr)

    def test_reinstall_keeps_original_and_restore_keeps_keys(self):
        self.invoke()
        self.invoke()
        self.assertEqual(self.backup.read_text(), ORIGINAL)
        self.assertEqual(self.service.read_text(), MANAGED)
        self.invoke("--restore")
        self.invoke("--restore")
        self.assertEqual(self.service.read_text(), ORIGINAL)
        self.assertTrue(self.key.exists())
        self.assertEqual((self.root / "restarts").read_text().splitlines(),
                         ["managed", "managed", "original"])

    def test_legacy_install_uses_firmware_original_when_available(self):
        self.put("etc/init.d/dropbear", MANAGED)
        self.invoke("--restore", success=False)
        self.assertEqual(self.service.read_text(), MANAGED)
        self.put("rom/etc/init.d/dropbear", ORIGINAL)
        self.invoke("--restore")
        self.assertEqual(self.service.read_text(), ORIGINAL)

    def test_repair_after_ota_saves_current_firmware_script(self):
        self.invoke()
        replacement = ORIGINAL.replace("original", "upgraded")
        self.put("etc/init.d/dropbear", replacement)
        self.invoke()
        self.invoke("--restore")
        self.assertEqual(self.service.read_text(), replacement)

    def test_failed_restore_puts_key_only_script_back(self):
        self.invoke()
        self.put("etc/dropbear/before-secure-auth.init", ORIGINAL + "exit 1\n")
        self.invoke("--restore", success=False)
        self.assertEqual(self.service.read_text(), MANAGED)
        self.assertEqual((self.root / "restarts").read_text().splitlines(),
                         ["managed", "original", "managed"])

    def test_failed_restart_puts_previous_script_back_and_restarts_it(self):
        self.put("dropbear.init", MANAGED + "exit 1\n")
        self.invoke(success=False)
        self.assertEqual(self.service.read_text(), ORIGINAL)
        self.assertEqual((self.root / "restarts").read_text().splitlines(), ["managed", "original"])

    def test_missing_key_leaves_ssh_alone(self):
        self.key.unlink()
        self.invoke(success=False)
        self.assertEqual(self.service.read_text(), ORIGINAL)
        self.assertFalse(self.backup.exists())
