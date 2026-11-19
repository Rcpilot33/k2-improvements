#!/usr/bin/env python3

import importlib.util
import sys
import types
import unittest
from unittest.mock import Mock, patch
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("screws_tilt_adjust.py")
PACKAGE = "screws_tilt_adjust_test_package"
sys.modules.setdefault(PACKAGE, types.ModuleType(PACKAGE))
sys.modules.setdefault(PACKAGE + ".probe", types.ModuleType(PACKAGE + ".probe"))
SPEC = importlib.util.spec_from_file_location(
    PACKAGE + ".screws_tilt_adjust", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class BedDropTests(unittest.TestCase):
    def make_adjuster(self, distance=None):
        config = Mock()
        config.get.side_effect = lambda key, default=None: (
            '10, 10' if key in ('screw1', 'screw2', 'screw3') else default)
        config.getfloatlist.return_value = (10., 10.)
        config.getchoice.return_value = 0
        config.error = ValueError
        config.getfloat.side_effect = lambda key, default, **kwargs: (
            default if distance is None else distance)
        with patch.object(MODULE.probe, 'ProbePointsHelper', create=True):
            adjuster = MODULE.ScrewsTiltAdjust(config)
        config.getfloat.assert_called_once_with('bed_drop_distance', 200., minval=0.)
        return adjuster

    def test_default_and_configured_drop_reach_the_motion_command(self):
        for distance, current, maximum, target in (
                (None, 10., 350., 210.), (75., 10., 350., 85.),
                (1000., 10., 350., 349.5), (100., 290., 300., 299.5)):
            with self.subTest(distance=distance, current=current):
                adjuster = self.make_adjuster(distance)
                toolhead = Mock()
                toolhead.get_status.return_value = {'axis_maximum': [350., 350., maximum]}
                toolhead.get_position.return_value = [50., 50., current, 0.]
                adjuster.printer.lookup_object.return_value = toolhead
                adjuster._lower_bed_for_adjustment(Mock())
                toolhead.manual_move.assert_called_once_with([None, None, target], 20.)
                toolhead.wait_moves.assert_called_once_with()

    def test_disabled_or_at_limit_never_moves_the_bed_up(self):
        for distance, current in ((0., 10.), (200., 349.5), (200., 350.)):
            adjuster = self.make_adjuster(distance)
            toolhead = Mock()
            toolhead.get_status.return_value = {'axis_maximum': [350., 350., 350.]}
            toolhead.get_position.return_value = [50., 50., current, 0.]
            adjuster.printer.lookup_object.return_value = toolhead
            adjuster._lower_bed_for_adjustment(Mock())
            toolhead.manual_move.assert_not_called()
            toolhead.wait_moves.assert_not_called()

    def test_nonfinite_setting_is_rejected(self):
        for distance in (float('nan'), float('inf'), -float('inf')):
            with self.assertRaisesRegex(ValueError, 'must be finite'):
                self.make_adjuster(distance)

    def test_failed_probing_does_not_drop_bed(self):
        adjuster = self.make_adjuster(75.)
        adjuster._prepare_safe_probe_points = Mock()
        adjuster._lower_bed_for_adjustment = Mock()
        adjuster.probe_helper.start_probe.side_effect = RuntimeError('probe failed')
        gcmd = Mock()
        gcmd.get.return_value = None
        with self.assertRaisesRegex(RuntimeError, 'probe failed'):
            adjuster.cmd_SCREWS_TILT_CALCULATE(gcmd)
        adjuster._lower_bed_for_adjustment.assert_not_called()


class SafeProbeCoordinateTests(unittest.TestCase):
    def test_stock_probe_keeps_screw_coordinate(self):
        self.assertEqual(
            MODULE.calculate_safe_probe_coordinate(28., 0., 352., 0.),
            28.)

    def test_jamin_offset_keeps_reachable_physical_screw_coordinate(self):
        probe_y = MODULE.calculate_safe_probe_coordinate(
            28., 0., 352., -15.)
        self.assertEqual(probe_y, 28.)
        self.assertEqual(probe_y - (-15.), 43.)

    def test_jimmyv_offset_uses_closest_safe_front_point(self):
        probe_y = MODULE.calculate_safe_probe_coordinate(
            28., 0., 352., 36.)
        self.assertEqual(probe_y, 36.5)
        self.assertEqual(probe_y - 36., .5)

    def test_negative_offset_trims_rear_probe_boundary(self):
        self.assertEqual(
            MODULE.calculate_safe_probe_coordinate(351., 0., 352., -15.),
            336.5)

    def test_impossible_probe_range_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "no reachable range"):
            MODULE.calculate_safe_probe_coordinate(28., 0., 20., 25.)

    def test_bed_access_move_uses_requested_distance(self):
        self.assertEqual(MODULE.calculate_bed_access_z(10., 350.), 210.)

    def test_bed_access_move_stays_inside_z_maximum(self):
        self.assertEqual(MODULE.calculate_bed_access_z(200., 350.), 349.5)


if __name__ == "__main__":
    unittest.main()
