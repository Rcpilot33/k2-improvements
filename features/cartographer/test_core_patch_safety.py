#!/usr/bin/env python3
"""Static safety checks for the Klipper core files replaced by Cartographer."""

import ast
import pathlib
import unittest


PATCHES = pathlib.Path(__file__).with_name("patches")


class CorePatchSafetyTests(unittest.TestCase):
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
            "# Photoelectric leveling is already complete"
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
