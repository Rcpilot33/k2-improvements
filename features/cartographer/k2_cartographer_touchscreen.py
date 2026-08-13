"""Expose Cartographer's active model offset to the K2 touchscreen.

The stock c440x touchscreen reads ``probe.z_offset`` while its live Z-offset
page is open.  Cartographer's Klipper probe adapter intentionally follows the
upstream probe status API, which does not include that Creality-only field.
This compatibility layer adds the field without changing motion or offset
handling.
"""

import logging


LOG_PREFIX = "[K2_CARTOGRAPHER_TOUCHSCREEN]"


class K2CartographerTouchscreen:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.cartographer = None
        self.probe = None
        self.original_get_status = None
        self.installed = False
        self.printer.register_event_handler("klippy:ready", self._handle_ready)

    def _handle_ready(self):
        self.cartographer = self.printer.lookup_object("cartographer", None)
        self.probe = self.printer.lookup_object("probe", None)
        if self.cartographer is None or self.probe is None:
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
            "%s exposing active Cartographer model as probe.z_offset", LOG_PREFIX
        )

    def _get_probe_status(self, eventtime):
        status = dict(self.original_get_status(eventtime))
        offset = self._get_active_model_offset()
        if offset is not None:
            status["z_offset"] = round(offset, 6)
        return status

    def _get_active_model_offset(self):
        scan = self.cartographer.scan_mode
        touch = self.cartographer.touch_mode

        # Match Cartographer's Z_OFFSET_APPLY_PROBE mode selection.  A K2 print
        # touch-homes Z, so touch is normally the newer mode while printing.
        mode = touch if touch.last_homing_time > scan.last_homing_time else scan
        try:
            if not mode.has_model():
                return None
            return float(mode.get_model().z_offset)
        except (AttributeError, KeyError, TypeError, ValueError):
            logging.exception("%s could not read the active model", LOG_PREFIX)
            return None

    def get_status(self, eventtime):
        del eventtime
        return {
            "installed": self.installed,
            "z_offset": self._get_active_model_offset() if self.installed else None,
        }


def load_config(config):
    return K2CartographerTouchscreen(config)
