import importlib.util
import pathlib
import stat
import tempfile
import unittest
from unittest import mock


HERE = pathlib.Path(__file__).parent
SPEC = importlib.util.spec_from_file_location(
    "reset_update_cache", HERE / "reset_update_cache.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ResetUpdateCacheTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.config = pathlib.Path(self.directory.name) / "fluidd.cfg"
        self.original = "[update_manager fluidd]\ntype: web\nrepo: Rcpilot33/fluidd\n"
        self.config.write_text(self.original, encoding="utf-8")
        self.config.chmod(0o640)
        self.mode = stat.S_IMODE(self.config.stat().st_mode)

    def test_disable_and_restore_preserve_config_and_mode(self):
        MODULE.disable(self.config)
        self.assertEqual(self.config.read_text(encoding="utf-8"), MODULE.DISABLED_CONFIG)
        self.assertEqual(MODULE.backup_path(self.config).read_text(encoding="utf-8"), self.original)
        MODULE.restore(self.config)
        self.assertEqual(self.config.read_text(encoding="utf-8"), self.original)
        self.assertEqual(stat.S_IMODE(self.config.stat().st_mode), self.mode)
        self.assertFalse(MODULE.backup_path(self.config).exists())

    def test_retry_restores_interrupted_backup_first(self):
        MODULE.disable(self.config)
        MODULE.disable(self.config)
        MODULE.restore(self.config)
        self.assertEqual(self.config.read_text(encoding="utf-8"), self.original)

    def test_missing_config_does_not_create_backup(self):
        self.config.unlink()
        with self.assertRaises(FileNotFoundError):
            MODULE.disable(self.config)
        self.assertFalse(MODULE.backup_path(self.config).exists())

    def test_failed_disable_restores_original_config(self):
        with mock.patch.object(MODULE, "write_atomic", side_effect=OSError("write failed")):
            with self.assertRaisesRegex(OSError, "write failed"):
                MODULE.disable(self.config)
        self.assertEqual(self.config.read_text(encoding="utf-8"), self.original)
        self.assertFalse(MODULE.backup_path(self.config).exists())

    def test_status_checks_reject_stale_remote_version(self):
        self.assertTrue(MODULE.matches("check-absent", None))
        self.assertFalse(MODULE.matches("check-absent", {"owner": "Rcpilot33"}))
        status = {
            "owner": "Rcpilot33", "repo_name": "fluidd",
            "version": "v1.37.4", "remote_version": "?",
        }
        self.assertTrue(MODULE.matches("check-fresh", status))
        self.assertTrue(MODULE.matches("check-fresh", dict(status, remote_version="v1.37.4")))
        self.assertFalse(MODULE.matches("check-fresh", dict(status, remote_version="v1.37.6")))
        self.assertFalse(MODULE.matches("check-fresh", dict(status, owner="Jacob10383")))
        self.assertFalse(MODULE.matches("check-fresh", dict(status, version=None, remote_version=None)))

    def test_fetch_reads_only_fluidd_updater(self):
        response = mock.MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = b'{"result":{"version_info":{"fluidd":{"remote_version":"?"},"klipper":{}}}}'
        with mock.patch.object(MODULE.urllib.request, "urlopen", return_value=response) as opener:
            self.assertEqual(MODULE.fetch_fluidd_status("http://127.0.0.1:7125"), {"remote_version": "?"})
        opener.assert_called_once_with("http://127.0.0.1:7125/machine/update/status", timeout=5)


if __name__ == "__main__":
    unittest.main()
