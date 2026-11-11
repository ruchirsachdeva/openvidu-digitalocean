"""Report recorder placement and run the bounded job-settlement collector.

Called by the existing media-node watcher. The pinned recorder's same-container
structured logs bind an EG job to its NE service and EGH handler. Missing/rotated
logs leave placement unknown rather than guessing that it matches the room node.
Placement itself is never release authority; only the separate job proof may
settle a successful recording. Neither operation authorizes VM deletion.
"""
import datetime as dt
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import re
import shlex
import stat
import subprocess
import sys
import time
import urllib.parse
import urllib.request

IMAGE = 'sha256:01a31780783080259b7f218f624e654dc30572be5b5f7999123ac0d98c259475'
ROOT = Path('/opt/openvidu')
IDENTITY = ('runtimeId', 'generation', 'nativeGeneration', 'creationAttemptId',
            'recordingAttemptId', 'partId', 'roomSid', 'egressId')


def logged_jobs(logs, service):
    if not re.fullmatch(r'NE_[A-Za-z0-9]+', service):
        raise ValueError('Exact service identity required')
    jobs, handlers = {}, {}
    for line in logs.splitlines():
        # Docker timestamps may prefix the structured provider log. Never echo
        # request/config/error fields: they can contain credentials or room data.
        start = line.find('{')
        if start < 0:
            continue
        try:
            item = json.loads(line[start:])
        except ValueError:
            continue
        if not isinstance(item, dict) or item.get('nodeID') != service or not item.get('handlerID'):
            continue
        job, handler = item.get('egressID'), item['handlerID']
        if (not isinstance(job, str) or not re.fullmatch(r'EG_[A-Za-z0-9]+', job)
                or not isinstance(handler, str) or not re.fullmatch(r'EGH_[A-Za-z0-9]+', handler)
                or job in jobs and jobs[job] != handler
                or handler in handlers and handlers[handler] != job):
            raise ValueError('Ambiguous recorder job mapping')
        jobs[job] = handler
        handlers[handler] = job
    return jobs


def container_identity(node, boot_time, root=ROOT):
    state, config = node['State'], node['Config']
    started = dt.datetime.fromisoformat(state['StartedAt'].replace('Z', '+00:00')).timestamp()
    if (node.get('Name') != '/egress' or node.get('Image') != IMAGE
            or config.get('Image') != 'docker.io/openvidu/egress@' + IMAGE
            or not state.get('Running') or state.get('Restarting') or started < boot_time
            or not re.fullmatch('[0-9a-f]{64}', node.get('Id', ''))):
        raise ValueError('Current-boot pinned recorder required')
    mounts = [m for m in node['Mounts'] if m['Destination'] == '/home/egress'
              or m['Destination'].startswith('/home/egress/')
              or '/home/egress'.startswith(m['Destination'].rstrip('/') + '/')]
    if (len(mounts) != 1 or mounts[0].get('Type') != 'bind' or mounts[0].get('RW') is not True
            or mounts[0]['Destination'] != '/home/egress'
            or mounts[0].get('Source') != str(root / 'data/egress_data/home/egress')):
        raise ValueError('Exact recorder storage identity required')
    return node['Id'], state['StartedAt'], state['Pid'], mounts


def publish(request, identity, jobs, unchanged, now=lambda: dt.datetime.now(dt.timezone.utc)):
    cursor, seen, sent = None, set(), 0
    for _ in range(20):
        path = 'recording-locations' + ('?' + urllib.parse.urlencode({'after': cursor}) if cursor else '')
        page = request('GET', path, None)
        if not isinstance(page, dict) or not isinstance(page.get('candidates'), list):
            raise ValueError('Recording work list unavailable')
        for candidate in page['candidates']:
            if not isinstance(candidate, dict) or any(key not in candidate for key in IDENTITY):
                raise ValueError('Incomplete recording identity')
            if candidate['egressId'] not in jobs:
                continue
            unchanged()
            body = {key: candidate[key] for key in IDENTITY}
            body.update(identity, observedAt=now().isoformat())
            request('POST', 'recording-location', body)
            sent += 1
        cursor = page.get('nextCursor')
        if cursor is None:
            return sent
        if not isinstance(cursor, str) or not cursor or cursor in seen or len(cursor) > 256:
            raise ValueError('Invalid recording work-list cursor')
        seen.add(cursor)
    raise ValueError('Recording work-list budget exhausted')


