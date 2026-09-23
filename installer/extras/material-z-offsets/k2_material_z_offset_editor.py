"""Live Fluidd editor and START_PRINT helper for material Z offsets."""

import hashlib
import logging
import os
import re
import tempfile


LOG_PREFIX = "[K2_MATERIAL_Z_OFFSET_EDITOR]"
SECTION_NAME = "gcode_macro _START_PRINT_VARS"
OFFSET_RE = re.compile(
    r"^[ \t]*variable_offset_([A-Za-z0-9_]+)[ \t]*:[ \t]*"
    r"([-+]?(?:\d+(?:\.\d*)?|\.\d+))(?:[ \t]*(?:#.*)?)?(?:\r?\n)?$",
    re.IGNORECASE,
)
SECTION_RE = re.compile(r"^[ \t]*\[([^]]+)\][ \t]*(?:#.*)?(?:\r?\n)?$")
MATERIAL_RE = re.compile(r"[^A-Za-z0-9]+")
DEFAULT_NEW_OFFSET = 0.0


def format_offset(value):
    value = round(float(value), 3)
    if value == 0:
        value = 0.0
    return "%.3f" % value


def normalize_material(value):
    name = MATERIAL_RE.sub("_", str(value).strip()).strip("_").upper()
    if not name:
        return ""
    return name[:64]


def parse_material_offsets(text):
    """Return ordered material offsets from _START_PRINT_VARS in *text*."""
    offsets = []
    in_section = False
    found_section = False
    for line in text.splitlines(True):
        section = SECTION_RE.match(line)
        if section:
            in_section = section.group(1).strip().casefold() == SECTION_NAME.casefold()
            found_section = found_section or in_section
            continue
        if not in_section:
            continue
        match = OFFSET_RE.match(line)
        if match:
            name = normalize_material(match.group(1))
            if name:
                offsets.append((name, round(float(match.group(2)), 3)))
    if not found_section:
        raise ValueError("[%s] was not found" % SECTION_NAME)

    # Preserve the first occurrence of each material and always display DEFAULT last.
    unique = []
    seen = set()
    default_value = None
    for name, value in offsets:
        if name in seen:
            continue
        seen.add(name)
        if name == "DEFAULT":
            default_value = value
        else:
            unique.append((name, value))
    if default_value is None:
        default_value = DEFAULT_NEW_OFFSET
    unique.append(("DEFAULT", default_value))
    return unique


def rewrite_material_offsets(text, offsets):
    """Put all material variables at the top of _START_PRINT_VARS."""
    lines = text.splitlines(True)
    start = end = None
    for index, line in enumerate(lines):
        section = SECTION_RE.match(line)
        if not section:
            continue
        if start is None and section.group(1).strip().casefold() == SECTION_NAME.casefold():
            start = index
            continue
        if start is not None:
            end = index
            break
    if start is None:
        raise ValueError("[%s] was not found" % SECTION_NAME)
    if end is None:
        end = len(lines)

    ordered = []
    seen = set()
    default_value = DEFAULT_NEW_OFFSET
    for name, value in offsets:
        name = normalize_material(name)
        if not name or name in seen:
            continue
        seen.add(name)
        if name == "DEFAULT":
            default_value = value
        else:
            ordered.append((name, value))
    ordered.append(("DEFAULT", default_value))

    body = [line for line in lines[start + 1 : end] if not OFFSET_RE.match(line)]
    while body and not body[0].strip():
        body.pop(0)
    offset_lines = [
        "variable_offset_%s: %s\n" % (name, format_offset(value))
        for name, value in ordered
    ]
    replacement = [lines[start]] + offset_lines + (["\n"] if body else []) + body
    return "".join(lines[:start] + replacement + lines[end:])


