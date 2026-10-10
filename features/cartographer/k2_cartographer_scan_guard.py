"""Mesh-scoped JimmyV front travel and safe motion-limit abort cleanup."""

import logging


class K2CartographerScanGuard:
    FRONT_LIMIT = -6.0
    MOUNT_OFFSETS = {"jimmyv_legacy": 36.0, "jimmyv_final_12": 12.0,
                     "jimmyv_final_17": 17.0}

    def __init__(self, config):
        self.printer = config.get_printer()
        self.gcode = self.printer.lookup_object("gcode")
        self.active = False
        self.front_active = False
        self.mount_profile = config.get("mount_profile", "none")
        self.front_travel = config.getfloat("mesh_front_travel", 0., minval=0., maxval=6.)
        if self.front_travel:
            offset = self.MOUNT_OFFSETS.get(self.mount_profile)
            carto = config.getsection("cartographer")
            if (offset is None or self.front_travel != 6.
                    or carto.getfloat("x_offset", 0.) != 0.
                    or carto.getfloat("y_offset") != offset):
                raise config.error("Mesh front travel requires an explicitly selected JimmyV mount")
        self._mesh_handler = None
        self.printer.register_event_handler("klippy:ready", self._install_mesh_hook)
        self.gcode.register_command(
            "_K2_CARTO_SCAN_GUARD", self.cmd_guard
        )
        self.printer.register_event_handler(
            "gcode:command_error", self._handle_command_error
        )

    def cmd_guard(self, gcmd):
        self.active = bool(gcmd.get_int("ACTIVE", minval=0, maxval=1))

    def _install_mesh_hook(self):
        if not self.front_travel or self._mesh_handler is not None:
            return
        # After ready, Cartographer and the managed macro have completed their
        # command registrations/rename. Do not expose a separate unlock command.
        name = "BED_MESH_CALIBRATE_ORIG"
        original = self.gcode.register_command(name, None)
        if original is None:
            raise self.printer.config_error("JimmyV mesh guard requires BED_MESH_CALIBRATE_ORIG")
        self._mesh_handler = original
        self.gcode.register_command(name, self._run_mesh)

    def _run_mesh(self, gcmd):
        if gcmd.get("METHOD", "scan").lower() != "scan":
            return self._mesh_handler(gcmd)
        if self.front_active:
            raise gcmd.error("A JimmyV mesh is already active")
        toolhead = self.printer.lookup_object("toolhead")
        kin = toolhead.get_kinematics()
        limits = tuple(tuple(pair) for pair in kin.limits)
        if any(lo >= hi for lo, hi in limits):
            raise gcmd.error("Home XYZ before using JimmyV mesh front travel")
        if kin.rails[1].get_range()[0] > self.FRONT_LIMIT:
            raise gcmd.error("Configured Y travel does not permit JimmyV mesh Y=-6")
        if not callable(getattr(kin, "set_limits", None)):
            raise gcmd.error("This firmware has no supported runtime XY limit setter")
        old_min = kin.axes_min
        # Complete earlier moves before changing the Python AND native C limits.
        toolhead.wait_moves()
        try:
            self.front_active = True
            kin.set_limits(limits[0][0], limits[0][1], self.FRONT_LIMIT, limits[1][1])
            # Cartographer uses axis_minimum for scan-path corner clearance.
            # Publish the same floor so rounded paths cannot extend past -6.
            kin.axes_min = old_min._replace(y=self.FRONT_LIMIT)
            gcmd.respond_info("JimmyV mesh-only front boundary opened to Y=-6.000")
            result = self._mesh_handler(gcmd)
            # End inside the ordinary boundary before closing it. Keep X/Z/E
            # unchanged and never lower the nozzle or extrude during this exit.
            target_y = max(0., limits[1][0])
            if toolhead.get_position()[1] < target_y:
                toolhead.manual_move([None, target_y, None], 50.)
            toolhead.wait_moves()
            return result
        finally:
            # Also runs on scan failure, disconnect, cancellation, and shutdown.
            # No recovery motion on errors, and never re-home an axis invalidated
            # by a motor-off/shutdown callback while scanning.
            kin.axes_min = old_min
            xy = [limits[i] if kin.limits[i][0] <= kin.limits[i][1]
                  else tuple(kin.limits[i]) for i in (0, 1)]
            self.front_active = False
            kin.set_limits(xy[0][0], xy[0][1], xy[1][0], xy[1][1])
            logging.info("JimmyV mesh-only front boundary restored")

    def get_status(self, eventtime):
        limits = self.printer.lookup_object("toolhead").get_kinematics().limits[1]
        return {"mesh_front_active": self.front_active,
                "mesh_front_travel": self.front_travel,
                "mount_profile": self.mount_profile,
                "y_limits": list(limits)}

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
