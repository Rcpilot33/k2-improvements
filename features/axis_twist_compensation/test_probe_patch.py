#!/usr/bin/env python3
"""Static regression checks for the K2 axis-twist probe patch."""

import ast
import pathlib
import unittest


PROBE_PATCH = pathlib.Path(__file__).with_name("probe.py")
COMPENSATION_PATCH = pathlib.Path(__file__).with_name(
    "axis_twist_compensation.py"
)


class ProbePatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tree = ast.parse(PROBE_PATCH.read_text(encoding="utf-8"))
        cls.classes = {
            node.name: node
            for node in cls.tree.body
            if isinstance(node, ast.ClassDef)
        }
        cls.functions = {
            node.name: node
            for node in cls.tree.body
            if isinstance(node, ast.FunctionDef)
        }

    def test_probe_does_not_reference_an_unbound_compensation_variable(self):
        printer_probe = self.classes["PrinterProbe"]
        probe_method = next(
            node for node in printer_probe.body
            if isinstance(node, ast.FunctionDef) and node.name == "_probe"
        )
        loaded_names = {
            node.id for node in ast.walk(probe_method)
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
        }
        self.assertNotIn("z_compensation", loaded_names)

    def test_single_probe_uses_the_legacy_probe_api(self):
        run_single_probe = self.functions["run_single_probe"]
        called_attributes = {
            node.func.attr for node in ast.walk(run_single_probe)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        }
        self.assertEqual(called_attributes, {"run_probe"})

    def test_endstop_wrapper_has_no_orphaned_session_api(self):
        wrapper_methods = {
            node.name for node in self.classes["ProbeEndstopWrapper"].body
            if isinstance(node, ast.FunctionDef)
        }
        self.assertNotIn("start_probe_session", wrapper_methods)
        self.assertNotIn("end_probe_session", wrapper_methods)

    def test_legacy_printer_probe_exposes_modern_parameter_bridge(self):
        printer_probe = self.classes["PrinterProbe"]
        method = next(
            node for node in printer_probe.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "get_probe_params"
        )
        returned_keys = {
            key.value
            for node in ast.walk(method)
            if isinstance(node, ast.Dict)
            for key in node.keys
            if isinstance(key, ast.Constant) and isinstance(key.value, str)
        }
        self.assertEqual(
            returned_keys,
            {
                "probe_speed",
                "lift_speed",
                "samples",
                "sample_retract_dist",
                "samples_tolerance",
                "samples_tolerance_retries",
                "samples_result",
            },
        )

    def test_zero_is_accepted_as_a_calibration_boundary(self):
        source = COMPENSATION_PATCH.read_text(encoding="utf-8")
        self.assertNotIn("if not all([", source)
        self.assertGreaterEqual(
            source.count("any(value is None for value in ("),
            3,
        )
        self.assertIn("self.y_end_point[1]", source)

    def test_safe_range_uses_active_probe_offset(self):
        compensation_tree = ast.parse(
            COMPENSATION_PATCH.read_text(encoding="utf-8")
        )
        function = next(
            node for node in compensation_tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "calculate_safe_bed_range"
        )
        constant = next(
            node for node in compensation_tree.body
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name)
                and target.id == "CALIBRATION_BOUNDARY_MARGIN"
                for target in node.targets
            )
        )
        namespace = {}
        module = ast.Module(body=[constant, function], type_ignores=[])
        exec(compile(module, str(COMPENSATION_PATCH), "exec"), namespace)
        safe_range = namespace["calculate_safe_bed_range"]

        self.assertEqual(safe_range(5., 345., 0., 350., 0.), (5., 345.))
        self.assertEqual(
            safe_range(5., 345., 0., 350., -15.), (5., 334.5)
        )
        self.assertEqual(
            safe_range(5., 345., 0., 350., 36.), (36.5, 345.)
        )

    def test_auto_calibration_preflights_all_probe_targets(self):
        source = COMPENSATION_PATCH.read_text(encoding="utf-8")
        self.assertIn("x_range, y_range = self._safe_calibration_ranges()", source)
        self.assertIn("self._validate_points(probe_targets)", source)
        self.assertLess(
            source.index("self._validate_points(probe_targets)"),
            source.index("self.compensation.clear_compensations()"),
        )

    def test_probe_points_use_xy_offsets_by_default(self):
        source = PROBE_PATCH.read_text(encoding="utf-8")
        self.assertIn("self.use_offsets = True", source)
        self.assertNotIn("self.use_offsets = False", source)


if __name__ == "__main__":
    unittest.main()