def file_digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def write_atomic(path, text):
    directory = os.path.dirname(path)
    mode = os.stat(path).st_mode
    descriptor, temporary = tempfile.mkstemp(prefix=".material-z-offsets-", dir=directory)
    try:
        with os.fdopen(descriptor, "w") as output:
            output.write(text)
            output.flush()
            os.fsync(output.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def normalize_file(path):
    with open(path, "r") as source:
        original = source.read()
    updated = rewrite_material_offsets(original, parse_material_offsets(original))
    if updated == original:
        return False
    write_atomic(path, updated)
    return True


class K2MaterialZOffsetEditor:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.gcode = self.printer.lookup_object("gcode")
        self.overrides_path = config.get(
            "overrides_path",
            "/mnt/UDISK/printer_data/config/custom/overrides.cfg",
        )
        self.materials = None
        self.session_digest = None

        self.gcode.register_command(
            "K2_MATERIAL_Z_OFFSETS", self.cmd_open,
            desc="Edit material Z offsets",
        )
        self.gcode.register_command("K2_MATERIAL_Z_STAGE", self.cmd_stage)
        self.gcode.register_command("K2_MATERIAL_Z_CANCEL", self.cmd_cancel)
        self.gcode.register_command("K2_MATERIAL_Z_SAVE", self.cmd_save)
        self.gcode.register_command(
            "K2_MATERIAL_Z_APPLY", self.cmd_apply,
            desc="Apply the selected material Z offset",
        )

    def get_status(self, eventtime):
        return {"session_open": self.materials is not None}

    def _read(self, gcmd):
        try:
            with open(self.overrides_path, "r") as source:
                return source.read()
        except OSError as exc:
            raise gcmd.error("Could not read overrides.cfg: %s" % exc)

    def _write(self, gcmd, text):
        try:
            write_atomic(self.overrides_path, text)
        except OSError as exc:
            raise gcmd.error("Could not save overrides.cfg: %s" % exc)

    def _printing_or_paused(self):
        print_stats = self.printer.lookup_object("print_stats", None)
        if print_stats is None:
            return False
        state = str(print_stats.get_status(0.0).get("state", "")).lower()
        return state in ("printing", "paused")

    def _action(self, message):
        self.gcode.respond_raw("// action:%s" % message)

    def _close_prompt(self):
        self._action("material_z_offsets_end")

    def _require_session(self, gcmd):
        if self.materials is None:
            raise gcmd.error("Open Material_Z_Offsets before saving values")

    def _active_offsets(self):
        macro = self.printer.lookup_object("gcode_macro _START_PRINT_VARS")
        status = macro.get_status(0.0)
        return {
            normalize_material(key[len("offset_") :]): round(float(value), 3)
            for key, value in status.items()
            if str(key).lower().startswith("offset_")
        }

    def _register_unknown(self, gcmd, material):
        text = self._read(gcmd)
        try:
            offsets = parse_material_offsets(text)
        except (TypeError, ValueError) as exc:
            raise gcmd.error("Could not parse material offsets: %s" % exc)
        if material in dict(offsets):
            return False
        offsets.insert(len(offsets) - 1, (material, DEFAULT_NEW_OFFSET))
        self._write(gcmd, rewrite_material_offsets(text, offsets))
        logging.info(
            "%s added variable_offset_%s=%s to overrides.cfg",
            LOG_PREFIX, material, format_offset(DEFAULT_NEW_OFFSET),
        )
        return True

    def cmd_apply(self, gcmd):
        material = normalize_material(gcmd.get("MATERIAL", ""))
        offsets = self._active_offsets()
        default_value = offsets.get("DEFAULT", DEFAULT_NEW_OFFSET)
        if not material:
            value = default_value
            gcmd.respond_info(
                "WARNING: Material type not passed into START_PRINT; using DEFAULT "
                "material Z offset of %s" % format_offset(value)
            )
        elif material in offsets:
            value = offsets[material]
            gcmd.respond_info(
                "Setting material Z offset of %s for %s"
                % (format_offset(value), material)
            )
        else:
            value = default_value
            added = self._register_unknown(gcmd, material)
            message = (
                "Unknown material %s: this print uses DEFAULT material Z offset %s"
                % (material, format_offset(value))
            )
            if added:
                message += "; saved %s at %s" % (
                    material, format_offset(DEFAULT_NEW_OFFSET)
                )
            else:
                message += "; its saved entry is not active yet"
            message += " and will activate after Save & Restart"
            gcmd.respond_info(message)
        self.gcode.run_script_from_command(
            "SET_GCODE_OFFSET Z=%s" % format_offset(value)
        )

    def cmd_open(self, gcmd):
        if self._printing_or_paused():
            raise gcmd.error("Material Z offsets cannot be edited during a print")
        text = self._read(gcmd)
        try:
            parsed = parse_material_offsets(text)
        except (TypeError, ValueError) as exc:
            raise gcmd.error("Could not parse material offsets: %s" % exc)
        self.session_digest = file_digest(text)
        self.materials = [
            {"name": name, "original": value, "current": value}
            for name, value in parsed
        ]
        self._action("material_z_offsets_begin")
        for index, material in enumerate(self.materials):
            self._action(
                "material_z_offsets_material %s|%s|%d"
                % (material["name"], format_offset(material["current"]), index)
            )
        self._action("material_z_offsets_show")

    def cmd_stage(self, gcmd):
        self._require_session(gcmd)
        index = gcmd.get_int("INDEX", minval=0, maxval=len(self.materials) - 1)
        value = round(gcmd.get_float("VALUE", minval=-5.0, maxval=5.0), 3)
        self.materials[index]["current"] = value

    def cmd_cancel(self, gcmd):
        self.materials = None
        self.session_digest = None
        self._close_prompt()
        gcmd.respond_info("Material Z Offset changes cancelled")

    def cmd_save(self, gcmd):
        self._require_session(gcmd)
        if self._printing_or_paused():
            raise gcmd.error("Save & Restart is not allowed during a print")
        text = self._read(gcmd)
        if file_digest(text) != self.session_digest:
            raise gcmd.error(
                "overrides.cfg changed while the editor was open; cancel and reopen it"
            )
        changed = any(
            material["current"] != material["original"]
            for material in self.materials
        )
        if not changed:
            self.materials = None
            self.session_digest = None
            self._close_prompt()
            gcmd.respond_info("No Material Z Offset changes to save")
            return
        updated = rewrite_material_offsets(
            text,
            [(material["name"], material["current"]) for material in self.materials],
        )
        self._write(gcmd, updated)
        self.materials = None
        self.session_digest = None
        self._close_prompt()
        self.gcode.run_script_from_command("FIRMWARE_RESTART")


def load_config(config):
    return K2MaterialZOffsetEditor(config)


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 3 or sys.argv[1] != "--normalize":
        sys.stderr.write("usage: k2_material_z_offset_editor.py --normalize overrides.cfg\n")
        sys.exit(2)
    changed = normalize_file(sys.argv[2])
    print("I: material Z offsets %s" % ("normalized" if changed else "already normalized"))
