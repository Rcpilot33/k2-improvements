"""Keep Creality's native PR Touch live adjustments transient.

master-server reads probe.z_offset for its live-offset display AND its
SET_GCODE_OFFSET / Z_OFFSET_APPLY_PROBE cleanup pair. Native PrinterProbe
normally publishes the loaded or staged calibration there, causing cleanup
to subtract a calibration instead of the live adjustment. Match the existing
Cartographer display contract without changing loaded probe calibration,
get_offsets(), or motion. Z_OFFSET_APPLY_PROBE retains the native in-memory
and print-recovery bookkeeping, but never stages a calibration save. A future
dedicated global-offset editor owns deliberate calibration persistence.
"""

import logging


LOG_PREFIX = "[K2_PRTOUCH_TOUCHSCREEN]"


class K2PRTouchTouchscreen:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.gcode = self.printer.lookup_object("gcode")
        self.probe = None
        self.gcode_move = None
        self.original_get_status = None
        self.installed = False
        self.gcode.register_command(
            "K2_PRTOUCH_TOUCHSCREEN_STATUS", self.cmd_status,
            desc="Show native PR Touch live-offset display compatibility status",
        )
        # Install before ready-time diagnostic command wrappers, so the passive
        # tracer still observes our replacement rather than being removed by it.
        self.printer.register_event_handler("klippy:connect", self._handle_ready)
        self.printer.register_event_handler("klippy:ready", self._handle_ready)

    def _handle_ready(self):
        if self.installed:
            return
        # Cartographer can expose a dummy prtouch_v3 object for factory clients.
        # Always exclude it before considering the native probe's identity.
        if self.printer.lookup_object("cartographer", None) is not None:
            logging.info("%s inactive; Cartographer is loaded", LOG_PREFIX)
            return
        native = self.printer.lookup_object("prtouch_v3", None)
        probe = self.printer.lookup_object("probe", None)
        gcode_move = self.printer.lookup_object("gcode_move", None)
        if (native is None or probe is None or gcode_move is None
                or getattr(probe, "name", None) != "prtouch_v3"
                or not hasattr(probe, "z_offset")
                or not hasattr(probe, "z_offset_calibrate")
                or not hasattr(probe, "z_offset_change_flag")
                or not callable(getattr(probe, "record_gcode_offset_when_printing", None))
                or not callable(getattr(probe, "get_offsets", None))
                or not callable(getattr(probe, "get_status", None))
                or not callable(getattr(gcode_move, "get_status", None))):
            logging.warning("%s inactive; supported native prtouch_v3 probe "
                            "is not loaded", LOG_PREFIX)
            return
        self.probe = probe
        self.gcode_move = gcode_move
        original = self.gcode.register_command("Z_OFFSET_APPLY_PROBE", None)
        if original is None:
            logging.warning("%s inactive; native offset-apply command missing",
                            LOG_PREFIX)
            return
        try:
            self.gcode.register_command(
                "Z_OFFSET_APPLY_PROBE", self.cmd_offset_apply,
                desc="Record temporary native PR Touch live adjustment without staging calibration",
            )
        except Exception:
            self.gcode.register_command("Z_OFFSET_APPLY_PROBE", None)
            self.gcode.register_command("Z_OFFSET_APPLY_PROBE", original)
            raise
        self.original_get_status = probe.get_status
        probe.get_status = self._get_probe_status
        self.installed = True
        logging.info("%s exposing inverse live gcode_move.homing_origin.z "
                     "as probe.z_offset; offset apply is transient-only", LOG_PREFIX)

    def cmd_offset_apply(self, gcmd):
        # The native handler performs exactly this bookkeeping after staging
        # configfile.set(name, 'z_offset', ...). Keep the recovery data and
        # native status attributes, but omit that staging call and SAVE_CONFIG
        # prompt. Do not remove/overwrite pre-existing deliberate pending values.
        self.probe.z_offset_calibrate = self.probe.z_offset - self._live_offset(0.0)
        self.probe.z_offset_change_flag = True
        self.probe.record_gcode_offset_when_printing()
        gcmd.respond_info(
            "prtouch_v3: transient offset %.3f; no calibration save staged"
            % self.probe.z_offset_calibrate
        )

    def _live_offset(self, eventtime):
        return float(self.gcode_move.get_status(eventtime)["homing_origin"].z)

    def _get_probe_status(self, eventtime):
        # Copy rather than mutate the original status mapping. All other probe
        # fields retain their native meaning, including query/result fields.
        status = dict(self.original_get_status(eventtime))
        status["z_offset"] = round(-self._live_offset(eventtime), 6)
        return status

    def get_status(self, eventtime):
        if not self.installed:
            return {"installed": False, "transient_only": False, "live_z_offset": None,
                    "probe_z_offset": None, "loaded_z_offset": None,
                    "native_reported_z_offset": None}
        live = self._live_offset(eventtime)
        return {
            "installed": True,
            "transient_only": True,
            "live_z_offset": live,
            "probe_z_offset": round(-live, 6),
            "loaded_z_offset": self.probe.z_offset,
            "native_reported_z_offset":
                self.original_get_status(eventtime).get("z_offset"),
        }

    def cmd_status(self, gcmd):
        status = self.get_status(0.0)
        gcmd.respond_info(
            "%s installed=%s transient_only=%s live_z_offset=%s probe_z_offset=%s "
            "loaded_z_offset=%s native_reported_z_offset=%s"
            % (LOG_PREFIX, status["installed"], status["transient_only"], status["live_z_offset"],
               status["probe_z_offset"], status["loaded_z_offset"],
               status["native_reported_z_offset"])
        )


def load_config(config):
    return K2PRTouchTouchscreen(config)
