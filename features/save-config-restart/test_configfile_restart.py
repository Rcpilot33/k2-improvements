import importlib.util
import os
import pathlib
import unittest
from unittest import mock


MODULE_PATH = pathlib.Path(__file__).with_name('configfile.py')
SPEC = importlib.util.spec_from_file_location(
    'k2_save_config_configfile', str(MODULE_PATH))
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class FakeGCode:
    def __init__(self):
        self.responses = []

    def error(self, message):
        return RuntimeError(message)

    def respond_info(self, message):
        self.responses.append(message)


class ProtectedRestartTests(unittest.TestCase):
    def setUp(self):
        self.config = MODULE.PrinterConfig.__new__(MODULE.PrinterConfig)
        self.gcode = FakeGCode()

    def test_schedules_detached_worker_from_same_checkout(self):
        fake_stdin = mock.MagicMock()
        fake_stdout = mock.MagicMock()
        fake_stdin.__enter__.return_value = fake_stdin
        fake_stdout.__enter__.return_value = fake_stdout
        open_mock = mock.mock_open()
        open_mock.side_effect = [fake_stdin, fake_stdout]
        fake_setsid = object()

        with mock.patch.object(MODULE.os.path, 'isfile', return_value=True), \
                mock.patch.object(MODULE.os, 'setsid', fake_setsid,
                                  create=True), \
                mock.patch.object(MODULE, 'open', open_mock,
                                  create=True), \
                mock.patch.object(MODULE.subprocess, 'Popen') as popen:
            self.config._schedule_protected_restart(self.gcode)

        helper = str(MODULE_PATH.parents[2] / 'scripts' /
                     'save_config_restart.sh')
        popen.assert_called_once_with(
            ['/bin/ash', helper], stdin=fake_stdin, stdout=fake_stdout,
            stderr=MODULE.subprocess.STDOUT, close_fds=True,
            preexec_fn=fake_setsid)
        fake_stdin.__exit__.assert_called_once()
        fake_stdout.__exit__.assert_called_once()
        self.assertEqual(
            self.gcode.responses,
            ['SAVE_CONFIG complete; protected Klippy and firmware restart '
             'scheduled'])

    def test_missing_worker_stops_without_requesting_restart(self):
        with mock.patch.object(MODULE.os.path, 'isfile', return_value=False), \
                self.assertRaisesRegex(RuntimeError,
                                       'protected restart helper is missing'):
            self.config._schedule_protected_restart(self.gcode)


if __name__ == '__main__':
    unittest.main()
