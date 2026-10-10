"""Install/remove reversible nozzle-camera protection on the printer itself."""

import argparse
import ast
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from ensure_included import add_include
from k2_nozzle_camera_guard import CAMERA_FLAGS, disable_camera_preferences

MARKER = "# k2-improvements: nozzle-camera replacement"
POWER_MARKER = "# k2-improvements: Cartographer nozzle USB power guard"
INIT_MARKER = "# k2-improvements: Cartographer nozzle USB startup"
DEPEND_BEGIN = "# BEGIN k2-improvements nozzle USB boot dependency"
DEPEND_END = "# END k2-improvements nozzle USB boot dependency"
PREFLIGHT = ("    # BEGIN k2-improvements nozzle USB preflight\n"
             "    /etc/init.d/k2-nozzle-usb start || return 1\n"
             "    # END k2-improvements nozzle USB preflight\n")


def klipper_boot_plan(path, enable):
    """Plan a narrow, reversible factory service edit; preserve other changes."""
    if path.is_symlink():
        raise ValueError("Unfamiliar linked Klipper service; inspect before changing")
    text = path.read_text()
    if DEPEND_BEGIN in text or DEPEND_END in text:
        pattern = (re.escape(DEPEND_BEGIN) + r"\n# original dependencies: ([A-Za-z0-9_,.-]+)\n"
                   r"(DEPEND=[A-Za-z0-9_,.-]+)\n" + re.escape(DEPEND_END) + r"\n")
        blocks = list(re.finditer(pattern, text))
        if len(blocks) != 1:
            raise ValueError("Modified nozzle USB dependency block; inspect before changing")
        block = blocks[0]
        if block.group(2) != "DEPEND=" + block.group(1) + ",k2-nozzle-usb":
            raise ValueError("Modified nozzle USB dependencies; refusing to discard changes")
        text = text[:block.start()] + "DEPEND=" + block.group(1) + "\n" + text[block.end():]
    if "# BEGIN k2-improvements nozzle USB preflight" in text or "# END k2-improvements nozzle USB preflight" in text:
        if text.count(PREFLIGHT) != 1:
            raise ValueError("Modified nozzle USB preflight; inspect before changing")
        text = text.replace(PREFLIGHT, "", 1)
    if not enable:
        return text
    dependencies = list(re.finditer(r"^DEPEND=([A-Za-z0-9_,.-]+)$", text, re.MULTILINE))
    starts = list(re.finditer(r"^start_service\(\)[ \t]*\n?[ \t]*\{\n", text, re.MULTILINE))
    if len(dependencies) != 1 or len(starts) != 1:
        raise ValueError("Unsupported Klipper service layout; boot ordering cannot be secured")
    original = dependencies[0].group(0)
    if "k2-nozzle-usb" in dependencies[0].group(1).split(","):
        raise ValueError("Unmanaged nozzle USB dependency; inspect before changing")
    # Avoid a second literal DEPEND assignment in a comment: vendor boot
    # dispatchers can parse script metadata without evaluating the shell.
    block = (DEPEND_BEGIN + "\n# original dependencies: " + dependencies[0].group(1) +
             "\n" + original + ",k2-nozzle-usb\n" + DEPEND_END + "\n")
    text = text[:dependencies[0].start()] + block + text[dependencies[0].end() + 1:]
    return re.sub(r"(^start_service\(\)[ \t]*\n?[ \t]*\{\n)",
                  lambda match: match.group(1) + PREFLIGHT, text, count=1, flags=re.MULTILINE)


def write_boot_plan(path, planned):
    if path.read_text() != planned:
        dest = Path(str(path) + ".before-nozzle-usb-boot")
        if not dest.exists():
            shutil.copy2(path, dest)
        descriptor, temporary = tempfile.mkstemp(prefix=".k2-nozzle-boot-", dir=str(path.parent))
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as target:
                target.write(planned)
                target.flush()
                os.fsync(target.fileno())
            os.chmod(temporary, path.stat().st_mode & 0o777)
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)


def managed(path, marker):
    return path.is_file() and marker in path.read_text()


def backup(path):
    dest = Path(str(path) + ".before-nozzle-camera-guard")
    if path.exists() and not dest.exists():
        shutil.copy2(path, dest)


