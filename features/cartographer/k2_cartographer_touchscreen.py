"""Expose Klipper's live G-code Z offset to the K2 touchscreen.

The stock c440x touchscreen reads ``probe.z_offset`` while its live Z-offset
page is open.  Cartographer's Klipper probe adapter intentionally follows the
upstream probe status API, which does not include that Creality-only field.
This compatibility layer derives that field from
``gcode_move.homing_origin.z`` without changing motion, the live offset, or
Cartographer's saved models.  Creality's screen treats ``probe.z_offset`` as
the inverse of the displayed live adjustment, matching the stock probe's
``Z_OFFSET_APPLY_PROBE`` behavior.
"""

import logging


LOG_PREFIX = "[K2_CARTOGRAPHER_TOUCHSCREEN]"


class K2CartographerTouchscreen:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.gcode = self.printer.lookup_object("gcode")
        self.cartographer = None
        self.probe = None
        self.gcode_move = None
        self.original_get_status = None
        self.installed = False
        self.gcode.register_command(
            "K2_CARTOGRAPHER_TOUCHSCREEN_STATUS",
            self.cmd_status,
            desc="Show Cartographer touchscreen Z-offset compatibility status",
        )
        self.printer.register_event_handler("klippy:ready", self._handle_ready)

    def _handle_ready(self):
        self.cartographer = self.printer.lookup_object("cartographer", None)
        self.probe = self.printer.lookup_object("probe", None)
        self.gcode_move = self.printer.lookup_object("gcode_move", None)
        if (
            self.cartographer is None
            or self.probe is None
            or self.gcode_move is None
        ):
            logging.info("%s inactive; Cartographer probe is not loaded", LOG_PREFIX)
            return

        if not hasattr(self.cartographer, "scan_mode") or not hasattr(
            self.cartographer, "touch_mode"
        ):
            logging.warning(
                "%s inactive; unsupported Cartographer object", LOG_PREFIX
            )
            return

        self.original_get_status = self.probe.get_status
        self.probe.get_status = self._get_probe_status
        self.installed = True
        logging.info(
            "%s exposing inverse live gcode_move.homing_origin.z as probe.z_offset",
            LOG_PREFIX,
        )

    def _get_probe_status(self, eventtime):
        status = dict(self.original_get_status(eventtime))
        status["z_offset"] = self._get_probe_z_offset(eventtime)
        return status

    def _get_live_z_offset(self, eventtime):
        origin = self.gcode_move.get_status(eventtime)["homing_origin"]
        return float(origin.z)

    def _get_probe_z_offset(self, eventtime):
        return round(-self._get_live_z_offset(eventtime), 6)

    def get_status(self, eventtime):
        return {
            "installed": self.installed,
            "z_offset": self._get_live_z_offset(eventtime) if self.installed else None,
            "probe_z_offset": self._get_probe_z_offset(eventtime)
            if self.installed
            else None,
        }

    def cmd_status(self, gcmd):
        status = self.get_status(0.0)
        gcmd.respond_info(
            "%s installed=%s z_offset=%s probe_z_offset=%s"
            % (
                LOG_PREFIX,
                status["installed"],
                status["z_offset"],
                status["probe_z_offset"],
            )
        )


def load_config(config):
    return K2CartographerTouchscreen(config)
