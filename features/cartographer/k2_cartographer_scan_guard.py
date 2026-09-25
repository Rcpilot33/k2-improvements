"""Restore safe configured motion limits when a Cartographer mesh aborts."""


class K2CartographerScanGuard:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.gcode = self.printer.lookup_object("gcode")
        self.active = False
        self.gcode.register_command(
            "_K2_CARTO_SCAN_GUARD", self.cmd_guard
        )
        self.printer.register_event_handler(
            "gcode:command_error", self._handle_command_error
        )

    def cmd_guard(self, gcmd):
        self.active = bool(gcmd.get_int("ACTIVE", minval=0, maxval=1))

    def _configured_limits(self):
        configfile = self.printer.lookup_object("configfile")
        settings = configfile.get_status(None)["settings"]["printer"]
        return (
            float(settings["max_velocity"]),
            float(settings["square_corner_velocity"]),
            float(settings["max_accel"]),
            float(settings.get("max_accel_to_decel", settings["max_accel"])),
        )

    def _handle_command_error(self):
        if not self.active:
            return
        self.active = False
        velocity, scv, accel, accel_to_decel = self._configured_limits()
        self.gcode.run_script_from_command(
            "SET_VELOCITY_LIMIT VELOCITY=%.6f "
            "SQUARE_CORNER_VELOCITY=%.6f ACCEL=%.6f "
            "ACCEL_TO_DECEL=%.6f"
            % (velocity, scv, accel, accel_to_decel)
        )
        self.gcode.respond_info(
            "Cartographer mesh aborted; restored configured motion limits"
        )


def load_config(config):
    return K2CartographerScanGuard(config)
