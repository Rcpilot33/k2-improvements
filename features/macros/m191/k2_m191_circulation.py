"""Temperature wait with alternating K2 model and side circulation fans."""


class K2M191Circulation:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.reactor = self.printer.get_reactor()
        self.gcode = self.printer.lookup_object("gcode")
        self.gcode.register_command(
            "K2_M191_CIRCULATION_WAIT",
            self.cmd_wait,
            desc="Wait for chamber temperature while cycling circulation fans",
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

    def _report_temperatures(self, eventtime, report_id, temperature, target):
        heaters = self.printer.lookup_object("heaters")
        standard_report = heaters._get_temp(eventtime)
        chamber_report = "%s:%.1f /%.1f" % (
            report_id, temperature, target
        )
        self.gcode.respond_raw("%s %s" % (standard_report, chamber_report))

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
