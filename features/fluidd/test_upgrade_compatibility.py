"""Run against the actual release ZIP and unchanged legacy overlay installer."""
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from download_build import read_build, check_installed
from prepare_bundle import prepare
from configure_update_manager import configure, TEST_CONFIG

class CompatibilityTests(unittest.TestCase):
    @unittest.skipUnless(os.environ.get('FLUIDD_TEST_ARCHIVE'), 'Set FLUIDD_TEST_ARCHIVE to the release ZIP')
    def test_release_and_old_installer(self):
        archive = Path(os.environ['FLUIDD_TEST_ARCHIVE']).resolve()
        build = read_build(HERE / 'test-release.json', 'fluidd-upgrade-compatibility-test')
        self.assertEqual(hashlib.sha256(archive.read_bytes()).hexdigest(), build['sha256'])
        for branch in ('main', 'integration-testing', 'fluidd-ui-consolidation'):
            self.assertIsNone(read_build(HERE / 'test-release.json', branch))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'ui'
            root.mkdir()
            prepare(archive, root)
            self.assertTrue(check_installed(build, root))
            self.assertEqual((root / 'k2-ui-overlay-support.txt').read_text().strip(), '8')
            self.assertEqual((root / 'k2-settings-api.txt').read_text().strip(), '1')
            conf = Path(directory) / 'fluidd.cfg'
            configure(build, conf, root)
            self.assertEqual(conf.read_text(), TEST_CONFIG)
            configure(None, conf, root)
            self.assertIn('[update_manager fluidd]', conf.read_text())
            # Version must differ from the old bundled v1.37.4, proving the
            # marker short-circuit preserves future versions too.
            (root / '.version').write_text('v1.37.5\n')
            before = {p.relative_to(root): hashlib.sha256(p.read_bytes()).hexdigest()
                      for p in root.rglob('*') if p.is_file() and p.name != 'release_info.json'}
            script = HERE.parents[1] / 'installer/extras/fluidd-ui-overlay/install.sh'
            env = dict(os.environ, FLUIDD_DIR=root.as_posix(), K2_SKIP_NGINX_RESTART='1')
            if os.name == 'nt':
                bash = 'C:/Program Files/Git/bin/bash.exe'
                # Git Bash paths must be translated for native Windows Python.
                env['TEST_PYTHON'] = sys.executable.replace('\\', '/')
                command = '''python3() { local args=(); for arg in "$@"; do
case "$arg" in /[a-z]/*) args+=("$(cygpath -w "$arg")");; *) args+=("$arg");; esac
done; "$TEST_PYTHON" "${args[@]}"; }; export -f python3
bash "$1"'''
                run = subprocess.run([bash, '-c', command, 'test', script.as_posix()], env=env, text=True, capture_output=True)
            else:
                run = subprocess.run(['sh', str(script)], env=env, text=True, capture_output=True)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn('already installed', run.stdout)
            after = {p.relative_to(root): hashlib.sha256(p.read_bytes()).hexdigest()
                     for p in root.rglob('*') if p.is_file() and p.name != 'release_info.json'}
            self.assertEqual(before, after)
            self.assertFalse(Path(str(root) + '.before-k2-ui-overlay').exists())

if __name__ == '__main__':
    unittest.main()
