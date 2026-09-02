#!/usr/bin/env python3

import os
import re
import sys


INCLUDE_RE = re.compile(r"^\s*(#\s*)?\[include\s+(.+?)\]\s*$", re.IGNORECASE)


def add_include(config_path, include_path, commented=False):
    """
    Ensure one include statement exists in the requested enabled/disabled state.

    Args:
        config_path (str): Full path to the configuration file
        include_path (str): Path to be included
        commented (bool): Whether to comment out the include (default: False)
    """
    active_target = f"[include {include_path}]"
    target = f"#{active_target}" if commented else active_target

    # Create the directory path if it doesn't exist
    config_dir = os.path.dirname(config_path)
    if config_dir:
        os.makedirs(config_dir, exist_ok=True)

    # If file doesn't exist, create it with the include
    if not os.path.exists(config_path):
        with open(config_path, 'w', newline='') as handle:
            handle.write(target + '\n')
        return

    with open(config_path, 'r', newline='') as handle:
        contents = handle.readlines()

    matching_indexes = []
    requested_path = include_path.casefold()
    for index, line in enumerate(contents):
        match = INCLUDE_RE.match(line.rstrip('\r\n'))
        if match and match.group(2).strip().casefold() == requested_path:
            matching_indexes.append(index)

    if matching_indexes:
        # Reuse the first occurrence so comments and feature ordering remain stable,
        # then remove stale commented/duplicate copies of the same include.
        first_index = matching_indexes[0]
        newline = '\r\n' if contents[first_index].endswith('\r\n') else '\n'
        contents[first_index] = target + newline
        for index in reversed(matching_indexes[1:]):
            del contents[index]
    else:
        insert_index = len(contents)
        for index, line in enumerate(contents):
            stripped = line.strip()
            if line.startswith('#*#') or stripped.casefold() == '[include overrides.cfg]':
                insert_index = index
                break
        contents.insert(insert_index, target + '\n')

    with open(config_path, 'w', newline='') as handle:
        handle.writelines(contents)


def parse_bool(value):
    return value.strip().casefold() in ('1', 'true', 'yes', 'on')

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: script.py <config_path> <include_path> [commented]")
        sys.exit(1)

    config_path = os.path.expanduser(sys.argv[1])
    include_path = os.path.expanduser(sys.argv[2])
    commented = parse_bool(sys.argv[3]) if len(sys.argv) > 3 else False

    add_include(config_path, include_path, commented)
