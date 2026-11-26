"""Minimal shell-command bridge for trusted, installer-owned K2 macros."""

import logging
import shlex
import os
import signal
import tempfile
from subprocess import Popen


class ShellCommand:
    def __init__(self, config):
        self.name = config.get_name().split()[-1]
        printer = config.get_printer()
        self.gcode = printer.lookup_object("gcode")
        self.reactor = printer.get_reactor()
        self.live = True
        self.process = None
        self.lock = printer.lookup_object("k2_shell_command_mutex", None)
        if self.lock is None:
            self.lock = self.reactor.mutex()
            printer.add_object("k2_shell_command_mutex", self.lock)
        printer.register_event_handler("klippy:disconnect", self._disconnect)
        self.command = config.get("command")
        self.timeout = config.getfloat("timeout", 2.0, above=0.0)
        self.verbose = config.getboolean("verbose", True)
        self.gcode.register_mux_command(
            "K2_RUN_CAMERA_COMMAND" if config.get_name().startswith("k2_camera_command ") else "RUN_SHELL_COMMAND",
            "CMD",
            self.name,
            self.cmd_RUN_SHELL_COMMAND,
            desc="Run a registered shell command",
        )

    cmd_RUN_SHELL_COMMAND_help = "Run a registered shell command"

    def cmd_RUN_SHELL_COMMAND(self, gcmd):
        params = gcmd.get("PARAMS", default="")
        try:
            argv = shlex.split(self.command)
            if params:
                argv.extend(shlex.split(params))
        except ValueError as exc:
            raise gcmd.error("Bad shell command: %s" % (exc,))

        if gcmd.get_int("BACKGROUND", 0, minval=0, maxval=1):
            self.reactor.register_callback(lambda eventtime: self._run_background(argv))
        else:
            try:
                self._run(argv)
            except (OSError, RuntimeError) as exc:
                raise gcmd.error(str(exc))

    def _run_background(self, argv):
        try:
            self._run(argv)
        except (OSError, RuntimeError) as exc:
            logging.warning("Shell command %s: %s", self.name, exc)
            if self.live:
                self.gcode.respond_info("%s: %s" % (self.name, exc))

    def _terminate(self):
        if self.process is not None and self.process.poll() is None:
            try:
                os.killpg(self.process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass

    def _disconnect(self):
        self.live = False
        self._terminate()

    def _run(self, argv):
        # Serialize ON/OFF, including timer requests, while other reactor work runs.
        with self.lock:
            if not self.live:
                return
            with tempfile.TemporaryFile() as output:
                self.process = Popen(argv, stdout=output, stderr=output, start_new_session=True)
                try:
                    deadline = self.reactor.monotonic() + self.timeout
                    while self.process.poll() is None:
                        now = self.reactor.monotonic()
                        if now >= deadline:
                            self._terminate()
                            raise RuntimeError("Shell command timed out after %.1f seconds" % self.timeout)
                        self.reactor.pause(min(now + 0.1, deadline))
                    if not self.live:
                        return
                    output.seek(0)
                    message = output.read(8192).decode("utf-8", errors="replace").strip()
                    if self.verbose and message:
                        self.gcode.respond_info(message)
                    if self.process.returncode:
                        raise RuntimeError("Shell command %s failed with exit code %d"
                                           % (self.name, self.process.returncode))
                finally:
                    self._terminate()
                    while self.process.poll() is None:
                        self.reactor.pause(self.reactor.monotonic() + 0.05)
                    self.process = None


def load_config_prefix(config):
    return ShellCommand(config)
