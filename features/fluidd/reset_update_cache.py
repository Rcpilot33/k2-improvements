#!/usr/bin/env python3
"""Stage a one-time Moonraker Fluidd updater cache reset safely."""

import argparse
import json
import os
import pathlib
import shutil
import stat
import tempfile
import time
import urllib.error
import urllib.request


DISABLED_CONFIG = "# Fluidd updater temporarily disabled to clear stale release state\n"
BACKUP_SUFFIX = ".update-cache-backup"


def backup_path(config_path):
    return config_path.with_name(config_path.name + BACKUP_SUFFIX)


def write_atomic(path, content, mode):
    descriptor, temporary = tempfile.mkstemp(prefix=".fluidd-updater-", dir=str(path.parent))
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as target:
            target.write(content)
            target.flush()
            os.fsync(target.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def restore(config_path):
    backup = backup_path(config_path)
    if backup.exists():
        os.replace(backup, config_path)


def disable(config_path):
    # Recover an interrupted prior attempt before taking a fresh backup.
    restore(config_path)
    mode = stat.S_IMODE(config_path.stat().st_mode)
    backup = backup_path(config_path)
    descriptor, temporary = tempfile.mkstemp(prefix=".fluidd-backup-", dir=str(config_path.parent))
    os.close(descriptor)
    try:
        shutil.copy2(config_path, temporary)
        os.replace(temporary, backup)
        write_atomic(config_path, DISABLED_CONFIG, mode)
    except BaseException:
        restore(config_path)
        raise
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def fetch_fluidd_status(api_url):
    url = api_url.rstrip("/") + "/machine/update/status"
    with urllib.request.urlopen(url, timeout=5) as response:
        payload = json.load(response)
    return payload["result"]["version_info"].get("fluidd")


def matches(mode, status):
    if mode == "check-absent":
        return status is None
    if not isinstance(status, dict):
        return False
    owner = str(status.get("owner", "")).casefold()
    repo = str(status.get("repo_name", "")).casefold()
    current = status.get("version")
    remote = status.get("remote_version")
    return (owner == "rcpilot33" and repo == "fluidd" and current not in (None, "?", "")
            and remote in ("?", current))


def wait_for_state(mode, api_url, timeout=30):
    deadline = time.monotonic() + timeout
    last_error = None
    while True:
        try:
            status = fetch_fluidd_status(api_url)
            if matches(mode, status):
                return
            last_error = "unexpected Fluidd updater state: %s" % status
        except (OSError, ValueError, KeyError, TypeError, urllib.error.URLError) as exc:
            last_error = str(exc)
        if time.monotonic() >= deadline:
            raise RuntimeError(last_error)
        time.sleep(1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("disable", "restore", "check-absent", "check-fresh"))
    parser.add_argument("config", nargs="?", type=pathlib.Path)
    args = parser.parse_args()
    if args.action in ("disable", "restore"):
        if args.config is None:
            parser.error("config path required")
        if args.action == "disable":
            disable(args.config)
        else:
            restore(args.config)
    else:
        wait_for_state(args.action, os.environ.get("MOONRAKER_URL", "http://127.0.0.1:7125"))


if __name__ == "__main__":
    main()
