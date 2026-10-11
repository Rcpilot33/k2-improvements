#!/usr/bin/env python3
"""Regression checks for optional live-editor install detection."""

import pathlib
import re
import unittest


DETECTOR = pathlib.Path(__file__).with_name("features.sh")
OVERLAY_INSTALLER = (
    pathlib.Path(__file__).resolve().parents[1]
    / "extras/fluidd-ui-overlay/install.sh"
)


class OptionalEditorDetectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.detector = DETECTOR.read_text(encoding="utf-8")
        cls.overlay_installer = OVERLAY_INSTALLER.read_text(encoding="utf-8")

    def test_current_overlay_version_satisfies_detector_minimum(self):
        installed = int(
            re.search(r"^OVERLAY_VERSION=(\d+)$", self.overlay_installer, re.M).group(1)
        )
        minimum = int(
            re.search(r'\[ "\$version" -ge "\$\{1:-(\d+)\}" \]', self.detector).group(1)
        )
        self.assertGreaterEqual(installed, minimum)

    def test_all_live_editors_use_shared_capability_detection(self):
        self.assertEqual(self.detector.count("    has_settings_ui_overlay"), 3)
        self.assertNotIn("grep -qx '3'", self.detector)

    def test_native_global_dialog_requires_overlay_8_without_raising_other_editor_minimum(self):
        body = self.detector.split('is_global_prtouch_offsets() {', 1)[1].split('\n}', 1)[0]
        self.assertIn('has_settings_ui_overlay 8', body)
        self.assertIn('${1:-3}', self.detector)

    def test_capability_marker_must_be_a_nonnegative_integer(self):
        self.assertIn("''|*[!0-9]*) return 1", self.detector)


if __name__ == "__main__":
    unittest.main()
