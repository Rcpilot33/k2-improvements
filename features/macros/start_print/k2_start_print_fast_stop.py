"""Make managed print preparation honor Creality Fast Stop."""

import inspect
import logging
import re


# Only managed, rendered no-Carto soak lines are intercepted. Other commands
# (including dwells inside native probe/cleaning routines) retain stock behavior.
SOAK_DWELL = re.compile(
    r"^\s*G4\s+P([0-9]+(?:\.[0-9]*)?)\s*(?:#.*)?$", re.IGNORECASE
)


class K2StartPrintFastStop:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.gcode = self.printer.lookup_object("gcode")
        self.active = False
        self.printer.register_event_handler("klippy:ready", self._handle_ready)

    def _supports_fast_stop(self):
        process_commands = getattr(self.gcode, "_process_commands", None)
        if process_commands is None or not hasattr(self.gcode, "cancel_pending"):
            return False
        try:
            parameters = inspect.signature(process_commands).parameters
        except (TypeError, ValueError):
            return False
        return "check_cancel" in parameters

    def _handle_ready(self):
        if self.active:
            return
        if not self._supports_fast_stop():
            logging.info(
                "START_PRINT Fast Stop inactive: Creality cancel API unavailable"
            )
            return

        start_print = self.printer.lookup_object("gcode_macro START_PRINT", None)
        if start_print is None or not hasattr(start_print, "template"):
            raise self.printer.config_error(
                "START_PRINT Fast Stop requires the managed START_PRINT macro"
            )
        stock_probe = (
            self.printer.lookup_object("prtouch_v3", None) is not None
            and self.printer.lookup_object("cartographer", None) is None
        )
        self._make_template_cancelable(start_print.template, stock_soaks=stock_probe)

        # M191 is a nested macro within START_PRINT.  Give its command loop the
        # same boundary checks so a canceled chamber wait does not execute its
        # normal successful-wait restoration before END_PRINT takes control.
        m191 = self.printer.lookup_object("gcode_macro M191", None)
        if m191 is not None and hasattr(m191, "template"):
            self._make_template_cancelable(m191.template)

        # Stock mesh creation has its own nested command loops. A canceled
        # M191 must unwind all of them, not resume with soak/tilt/mesh commands.
        # Leave the Cartographer path and native probe routines unchanged.
        if stock_probe:
            for name in ("MESH_IF_NEEDED", "_CREATE_MESH"):
                macro = self.printer.lookup_object("gcode_macro " + name, None)
                if macro is not None and hasattr(macro, "template"):
                    self._make_template_cancelable(macro.template, stock_soaks=True)

        self.active = True
        logging.info("START_PRINT Fast Stop enabled")

    def _make_template_cancelable(self, template, stock_soaks=False):
        if getattr(template, "k2_fast_stop_active", False):
            return

        def run_cancelable_start_print(context=None):
            script = template.render(context)
            if stock_soaks:
                self._run_stock_commands(script.split("\n"))
            else:
                self.gcode._process_commands(
                    script.split("\n"), need_ack=False, check_cancel=True
                )

        template.run_gcode_from_command = run_cancelable_start_print
        template.k2_fast_stop_active = True

    def _run_stock_commands(self, commands):
        pending = []
        for line in commands:
            dwell = SOAK_DWELL.fullmatch(line)
            if dwell is None:
                pending.append(line)
                continue
            self.gcode._process_commands(
                pending, need_ack=False, check_cancel=True
            )
            pending = []
            if self.is_cancel_pending() or self.printer.is_shutdown():
                return
            if not self._wait_stock_soak(float(dwell.group(1)) / 1000.):
                return
        self.gcode._process_commands(pending, need_ack=False, check_cancel=True)

    def _wait_stock_soak(self, seconds):
        # Do not queue a multi-minute idle interval on the MCU: END_PRINT would
        # inherit that interval even if the remaining macro commands are skipped.
        # Finish preceding physical moves, then wait on the host reactor instead.
        if self.printer.get_start_args().get("debugoutput") is not None:
            return True
        self.printer.lookup_object("toolhead").wait_moves()
        reactor = self.printer.get_reactor()
        eventtime = reactor.monotonic()
        deadline = eventtime + seconds
        while not self.printer.is_shutdown():
            if self.is_cancel_pending():
                self.gcode.respond_info("Heat soak stopped by print cancellation")
                return False
            if eventtime >= deadline:
                return True
            eventtime = reactor.pause(min(deadline, eventtime + 1.))
        return False

    def get_status(self, eventtime):
        return {"active": self.active}

    def is_cancel_pending(self):
        """Report Creality Fast Stop only while this gated helper is active."""
        return self.active and bool(getattr(self.gcode, "cancel_pending", False))


def load_config(config):
    return K2StartPrintFastStop(config)
