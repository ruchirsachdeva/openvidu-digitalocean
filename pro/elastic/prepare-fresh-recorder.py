"""Install an UNARMED recorder guard before a fresh isolated node's first start.

Never arm recording, migrate existing containers, or remove recording data.
The enclosing bootstrap must install its systemd start barrier before the vendor
installer enables the service. This helper deliberately does not remove that barrier.
"""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

IMAGE = 'docker.io/openvidu/egress@sha256:01a31780783080259b7f218f624e654dc30572be5b5f7999123ac0d98c259475'


def merge(existing, candidate):
    for value in (existing, candidate):
        if re.findall(r'^([^ #\n][^\n]*):\s*$', value, re.MULTILINE) != ['services']:
            raise ValueError('Expected a single services mapping')
    if re.search(r'^  [\'"]?egress[\'"]?\s*:', existing, re.MULTILINE):
        raise ValueError('Existing recorder override requires review')
    if re.findall(r'^  ([\w-]+):', candidate, re.MULTILINE) != ['egress']:
        raise ValueError('Candidate must customize recorder only')
    return existing.rstrip() + '\n' + candidate.split('services:\n', 1)[1]


def validate(before, after, root):
    before, after = json.loads(json.dumps(before)), json.loads(json.dumps(after))
    old, new = before['services'].pop('egress'), after['services'].pop('egress')
    if before != after:
        raise ValueError('Changes outside recorder')
    if old.get('image') not in ('openvidu/egress:3.8.0', 'docker.io/openvidu/egress:3.8.0'):
        raise ValueError('Unreviewed recorder image')
    changed = {'image', 'platform', 'user', 'restart', 'entrypoint', 'command', 'environment', 'volumes'}
    if any(old.get(k) != new.get(k) for k in (set(old) | set(new)) - changed):
        raise ValueError('Unexpected recorder configuration change')
    expected = dict(image=IMAGE, platform='linux/amd64', user='egress', restart='unless-stopped',
                    entrypoint=['/bin/bash', '/courseultra-guard/start.sh'], command=[])
    if any(new.get(k) != v for k, v in expected.items()):
        raise ValueError('Guard launch contract changed')
    if new.get('environment') != dict(old.get('environment', {}), EGRESS_CONFIG_FILE='/config/egress.yaml'):
        raise ValueError('Unexpected environment change')
    targets = {'/courseultra-guard/start.sh': 'start.sh',
               '/courseultra-guard/start.lock': 'start.lock',
               '/courseultra-guard/egress-config.sha256': 'egress-config.sha256',
               '/config/egress.yaml': 'egress.yaml'}
    if any(m['target'] in targets for m in old.get('volumes', [])):
        raise ValueError('Existing guard mounts require review')
    if [m for m in new.get('volumes', []) if m['target'] not in targets] != old.get('volumes', []):
        raise ValueError('Existing mounts changed')
    added = [m for m in new.get('volumes', []) if m['target'] in targets]
    if len(added) != len(targets) or len({m['target'] for m in added}) != len(targets):
        raise ValueError('Missing or duplicate guard mount')
    for mount in added:
        if (mount.get('type') != 'bind' or not mount.get('read_only')
                or mount.get('source') != str(root / 'courseultra-recorder-guard' / targets[mount['target']])
                or mount.get('bind', {}).get('create_host_path', False)):
            raise ValueError('Unsafe guard mount')


