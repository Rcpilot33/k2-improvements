#!/usr/bin/env python3
"""Static checks for optional-feature reporting in system status."""

import pathlib
import unittest


STATUS = pathlib.Path(__file__).with_name("status.sh")


class StatusMenuTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.status = STATUS.read_text(encoding="utf-8")

    def test_material_offsets_are_reported_for_every_setup(self):
        material = self.status.index(
            "status_line 'Material Z Offsets' is_material_z_offsets"
        )
        stock_branch = self.status.index("if ! is_cartographer; then")
        cartographer_branch = self.status.index("if is_cartographer; then", stock_branch)
        self.assertLess(material, stock_branch)
        self.assertLess(material, cartographer_branch)

    def test_global_touch_offsets_are_reported_only_for_cartographer(self):
        cartographer_branch = self.status.index("if is_cartographer; then")
        global_offsets = self.status.index(
            "status_line 'Global Carto Z Offsets' is_global_touch_offsets"
        )
        maintenance = self.status.index("printf '\\n Maintenance\\n'", cartographer_branch)
        self.assertLess(cartographer_branch, global_offsets)
        self.assertLess(global_offsets, maintenance)

    def test_stock_nozzle_camera_is_reported(self):
        self.assertIn(
            "status_line 'Stock nozzle camera stream' is_nozzle_camera",
            self.status,
        )


if __name__ == "__main__":
    unittest.main()
