"""Exercise the shell bridge without running a camera or Klipper."""
from contextlib import nullcontext
from unittest import TestCase
from unittest.mock import MagicMock, patch

import gcode_shell_command as bridge


class ShellCommandTests(TestCase):
    def setUp(self):
        config = MagicMock()
        config.get_name.return_value = "gcode_shell_command nozzle_camera_on"
        config.get.return_value = "/camera on"
        config.getfloat.return_value = 5
        printer = config.get_printer.return_value
        self.gcode = MagicMock()
        printer.lookup_object.side_effect = lambda name, *args: self.gcode if name == "gcode" else None
        printer.get_reactor.return_value.mutex.return_value = nullcontext()
        self.command = bridge.ShellCommand(config)
        self.reactor = self.command.reactor
        self.request = MagicMock()
        self.request.get.return_value = ""
        self.request.get_int.return_value = 1

    def test_background_returns_before_launch_and_yields_while_running(self):
        with patch.object(bridge, "Popen") as launch:
            self.command.cmd_RUN_SHELL_COMMAND(self.request)
            launch.assert_not_called()
            callback, = self.reactor.register_callback.call_args.args
            launch.return_value.poll.side_effect = [None, None, 0, 0, 0]
            launch.return_value.returncode = 0
            self.reactor.monotonic.return_value = 1
            callback(1)
            self.assertEqual(self.reactor.pause.call_count, 2)
            self.assertEqual(launch.call_args.args[0], ["/camera", "on"])

    def test_timeout_terminates_command_group_and_reports_failure(self):
        with patch.object(bridge, "Popen") as launch, patch.object(bridge.os, "killpg", create=True) as kill, \
                patch.object(bridge.signal, "SIGKILL", 9, create=True):
            proc = launch.return_value
            proc.poll.side_effect = [None, None, -9, -9]
            self.reactor.monotonic.side_effect = [0, 6]
            self.command._run_background(["/camera", "off"])
            kill.assert_called_once_with(proc.pid, 9)
            self.assertIn("timed out", self.gcode.respond_info.call_args.args[0])

    def test_disconnect_discards_a_queued_command(self):
        self.command.cmd_RUN_SHELL_COMMAND(self.request)
        callback, = self.reactor.register_callback.call_args.args
        self.command._disconnect()
        with patch.object(bridge, "Popen") as launch:
            callback(1)
            launch.assert_not_called()
