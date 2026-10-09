"""Live Fluidd editor for saved Cartographer Scan- or Touch-model Z offsets."""

import logging
from dataclasses import replace


LOG_PREFIX = "[K2_CARTOGRAPHER_OFFSET_EDITOR]"
MODEL_PREFIXES = {
    "touch": "cartographer touch_model ",
    "scan": "cartographer scan_model ",
}
PREFERRED_ORDER = ("default", "textured_pei", "epoxy", "high_temp", "custom")


class K2CartographerOffsetEditor:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.gcode = self.printer.lookup_object("gcode")
        self.configfile = self.printer.lookup_object("configfile")
        self.models = None
        self.mode = None

        self.gcode.register_command(
            "K2_CARTOGRAPHER_GLOBAL_Z_OFFSETS",
            self.cmd_open,
            desc="Edit saved Cartographer Scan- or Touch-model Z offsets",
        )
        self.gcode.register_command(
            "K2_CARTOGRAPHER_GLOBAL_Z_STAGE", self.cmd_stage
        )
        self.gcode.register_command(
            "K2_CARTOGRAPHER_GLOBAL_Z_CANCEL", self.cmd_cancel
        )
        self.gcode.register_command(
            "K2_CARTOGRAPHER_GLOBAL_Z_SAVE", self.cmd_save
        )

    @staticmethod
    def _format_offset(value):
        value = round(float(value), 3)
        if value == 0:
            value = 0.0
        return "%.3f" % value

    @staticmethod
    def _safe_text(value):
        return str(value).replace("\r", " ").replace("\n", " ").replace("|", "/")

    @staticmethod
    def _sort_key(model):
        name = model["name"].lower()
        try:
            return (0, PREFERRED_ORDER.index(name))
        except ValueError:
            return (1, name)

    def _printing_or_paused(self):
        print_stats = self.printer.lookup_object("print_stats", None)
        if print_stats is None:
            return False
        state = str(print_stats.get_status(0.0).get("state", "")).lower()
        return state in ("printing", "paused")

    def _active_mode(self, gcmd):
        macro = self.printer.lookup_object("gcode_macro _START_PRINT_VARS", None)
        status = macro.get_status(0.0) if macro is not None else {}
        mode = str(status.get("carto_final_z_mode", "touch")).strip().lower()
        if mode not in MODEL_PREFIXES:
            raise gcmd.error("carto_final_z_mode must be touch or scan")
        return mode

    def _load_models(self, gcmd, mode):
        raw_config = self.configfile.get_status(0.0).get("config", {})
        cartographer = self.printer.lookup_object("cartographer", None)
        model_config = getattr(getattr(cartographer, "config", None), mode, None)
        live_models = getattr(model_config, "models", None) or {}
        prefix = MODEL_PREFIXES[mode]
        models = []
        for section, options in raw_config.items():
            if not section.lower().startswith(prefix):
                continue
            name = section[len(prefix) :].strip()
            if not name or "z_offset" not in options:
                continue
            try:
                offset = round(float(options["z_offset"]), 3)
                if name in live_models:
                    offset = round(float(live_models[name].z_offset), 3)
            except (TypeError, ValueError):
                raise gcmd.error(
                    "Invalid z_offset in [%s]: %s"
                    % (section, options.get("z_offset"))
                )
            models.append(
                {
                    "section": section,
                    "name": name,
                    "original": offset,
                    "current": offset,
                }
            )

        if not models:
            raise gcmd.error("No saved Cartographer %s models were found" % mode.title())
        models.sort(key=self._sort_key)
        return models

    def _action(self, message):
        self.gcode.respond_raw("// action:%s" % message)

    def _close_prompt(self):
        self._action("global_carto_offsets_end")

    def _require_session(self, gcmd):
        if self.models is None or self.mode is None:
            raise gcmd.error("Open Global_Z_Offsets_Carto before saving values")

    def cmd_open(self, gcmd):
        if self._printing_or_paused():
            raise gcmd.error("Global Z offsets cannot be edited during a print")
        if self.models is not None:
            self._close_prompt()
        mode = self._active_mode(gcmd)
        self.models = self._load_models(gcmd, mode)
        self.mode = mode
        self._action("global_carto_offsets_begin %s" % mode)
        for index, model in enumerate(self.models):
            self._action(
                "global_carto_offsets_model %s|%s|%d"
                % (
                    self._safe_text(model["name"].upper()),
                    self._format_offset(model["current"]),
                    index,
                )
            )
        self._action("global_carto_offsets_show")

    def cmd_stage(self, gcmd):
        self._require_session(gcmd)
        index = gcmd.get_int("INDEX", minval=0, maxval=len(self.models) - 1)
        value = round(gcmd.get_float("VALUE", minval=-5.0, maxval=0.0), 3)
        self.models[index]["current"] = value

    def cmd_cancel(self, gcmd):
        self.models = None
        self.mode = None
        self._close_prompt()
        gcmd.respond_info("Global Carto Z Offset changes cancelled")

    def cmd_save(self, gcmd):
        self._require_session(gcmd)
        if self._printing_or_paused():
            raise gcmd.error("Saving offsets is not allowed during a print")

        changed = [
            model for model in self.models if model["current"] != model["original"]
        ]
        if not changed:
            self.models = None
            self.mode = None
            self._close_prompt()
            gcmd.respond_info("No Global Carto Z Offset changes to save")
            return

        cartographer = self.printer.lookup_object("cartographer", None)
        model_mode = getattr(cartographer, "%s_mode" % self.mode, None)
        model_config = getattr(getattr(cartographer, "config", None), self.mode, None)
        live_models = getattr(model_config, "models", None)
        if (
            not isinstance(live_models, dict)
            or model_mode is None
            or getattr(model_mode, "_models", None) is not live_models
        ):
            raise gcmd.error("Cartographer live %s models are unavailable; nothing was saved" % self.mode)
        if not all(model["name"] in live_models for model in changed):
            raise gcmd.error("A Cartographer %s model changed; reopen the editor" % self.mode)
        try:
            replacements = {
                model["name"]: replace(
                    live_models[model["name"]], z_offset=model["current"]
                )
                for model in changed
            }
            active_name = model_mode.get_model().name if model_mode.has_model() else None
        except (AttributeError, TypeError, ValueError) as exc:
            raise gcmd.error("Could not prepare live Cartographer offsets: %s" % exc)

        for model in changed:
            value = self._format_offset(model["current"])
            self.configfile.set(model["section"], "z_offset", value)
            logging.info(
                "%s staged [%s] z_offset=%s",
                LOG_PREFIX,
                model["section"],
                value,
            )

        self.gcode.run_script_from_command("CXSAVE_CONFIG")
        live_models.update(replacements)
        if active_name in replacements:
            model_mode.load_model(active_name)
        self.models = None
        mode = self.mode
        self.mode = None
        self._close_prompt()
        gcmd.respond_info("Global Carto %s Z offsets saved and active; no restart needed" % mode.title())


def load_config(config):
    return K2CartographerOffsetEditor(config)
