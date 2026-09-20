"""Execute the read-only firmware display detector without a printer."""
import os
from pathlib import Path
import shutil
import subprocess
import unittest

BASH = shutil.which("bash") or "C:/Program Files/Git/bin/bash.exe"
SOURCE = Path(__file__).with_name("cartographer.sh")


@unittest.skipUnless(Path(BASH).exists(), "bash required")
class CartographerVersionTests(unittest.TestCase):
    def detect(self, version, fallback=False):
        source = SOURCE.read_text()
        if fallback:
            # Use a shell-owned fixture in place of the printer's fixed log path.
            source = source.replace(
                "local k=/mnt/UDISK/printer_data/logs/klippy.log",
                'local k="$fixture"',
            )
            setup = '''
fixture=$(mktemp)
trap 'rm -f "$fixture"' EXIT
printf "Loaded MCU 'cartographer' CARTOGRAPHER V3 6.1.0\\nLoaded MCU 'cartographer' %s\\n" "$TEST_VERSION" > "$fixture"
command() { return 1; }
'''
        else:
            setup = '_detect_carto_version_string() { printf "%s\\n" "$TEST_VERSION"; }\n'
        result = subprocess.run(
            [BASH, "-c", source + "\n" + setup + "detect_carto_hw; detect_carto_fw"],
            env=dict(os.environ, TEST_VERSION=version), capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.splitlines()

    def test_live_versions(self):
        for version, expected in (
            ("CARTOGRAPHER V3 6.1.0 lite", ["V3", "6.1.0 (Lite)"]),
            ("CARTOGRAPHER V3 6.1.0", ["V3", "6.1.0 (Full)"]),
            ("CARTOGRAPHER 5.1.0", ["V3", "5.1.0 (Full)"]),
            ("CARTOGRAPHER K1 5.1.0", ["V3", "5.1.0 (Lite)"]),
            ("CARTOGRAPHER V4 6.0.0", ["V4", "6.0.0 (Full)"]),
            ("", ["unknown", "unknown"]),
        ):
            with self.subTest(version=version):
                self.assertEqual(self.detect(version), expected)

    def test_log_fallback_preserves_latest_lite_suffix(self):
        self.assertEqual(
            self.detect("CARTOGRAPHER V3 6.1.0 lite", fallback=True),
            ["V3", "6.1.0 (Lite)"],
        )


if __name__ == "__main__":
    unittest.main()