def configure(config, klipper, system, preferences, mode):
    custom = config / "custom"
    guard = custom / "k2_nozzle_camera_guard.cfg"
    saved = custom / ".k2-nozzle-camera-preferences.json"
    module = klipper / "klippy/extras/k2_nozzle_camera_guard.py"
    power = system / "usr/bin/nozzle_cam_power.sh"
    factory = Path(str(power) + ".k2-factory")
    init = system / "etc/init.d/k2-nozzle-usb"
    boot = system / "etc/rc.d/S53k2-nozzle-usb"
    main = custom / "main.cfg"
    klipper_service = system / "etc/init.d/klipper"
    if guard.exists() and not managed(guard, MARKER):
        raise ValueError("Unfamiliar guard config; refusing to overwrite")
    if module.exists() or module.is_symlink():
        if not module.is_symlink() or module.resolve() != HERE / module.name:
            raise ValueError("Unfamiliar guard module; refusing to overwrite")
    if (init.exists() or init.is_symlink()) and not managed(init, INIT_MARKER):
        raise ValueError("Unfamiliar startup hook; refusing to overwrite")
    if (boot.exists() or boot.is_symlink()) and (
            not boot.is_symlink() or boot.resolve() != init.resolve()):
        raise ValueError("Unfamiliar boot link; refusing to overwrite")
    protected = managed(power, POWER_MARKER)
    if protected and not factory.is_file():
        raise ValueError("Factory power backup is missing; manual recovery required")
    if mode == "remove":
        if factory.exists() and not protected:
            raise ValueError("Factory power script changed; refusing automatic restoration")
        boot_plan = klipper_boot_plan(klipper_service, False)
        if saved.exists():
            data = json.loads(preferences.read_text())
            values = json.loads(saved.read_text())
            control = data["ai_control"]
            # Restore original camera flags only if still managed as disabled.
            for key in CAMERA_FLAGS:
                if control.get(key) == 0:
                    control[key] = values[key]
            backup(preferences)
            preferences.write_text(json.dumps(data, indent=2) + "\n")
            saved.unlink()
        write_boot_plan(klipper_service, boot_plan)
        if protected:
            shutil.copy2(factory, power)
            factory.unlink()
        for target in (boot, init, module, guard):
            if target.exists() or target.is_symlink():
                target.unlink()
        add_include(str(main), guard.name, commented=True)
        return
    if not main.is_file() or not module.parent.is_dir():
        raise ValueError("Managed config and Klipper extras are required")
    # Refuse unknown factory APIs before making any changes.
    tree = ast.parse((module.parent / "load_ai.py").read_text())
    methods = {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}
    required = {"execute_toolhead_ai_waste_management", "execute_ai_waste_detection",
                "nozzle_cam_power_on", "nozzle_cam_power_off", "ai_capture",
                "cmd_LOAD_AI_SET_AI_CONTROL_PREFER"}
    if not required <= methods:
        raise ValueError("Unsupported factory nozzle-camera AI API")
    data = json.loads(preferences.read_text())
    control = data.get("ai_control", {})
    if any(key not in control for key in CAMERA_FLAGS):
        raise ValueError("Unsupported factory ai_control preferences")
    if mode == "refresh":
        if not managed(guard, MARKER):
            raise ValueError("Cannot refresh an uninstalled option")
        mode = "power" if "# usb_power_hold: 1" in guard.read_text() else "ai-only"
    if mode == "power" and not protected:
        content = power.read_text()
        if factory.exists() or power.is_symlink() or not all(part in content for part in (
                "USB_P_EN3=162", "echo 0 > /sys/class/gpio/gpio$USB_P_EN3/value",
                "echo 1 > /sys/class/gpio/gpio$USB_P_EN3/value")):
            raise ValueError("Unrecognized factory power control; inspect before installing")
    if mode == "power":
        # A custom early Klipper service must not connect before rail power.
        priorities = []
        for name in ("board_init", "klipper"):
            match = re.search(r"^START\s*=\s*(\d+)\s*$",
                              (system / "etc/init.d" / name).read_text(), re.MULTILINE)
            if not match:
                raise ValueError("Unknown boot priority for " + name)
            priorities.append(int(match.group(1)))
        if not priorities[0] < 53 < priorities[1]:
            raise ValueError("Unsupported startup order: need board_init < 53 < Klipper")
    boot_plan = klipper_boot_plan(klipper_service, mode == "power")
    # All validation above is read-only. Retain recovery data before edits.
    backup(main)
    backup(preferences)
    if not saved.exists():
        saved.write_text(json.dumps({key: control[key] for key in CAMERA_FLAGS}) + "\n")
    disable_camera_preferences(str(preferences))
    guard.write_text(MARKER + "\n# usb_power_hold: " + str(int(mode == "power")) +
                     "\n[k2_nozzle_camera_guard]\npreferences_path: " + str(preferences) + "\n")
    if module.is_symlink():
        module.unlink()
    module.symlink_to(HERE / module.name)
    for cached in list(module.parent.glob("__pycache__/k2_nozzle_camera_guard.*.pyc")) + [module.with_suffix(".pyc")]:
        if cached.exists():
            cached.unlink()
    add_include(str(main), guard.name)
    if mode == "power":
        if not protected:
            shutil.copy2(power, factory)
        shutil.copyfile(HERE / "nozzle-power.sh", power)
        power.chmod(0o755)
        init.parent.mkdir(parents=True, exist_ok=True)
        if init.is_symlink():
            init.unlink()
        shutil.copyfile(HERE / "nozzle-usb.init", init)
        init.chmod(0o755)
        boot.parent.mkdir(parents=True, exist_ok=True)
        if boot.is_symlink():
            boot.unlink()
        boot.symlink_to(init)
    elif protected:
        shutil.copy2(factory, power)
        factory.unlink()
        for target in (boot, init):
            if target.exists() or target.is_symlink():
                target.unlink()
    write_boot_plan(klipper_service, boot_plan)
    # Do not execute power commands here. The shell workflow does that only on
    # explicit enable, never during removal or disabling of the power option.


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("ai-only", "power", "refresh", "remove"))
    args = parser.parse_args()
    configure(Path(os.environ.get("PRINTER_CFG_DIR", "/mnt/UDISK/printer_data/config")),
              Path(os.environ.get("KLIPPER_DIR", "/usr/share/klipper")),
              Path(os.environ.get("K2_SYSTEM_ROOT", "/")),
              Path(os.environ.get("K2_CAMERA_PREFERENCES", "/mnt/UDISK/creality/userdata/config/user_print_refer.json")),
              args.mode)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, SyntaxError) as error:
        sys.exit("ERROR: " + str(error))
