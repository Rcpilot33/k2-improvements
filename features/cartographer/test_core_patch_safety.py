#!/usr/bin/env python3
"""Static safety checks for the Klipper core files replaced by Cartographer."""

import ast
import importlib.util
import pathlib
import sys
import types
import unittest
from unittest.mock import Mock, patch


PATCHES = pathlib.Path(__file__).with_name("patches")


class CorePatchSafetyTests(unittest.TestCase):
    def load_bed_mesh(self):
        package = types.ModuleType("bed_mesh_test")
        package.probe = types.ModuleType("probe")
        spec = importlib.util.spec_from_file_location("bed_mesh_test.bed_mesh", PATCHES / "bed_mesh.py")
        module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {"bed_mesh_test": package}):
            spec.loader.exec_module(module)
        return module

    def test_touchscreen_get_mesh_tracks_active_probed_matrix(self):
        module = self.load_bed_mesh()
        config = Mock()
        config.getfloat.side_effect = lambda name, default: default
        hooks = {}
        webhooks = config.get_printer.return_value.lookup_object.return_value
        webhooks.register_endpoint.side_effect = hooks.__setitem__
        with patch.object(module, "BedMeshCalibrate"), patch.object(module, "ProfileManager"), patch.object(module, "MoveSplitter"):
            bed = module.BedMesh(config)
        self.assertIn("bed_mesh/dump_mesh", hooks)
        active = Mock()
        active.get_mesh_params.return_value = dict(min_x=0, min_y=0, max_x=5, max_y=5)
        points = [[0.1, 0.2], [0.3, 0.4]]
        active.get_probed_matrix.return_value = points
        for mesh, expected in ((None, [[]]), (active, points), (None, [[]])):
            bed.set_mesh(mesh)
            request = Mock()
            hooks["get_mesh"](request)
            request.send.assert_called_once_with({"probed_matrix": expected})

    def test_factory_home_default_mesh_load_is_scoped_to_the_single_z_conversion(self):
        module = self.load_bed_mesh()
        for single_z, homing, profile, expected_load in (
            (True, True, "default", False), (True, False, "default", True),
            (True, True, "textured", True), (False, True, "default", True),
        ):
            with self.subTest(single_z=single_z, homing=homing, profile=profile):
                manager = object.__new__(module.ProfileManager)
                manager.printer = Mock()
                manager.printer.lookup_object.return_value.in_script = homing
                manager.skip_stock_home_profile = single_z
                manager.load_profile = Mock()
                manager.cmd_BED_MESH_PROFILE({"LOAD": profile})
                self.assertEqual(manager.load_profile.called, expected_load)

    def test_homing_constructor_tolerates_missing_cartographer(self):
        source = (PATCHES / "homing.py").read_text(encoding="utf-8")
        self.assertIn("lookup_object('cartographer', None)", source)
        self.assertIn("if self.prtouch_v3 is not None:", source)

    def test_motor_protection_paths_raise_an_explicit_command_error(self):
        tree = ast.parse(
            (PATCHES / "homing.py").read_text(encoding="utf-8")
        )
        motor_error_branches = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.If) or not isinstance(node.test, ast.Compare):
                continue
            names = {
                child.id for child in ast.walk(node.test)
                if isinstance(child, ast.Name)
            }
            if {"ret", "MOTOR_PROTECT_ERROR"}.issubset(names):
                motor_error_branches.append(node)

        explicit_raise_count = 0
        self.assertGreaterEqual(len(motor_error_branches), 2)
        for branch in motor_error_branches:
            with self.subTest(line=branch.lineno):
                raises = [
                    child for child in branch.body
                    if isinstance(child, ast.Raise)
                ]
                self.assertTrue(all(item.exc is not None for item in raises))
                explicit_raise_count += len(raises)
        self.assertGreaterEqual(explicit_raise_count, 2)

    def test_serial_debug_handles_a_disconnected_queue(self):
        tree = ast.parse(
            (PATCHES / "serialhdl.py").read_text(encoding="utf-8")
        )
        serial_reader = next(
            node for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name == "SerialReader"
        )
        dump_debug = next(
            node for node in serial_reader.body
            if isinstance(node, ast.FunctionDef) and node.name == "dump_debug"
        )
        first_statement = dump_debug.body[0]
        self.assertIsInstance(first_statement, ast.If)
        self.assertTrue(
            any(
                isinstance(node, ast.Attribute)
                and node.attr == "serialqueue"
                for node in ast.walk(first_statement.test)
            )
        )
        self.assertTrue(
            any(isinstance(node, ast.Return) for node in first_statement.body)
        )

    def test_can_open_retries_operating_system_errors(self):
        source = (PATCHES / "serialhdl.py").read_text(encoding="utf-8")
        self.assertIn("except (can.CanError, os.error, IOError) as e:", source)

    def test_connect_logging_truncates_large_generated_meshes(self):
        source = (PATCHES / "bed_mesh.py").read_text(encoding="utf-8")
        self.assertIn(
            "self.bmc.print_generated_points(logging.info, truncate=True)",
            source,
        )
        self.assertIn("if i >= 50 and truncate:", source)

    def test_disconnected_scanner_blocks_fast_z_rehome_preposition(self):
        source = (PATCHES / "homing.py").read_text(encoding="utf-8")
        branch_start = source.index(
            "# Direct scanner homing:"
        )
        branch_end = source.index("kin.home(homing_state)", branch_start)
        branch = source[branch_start:branch_end]
        fast_move = branch.index("gcmd = 'G1 F%d Z%.3f'")

        self.assertLess(
            branch.index("self._check_scanner_model_ready()"), fast_move
        )
        self.assertLess(
            branch.index("self._check_scanner_connected()"), fast_move
        )


if __name__ == "__main__":
    unittest.main()
