#!/usr/bin/env python3

import json
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import set_release_source


class SetReleaseSourceTests(unittest.TestCase):
    def test_changes_owner_and_project_without_changing_version(self):
        with tempfile.TemporaryDirectory() as directory:
            release_info = pathlib.Path(directory) / "release_info.json"
            release_info.write_text(
                json.dumps(
                    {
                        "project_name": "fluidd",
                        "project_owner": "Jacob10383",
                        "version": "v1.37.4",
                    }
                ),
                encoding="utf-8",
            )

            set_release_source.update_release_source(
                release_info, "Rcpilot33", "fluidd"
            )

            updated = json.loads(release_info.read_text(encoding="utf-8"))
            self.assertEqual(updated["project_owner"], "Rcpilot33")
            self.assertEqual(updated["project_name"], "fluidd")
            self.assertEqual(updated["version"], "v1.37.4")

    def test_rejects_metadata_without_a_version(self):
        with tempfile.TemporaryDirectory() as directory:
            release_info = pathlib.Path(directory) / "release_info.json"
            release_info.write_text("{}", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "missing its version"):
                set_release_source.update_release_source(
                    release_info, "Rcpilot33", "fluidd"
                )


if __name__ == "__main__":
    unittest.main()
