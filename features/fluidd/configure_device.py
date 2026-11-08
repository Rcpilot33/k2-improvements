#!/usr/bin/env python3
"""Install/update the K2 device bridge without changing printer calibration."""
import argparse
import ast
import os
from pathlib import Path
import tempfile
import subprocess
import stat
import json
import urllib.request

HEADER = '# Managed K2 Fluidd device cards\n'


def atomic_write(path, content):
    mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o644
    descriptor, temporary = tempfile.mkstemp(prefix='.k2-device-', dir=str(path.parent))
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8', newline='\n') as stream:
            stream.write(content)
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def configure(moonraker, config_dir):
    components = Path(moonraker) / 'moonraker/components'
    config_dir = Path(config_dir)
    main = (config_dir / 'moonraker.conf').resolve()
    if not components.is_dir() or not main.is_file():
        raise ValueError('Install the maintained Moonraker before K2 device cards')
    source = Path(__file__).with_name('k2_device.py').read_text(encoding='utf-8')
    ast.parse(source, feature_version=(3, 9))
    target = components / 'k2_device.py'
    managed = config_dir / 'k2_device.conf'
    include = '[include k2_device.conf]'
    contents = main.read_text(encoding='utf-8')
    if target.exists() and not target.read_text(encoding='utf-8').startswith('"""K2 native device cards,'):
        raise ValueError('An unmanaged k2_device.py already exists')
    if managed.exists() and not managed.read_text(encoding='utf-8').startswith(HEADER):
        raise ValueError('An unmanaged k2_device.conf already exists')
    if any(line.strip() == '[k2_device]' for line in contents.splitlines()):
        raise ValueError('Remove the duplicate [k2_device] section from moonraker.conf first')
    if (Path(moonraker) / '.git').exists():
        git_args = ['git', '-C', str(moonraker)]
        tracked = subprocess.run(git_args + ['ls-files', '--error-unmatch',
                                            'moonraker/components/k2_device.py'],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if tracked.returncode == 0:
            raise ValueError('Refusing to replace a tracked Moonraker component')
        exclude = Path(subprocess.check_output(git_args + [
            'rev-parse', '--path-format=absolute', '--git-path', 'info/exclude'], text=True).strip())
        existing = exclude.read_text(encoding='utf-8') if exclude.exists() else ''
        pattern = '/moonraker/components/k2_device.py'
        if pattern not in existing.splitlines():
            exclude.parent.mkdir(parents=True, exist_ok=True)
            atomic_write(exclude, existing.rstrip() + '\n' + pattern + '\n')
    for path, value in ((target, source), (managed, HEADER + '[k2_device]\n')):
        if not path.exists() or path.read_text(encoding='utf-8') != value:
            atomic_write(path, value)
    if include not in (line.strip() for line in contents.splitlines()):
        atomic_write(main, contents.rstrip() + '\n\n' + include + '\n')


def verify(moonraker, config_dir):
    config_dir = Path(config_dir)
    source = Path(__file__).with_name('k2_device.py').read_bytes()
    if (Path(moonraker) / 'moonraker/components/k2_device.py').read_bytes() != source:
        raise ValueError('K2 device bridge needs an update')
    if (config_dir / 'k2_device.conf').read_text() != HEADER + '[k2_device]\n':
        raise ValueError('K2 device configuration differs')
    if '[include k2_device.conf]' not in (line.strip() for line in
            (config_dir / 'moonraker.conf').read_text().splitlines()):
        raise ValueError('K2 device configuration is not included')


def verify_live():
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open('http://127.0.0.1:7125/server/k2_device/status', timeout=5) as response:
        state = json.load(response)['result']
    if not isinstance(state.get('fans'), dict) or not isinstance(state.get('slots'), list):
        raise ValueError('Moonraker has not loaded the K2 device bridge')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--moonraker-dir', type=Path, default=Path.home() / 'moonraker')
    parser.add_argument('--config-dir', type=Path, default=Path.home() / 'printer_data/config')
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--live', action='store_true')
    args = parser.parse_args()
    (verify if args.check else configure)(args.moonraker_dir, args.config_dir)
    if args.live:
        verify_live()
