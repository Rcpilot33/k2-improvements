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

    def test_installed_check_requires_both_exact_zip_and_source_revision(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertFalse(download_build.check_installed(self.build(), root))
            (root / 'k2-installed-build.json').write_text(json.dumps({'sha256': self.build()['sha256']}))
            (root / 'k2-build.json').write_text(json.dumps({'commit': 'a' * 40}))
            self.assertTrue(download_build.check_installed(self.build(), root))
            (root / 'k2-build.json').write_text(json.dumps({'commit': 'b' * 40}))
            self.assertFalse(download_build.check_installed(self.build(), root))
            self.assertTrue(download_build.check_installed(None, root))


if __name__ == '__main__':
    unittest.main()
