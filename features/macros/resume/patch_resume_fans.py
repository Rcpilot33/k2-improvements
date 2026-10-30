"""Initialize off-fan restore values in the factory RESUME_EXTERNAL macro."""
from pathlib import Path
import re
import sys
import os
import tempfile

MARKER = '# k2-improvements: resume off-fan defaults'


def patch_text(text):
    matches=list(re.finditer(r'^\[gcode_macro RESUME_EXTERNAL\][^\n]*\n.*?(?=^\[|\Z)',text,re.M|re.S))
    if len(matches)!=1:
        raise ValueError('expected one factory RESUME_EXTERNAL section')
    match=matches[0];section=match.group()
    if MARKER in section:
        return text,False
    # Known factory variants restore fans with or without F1. Match active,
    # complete command lines: a commented example is not a restore command.
    # Keep the original commands/flags byte-for-byte; only add defaults.
    for fan, variable in ((2, 's_value'), (0, 's_value_0')):
        command = (r'^[ \t]*M106[ \t]+P' + str(fan) + r'[ \t]+S\{'
                   + variable + r'\}(?:[ \t]+F1)?[ \t]*(?:;[^\r\n]*)?\r?$')
        if len(re.findall(command, section, re.M)) != 1:
            raise ValueError('unsupported factory fan restore macro; refusing to overwrite')
    for token in ("printer['gcode_macro PRINTER_PARAM'].fan2_speed > 0",
                  "printer['gcode_macro PRINTER_PARAM'].fan0_speed > 0"):
        if token not in section:
            raise ValueError('unsupported factory fan restore macro; refusing to overwrite')
    header=re.search(r'^gcode\s*[:=][^\r\n]*\r?\n',section,re.M)
    if not header:
        raise ValueError('missing macro gcode header')
    nl='\r\n' if '\r\n' in text else '\n'
    additions=nl.join(['  '+MARKER,'  {% set s_value = 0 %}','  {% set s_value_0 = 0 %}',''])
    section=section[:header.end()]+additions+section[header.end():]
    return text[:match.start()]+section+text[match.end():],True


def main(argv):
    target=Path(argv[1]);raw=target.read_bytes()
    try:
        text=raw.decode('utf-8');encoding='utf-8'
    except UnicodeDecodeError:
        text=raw.decode('gbk');encoding='gbk'
    patched,changed=patch_text(text)
    if changed:
        backup=target.with_name(target.name+'.before-resume-fan-defaults')
        if not backup.exists():
            backup.write_bytes(raw)
        descriptor,name=tempfile.mkstemp(prefix='.resume-fans-',dir=str(target.parent))
        temporary=Path(name)
        try:
            with os.fdopen(descriptor,'wb') as stream:
                stream.write(patched.encode(encoding))
            temporary.chmod(target.stat().st_mode)
            temporary.replace(target)
        finally:
            if temporary.exists():
                temporary.unlink()
    print('I: resume fan defaults '+('installed' if changed else 'already installed'))
    return 0


if __name__=='__main__':
    try:
        sys.exit(main(sys.argv))
    except Exception as exc:
        print('E: '+str(exc),file=sys.stderr)
        sys.exit(1)
