import json
from pathlib import Path
import tempfile
import unittest
import shutil
import subprocess
from unittest.mock import patch
from zipfile import ZipFile

import configure_device
import prepare_bundle
import get_latest_release
import io
from unittest.mock import Mock, call


class InstallationTests(unittest.TestCase):
    def test_device_install_is_idempotent_and_preserves_config(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            components = root / 'moonraker/moonraker/components'
            components.mkdir(parents=True)
            config = root / 'config'
            config.mkdir()
            main = config / 'moonraker.conf'
            original = '[server]\nport: 7125\n# user comment\n'
            main.write_text(original)
            configure_device.configure(root / 'moonraker', config)
            once = main.read_text()
            configure_device.configure(root / 'moonraker', config)
            self.assertEqual(once, main.read_text())
            self.assertTrue(once.startswith(original))
            self.assertEqual(once.count('[include k2_device.conf]'), 1)
            self.assertEqual((components / 'k2_device.py').read_bytes(),
                             Path(configure_device.__file__).with_name('k2_device.py').read_bytes())
            configure_device.verify(root / 'moonraker', config)

    @unittest.skipUnless(shutil.which('git'), 'git required')
    def test_owned_bridge_does_not_dirty_the_moonraker_checkout(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo = root / 'moonraker'
            (repo / 'moonraker/components').mkdir(parents=True)
            config = root / 'config'
            config.mkdir()
            (config / 'moonraker.conf').write_text('[server]\n')
            hooks = root / 'empty-hooks'
            hooks.mkdir()
            subprocess.run(['git', '-c', f'core.hooksPath={hooks.as_posix()}',
                            'init', '--quiet', str(repo)], check=True)
            configure_device.configure(repo, config)
            subprocess.run(['git', '-C', str(repo), 'check-ignore', '--quiet',
                            'moonraker/components/k2_device.py'], check=True)
            configure_device.configure(repo, config)
            self.assertEqual((repo / '.git/info/exclude').read_text().count(
                '/moonraker/components/k2_device.py'), 1)

    def test_installer_downloads_only_the_exact_zip_asset(self):
        release = {'assets': [
            {'name': 'fluidd.zip', 'browser_download_url': 'https://example.invalid/build', 'size': 1},
            {'name': 'fluidd.zip.sha256', 'browser_download_url': 'https://example.invalid/hash', 'size': 1}
        ]}
        with patch.object(get_latest_release, 'fetch_latest_release', return_value=release), \
                patch.object(get_latest_release, 'download_file') as download:
            get_latest_release.download_latest_release('Rcpilot33/fluidd', asset_name='fluidd.zip')
            download.assert_called_once_with('https://example.invalid/build', 'fluidd.zip', None)

    def test_conflicts_are_detected_before_modification(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'moonraker/components').mkdir(parents=True)
            config = root / 'config'
            config.mkdir()
            (config / 'moonraker.conf').write_text('[server]\n')
            (config / 'k2_device.conf').write_text('# user settings\n[k2_device]\n')
            with self.assertRaises(ValueError):
                configure_device.configure(root, config)
            self.assertFalse((root / 'moonraker/components/k2_device.py').exists())

    def make_bundle(self, archive, **overrides):
        entries = {'.version': 'v1.37.5', 'release_info.json': json.dumps({
            'project_name': 'fluidd', 'project_owner': 'Rcpilot33', 'version': 'v1.37.5'}),
            'k2-ui-overlay-support.txt': '8\n', 'k2-settings-api.txt': '1', 'k2-device-cards-api.txt': '1',
            'index.html': '<html></html>', 'sw.js': '/* worker */'}
        entries.update(overrides)
        with ZipFile(archive, 'w') as bundle:
            for name, value in entries.items():
                bundle.writestr(name, value)

    def test_validates_capabilities_before_extraction(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            stage = root / 'stage'
            stage.mkdir()
            archive = root / 'fluidd.zip'
            for overrides in ({'k2-ui-overlay-support.txt': '9'},
                              {'k2-ui-overlay-support.txt': '8\r\n'},
                              {'k2-settings-api.txt': ''}, {'../escape': 'bad'},
                              {'k2-device-cards-api.txt': '2'}, {'sw.js': ''}):
                self.make_bundle(archive, **overrides)
                with self.assertRaises(ValueError):
                    prepare_bundle.prepare(archive, stage)
                self.assertEqual(list(stage.iterdir()), [])
            self.make_bundle(archive)
            prepare_bundle.prepare(archive, stage)
            self.assertTrue((stage / 'index.html').is_file())

    def test_ui_root_itself_gets_traversal_permissions_not_only_children(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            stage = root / 'stage'
            stage.mkdir(mode=0o700)
            archive = root / 'fluidd.zip'
            self.make_bundle(archive)
            with patch.object(Path, 'chmod', autospec=True) as chmod:
                prepare_bundle.prepare(archive, stage)
            self.assertIn(call(stage, 0o755), chmod.call_args_list)
            self.assertIn(call(stage / 'index.html', 0o644), chmod.call_args_list)

    def test_live_verifier_requires_nginx_to_serve_the_application(self):
        for page, valid in [(b'<div id="app"></div>', True), (b'403 Forbidden', False)]:
            opener = Mock()
            opener.open.side_effect = [io.BytesIO(json.dumps({'result': {'fans': {}, 'slots': []}}).encode()),
                                       io.BytesIO(page)]
            with patch.object(configure_device.urllib.request, 'build_opener', return_value=opener):
                if valid:
                    configure_device.verify_live()
                else:
                    with self.assertRaises(ValueError):
                        configure_device.verify_live()


if __name__ == '__main__':
    unittest.main()