def prepare(root, candidate, guard, run, role='media_node'):
    if role not in ('master_node', 'media_node'):
        raise ValueError('Exact node role required')
    root = Path(root)
    override = root / 'docker-compose.override.yaml'
    destination = root / 'courseultra-recorder-guard'
    recovery = root / 'data/egress_data/home/egress'
    def fresh():
        for selector in ('label=com.docker.compose.project=openvidu', 'name=^/egress$'):
            if run(['docker', 'ps', '-aq', '--filter', selector]).strip():
                raise ValueError('Existing containers require migration review')
        for path in (override, destination, recovery, *recovery.parents):
            if path.is_symlink():
                raise ValueError('Symlinked bootstrap path')
        if destination.exists():
            raise ValueError('Existing or partial guard preparation requires review')
        # Fail on all pre-existing recorder data, not only recognised media suffixes.
        data = root / 'data/egress_data'
        if data.exists() and (not data.is_dir() or any(data.iterdir())):
            raise ValueError('Existing recorder data requires review')
    fresh()
    original = override.read_text() if override.exists() else None
    command = ['/usr/local/bin/docker-compose', '-p', 'openvidu', '-f', str(root / 'docker-compose.yaml')]
    before = json.loads(run(command + (['-f', str(override)] if original is not None else []) + ['config', '--format', 'json']))
    if role == 'master_node':
        # Elastic master owns cluster egress config, not a static egress service.
        # Never add a recorder there merely to guard it. This checks declarative
        # absence only; operator/out-of-band worker inventory is a separate gate.
        services = before.get('services')
        if not isinstance(services, dict) or not services:
            raise ValueError('Master service inventory unavailable')
        if any(name == 'egress' or service.get('container_name') == 'egress'
               or re.search(r'(^|/)egress(?:[:@]|$)', service.get('image', ''))
               for name, service in services.items()):
            raise ValueError('Unexpected master recorder requires review')
        fresh()
        if (override.read_text() if override.exists() else None) != original:
            raise ValueError('Master override changed during preparation')
        return
    merged = merge(original if original is not None else 'services:\n', candidate)
    fd, name = tempfile.mkstemp(prefix='.recorder-override-', suffix='.yaml', dir=root)
    staged = Path(name)
    try:
        with os.fdopen(fd, 'w') as stream:
            stream.write(merged)
        after = json.loads(run(command + ['-f', str(staged), 'config', '--format', 'json']))
        validate(before, after, root)
        fresh()
        if (override.read_text() if override.exists() else None) != original:
            raise ValueError('Override changed during preparation')
        destination.mkdir(mode=0o750)
        for filename, body in [('start.sh', guard), ('start.lock', ''), ('egress.yaml', '# Unarmed isolated recorder\n'),
                               ('egress-config.sha256', 'UNARMED\n')]:
            with (destination / filename).open('x') as stream:
                stream.write(body)
            (destination / filename).chmod(0o640)
        # Vendor setup-volumes later sets its normal ownership. Until then gid0
        # permits the pinned non-root egress user to access these empty directories.
        for path in (recovery, recovery / 'tmp', recovery / 'backup_storage'):
            path.mkdir(mode=0o770, parents=True, exist_ok=True)
            # Cloud-init deliberately uses umask 077. mkdir's requested mode
            # alone becomes 0700, leaving the root-owned tmp unreadable to the
            # pinned egress UID1001/GID0. Only these newly-created empty paths
            # get the intended mode; never repair an existing recovery tree.
            path.chmod(0o770)
        os.replace(staged, override)
    finally:
        if staged.exists():
            staged.unlink()


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in ('master_node', 'media_node') or os.geteuid() != 0:
        raise SystemExit('Fresh recorder preparation requires root and an exact node role')
    root = Path('/opt/openvidu')
    env = dict(os.environ, COMPOSE_ENV_FILES=str(root / 'config/node' / (sys.argv[1] + '.env')))
    def run(args):
        result = subprocess.run(args, cwd=root, env=env, capture_output=True, text=True, timeout=60)
        if result.returncode:
            raise RuntimeError('Private recorder configuration validation failed')
        return result.stdout
    try:
        prepare(root, Path('/usr/local/share/courseultra-recorder.override.yaml').read_text(),
                Path('/usr/local/share/courseultra-recorder-start.sh').read_text(), run, sys.argv[1])
    except (ValueError, RuntimeError, OSError, KeyError):
        raise SystemExit('Fresh recorder setup refused. Preserve existing state; no recovery or arming attempted.')


if __name__ == '__main__':
    main()
