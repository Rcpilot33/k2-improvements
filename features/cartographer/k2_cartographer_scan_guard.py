"""Restore safe configured motion limits when a Cartographer mesh aborts."""

import logging


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
        # command_error fires while G-code dispatch is already unwinding. Do
        # not recursively run SET_VELOCITY_LIMIT from that handler; restore
        # the same ToolHead fields directly and recalculate junction limits.
        toolhead = self.printer.lookup_object("toolhead")
        toolhead.max_velocity = velocity
        toolhead.square_corner_velocity = scv
        toolhead.max_accel = accel
        toolhead.max_accel_to_decel = accel_to_decel
        toolhead._calc_junction_deviation()
        logging.warning(
            "Cartographer mesh aborted; restored configured motion limits"
        )


def load_config(config):
    return K2CartographerScanGuard(config)
