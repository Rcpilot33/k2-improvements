#!/usr/bin/env python3

import os
import tempfile
import unittest

from ensure_included import add_include, parse_bool


class EnsureIncludedTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_path = os.path.join(self.temp_dir.name, 'main.cfg')

    def tearDown(self):
        self.temp_dir.cleanup()

    def write_config(self, contents):
        with open(self.config_path, 'w', newline='') as handle:
            handle.write(contents)

    def read_config(self):
        with open(self.config_path, 'r', newline='') as handle:
            return handle.read()

    def test_uncomments_existing_include_without_adding_duplicate(self):
        self.write_config(
            '[include bed_mesh.cfg]\n'
            '#[include prime_tower.cfg]\n'
            '[include overrides.cfg]\n'
        )

        add_include(self.config_path, 'prime_tower.cfg')

        contents = self.read_config()
        self.assertEqual(contents.count('[include prime_tower.cfg]'), 1)
        self.assertNotIn('#[include prime_tower.cfg]', contents)
        self.assertLess(
            contents.index('[include prime_tower.cfg]'),
            contents.index('[include overrides.cfg]'),
        )

    def test_normalizes_case_and_removes_active_commented_duplicates(self):
        self.write_config(
            '#[include prime_tower.cfg]\n'
            '[include Prime_Tower.cfg]\n'
            '[include overrides.cfg]\n'
        )

        add_include(self.config_path, 'prime_tower.cfg')

        self.assertEqual(
            self.read_config(),
            '[include prime_tower.cfg]\n[include overrides.cfg]\n',
        )

    def test_can_disable_an_existing_active_include(self):
        self.write_config('[include prtouch_v3.cfg]\n')

        add_include(self.config_path, 'prtouch_v3.cfg', commented=True)

        self.assertEqual(self.read_config(), '#[include prtouch_v3.cfg]\n')

    def test_new_include_is_inserted_before_overrides(self):
        self.write_config('[include start_print.cfg]\n[include overrides.cfg]\n')

        add_include(self.config_path, 'bed_mesh.cfg')

        self.assertEqual(
            self.read_config(),
            '[include start_print.cfg]\n'
            '[include bed_mesh.cfg]\n'
            '[include overrides.cfg]\n',
        )

    def test_boolean_parser_does_not_treat_false_as_true(self):
        self.assertTrue(parse_bool('True'))
        self.assertTrue(parse_bool('1'))
        self.assertFalse(parse_bool('False'))
        self.assertFalse(parse_bool('0'))


if __name__ == '__main__':
    unittest.main()
