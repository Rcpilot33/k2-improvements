#!/usr/bin/env python3

import importlib.util
import pathlib
import tempfile
import unittest


SCRIPT = pathlib.Path(__file__).with_name("patch_probe_offsets.py")
SPEC = importlib.util.spec_from_file_location("patch_probe_offsets", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ProbeOffsetPatchTests(unittest.TestCase):
    def test_patches_exactly_one_disabled_setting(self):
        updated, changed = MODULE.patch("before\nself.use_offsets = False\nafter\n")
        self.assertTrue(changed)
        self.assertIn("self.use_offsets = True", updated)
        self.assertNotIn("self.use_offsets = False", updated)

    def test_already_patched_is_idempotent(self):
        original = "self.use_offsets = True\n"
        updated, changed = MODULE.patch(original)
        self.assertFalse(changed)
        self.assertEqual(updated, original)

    def test_unknown_or_ambiguous_source_fails(self):
        for source in (
            "no setting\n",
            "self.use_offsets = False\nself.use_offsets = False\n",
            "self.use_offsets = False\nself.use_offsets = True\n",
        ):
            with self.subTest(source=source):
                with self.assertRaises(ValueError):
                    MODULE.patch(source)

    def test_main_writes_verified_result(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "probe.py"
            path.write_text("self.use_offsets = False\n", encoding="utf-8")
            self.assertEqual(MODULE.main([str(SCRIPT), str(path)]), 0)
            self.assertEqual(
                path.read_text(encoding="utf-8"),
                "self.use_offsets = True\n",
            )


if __name__ == "__main__":
    unittest.main()