def main(settings_path):
    if os.geteuid() != 0:
        raise ValueError('Root-owned collector required')
    module_path = Path(__file__).with_name('courseultra-media-drain-guard')
    if not module_path.exists():
        module_path = Path(__file__).with_name('media_drain_guard.py')
    loader = importlib.machinery.SourceFileLoader('capacity_drain_guard', str(module_path))
    module = importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name, loader))
    loader.exec_module(module)
    settings_path = Path(settings_path)
    info = settings_path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o077 or info.st_nlink != 1:
        raise ValueError('Private capacity settings required')
    settings = json.loads(settings_path.read_text())
    url, token = settings.get('url'), settings.get('token')
    parsed = urllib.parse.urlparse(url if isinstance(url, str) else '')
    if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password
            or parsed.query or parsed.fragment or not isinstance(token, str) or not token):
        raise ValueError('Capacity authority is not configured')
    opener = urllib.request.build_opener(module.NoCapacityRedirects())

    def request(method, path, body):
        req = urllib.request.Request(url.rstrip('/') + '/webhooks/openvidu/capacity/' + path,
            data=json.dumps(body).encode() if body is not None else None, method=method,
            headers={'X-Capacity-Token': token, 'Content-Type': 'application/json'})
        with opener.open(req, timeout=10) as response:
            data = response.read(4 * 1024 * 1024 + 1)
            if response.status != 200 or len(data) > 4 * 1024 * 1024:
                raise ValueError('Capacity response unavailable')
            return json.loads(data) if data else {}

    def metadata(path):
        with urllib.request.urlopen('http://169.254.169.254/metadata/v1/' + path, timeout=2) as response:
            return response.read(128).decode().strip()

    secrets = {}
    for line in (ROOT / 'secrets.env').read_text().splitlines():
        if line.startswith(('REDIS_PASSWORD=', 'MASTER_NODE_PRIVATE_IP=')):
            key, value = line.split('=', 1)
            secrets[key] = shlex.split(value)[0]
    own_id = metadata('id')
    own_ip = metadata('interfaces/private/0/ipv4/address')
    if not own_id.isdecimal():
        raise ValueError('Invalid Droplet identity')
    boot_path = Path('/proc/sys/kernel/random/boot_id')
    boot = boot_path.read_text().strip()
    if not re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', boot):
        raise ValueError('Exact boot identity required')
    redis = module.Redis(secrets['MASTER_NODE_PRIVATE_IP'], secrets['REDIS_PASSWORD'])
    try:
        pairs = redis.call('HGETALL', 'nodes_openvidu')
        if len(pairs) % 2:
            raise ValueError('Incomplete provider registration')
        registrations = {pairs[i]: json.loads(pairs[i+1]) for i in range(0, len(pairs), 2)}
        matches = [(key, value) for key, value in registrations.items() if value.get('privateIp') == own_ip]
        if len(matches) != 1 or matches[0][1].get('nodeId') != matches[0][0].decode():
            raise ValueError('Exact local media registration required')
        node, registration = matches[0]
        blob = redis.call('HGET', 'nodes', node)
        if not blob or not module.serving(node, blob, registration.get('nodeIp'), time.time()):
            raise ValueError('Current provider incarnation unavailable')
    finally:
        redis.close()

    boot_time = next(int(line.split()[1]) for line in Path('/proc/stat').read_text().splitlines() if line.startswith('btime '))
    def inspect():
        return json.loads(subprocess.run(['docker', 'inspect', 'egress'], capture_output=True,
                                        text=True, check=True, timeout=10).stdout)[0]
    before = inspect()
    expected = container_identity(before, boot_time)
    tmp = ROOT / 'data/egress_data/home/egress/tmp'
    if any(path.is_symlink() for path in (tmp, *tmp.parents)):
        raise ValueError('Recorder storage path changed')
    services = [p for p in tmp.iterdir() if re.fullmatch(r'NE_[A-Za-z0-9]+', p.name)]
    if (len(services) != 1 or services[0].is_symlink() or not services[0].is_dir()
            or not stat.S_ISSOCK((services[0] / 'service_ipc.sock').lstat().st_mode)):
        raise ValueError('Exact current recorder service required')
    logs = subprocess.run(['docker', 'logs', '--since', before['State']['StartedAt'], '--tail', '20000', before['Id']],
                          capture_output=True, text=True, check=True, timeout=10)
    if len(logs.stdout) + len(logs.stderr) > 16 * 1024 * 1024:
        raise ValueError('Recorder log evidence exceeds budget')
    jobs = logged_jobs(logs.stdout + '\n' + logs.stderr, services[0].name)

    def unchanged():
        if boot_path.read_text().strip() != boot or container_identity(inspect(), boot_time) != expected:
            raise ValueError('Recorder incarnation changed')

    identity = {'dropletId': own_id, 'nodeId': node.decode(), 'nodeGeneration': boot}
    sent = publish(request, identity, jobs, unchanged)
    # Reuse the same private transport, exact node identity and bounded watcher.
    # A distinct JOB receipt cannot weaken the legacy whole-node drain proof.
    spec = importlib.util.spec_from_file_location('recording_job_settlement',
        Path(__file__).with_name('settle-recording-jobs.py'))
    collector = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(collector)
    settled = collector.run(request, identity,
        lambda: collector.capture(inspect, jobs, services[0].name), unchanged,
        ROOT / '.courseultra-recording-jobs')
    print(json.dumps({'recordingLocationsReported': sent, 'recordingJobsSettled': settled,
                     'nodeDeletionAuthorized': False}))


if __name__ == '__main__':
    try:
        if len(sys.argv) != 2:
            raise ValueError('Private settings path required')
        main(sys.argv[1])
    except Exception:
        # HTTP/provider errors and docker output can contain secrets. Retain unknown
        # ownership; the existing watcher still attempts its guarded drain afterwards.
        raise SystemExit('Recording location report held; ownership remains protected')
