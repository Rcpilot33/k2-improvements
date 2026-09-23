"""Guard Creality's chamber and case-fan commands around print handoff."""


class K2M141Guard:
    PREFILE_CASE_FAN_WINDOW = 2.0

    def __init__(self, config):
        self.printer = config.get_printer()
        self.gcode = self.printer.lookup_object("gcode")
        self.reactor = self.printer.get_reactor()
        self.original_m141 = None
        self.original_m106 = None
        self.pre_file_case_fan_deadline = 0.0
        self.printer.register_event_handler("klippy:ready", self._handle_ready)

    def _handle_ready(self):
        if self.original_m141 is not None or self.original_m106 is not None:
            return
        original_m141 = self.gcode.register_command("M141", None)
        original_m106 = self.gcode.register_command("M106", None)
        if original_m141 is None or original_m106 is None:
            if original_m141 is not None:
                self.gcode.register_command("M141", original_m141)
            if original_m106 is not None:
                self.gcode.register_command("M106", original_m106)
            raise self.printer.config_error(
                "k2_m141_guard could not find Creality's original fan handlers"
            )

        self.original_m141 = original_m141
        self.original_m106 = original_m106
        try:
            self.gcode.register_command(
                "M141",
                self.cmd_M141,
                desc="Set chamber temperature without losing the print exhaust ceiling",
            )
            self.gcode.register_command(
                "M106",
                self.cmd_M106,
                desc="Set fan speed while filtering Creality's pre-file case-fan request",
            )
        except Exception:
            self.gcode.register_command("M141", None)
            self.gcode.register_command("M106", None)
            self.gcode.register_command("M141", self.original_m141)
            self.gcode.register_command("M106", self.original_m106)
            self.original_m141 = None
            self.original_m106 = None
            raise

    def _print_state(self):
        print_stats = self.printer.lookup_object("print_stats")
        return print_stats.get_status(self.reactor.monotonic()).get("state")

    def _chamber_fan_margin(self):
        variables = self.printer.lookup_object("gcode_macro _M191_VARS")
        status = variables.get_status(self.reactor.monotonic())
        return float(status["chamber_fan_margin"])

    def cmd_M141(self, gcmd):
        target = gcmd.get_float("S", None)
        print_state = self._print_state()
        should_restore = (
            target is not None
            and target > 40.0
            and print_state == "printing"
        )

        # Heated-bed deformation calibration sends M141 S30, then sends a
        # direct M106 P1 request about 200 ms later, before it starts the file.
        # Arm only that short, idle pre-file handoff; slicer and manual fan
        # commands outside the window continue to use Creality's handler.
        if target == 30.0 and print_state not in ("printing", "paused"):
            self.pre_file_case_fan_deadline = (
                self.reactor.monotonic() + self.PREFILE_CASE_FAN_WINDOW
            )

        if should_restore:
            margin = self._chamber_fan_margin()
            if margin < 0.0 or margin > 10.0:
                raise gcmd.error(
                    "M191 chamber_fan_margin must be from 0 to 10 C"
                )

        self.original_m141(gcmd)

        if should_restore:
            self.gcode.run_script_from_command(
                "SET_TEMPERATURE_FAN_TARGET "
                "TEMPERATURE_FAN=chamber_fan TARGET=%.6f"
                % (target + margin)
            )

    def cmd_M106(self, gcmd):
        fan = gcmd.get_int("P", 0)
        speed = gcmd.get_float("S", 255.0)
        within_pre_file_window = (
            self.reactor.monotonic() <= self.pre_file_case_fan_deadline
            and self._print_state() not in ("printing", "paused")
        )
        if fan == 1 and speed > 0.0 and within_pre_file_window:
            self.pre_file_case_fan_deadline = 0.0
            gcmd.respond_info(
                "[CASE_FAN]: Suppressed Creality pre-file case-fan override"
            )
            return
        self.original_m106(gcmd)


def load_config(config):
    return K2M141Guard(config)
