"""An editor installation must never replace a newer Fluidd build."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

HERE = Path(__file__).parent
BASH = shutil.which('bash') or 'C:/Program Files/Git/bin/bash.exe'


@unittest.skipUnless(Path(BASH).exists(), 'bash required')
class SettingsCapabilityTests(unittest.TestCase):
    def test_check_accepts_current_and_future_builds_without_changing_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            index = root / 'index.html'
            index.write_text('installed UI sentinel')
            for value, api, expected in [('8', '1', 0), ('9', '1', 0), ('10', '1', 0),
                                         ('8', '', 1), ('7', '1', 1), ('garbage', '1', 1), ('', '1', 1)]:
                (root / 'k2-settings-api.txt').write_text(api)
                (root / 'k2-ui-overlay-support.txt').write_text(value)
                before = {p.name: p.read_bytes() for p in root.iterdir()}
                result = subprocess.run([BASH, (HERE / 'install.sh').as_posix()],
                                        capture_output=True, text=True,
                                        env=dict(os.environ, FLUIDD_DIR=root.as_posix()))
                self.assertEqual(result.returncode, expected, result.stderr)
                self.assertEqual(before, {p.name: p.read_bytes() for p in root.iterdir()})


if __name__ == '__main__':
    unittest.main()
