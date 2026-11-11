"""Fresh Ubuntu bootstrap: avoid the DO mirror inconsistency observed 2026-09-23.

Change only the exact vendor Ubuntu URI, retaining suites, components and signing
configuration. Stage dependencies with one bounded archive-404 refresh; never
retry installation, bypass package verification or repair a running node.
"""
from pathlib import Path
import re
import os
import subprocess


DEPENDENCIES = ('curl', 'unzip', 'jq', 'ca-certificates', 'gnupg', 'lsb-release', 'openssl')


def require_fresh(root):
    if any((root / path).exists() for path in ('opt/openvidu/config', 'opt/openvidu/secrets.env',
                                               'usr/local/bin/openvidu_install_counter.txt')):
        raise ValueError('APT mirror preparation is fresh-bootstrap-only')


def missing_ubuntu_archives(output):
    """Only an official Ubuntu .deb 404 permits one metadata refresh, not arbitrary failures."""
    errors = [line for line in output.splitlines() if line.startswith('E:')]
    missing = r'^E: Failed to fetch https?://(?:security|archive)\.ubuntu\.com/ubuntu/\S+\.deb\s+404(?:\s|$)'
    return (any(re.match(missing, line) for line in errors)
            and all(re.match(missing, line) or line.startswith('E: Unable to fetch some archives,')
                    for line in errors))


def stage_dependencies(root=Path('/'), run=subprocess.run):
    """Fetch signed metadata and all packages before the caller performs its single install.

    A repository publication/cache race can advertise a removed archive. Retry only
    downloading, once, after a strict metadata refresh; never replay dpkg/cloud-init.
    The caller uses --no-download so a later index change fails rather than fetching
    a newly selected package during installation.
    """
    require_fresh(root)
    env = dict(os.environ, LC_ALL='C')
    for attempt in range(2):
        update = run(['apt-get', '-o', 'Acquire::http::No-Cache=true',
                      '-o', 'Acquire::https::No-Cache=true', '--error-on=any', 'update'],
                     capture_output=True, text=True, env=env)
        if update.returncode:
            raise RuntimeError('Fresh APT metadata update failed; installation not attempted')
        fetched = run(['apt-get', '--download-only', 'install', '-y', *DEPENDENCIES],
                      capture_output=True, text=True, env=env)
        if not fetched.returncode:
            return
        if attempt or not missing_ubuntu_archives(fetched.stdout + '\n' + fetched.stderr):
            raise RuntimeError('Fresh APT package download failed; installation not attempted')
        print('Ubuntu package archive unavailable; refreshing signed metadata once before installation')


def prepare(root=Path('/')):
    apt = root / 'etc/apt'
    paths = [apt / 'sources.list', *sorted((apt / 'sources.list.d').glob('*.sources')),
             *sorted((apt / 'sources.list.d').glob('*.list'))]
    changes = []
    for path in paths:
        if not path.exists():
            continue
        if path.is_symlink() or not path.is_file():
            raise ValueError('Regular APT source file required')
        before = path.read_text()
        lines = []
        for line in before.splitlines(keepends=True):
            # Only source declarations, not comments or unrelated repository fields.
            if re.match(r'^\s*(URIs:|deb(?:-src)?\s)', line):
                line = re.sub(r'https?://mirrors\.digitalocean\.com/ubuntu/?(?=\s|$)',
                              'http://archive.ubuntu.com/ubuntu/', line)
            lines.append(line)
        after = ''.join(lines)
        if after != before:
            changes.append((path, before, after))
    if not changes:
        return 0
    require_fresh(root)
    # Validate every backup before changing any source. Never overwrite the original.
    for path, before, _ in changes:
        backup = path.with_name(path.name + '.courseultra-original')
        if backup.exists() or backup.is_symlink():
            raise ValueError('Existing mirror backup requires inspection')
    for path, before, after in changes:
        backup = path.with_name(path.name + '.courseultra-original')
        with backup.open('x') as stream:
            stream.write(before)
        backup.chmod(path.stat().st_mode & 0o777)
        path.write_text(after)
    return len(changes)


if __name__ == '__main__':
    print('Prepared fresh Ubuntu source files:', prepare())
    stage_dependencies()
