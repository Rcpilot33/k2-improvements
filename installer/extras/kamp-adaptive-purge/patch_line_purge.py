#!/usr/bin/env python3
"""Create the K2 Plus-compatible LINE_PURGE macro from upstream KAMP."""

import os
import re
import sys
import tempfile
from pathlib import Path


MARKER = "k2-improvements: balance LINE_PURGE retraction before slicer travel"


def fail(message):
    print(f"E: {message}", file=sys.stderr)
    raise SystemExit(1)


def quote_firmware_commands(text):
    assignments = (
        (
            "{% set RETRACT = G10 | string %}",
            "{% set RETRACT = 'G10' | string %}",
        ),
        (
            "{% set UNRETRACT = G11 | string %}",
            "{% set UNRETRACT = 'G11' | string %}",
        ),
    )

    for unquoted, quoted in assignments:
        if unquoted in text:
            text = text.replace(unquoted, quoted)
        elif quoted not in text:
            fail(f"upstream LINE_PURGE no longer contains a recognized assignment: {unquoted}")

    return text


def add_balancing_unretracts(text):
    lines = text.splitlines(keepends=True)
    output = []
    break_moves = 0
    balanced_moves = 0

    for index, line in enumerate(lines):
        output.append(line)
        if "Rapid move to break string" not in line:
            continue

        break_moves += 1
        next_command = ""
        for following in lines[index + 1 :]:
            stripped = following.strip()
            if stripped and not stripped.startswith("#"):
                next_command = stripped
                break

        if next_command.startswith("{UNRETRACT}"):
            balanced_moves += 1
            continue

        indent = re.match(r"\s*", line).group(0)
        newline = "\r\n" if line.endswith("\r\n") else "\n"
        output.append(f"{indent}{{UNRETRACT}}  # {MARKER}{newline}")
        balanced_moves += 1

    if break_moves != 2:
        fail(
            "expected two upstream rapid string-break moves, "
            f"found {break_moves}; refusing to install an unverified macro"
        )
    if balanced_moves != break_moves:
        fail("not every upstream string-break move has a balancing unretract")

    result = "".join(output)
    command_count = sum(
        1 for line in result.splitlines() if line.strip().startswith("{UNRETRACT}")
    )
    if command_count != break_moves:
        fail(
            f"expected {break_moves} UNRETRACT commands after patching, "
            f"found {command_count}"
        )
    if result.count(MARKER) != break_moves:
        fail("the installed macro is missing its K2 compatibility markers")

    return result


def write_atomic(destination, text, mode):
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        newline="",
        dir=str(destination.parent),
        prefix=f".{destination.name}.",
        delete=False,
    ) as handle:
        temp_name = handle.name
        handle.write(text)

    try:
        os.chmod(temp_name, mode)
        os.replace(temp_name, destination)
    except BaseException:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def main():
    if len(sys.argv) != 3:
        fail(f"usage: {Path(sys.argv[0]).name} SOURCE DESTINATION")

    source = Path(sys.argv[1])
    destination = Path(sys.argv[2])
    if not source.is_file():
        fail(f"upstream LINE_PURGE source not found: {source}")

    text = source.read_text(encoding="utf-8")
    text = quote_firmware_commands(text)
    text = add_balancing_unretracts(text)

    # os.replace() must target the installed file, not an older upstream symlink.
    if destination.is_symlink():
        destination.unlink()
    write_atomic(destination, text, source.stat().st_mode & 0o777)
    print(f"I: installed corrected LINE_PURGE macro at {destination}")


if __name__ == "__main__":
    main()
