"""Freeze a reviewed config for one stopped, fresh qualification recorder.

Never starts containers, changes provider membership or removes recovery data.
The campaign must inspect the config privately and supply its exact fingerprint;
hashing whatever happens to exist is not approval of a capacity profile.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

IMAGE = 'docker.io/openvidu/egress@sha256:01a31780783080259b7f218f624e654dc30572be5b5f7999123ac0d98c259475'


def regular(path):
    if any(p.is_symlink() for p in (path, *path.parents)) or not path.is_file():
        raise ValueError('Expected regular non-symlink file')
    return path.read_bytes()


def arm(root, expected, inspect):
    if not re.fullmatch('[0-9a-f]{64}', expected):
        raise ValueError('Reviewed config fingerprint required')
    root = Path(root)
    folder = root / 'courseultra-recorder-guard'
    for path in (root, folder, folder / 'start.sh', folder / 'start.lock', folder / 'egress.yaml', folder / 'egress-config.sha256'):
        info = path.lstat()
        if path.is_symlink() or info.st_uid != os.geteuid() or info.st_mode & 0o022:
            raise ValueError('Snapshot paths must be caller-owned and not group/world writable')
    if regular(folder / 'start.lock') != b'' or (folder / 'start.lock').stat().st_nlink != 1:
        raise ValueError('Persistent empty startup lock required')
    regular(root / '.courseultra-recorder-prepared')
    config = regular(root / 'data/runtime/config/egress/egress.yaml')
    if hashlib.sha256(config).hexdigest() != expected:
        raise ValueError('Reviewed runtime config changed')
    if regular(folder / 'egress-config.sha256') != b'UNARMED\n':
        raise ValueError('Not a fresh unarmed recorder')
    if regular(folder / 'egress.yaml') != b'# Unarmed isolated recorder\n':
        raise ValueError('Placeholder changed')
    guard = regular(folder / 'start.sh')
    if guard != Path(__file__).with_name('recorder-startup-guard.sh').read_bytes():
        raise ValueError('Guard differs from reviewed source')
    node = inspect()
    settings = node['Config']
    if (node['Name'] != '/egress' or node['State']['Status'] not in ('exited', 'created')
            or node['State'].get('Running') or node['State'].get('Restarting')
            or settings.get('Image') != IMAGE or settings.get('User') != 'egress'
            or settings.get('Entrypoint') != ['/bin/bash', '/courseultra-guard/start.sh']
            or settings.get('Cmd') not in (None, [])
            or settings.get('Labels', {}).get('com.docker.compose.service') != 'egress'
            or settings.get('Labels', {}).get('com.docker.compose.project') != 'openvidu'):
        raise ValueError('Expected exact stopped guarded recorder')
    mounts = {m['Destination']: m for m in node['Mounts']}
    if len(mounts) != len(node['Mounts']):
        raise ValueError('Duplicate mount destinations')
    recovery_mounts = [m for m in node['Mounts'] if m['Destination'] == '/home/egress'
                       or m['Destination'].startswith('/home/egress/')
                       or '/home/egress'.startswith(m['Destination'].rstrip('/') + '/')]
    if (len(recovery_mounts) != 1 or recovery_mounts[0].get('Type') != 'bind'
            or recovery_mounts[0].get('Destination') != '/home/egress'
            or recovery_mounts[0].get('Source') != str(root / 'data/egress_data/home/egress')
            or recovery_mounts[0].get('RW') is not True):
        raise ValueError('Exact unshadowed recovery bind required')
    for target, name in [('/courseultra-guard/start.sh', 'start.sh'),
                         ('/courseultra-guard/start.lock', 'start.lock'),
                         ('/courseultra-guard/egress-config.sha256', 'egress-config.sha256'),
                         ('/config/egress.yaml', 'egress.yaml')]:
        mount = mounts.get(target, {})
        if mount.get('Type') != 'bind' or mount.get('RW') is not False or mount.get('Source') != str(folder / name):
            raise ValueError('Guard snapshot mount mismatch')
    for name in ('tmp', 'backup_storage'):
        path = root / 'data/egress_data/home/egress' / name
        if any(p.is_symlink() for p in (path, *path.parents)) or not path.is_dir() or any(path.iterdir()):
            raise ValueError('Recovery artifacts or unknown storage; preserve and investigate')
    # A concurrent restart/identity change is not a safe arming window. This is a
    # controlled isolated operation, not a distributed lock against host admins.
    second = inspect()
    if second['Id'] != node['Id'] or second['State'] != node['State']:
        raise ValueError('Recorder changed during review')
    for name, content in [('egress.yaml', config), ('egress-config.sha256', (expected + '\n').encode())]:
        fd, temporary = tempfile.mkstemp(prefix='.arming-', dir=folder)
        try:
            with os.fdopen(fd, 'wb') as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(temporary, 0o640)
            os.replace(temporary, folder / name)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
    return {'configSha256': expected, 'previousContainerId': node['Id'],
            'snapshotPrepared': True, 'requiresRecreateAndLiveVerification': True}


def main():
    if os.geteuid() != 0 or len(sys.argv) != 2:
        raise SystemExit('Root and reviewed config fingerprint required')
    def inspect():
        result = subprocess.run(['docker', 'inspect', 'egress'], capture_output=True, text=True, timeout=15)
        if result.returncode:
            raise ValueError('Recorder inspection unavailable')
        return json.loads(result.stdout)[0]
    try:
        receipt = arm(Path('/opt/openvidu'), sys.argv[1], inspect)
    except (ValueError, OSError, KeyError, subprocess.TimeoutExpired):
        raise SystemExit('Recorder arming refused; no container start or recovery deletion attempted')
    print(json.dumps(receipt))


if __name__ == '__main__':
    main()
