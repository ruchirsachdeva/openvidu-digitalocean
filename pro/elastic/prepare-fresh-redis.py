"""Prepare persistence before a fresh master's first start; never migrate live data."""
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile


def merge_override(existing, candidate):
    # Preserve operator comments/Meet configuration verbatim. Unknown YAML shapes
    # need review, not a best-effort rewrite of security-sensitive configuration.
    for text in (existing, candidate):
        if re.findall(r'^([^ #\n][^\n]*):\s*$', text, re.MULTILINE) != ['services']:
            raise ValueError('Expected a single services mapping')
    if re.search(r'^  [\'"]?redis[\'"]?\s*:', existing, re.MULTILINE):
        raise ValueError('Existing Redis customization requires migration review')
    if re.findall(r'^  ([\w-]+):', candidate, re.MULTILINE) != ['redis']:
        raise ValueError('Candidate must customize Redis only')
    return existing.rstrip() + '\n' + candidate.split('services:\n', 1)[1]


def validate_config(before, after, data):
    before, after = json.loads(json.dumps(before)), json.loads(json.dumps(after))
    old = before['services'].pop('redis')
    new = after['services'].pop('redis')
    if before != after:
        raise ValueError('Configuration changed outside Redis')
    # TODO(OpenVidu upgrade): requalify the entrypoint and restart/restore tests
    # against the new Redis image before extending this exact-version allowlist.
    if old.get('image') not in {prefix + version for prefix in ('redis:', 'docker.io/redis:')
                                for version in ('8.6.2-alpine', '8.6.4-alpine')}:
        raise ValueError('Redis image requires persistence compatibility review')
    for key in set(old) | set(new):
        if key not in {'volumes', 'entrypoint', 'stop_grace_period'} and old.get(key) != new.get(key):
            raise ValueError('Unexpected Redis configuration change')
    mounts = new.get('volumes', [])
    data_mounts = [v for v in mounts if v.get('target') == '/data']
    if any(v.get('target') == '/data' for v in old.get('volumes', [])):
        raise ValueError('Existing persistence requires review')
    if [v for v in mounts if v.get('target') != '/data'] != old.get('volumes', []):
        raise ValueError('Existing Redis mount changed')
    if len(data_mounts) != 1:
        raise ValueError('Exactly one persistent data mount required')
    mount = data_mounts[0]
    if (mount.get('type') != 'bind' or mount.get('source') != str(data)
            or mount.get('read_only', False) or mount.get('bind', {}).get('create_host_path') is not False):
        raise ValueError('Unsafe Redis data mount')


def prepare(root, candidate, run):
    root = Path(root)
    override = root / 'docker-compose.override.yaml'
    data = root / 'data/redis'
    # Empty persistence is valid only on a fresh installation. Stopped containers
    # count too: their writable layers may contain the only surviving dataset.
    def has_containers():
        return any(run(['docker', 'ps', '-aq', '--filter', selector]).strip() for selector in
                   ('label=com.docker.compose.project=openvidu', 'name=^/redis$'))

    if has_containers():
        raise ValueError('Existing OpenVidu containers require migration review')
    if any(p.is_symlink() for p in (root, override, data.parent, data)):
        raise ValueError('Refusing symlinked configuration or persistence paths')
    if data.exists() and (not data.is_dir() or any(data.iterdir())):
        raise ValueError('Existing Redis data requires migration review')
    original = override.read_text() if override.exists() else None
    merged = merge_override(original if original is not None else 'services:\n', candidate)
    command = ['/usr/local/bin/docker-compose', '-p', 'openvidu', '-f', str(root / 'docker-compose.yaml')]
    before = json.loads(run(command + (['-f', str(override)] if original is not None else [])
                            + ['config', '--format', 'json']))
    fd, name = tempfile.mkstemp(prefix='.redis-override-', suffix='.yaml', dir=root)
    staged = Path(name)
    try:
        with os.fdopen(fd, 'w') as stream:
            stream.write(merged)
        after = json.loads(run(command + ['-f', str(staged), 'config', '--format', 'json']))
        validate_config(before, after, data)
        # Bootstrap is serialized by cloud-init. Recheck before committing files
        # so an unexpected concurrent start cannot be mistaken for a fresh node.
        if has_containers():
            raise ValueError('OpenVidu started during bootstrap preparation')
        if (override.read_text() if override.exists() else None) != original:
            raise ValueError('Override changed during preparation')
        data.mkdir(mode=0o700, parents=True, exist_ok=True)
        if any(data.iterdir()):
            raise ValueError('Redis data appeared during preparation')
        data.chmod(0o700)
        os.replace(staged, override)
    finally:
        if staged.exists():
            staged.unlink()


def main():
    root = Path('/opt/openvidu')
    env = dict(os.environ, COMPOSE_ENV_FILES=str(root / 'config/node/master_node.env'))

    def run(args):
        result = subprocess.run(args, cwd=root, env=env, text=True,
                                capture_output=True, timeout=60)
        if result.returncode:
            # Effective Compose configuration/errors may contain credentials.
            raise RuntimeError('Fresh Redis validation failed; inspect protected configuration')
        return result.stdout

    try:
        prepare(root, Path('/usr/local/share/courseultra-redis.override.yaml').read_text(), run)
    except (ValueError, RuntimeError, OSError, KeyError):
        raise SystemExit('Fresh Redis setup refused; review existing state and protected configuration. No migration was attempted.')


if __name__ == '__main__':
    main()
