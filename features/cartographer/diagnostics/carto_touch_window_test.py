"""Opt-in, bounded K2 touch-disconnect diagnostic. Never installed by default.

Uses native toolhead coordinates, not G-code offsets. Physical clearance must
be verified independently; this code cannot detect an incorrect Z origin.
"""

import logging
import math


START_Z = 150.0
END_Z = 50.0
SPEED = 2.0
ACCEL = 100.0


class TouchWindowTest:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.used = False
        self.printer.lookup_object("gcode").register_command(
            "CARTO_TOUCH_WINDOW_TEST", self.run,
            desc="Diagnostic only: one bounded touch move Z150 to Z50; shuts down afterward",
        )

    def run(self, gcmd):
        if self.used:
            raise gcmd.error("Diagnostic already attempted; restart and rehome before another test")
        if gcmd.get("CONFIRM", "") != "CLEAR_WINDOW":
            raise gcmd.error("Verify physical clearance throughout Z50..150, then use CONFIRM=CLEAR_WINDOW")
        if self.printer.is_shutdown():
            raise gcmd.error("Printer is shut down")
        toolhead = self.printer.lookup_object("toolhead")
        now = self.printer.get_reactor().monotonic()
        status = toolhead.get_status(now)
        if not all(axis in status["homed_axes"] for axis in "xyz"):
            raise gcmd.error("Accurately home XYZ with Cartographer connected before testing")
        stats = self.printer.lookup_object("print_stats", None)
        if stats is not None and stats.get_status(now)["state"] in ("printing", "paused"):
            raise gcmd.error("Cannot test during a print or paused print")
        sd = self.printer.lookup_object("virtual_sdcard", None)
        if sd is not None and sd.is_active():
            raise gcmd.error("Cannot test while virtual SD is active")
        position = toolhead.get_position()[:]
        if not all(math.isfinite(value) for value in position[:3]):
            raise gcmd.error("Invalid toolhead position")
        if position[2] < END_Z:
            raise gcmd.error("First position the bed at a verified clearance of at least Z50")
        if not (status["axis_minimum"][2] <= END_Z < START_Z <= status["axis_maximum"][2]):
            raise gcmd.error("Z50..150 is outside configured travel limits")
        actual, target = toolhead.get_extruder().get_heater().get_temp(now)
        if not (math.isfinite(actual) and actual <= 50.0 and target == 0.0):
            raise gcmd.error("Nozzle must be below 50C with heater target zero")
        carto = self.printer.lookup_object("cartographer")
        carto.mcu.ensure_connected()
        model = carto.touch_mode.get_model()
        if not math.isfinite(model.threshold) or model.threshold <= 0:
            raise gcmd.error("Load a valid calibrated touch model first")
        if not carto.touch_mode.boundaries.is_within(x=position[0], y=position[1]):
            raise gcmd.error("Position XY inside the configured touch boundaries first")

        # Import only when explicitly invoked; use the exact production endstop.
        from cartographer.adapters.klipper.endstop import KlipperEndstop

        endstop = KlipperEndstop(carto.mcu, carto.touch_mode)
        homing = self.printer.lookup_object("homing")
        old_accel = toolhead.get_max_accel()
        self.used = True
        try:
            toolhead.wait_moves()
            gcmd.respond_info("Touch window test: positioning to Z150. DO NOT UNPLUG YET.")
            toolhead.manual_move([None, None, START_Z], speed=5.0)
            toolhead.wait_moves()
            carto.mcu.ensure_connected()
            # Match the production touch acceleration and fresh-sample preflight.
            self.printer.lookup_object("gcode").run_script_from_command("SET_VELOCITY_LIMIT ACCEL=%g" % ACCEL)
            move_time = toolhead.get_last_move_time()
            with carto.mcu.start_session(lambda sample: sample.time >= move_time):
                pass
            destination = toolhead.get_position()[:]
            if not all(math.isfinite(value) for value in destination[:3]) or abs(destination[2] - START_Z) > 0.01:
                raise gcmd.error("Failed to reach diagnostic start position")
            destination[2] = END_Z
            gcmd.respond_info(
                "Touch window test: issuing ONE touch-armed Z150 -> Z50 move at 2mm/s. "
                "Wait for visible approach before unplugging. Do not reconnect until shutdown."
            )
            homing.probing_move(endstop, destination, SPEED)
            gcmd.respond_info(
                "Touch window move returned. This is NOT a calibration or automatic PASS; inspect logs and motion."
            )
        except Exception:
            logging.exception("Touch window diagnostic ended with an error")
            raise
        finally:
            # Do not issue any retract, retry, homing, or model save. A failed
            # homing cleanup can leave commanded position unlike physical Z.
            self.printer.invoke_shutdown("Touch window diagnostic ended; restart and rehome before further motion")
            logging.info("Touch window diagnostic prior acceleration was %.3f; restart restores configuration", old_accel)


def load_config(config):
    return TouchWindowTest(config)
