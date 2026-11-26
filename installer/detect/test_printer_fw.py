#!/usr/bin/env python3
"""Tests for firmware-version comparisons used by gated features."""

import os
from pathlib import Path
import shutil
import subprocess
import unittest


SCRIPT = Path(__file__).with_name("printer_fw.sh")
FEATURES = SCRIPT.with_name("features.sh")
UPDATE = SCRIPT.parent.parent / "menus" / "update.sh"
BASH = shutil.which("bash") or "C:/Program Files/Git/bin/bash.exe"


@unittest.skipUnless(Path(BASH).exists(), "bash required")
class PrinterFirmwareVersionTests(unittest.TestCase):
    def compare(self, current, minimum="1.1.5.5"):
        return subprocess.run(
            [
                BASH,
                "-c",
                '. "$SCRIPT"; printer_fw_at_least "$CURRENT" "$MINIMUM"',
            ],
            env=dict(
                os.environ,
                SCRIPT=SCRIPT.as_posix(),
                CURRENT=current,
                MINIMUM=minimum,
            ),
            capture_output=True,
            text=True,
        ).returncode

    def test_1155_and_newer_are_supported(self):
        for version in ("1.1.5.5", "1.1.5.6", "1.1.6.0", "2.0"):
            with self.subTest(version=version):
                self.assertEqual(self.compare(version), 0)

    def test_plus_image_fallback_is_limited_to_plus(self):
        script = '''
. "$SCRIPT"
detect_installed_firmware() { echo "$LOG_VERSION"; }
get_sn_mac.sh() { echo "$MODEL"; }
ls() { echo CR0CN240110C10_ota_img_V1.1.8.0.img; }
detect_printer_fw
'''
        for model, logged, expected in (("F008", "", "1.1.8.0"), ("F012", "", "unknown"),
                                        ("", "", "unknown"), ("F012", "1.1.8.3", "1.1.8.3")):
            with self.subTest(model=model, logged=logged):
                result = subprocess.run(
                    [BASH, "-c", script], check=True, capture_output=True, text=True,
                    env=dict(os.environ, SCRIPT=SCRIPT.as_posix(), MODEL=model,
                             K2_PRINTER_MODEL="", LOG_VERSION=logged),
                )
                self.assertEqual(result.stdout.strip(), expected)

    def test_older_unknown_and_malformed_versions_are_rejected(self):
        for version in ("1.1.5.4", "1.1.3.13", "unknown", "1.1.beta.5", ""):
            with self.subTest(version=version):
                self.assertNotEqual(self.compare(version), 0)

    def eligible(self, current):
        return subprocess.run(
            [BASH, "-c", '''
. "$FW_SCRIPT"
. "$FEATURE_SCRIPT"
detect_printer_fw() { printf '%s\n' "$CURRENT"; }
is_macros() { return 0; }
is_start_print_fast_stop_eligible
'''],
            env=dict(
                os.environ,
                FW_SCRIPT=SCRIPT.as_posix(),
                FEATURE_SCRIPT=FEATURES.as_posix(),
                CURRENT=current,
            ),
            capture_output=True,
            text=True,
        ).returncode

    def test_fast_stop_component_is_applicable_only_on_1155_or_newer(self):
        self.assertEqual(self.eligible("1.1.5.5"), 0)
        self.assertEqual(self.eligible("1.1.6.0"), 0)
        self.assertNotEqual(self.eligible("1.1.5.4"), 0)
        self.assertNotEqual(self.eligible("unknown"), 0)

    def test_update_snapshot_cannot_bypass_fast_stop_firmware_gate(self):
        update = UPDATE.read_text(encoding="utf-8")
        applicable = update.split("migration_component_applicable() {", 1)[1]
        applicable = applicable.split("\n}", 1)[0]
        gate = applicable.index('[ "$1" = start-print-fast-stop ]')
        snapshot = applicable.index("MIGRATION_INSTALLED_SNAPSHOT")
        self.assertLess(gate, snapshot)
