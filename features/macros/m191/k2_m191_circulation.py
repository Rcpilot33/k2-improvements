"""Temperature wait with alternating K2 model and side circulation fans."""


class K2M191Circulation:
    CHAMBER_FAN_OFF_TARGET = 80.0
    CHAMBER_FAN_ON_TARGET = 1.0
    CHAMBER_FAN_TRANSITION_TIMEOUT = 2.0
    CHAMBER_FAN_POLL_INTERVAL = 0.050

    def __init__(self, config):
        self.printer = config.get_printer()
        self.reactor = self.printer.get_reactor()
        self.gcode = self.printer.lookup_object("gcode")
        self.gcode.register_command(
            "K2_M191_CIRCULATION_WAIT",
            self.cmd_wait,
            desc="Wait for chamber temperature while cycling circulation fans",
        )
        self.gcode.register_command(
            "K2_CHAMBER_FAN_RESYNC",
            self.cmd_chamber_fan_resync,
            desc="Resynchronize the chamber thermostat with its shared fan pin",
        )

    def _set_fans(self, pwm):
        pwm = max(0, min(255, int(pwm)))
        self.gcode.run_script_from_command(
            "M106 S%d\nM106 P2 S%d" % (pwm, pwm)
        )

    def _lookup_sensor(self, sensor_name):
        heaters = self.printer.lookup_object("heaters")
        if sensor_name in heaters.heaters:
            return heaters.heaters[sensor_name]
        return self.printer.lookup_object(sensor_name, None)

    def _set_chamber_fan_target(self, target):
        self.gcode.run_script_from_command(
            "SET_TEMPERATURE_FAN_TARGET "
            "TEMPERATURE_FAN=chamber_fan TARGET=%.6f" % target
        )

    def _wait_for_chamber_fan_output(self, chamber_fan, enabled, gcmd):
        eventtime = self.reactor.monotonic()
        deadline = eventtime + self.CHAMBER_FAN_TRANSITION_TIMEOUT
        while eventtime < deadline:
            speed = float(chamber_fan.get_status(eventtime).get("speed", 0.0))
            if (speed > 0.0) == enabled:
                return
            eventtime = self.reactor.pause(
                min(eventtime + self.CHAMBER_FAN_POLL_INTERVAL, deadline)
            )
        state = "on" if enabled else "off"
        raise gcmd.error(
            "Chamber fan controller did not transition %s during resync" % state
        )

    def cmd_chamber_fan_resync(self, gcmd):
        target = gcmd.get_float("TARGET", minval=-30.0, maxval=80.0)
        chamber_fan = self.printer.lookup_object(
            "temperature_fan chamber_fan", None
        )
        if chamber_fan is None:
            raise gcmd.error("Unknown temperature_fan chamber_fan")

        try:
            self._set_chamber_fan_target(self.CHAMBER_FAN_OFF_TARGET)
            self._wait_for_chamber_fan_output(chamber_fan, False, gcmd)
            self._set_chamber_fan_target(self.CHAMBER_FAN_ON_TARGET)
            self._wait_for_chamber_fan_output(chamber_fan, True, gcmd)
        finally:
            self._set_chamber_fan_target(target)

    def _report_temperatures(self, eventtime, report_id, temperature, target):
        heaters = self.printer.lookup_object("heaters")
        standard_report = heaters._get_temp(eventtime)
        chamber_report = "%s:%.1f /%.1f" % (
            report_id, temperature, target
        )
        self.gcode.respond_raw("%s %s" % (standard_report, chamber_report))

    def _fast_stop_requested(self):
        # This object is installed only after the firmware-version and API
        # checks in install_fast_stop.sh succeed.  Older firmware therefore
        # retains the original M191 behavior.
        helper = self.printer.lookup_object("k2_start_print_fast_stop", None)
        check_cancel = getattr(helper, "is_cancel_pending", None)
        return check_cancel is not None and check_cancel()

    def cmd_wait(self, gcmd):
        sensor_name = gcmd.get("SENSOR")
        minimum = gcmd.get_float("MINIMUM", float("-inf"))
        maximum = gcmd.get_float("MAXIMUM", float("inf"), above=minimum)
        if minimum == float("-inf") and maximum == float("inf"):
            raise gcmd.error(
                "K2_M191_CIRCULATION_WAIT requires MINIMUM or MAXIMUM"
            )

        low_pwm = gcmd.get_int("LOW_PWM", minval=0, maxval=255)
        high_pwm = gcmd.get_int("HIGH_PWM", minval=low_pwm, maxval=255)
        low_seconds = gcmd.get_float("LOW_SECONDS", above=0.0, maxval=600.0)
        high_seconds = gcmd.get_float("HIGH_SECONDS", above=0.0, maxval=600.0)
        cycle_fans = gcmd.get_int("CYCLE_FANS", minval=0, maxval=1)
        report_id = gcmd.get("REPORT_ID")
        report_target = gcmd.get_float("REPORT_TARGET")

        if self.printer.get_start_args().get("debugoutput") is not None:
            return

        sensor = self._lookup_sensor(sensor_name)
        if sensor is None:
            raise gcmd.error("Unknown temperature sensor %s" % sensor_name)
        toolhead = self.printer.lookup_object("toolhead")
        eventtime = self.reactor.monotonic()
        low_phase = True
        next_transition = eventtime + low_seconds
        if cycle_fans:
            self._set_fans(low_pwm)

        try:
            while not self.printer.is_shutdown():
                if self._fast_stop_requested():
                    gcmd.respond_info("Chamber wait stopped by print cancellation")
                    return

                temperature, _target = sensor.get_temp(eventtime)
                if minimum <= temperature <= maximum:
                    return

                self._report_temperatures(
                    eventtime, report_id, temperature, report_target
                )

                if cycle_fans and eventtime >= next_transition:
                    low_phase = not low_phase
                    if low_phase:
                        self._set_fans(low_pwm)
                        duration = low_seconds
                        label = "low"
                    else:
                        self._set_fans(high_pwm)
                        duration = high_seconds
                        label = "high"
                    gcmd.respond_info(
                        "Bed assist circulation changed to %s fan speed" % label
                    )
                    next_transition = eventtime + duration

                # Match Klipper's normal temperature wait cadence while waking
                # exactly on a fan transition when it is less than a second away.
                toolhead.get_last_move_time()
                eventtime = self.reactor.pause(
                    min(eventtime + 1.0, next_transition)
                    if cycle_fans else eventtime + 1.0
                )
        finally:
            if cycle_fans:
                self._set_fans(0)


def load_config(config):
    return K2M191Circulation(config)
