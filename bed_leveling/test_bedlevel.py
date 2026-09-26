#!/usr/bin/env python3

import pathlib
import unittest


SCRIPT = pathlib.Path(__file__).with_name("bedlevel.py").read_text(
    encoding="utf-8"
)


class BedLevelCoordinateTests(unittest.TestCase):
    def test_coordinates_follow_actual_mesh_shape(self):
        self.assertIn(
            "np.linspace(mesh_min[0], mesh_max[0], mesh.shape[1])", SCRIPT
        )
        self.assertIn(
            "np.linspace(mesh_min[1], mesh_max[1], mesh.shape[0])", SCRIPT
        )
        self.assertNotIn("np.arange(5, 346, 42.5)", SCRIPT)

    def test_invalid_mesh_shape_fails_before_plotting(self):
        validation = SCRIPT.index("if mesh.ndim != 2")
        plotting = SCRIPT.index("plt.subplots")
        self.assertLess(validation, plotting)
        self.assertIn("mesh.shape[0] < 2", SCRIPT)
        self.assertIn("mesh.shape[1] < 2", SCRIPT)


if __name__ == "__main__":
    unittest.main()
