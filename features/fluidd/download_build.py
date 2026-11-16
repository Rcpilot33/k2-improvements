#!/usr/bin/env python3
"""Select the branch-pinned Fluidd test ZIP or the normal stable release."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import urllib.parse
import urllib.request

from get_latest_release import download_latest_release

HERE = Path(__file__).resolve().parent


def read_build(manifest, branch):
    if not Path(manifest).is_file():
        return None
    build = json.loads(Path(manifest).read_text(encoding='utf-8'))
    # A test manifest carried through a merge must never redirect main or
    # integration-testing away from the ordinary Fluidd stable releases.
    if branch != build.get('installer_branch'):
        return None
    url = urllib.parse.urlsplit(build.get('url', ''))
    if (url.scheme != 'https' or url.netloc != 'github.com' or
            not re.fullmatch(r'/Rcpilot33/fluidd/releases/download/[A-Za-z0-9._-]+/fluidd\.zip', url.path)
            or url.query or url.fragment or
            not re.fullmatch(r'[a-f0-9]{64}', build.get('sha256', '')) or
            not re.fullmatch(r'[a-f0-9]{40}', build.get('fluidd_commit', ''))):
        raise ValueError('Invalid pinned Fluidd test build')
    return build


def configured_build():
    manifest = HERE / 'test-release.json'
    if not manifest.is_file():
        return None
    result = subprocess.run(['git', '-C', str(HERE.parents[1]),
                             'symbolic-ref', '--quiet', '--short', 'HEAD'],
                            capture_output=True, text=True, check=False)
    return read_build(manifest, result.stdout.strip() if result.returncode == 0 else '')


def download(build, destination):
    destination = Path(destination).resolve()
    if build is None:
        download_latest_release('Rcpilot33/fluidd', asset_name='fluidd.zip')
        downloaded = Path('fluidd.zip').resolve()
        if downloaded != destination:
            downloaded.replace(destination)
        return
    print('I: downloading Fluidd prerelease test build from ' + build['url'])
    request = urllib.request.Request(build['url'], headers={'User-Agent': 'K2-Fluidd-Installer'})
    digest = hashlib.sha256()
    try:
        with urllib.request.urlopen(request, timeout=60) as response, destination.open('wb') as target:
            while True:
                chunk = response.read(65536)
                if not chunk:
                    break
                digest.update(chunk)
                target.write(chunk)
        if digest.hexdigest() != build['sha256']:
            raise ValueError('Fluidd test ZIP checksum does not match the pinned build')
    except BaseException:
        if destination.exists():
            destination.unlink()
        raise
    print('I: verified Fluidd test ZIP SHA256; source commit ' + build['fluidd_commit'][:8])


def check_installed(build, root):
    try:
        if build is None:
            # Capability markers are shared by test and stable builds. Keep a
            # compatible stable UI, but replace prereleases when leaving tests.
            version = (Path(root) / '.version').read_text().strip()
            release = json.loads((Path(root) / 'release_info.json').read_text())
            return (isinstance(release, dict)
                    and re.fullmatch(r'v?\d+\.\d+\.\d+', version) is not None
                    and release.get('version') == version
                    and release.get('project_owner') == 'Rcpilot33'
                    and release.get('project_name') == 'fluidd')
        receipt = json.loads((Path(root) / 'k2-installed-build.json').read_text())
        source = json.loads((Path(root) / 'k2-build.json').read_text())
        return receipt.get('sha256') == build['sha256'] and source.get('commit') == build['fluidd_commit']
    except (OSError, ValueError):
        return False


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination', type=Path, nargs='?')
    parser.add_argument('--check-installed', type=Path)
    args = parser.parse_args()
    build = configured_build()
    if args.check_installed:
        raise SystemExit(0 if check_installed(build, args.check_installed) else 1)
    if args.destination is None:
        parser.error('destination is required')
    download(build, args.destination)
