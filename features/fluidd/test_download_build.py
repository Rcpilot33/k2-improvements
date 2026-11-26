import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import download_build


class PinnedBuildTests(unittest.TestCase):
    def build(self, payload=b'test archive'):
        return dict(installer_branch='fluidd-ui-consolidation',
                    url='https://github.com/Rcpilot33/fluidd/releases/download/k2-cards-test-1/fluidd.zip',
                    sha256=hashlib.sha256(payload).hexdigest(), fluidd_commit='a' * 40)

    def test_only_the_named_test_branch_selects_the_prerelease(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory) / 'test-release.json'
            manifest.write_text(json.dumps(self.build()))
            self.assertEqual(download_build.read_build(manifest, 'fluidd-ui-consolidation'), self.build())
            for branch in ('main', 'integration-testing', 'other', ''):
                self.assertIsNone(download_build.read_build(manifest, branch))

    def test_rejects_unexpected_download_hosts_or_missing_checksums(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory) / 'test-release.json'
            for override in ({'url': 'http://127.0.0.1/internal'}, {'sha256': ''},
                             {'url': 'https://github.com/other/fluidd/releases/download/test/fluidd.zip'}):
                manifest.write_text(json.dumps(dict(self.build(), **override)))
                with self.assertRaises(ValueError):
                    download_build.read_build(manifest, 'fluidd-ui-consolidation')

    def test_verifies_download_and_removes_partial_or_mismatched_zip(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'fluidd.zip'
            with patch.object(download_build.urllib.request, 'urlopen', return_value=io.BytesIO(b'test archive')):
                download_build.download(self.build(), target)
            self.assertEqual(target.read_bytes(), b'test archive')
            with patch.object(download_build.urllib.request, 'urlopen', return_value=io.BytesIO(b'wrong')):
                with self.assertRaises(ValueError):
                    download_build.download(self.build(), target)
            self.assertFalse(target.exists())

    def test_stable_install_uses_the_pinned_url_and_rejects_other_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'fluidd.zip'
            with patch.object(download_build.urllib.request, 'urlopen',
                              return_value=io.BytesIO(b'wrong stable zip')) as fetch:
                with self.assertRaisesRegex(ValueError, 'checksum'):
                    download_build.download(None, target)
            self.assertEqual(fetch.call_args[0][0].full_url, download_build.STABLE_BUILD['url'])
            self.assertFalse(target.exists())

    def test_installed_check_requires_both_exact_zip_and_source_revision(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertFalse(download_build.check_installed(self.build(), root))
            (root / 'k2-installed-build.json').write_text(json.dumps({'sha256': self.build()['sha256']}))
            (root / 'k2-build.json').write_text(json.dumps({'commit': 'a' * 40}))
            self.assertTrue(download_build.check_installed(self.build(), root))
            (root / 'k2-build.json').write_text(json.dumps({'commit': 'b' * 40}))
            self.assertFalse(download_build.check_installed(self.build(), root))
            self.assertFalse(download_build.check_installed(None, root))

    def test_stable_transition_rejects_test_missing_and_mismatched_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertFalse(download_build.check_installed(None, root))
            for version, accepted in [('v1.37.5', True), ('v1.38.0', True),
                                      ('v1.37.5-rc.2', False),
                                      ('k2-cards-test-3', False), ('', False)]:
                (root / '.version').write_text(version + '\n')
                release = dict(version=version, project_owner='Rcpilot33', project_name='fluidd')
                (root / 'release_info.json').write_text(json.dumps(release))
                self.assertEqual(download_build.check_installed(None, root), accepted, version)
            (root / '.version').write_text('v1.37.5\n')
            for release in (dict(version='v1.37.5-rc.2', project_owner='Rcpilot33', project_name='fluidd'),
                            dict(version='v1.37.5', project_owner='other', project_name='fluidd'), []):
                (root / 'release_info.json').write_text(json.dumps(release))
                self.assertFalse(download_build.check_installed(None, root))


if __name__ == '__main__':
    unittest.main()
