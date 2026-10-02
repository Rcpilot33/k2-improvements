#!/usr/bin/env python3

import pathlib
import re
import unittest
import zipfile
import json


HERE = pathlib.Path(__file__).parent
ARCHIVE = HERE / "fluidd-v1.37.4.zip"
PATCH = HERE / "fluidd-v1.37.4.patch"
INSTALLER = HERE / "install.sh"
FEATURE_DETECTORS = HERE.parent.parent / "detect" / "features.sh"


class FluiddBundleTests(unittest.TestCase):
    def test_preserves_jacob_release_identity(self):
        with zipfile.ZipFile(ARCHIVE) as archive:
            self.assertEqual(archive.read(".version").decode().strip(), "v1.37.4")
            info = json.loads(archive.read("release_info.json"))
            self.assertEqual(info["project_owner"], "Jacob10383")
            self.assertEqual(info["version"], "v1.37.4")
            self.assertEqual(archive.read("k2-ui-overlay-support.txt").decode().strip(), "5")
            self.assertNotIn("global-touch-offsets-support.txt", archive.namelist())

    def test_entry_points_reference_files_in_the_archive(self):
        with zipfile.ZipFile(ARCHIVE) as archive:
            names = set(archive.namelist())
            index = archive.read("index.html").decode("utf-8")
            self.assertIn("sw.js", names)
            for asset in re.findall(r'(?:src|href)="\./(assets/[^"#?]+)', index):
                self.assertIn(asset, names)

    def test_static_files_are_readable_by_nginx(self):
        with zipfile.ZipFile(ARCHIVE) as archive:
            for entry in archive.infolist():
                with self.subTest(path=entry.filename):
                    self.assertEqual(entry.external_attr >> 16 & 0o777, 0o644)

    def test_contains_all_live_settings_dialogs(self):
        with zipfile.ZipFile(ARCHIVE) as archive:
            scripts = b"\n".join(
                archive.read(name) for name in archive.namelist()
                if name.startswith("assets/") and name.endswith(".js")
            )
        for value in (
            b"global_touch_offsets_",
            b"material_z_offsets_",
            b"K2_CARTOGRAPHER_GLOBAL_Z_STAGE",
            b"K2_MATERIAL_Z_STAGE",
            b"Material Z Offsets",
            b"m191_settings_",
            b"K2_M191_SETTINGS_STAGE",
            b"Bed Assist",
        ):
            self.assertIn(value, scripts)

        self.assertEqual(scripts.count(b'"save-button-text":`Save`'), 2)
        self.assertNotIn(b'"save-button-text":`Save & Restart`', scripts)
        self.assertIn(b' Save & Restart ', scripts)  # Bed Assist still restarts.

    def test_changed_dialog_asset_is_refreshed_by_service_worker(self):
        with zipfile.ZipFile(ARCHIVE) as archive:
            self.assertIn(
                b'{"revision":"offset-live-5","url":"assets/index-B6qRjk0F.js"}',
                archive.read("sw.js"),
            )

    def test_preserves_creality_camera_component(self):
        with zipfile.ZipFile(ARCHIVE) as archive:
            names = archive.namelist()
            scripts = b"\n".join(
                archive.read(name) for name in names
                if name.startswith("assets/") and name.endswith(".js")
            )
        self.assertTrue(any(
            name.startswith("assets/WebrtcCrealityk2RtcCamera-") and name.endswith(".js")
            for name in names
        ))
        self.assertIn(b"WebrtcCrealityk2RtcCamera", scripts)
        self.assertNotIn(b"WebrtcCrealityk2rtcCamera", scripts)

    def test_installer_detects_the_actual_camera_asset_case(self):
        detectors = FEATURE_DETECTORS.read_text(encoding="utf-8")
        self.assertIn("grep -ilq 'crealityk2'", detectors)

    def test_source_patch_and_installer_are_self_contained(self):
        patch = PATCH.read_text(encoding="utf-8")
        installer = INSTALLER.read_text(encoding="utf-8")
        self.assertIn("GlobalTouchOffsetsDialog.vue", patch)
        self.assertIn("MaterialZOffsetsDialog.vue", patch)
        self.assertIn("M191SettingsDialog.vue", patch)
        self.assertIn("WebrtcCrealityk2RtcCamera.vue", patch)
        self.assertIn("fluidd-v1.37.4.zip", installer)
        self.assertIn('chmod -R a+rX "$staging"', installer)
        self.assertIn('chmod -R a+rX "$fluidd_target"', installer)
        self.assertNotIn("Rcpilot33/fluidd", installer)


if __name__ == "__main__":
    unittest.main()
