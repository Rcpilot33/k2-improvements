import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import configure_update_manager as manager
import reset_update_cache


class TestUpdaterIsolation(unittest.TestCase):
    def test_test_mode_disables_only_the_fluidd_updater_and_stable_restores_it(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / 'updates/fluidd.cfg'
            other = root / 'updates/other.cfg'
            other.parent.mkdir()
            other.write_text('[update_manager another]\n')
            build = {'sha256': 'a' * 64, 'fluidd_commit': 'b' * 40}
            (root / 'k2-installed-build.json').write_text(json.dumps({'sha256': build['sha256']}))
            (root / 'k2-build.json').write_text(json.dumps({'commit': build['fluidd_commit']}))
            manager.configure(build, config, root)
            self.assertEqual(config.read_text(), manager.TEST_CONFIG)
            self.assertNotIn('[update_manager', config.read_text())
            self.assertEqual(other.read_text(), '[update_manager another]\n')
            manager.configure(build, config, root, check=True)
            manager.configure(None, config, root)
            self.assertIn('[update_manager fluidd]', config.read_text())
            self.assertIn('repo: Rcpilot33/fluidd', config.read_text())
            manager.configure(None, config, root, check=True)

    def test_unknown_build_cannot_disable_the_updater(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / 'fluidd.cfg'
            with self.assertRaises(ValueError):
                manager.configure({'sha256': 'a', 'fluidd_commit': 'b'}, config, root)
            self.assertFalse(config.exists())

    def test_absent_updater_is_accepted_only_for_verified_test_mode(self):
        self.assertFalse(reset_update_cache.matches('check-fresh', None))
        self.assertTrue(reset_update_cache.matches('check-fresh', None, True))
        with patch.object(manager, 'configured_build', return_value=None):
            self.assertFalse(manager.test_updates_disabled())


if __name__ == '__main__':
    unittest.main()
