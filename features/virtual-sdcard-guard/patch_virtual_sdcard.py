#!/usr/bin/env python3
"""Protect terminal upload boundaries and ignored-tool resume byte offsets."""

from pathlib import Path
import re
import sys


MARKER = "k2-improvements: terminal multipart upload boundary guard"

HELPER_PATTERN = re.compile(
    r"^VALID_GCODE_EXTS = \['gcode', 'g', 'gco'\]\r?\n", re.MULTILINE
)
HELPER = '''
# k2-improvements: terminal multipart upload boundary guard
def _is_terminal_multipart_boundary(line, next_position, file_size):
    # Some K2 upload requests intermittently append their closing multipart
    # delimiter to the stored G-code. Only recognize the observed, strict
    # hexadecimal form when it occupies the physical final line.
    if next_position < file_size:
        return False
    candidate = line.rstrip('\\r')
    if not candidate.endswith('--'):
        return False
    body = candidate[:-2]
    token = body.lstrip('-')
    dash_count = len(body) - len(token)
    return (dash_count >= 20 and 16 <= len(token) <= 64
            and all(ch in '0123456789abcdefABCDEF' for ch in token))
'''

POSITION_PATTERN = re.compile(
    r"^(?P<indent>[ \t]*)self\.next_file_position = next_file_position\r?\n",
    re.MULTILINE,
)
GUARD = '''# Ignore only a closing upload boundary on the physical EOF.
if _is_terminal_multipart_boundary(
        line, next_file_position, self.file_size):
    logging.warning(
        "virtual_sdcard: ignored trailing multipart upload boundary")
    self.gcode.respond_info(
        "[VIRTUAL_SDCARD]: Ignored trailing multipart upload boundary")
    self.cmd_from_sd = False
    self.file_position = self.next_file_position
    continue
'''


def is_terminal_multipart_boundary(line, next_position, file_size):
    """Test the same predicate installed into virtual_sdcard.py."""
    if next_position < file_size:
        return False
    candidate = line.rstrip("\r")
    if not candidate.endswith("--"):
        return False
    body = candidate[:-2]
    token = body.lstrip("-")
    dash_count = len(body) - len(token)
    return (
        dash_count >= 20
        and 16 <= len(token) <= 64
        and all(ch in "0123456789abcdefABCDEF" for ch in token)
    )


def patch_boundary_text(text):
    if MARKER in text:
        return text, False
    helper_matches = list(HELPER_PATTERN.finditer(text))
    if len(helper_matches) != 1:
        raise ValueError("could not locate VALID_GCODE_EXTS insertion point")
    matches = list(POSITION_PATTERN.finditer(text))
    if len(matches) != 1:
        raise ValueError("could not locate virtual-SD dispatch position")
    helper_match = helper_matches[0]
    newline = "\r\n" if helper_match.group(0).endswith("\r\n") else "\n"
    helper = HELPER.replace("\n", newline)
    text = text[:helper_match.end()] + helper + text[helper_match.end():]
    match = POSITION_PATTERN.search(text)
    indent = match.group("indent")
    indented_guard = "".join(
        indent + line if line.strip() else line
        for line in GUARD.splitlines(keepends=True)
    )
    if newline == "\r\n":
        indented_guard = indented_guard.replace("\n", "\r\n")
    text = text[:match.end()] + indented_guard + text[match.end():]
    return text, True


SKIP_MARKER = 'k2-improvements: count ignored tool commands before pause'


def patch_text(text):
    text, boundary_changed = patch_boundary_text(text)
    if SKIP_MARKER in text or 'self.ignore_t_code(line)' not in text:
        return text, boundary_changed
    pattern = re.compile(r'^(?P<i>[ \t]*)if self\.ignore_t_code\(line\):[ \t]*continue[ \t]*\r?$', re.MULTILINE)
    matches = list(pattern.finditer(text))
    if len(matches) != 1:
        raise ValueError('unsupported ignored-tool dispatch; refusing to patch')
    match = matches[0]
    indent = match.group('i')
    newline = '\r\n' if '\r\n' in text else '\n'
    block = newline.join([indent+'if self.ignore_t_code(line):',
                          indent+'    # '+SKIP_MARKER,
                          indent+'    self.cmd_from_sd = False',
                          indent+'    self.file_position = self.next_file_position',
                          indent+'    continue'])
    return text[:match.start()]+block+text[match.end():], True


def decode_source(raw):
    try:
        return raw.decode("utf-8"), "utf-8"
    except UnicodeDecodeError:
        return raw.decode("gbk"), "gbk"


def ensure_encoding_cookie(text, encoding):
    if encoding == "utf-8":
        return text
    first_two = text.splitlines()[:2]
    if any("coding" in line for line in first_two):
        return text
    cookie = "# -*- coding: {} -*-\n".format(encoding)
    if text.startswith("#!"):
        newline = text.find("\n")
        if newline >= 0:
            return text[:newline + 1] + cookie + text[newline + 1:]
    return cookie + text


def main(argv):
    if len(argv) != 2:
        print("Usage: patch_virtual_sdcard.py <virtual_sdcard.py>", file=sys.stderr)
        return 1
    target = Path(argv[1])
    try:
        original_bytes = target.read_bytes()
        original, encoding = decode_source(original_bytes)
        patched, changed = patch_text(original)
        if not changed:
            print("I: virtual-SD protections already installed")
            return 2
        patched = ensure_encoding_cookie(patched, encoding)
        backup = target.with_name(target.name + ".before-upload-boundary-guard")
        if not backup.exists():
            backup.write_bytes(original_bytes)
        if SKIP_MARKER in patched and SKIP_MARKER not in original:
            resume_backup = target.with_name(target.name + '.before-ignored-tool-position')
            if not resume_backup.exists():
                resume_backup.write_bytes(original_bytes)
        target.write_bytes(patched.encode(encoding))
        print("I: installed virtual-SD upload and pause/refill position protection")
        return 0
    except Exception as exc:
        print("E: could not patch {}: {}".format(target, exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
