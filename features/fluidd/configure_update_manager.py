#!/usr/bin/env python3
"""Keep test ZIPs managed by the installer, restoring web updates for stable builds."""
import argparse
from pathlib import Path

from configure_device import atomic_write
from download_build import configured_build, check_installed

TEST_CONFIG = (
    '# Fluidd test build: updates are managed by K2-improvements installer menus.\n'
    '# The stable web updater is disabled so Update All cannot replace this test UI.\n'
)


def config_path():
    return Path.home() / 'printer_data/config/updates/fluidd.cfg'


def expected_config(build, root):
    if build is not None:
        if not check_installed(build, root):
            raise ValueError('Install the pinned Fluidd test build before configuring its updater')
        return TEST_CONFIG
    return Path(__file__).with_name('update-manager.cfg').read_text(encoding='utf-8')


def configure(build, path, root, check=False):
    expected = expected_config(build, root)
    path = Path(path)
    if check:
        if path.read_text(encoding='utf-8') != expected:
            raise ValueError('Fluidd updater configuration does not match the installed build')
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write(path, expected)


def test_updates_disabled():
    build = configured_build()
    if build is None or not check_installed(build, '/usr/share/fluidd'):
        return False
    try:
        return config_path().read_text(encoding='utf-8') == TEST_CONFIG
    except OSError:
        return False


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=config_path())
    parser.add_argument('--fluidd-dir', type=Path, default=Path('/usr/share/fluidd'))
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    configure(configured_build(), args.config, args.fluidd_dir, args.check)
