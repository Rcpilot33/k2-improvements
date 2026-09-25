#!/usr/bin/env python3

import importlib.util
import ast
import pathlib
import tempfile
import unittest
from unittest import mock


MODULE_PATH = pathlib.Path(__file__).with_name("ensure_cartographer_overrides.py")
OVERRIDES_PATH = pathlib.Path(__file__).with_name("overrides.cfg")
CARTOGRAPHER_INSTALLER = pathlib.Path(__file__).parents[2] / "cartographer" / "install.sh"
OVERRIDES_INSTALLER = pathlib.Path(__file__).with_name("install.sh")
SPEC = importlib.util.spec_from_file_location("ensure_cartographer_overrides", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class CartographerOverridesTests(unittest.TestCase):
    def test_cartographer_install_paths_apply_override_migration(self):
        command = 'python3 "${SCRIPT_DIR}/../macros/overrides/ensure_cartographer_overrides.py"'
        self.assertIn(command, CARTOGRAPHER_INSTALLER.read_text(encoding="utf-8"))
        self.assertIn(
            'python3 "${SCRIPT_DIR}/ensure_cartographer_overrides.py"',
            OVERRIDES_INSTALLER.read_text(encoding="utf-8"),
        )

    def test_annotations_are_compatible_with_printer_python_39(self):
        tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
        annotations = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                annotations.extend(
                    argument.annotation
                    for argument in node.args.args + node.args.kwonlyargs
                    if argument.annotation is not None
                )
                if node.returns is not None:
                    annotations.append(node.returns)

        self.assertFalse(
            any(
                isinstance(child, ast.BinOp) and isinstance(child.op, ast.BitOr)
                for annotation in annotations
                for child in ast.walk(annotation)
            ),
            "Python 3.10 union annotations are not supported by printer Python 3.9",
        )

    def test_shared_template_has_no_cartographer_only_settings(self):
        text = OVERRIDES_PATH.read_text(encoding="utf-8")

        self.assertIn("probe_count: 19, 19", text)
        self.assertIn("# Stock probe default", text)
        self.assertIn("[gcode_macro _M191_VARS]", text)
        self.assertNotIn("[gcode_macro _KAMP_Settings]", text)
        self.assertNotIn("speed: 150", text)
        self.assertNotIn("[cartographer ", text)
        for material in ("PLA", "PETG", "ABS", "ASA", "DEFAULT"):
            self.assertIn(f"variable_offset_{material}: 0.00", text)

    def test_adds_presented_cartographer_defaults(self):
        original = (
            "# User settings\n\n"
            "[virtual_sdcard]\nforced_leveling: false\n\n"
            "[bed_mesh]\nprobe_count: 50,50\n\n"
            "[gcode_macro _START_PRINT_VARS]\ngcode:\n\n"
            "[gcode_macro _M191_VARS]\ngcode:\n"
        )
        updated, changed = MODULE.ensure_defaults(original)

        self.assertTrue(changed)
        self.assertIn("speed: 150", updated)
        self.assertIn("# 200 can be set for Full firmware", updated)
        self.assertIn("max_noisy_samples: 2", updated)
        self.assertIn("mesh_runs: 1", updated)
        self.assertIn("mesh_path: spiral", updated)
        self.assertIn(
            "# Spiral scan; change to snake for the default path",
            updated,
        )
        self.assertNotIn("[gcode_macro _KAMP_Settings]", updated)
        self.assertLess(updated.index("probe_count: 50,50"), updated.index("speed: 150"))

    def test_converts_untouched_stock_probe_count_for_cartographer(self):
        updated, changed = MODULE.ensure_defaults(
            "[bed_mesh]\nprobe_count: 19, 19 # Stock probe default\n"
        )

        self.assertTrue(changed)
        self.assertIn("probe_count: 50,50", updated)
        self.assertIn("# Cartographer default: 50,50", updated)
        self.assertIn("speed: 150", updated)
        self.assertNotIn("probe_count: 19,19", updated)

    def test_adds_cartographer_probe_count_when_missing(self):
        updated, changed = MODULE.ensure_defaults("[bed_mesh]\nmesh_pps: 0,0\n")

        self.assertTrue(changed)
        self.assertIn("probe_count: 50,50", updated)
        self.assertIn("speed: 150", updated)

    def test_orders_user_sections_like_settings_panel(self):
        original = (
            "[gcode_macro _KAMP_Settings]\ngcode:\n\n"
            "[cartographer scan]\nmesh_path: hilbert\n\n"
            "[gcode_macro _M191_VARS]\ngcode:\n\n"
            "[bed_mesh]\nspeed: 200\n\n"
            "[cartographer touch]\nmax_noisy_samples: 0\n\n"
            "[gcode_macro _START_PRINT_VARS]\ngcode:\n\n"
            "[virtual_sdcard]\nforced_leveling: false\n"
        )
        updated, _ = MODULE.ensure_defaults(original)
        names = [MODULE._section_name(block) for block in MODULE._split(updated)[1]]

        self.assertEqual(
            names,
            [
                "virtual_sdcard",
                "bed_mesh",
                "gcode_macro _START_PRINT_VARS",
                "cartographer touch",
                "cartographer scan",
                "gcode_macro _M191_VARS",
                "gcode_macro _KAMP_Settings",
            ],
        )

    def test_optional_kamp_section_is_ordered_but_never_created(self):
        without_kamp, _ = MODULE.ensure_defaults(
            "[gcode_macro _M191_VARS]\ngcode:\n"
        )
        self.assertNotIn("[gcode_macro _KAMP_Settings]", without_kamp)

        with_kamp, _ = MODULE.ensure_defaults(
            "[gcode_macro _KAMP_Settings]\n"
            "variable_purge_height: 0.4\n"
            "gcode:\n\n"
            "[gcode_macro _M191_VARS]\ngcode:\n"
        )
        self.assertLess(
            with_kamp.index("[gcode_macro _M191_VARS]"),
            with_kamp.index("[gcode_macro _KAMP_Settings]"),
        )
        self.assertIn("variable_purge_height: 0.4", with_kamp)

    def test_managed_kamp_heading_moves_with_its_section(self):
        original = (
            "[cartographer scan]\n"
            "mesh_runs: 1\n"
            "mesh_path: spiral\n\n"
            "# User-selected KAMP settings. Preserved during KAMP reinstalls.\n\n"
            "[gcode_macro _M191_VARS]\n"
            "gcode:\n\n"
            "[gcode_macro _KAMP_Settings]\n"
            "variable_purge_height: 0.4\n"
            "gcode:\n"
        )
        updated, changed = MODULE.ensure_defaults(original)

        self.assertTrue(changed)
        heading = updated.index(MODULE.KAMP_HEADING)
        kamp = updated.index("[gcode_macro _KAMP_Settings]")
        m191 = updated.index("[gcode_macro _M191_VARS]")
        self.assertLess(m191, heading)
        self.assertLess(heading, kamp)
        self.assertEqual(updated.count(MODULE.KAMP_HEADING), 1)
        self.assertIn(
            MODULE.KAMP_HEADING + "\n[gcode_macro _KAMP_Settings]",
            updated,
        )

    def test_preserves_existing_user_choices(self):
        original = (
            "[bed_mesh]\nspeed: 200 # user choice\n\n"
            "[cartographer touch]\nmax_noisy_samples: 0\n\n"
            "[cartographer scan]\nmesh_runs: 3\nmesh_path: hilbert\n"
        )
        updated, _ = MODULE.ensure_defaults(original)

        self.assertIn("speed: 200", updated)
        self.assertIn(
            "# 200 can be set for Full firmware",
            updated,
        )
        self.assertIn("max_noisy_samples: 0", updated)
        self.assertIn("mesh_runs: 3", updated)
        self.assertIn("mesh_path: hilbert", updated)
        self.assertNotIn("speed: 150", updated)

    def test_normalizes_bed_mesh_comments_without_changing_values(self):
        original = (
            "[bed_mesh]\n"
            "probe_count:50,50          #50,50 is a good starting point if using carto\n"
            "speed: 200       \x00#150 recommended for lite firmware\n"
        )
        updated, changed = MODULE.ensure_defaults(original)

        self.assertTrue(changed)
        self.assertIn("probe_count: 50,50", updated)
        self.assertIn("# Cartographer default: 50,50", updated)
        self.assertIn("speed: 150", updated)
        self.assertNotIn("speed: 200", updated)
        self.assertIn(
            "# 200 can be set for Full firmware",
            updated,
        )
        self.assertNotIn("\x00", updated)

    def test_preserves_unknown_sections_and_content(self):
        original = (
            "# heading\n"
            "[bed_mesh]\nprobe_count: 31,31\n\n"
            "[user_custom]\nvalue: chosen # keep me\n"
        )
        updated, _ = MODULE.ensure_defaults(original)

        self.assertTrue(updated.startswith("# heading\n"))
        self.assertIn("[user_custom]\nvalue: chosen # keep me", updated)

    def test_crlf_and_file_update_are_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "overrides.cfg"
            path.write_bytes(b"[bed_mesh]\r\nprobe_count: 31,31\r\n")
            with mock.patch.object(MODULE.sys, "argv", ["ensure", str(path)]):
                self.assertEqual(MODULE.main(), 0)
                once = path.read_bytes()
                self.assertEqual(MODULE.main(), 0)
                self.assertEqual(path.read_bytes(), once)
            self.assertIn(b"\r\n", once)
            self.assertNotIn(b"\n", once.replace(b"\r\n", b""))

    def test_rejects_duplicate_managed_sections(self):
        with self.assertRaisesRegex(ValueError, "multiple"):
            MODULE.ensure_defaults("[bed_mesh]\nspeed: 150\n[bed_mesh]\nspeed: 200\n")


if __name__ == "__main__":
    unittest.main()
