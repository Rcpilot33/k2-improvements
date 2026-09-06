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
            self.config._schedule_post_restart_firmware_reset(self.gcode)

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
            ['SAVE_CONFIG complete; stock Klipper restart and protected '
             'firmware restart scheduled'])

    def test_missing_worker_stops_without_requesting_restart(self):
        with mock.patch.object(MODULE.os.path, 'isfile', return_value=False), \
                self.assertRaisesRegex(RuntimeError,
                                       'protected restart helper is missing'):
            self.config._schedule_post_restart_firmware_reset(self.gcode)

    def test_save_config_preserves_stock_restart_then_uses_worker(self):
        source = MODULE_PATH.read_text(encoding='utf-8')
        command = source.split('def cmd_SAVE_CONFIG(self, gcmd):', 1)[1]
        command = command.split('cmd_CXSAVE_CONFIG_help', 1)[0]
        schedule = command.index(
            'self._schedule_post_restart_firmware_reset(gcode)')
        stock_restart = command.index("gcode.request_restart('restart')")
        self.assertLess(schedule, stock_restart)

    def test_worker_avoids_klippy_service_restart(self):
        worker = MODULE_PATH.parents[2] / 'scripts' / 'save_config_restart.sh'
        source = worker.read_text(encoding='utf-8')
        self.assertIn('motor_control=motor_ready', source)
        self.assertIn('K2_FIRMWARE_RESTART_ATTEMPTS=1', source)
        self.assertNotIn('klippy_code_restart.sh', source)

    def test_worker_recovers_only_validated_motor_e_signature(self):
        worker = MODULE_PATH.parents[2] / 'scripts' / 'save_config_restart.sh'
        source = worker.read_text(encoding='utf-8')
        self.assertIn('is_recoverable_motor_e_error', source)
        self.assertIn('"key798"', source)
        self.assertIn('Motor connection failed, exceeding maximum retry count',
                      source)
        self.assertIn('complete(recovered-motor-e)', source)
        self.assertIn('failed(stock-error)', source)
        self.assertIn('K2_FIRMWARE_RESTART_ATTEMPTS=1', source)


if __name__ == '__main__':
    unittest.main()
