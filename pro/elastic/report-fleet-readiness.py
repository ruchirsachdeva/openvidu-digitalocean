"""Existing-watcher fleet facts. No provisioning, arming, settlement or invented sizing."""
import datetime as dt
import hashlib
import importlib.machinery
import importlib.util
import ipaddress
import json
import math
import os
from pathlib import Path
import re
import shlex
import stat
import subprocess
import sys
import urllib.parse
import urllib.request
from recorder_admission import parse_config, reviewed_config, endpoint_owner, admission_metrics, validate_combined_cpu_policy

ROOT = Path('/opt/openvidu')
PROFILE = Path('/etc/courseultra-capacity-fleet-profile.json')


def private_json(path):
    path = Path(path)
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o077 or info.st_nlink != 1:
        raise ValueError('Private regular input required')
    return json.loads(path.read_text())


def cloud_inventory(fetch, settings, descriptor):
    """Walk the full account listing; never accept a truncated page as the pool."""
    nodes, seen, masters, total = [], set(), [], None
    for page in range(1, 101):
        value = fetch(page)
        if not isinstance(value, dict) or not isinstance(value.get('droplets'), list):
            raise ValueError('Cloud inventory unavailable')
        count = value.get('meta', {}).get('total')
        if type(count) is not int or count < 0 or total is not None and count != total:
            raise ValueError('Cloud inventory changed')
        total = count
        for node in value['droplets']:
            identity = str(node.get('id', ''))
            if not identity.isdecimal() or identity in seen:
                raise ValueError('Cloud inventory duplicate')
            seen.add(identity)
            tags = node.get('tags')
            if not isinstance(tags, list):
                raise ValueError('Cloud tags missing')
            is_master = {settings['stackName'], 'master-node'}.issubset(tags)
            if is_master:
                masters.append(identity)
            if not is_master and identity != descriptor.get('masterDropletId') and not {settings['mediaTag'], settings['drainingTag']}.intersection(tags):
                continue
            def address(kind):
                # Some paginated responses repeat the same reserved address.
                # Deduplicate identical facts, not distinct addresses.
                values = list({n.get('ip_address') for n in node.get('networks', {}).get('v4', []) if n.get('type') == kind})
                # The master has both its Droplet IP and an attached reserved IP.
                # It never hosts a media registration, so a stable API-reported
                # public address is sufficient for its inventory row. Media nodes
                # must still have exactly one address to match provider identity.
                maximum = 2 if is_master and kind == 'public' else 1
                if not 1 <= len(values) <= maximum or any(
                        ipaddress.ip_address(value).version != 4 for value in values):
                    raise ValueError('Cloud address incomplete')
                return min(values, key=lambda value: int(ipaddress.ip_address(value)))
            if node.get('status') != 'active':
                raise ValueError('Allocated node is still booting')
            nodes.append(dict(dropletId=identity, privateIp=address('private'), publicIp=address('public'),
                              size=node.get('size_slug'), region=node.get('region', {}).get('slug'),
                              vpcId=node.get('vpc_uuid'), draining=settings['drainingTag'] in tags))
        next_page = value.get('links', {}).get('pages', {}).get('next')
        if next_page is None:
            if len(seen) != total:
                raise ValueError('Cloud inventory incomplete')
            if not nodes or len(nodes) > 512:
                raise ValueError('Bounded complete fleet required')
            if len(masters) != 1 or descriptor.get('masterDropletId') not in (None, '', masters[0]):
                raise ValueError('Exact cloud master identity required')
            # The fresh cloud ID cannot be known before Terraform creates it.
            # Resolve only the unique stack-tagged master from this complete listing.
            descriptor['masterDropletId'] = masters[0]
            return sorted(nodes, key=lambda n: n['dropletId'])
        parsed = urllib.parse.urlparse(next_page)
        query = urllib.parse.parse_qs(parsed.query)
        if (parsed.scheme != 'https' or parsed.netloc != 'api.digitalocean.com'
                or parsed.path != '/v2/droplets' or parsed.fragment
                or query.get('page') != [str(page + 1)] or query.get('per_page') != ['200']):
            raise ValueError('Invalid cloud pagination')
        # Construct the next URL ourselves; never forward credentials to a supplied URL.
    raise ValueError('Cloud page bound exceeded')


def registrations(pairs, native, guard, now, draining_ips=frozenset()):
    if not isinstance(pairs, list) or len(pairs) % 2 or len(pairs) > 1024:
        raise ValueError('Incomplete registration inventory')
    result, seen = [], set()
    for key, raw in zip(pairs[::2], pairs[1::2]):
        node = json.loads(raw)
        identity = key.decode()
        if identity in seen or node.get('nodeId') != identity:
            raise ValueError('Ambiguous provider identity')
        seen.add(identity)
        if not guard.serving(key, native.get(key, b''), node.get('nodeIp'), now):
            # Draining registrations may stop heartbeating before physical storage
            # settlement. They remain identity evidence, never ready capacity.
            fields = guard.protobuf_fields(native.get(key, b''))
            if (node.get('privateIp') not in draining_ips or fields.get(1) != key
                    or fields.get(2) != node.get('nodeIp', '').encode() or fields.get(6) not in (1, 2)):
                raise ValueError('Non-serving or stale provider node')
        result.append(dict(nodeId=identity, privateIp=node.get('privateIp'), publicIp=node.get('nodeIp')))
    if set(native) != {key for key in pairs[::2]}:
        raise ValueError('Unknown native worker')
    return sorted(result, key=lambda n: n['nodeId'])


def artifact(path):
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('Unsafe artifact path')
    return hashlib.sha256(path.read_bytes()).hexdigest()


def local_receipt(own, boot, nodes, containers, descriptor, guard, run, root=ROOT, proc=Path('/proc')):
    if not re.fullmatch(r'[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}', boot):
        raise ValueError('Linux boot identity required')
    cloud = [n for n in nodes if n['dropletId'] == own]
    if len(cloud) != 1:
        raise ValueError('Local cloud identity missing')
    master = own == descriptor['masterDropletId']
    workers = [c for c in containers if c.get('Name') == '/egress'
               or re.search(r'(^|/)egress(?:[:@]|$)', c.get('Config', {}).get('Image', ''))]
    running_pids = []
    for p in proc.iterdir():
        if p.name.isdecimal():
            try:
                if (p / 'comm').read_text().strip() == 'egress':
                    running_pids.append((p / 'cgroup').read_text())
            except FileNotFoundError:
                raise ValueError('Process inventory changed') from None
    receipt = dict(dropletId=own, bootId=boot, nodeId=None, observedAt=dt.datetime.now(dt.timezone.utc).isoformat(),
                   mediaReady=False, recorderRunning=False, recorderAdmissionVerified=False,
                   recorderExcluded=False, unmanagedWorker=False, secondaryChecksPassed=False)
    memory = {x.split(':')[0]: int(x.split()[1]) * 1024 for x in (proc / 'meminfo').read_text().splitlines() if x.startswith('MemAvailable:')}
    load = float((proc / 'loadavg').read_text().split()[0])
    limits = [descriptor.get('minimumFreeMemoryBytes'), descriptor.get('minimumFreeDiskBytes'), descriptor.get('maximumLoadAverage')]
    if any(type(v) not in (int, float) or not math.isfinite(v) or v <= 0 for v in limits):
        raise ValueError('Explicit secondary limits required')
    fs = os.statvfs(root)
    secondary = memory.get('MemAvailable', 0) >= limits[0] and fs.f_bavail * fs.f_frsize >= limits[1] and load <= limits[2]
    if master:
        receipt.update(unmanagedWorker=bool(workers or running_pids), recorderExcluded=not workers and not running_pids,
                       secondaryChecksPassed=secondary)
        return receipt
    if len(workers) != 1 or workers[0].get('Name') != '/egress':
        receipt['unmanagedWorker'] = True
        return receipt
    worker = workers[0]
    if any(worker.get('Id', '') not in group for group in running_pids):
        receipt['unmanagedWorker'] = True
        return receipt
    media = [c for c in containers if c.get('Name') == '/openvidu']
    if len(media) != 1:
        raise ValueError('Exact media container required')
    state = worker.get('State', {})
    mounts = {m.get('Destination'): m for m in worker.get('Mounts', [])}
    expected = {'/config/egress.yaml': 'egress.yaml', '/courseultra-guard/start.sh': 'start.sh',
                '/courseultra-guard/egress-config.sha256': 'egress-config.sha256', '/courseultra-guard/start.lock': 'start.lock'}
    if worker.get('Config', {}).get('Entrypoint') != ['/bin/bash', '/courseultra-guard/start.sh']:
        raise ValueError('Guarded recorder entrypoint required')
    for destination, filename in expected.items():
        mount = mounts.get(destination, {})
        if mount.get('Type') != 'bind' or mount.get('RW') is not False or mount.get('Source') != str(root / 'courseultra-recorder-guard' / filename):
            raise ValueError('Recorder guard mount mismatch')
    receipt.update(mediaImage=media[0].get('Image'), recorderImage=worker.get('Image'),
                   recorderContainerId=worker.get('Id'), recorderStartedAt=state.get('StartedAt'),
                   recorderConfigSha256=artifact(root / 'courseultra-recorder-guard/egress.yaml'),
                   startupGuardSha256=artifact(root / 'courseultra-recorder-guard/start.sh'),
                   recorderRunning=state.get('Running') is True and state.get('Restarting') is False,
                   secondaryChecksPassed=secondary)
    config_path = root / 'courseultra-recorder-guard/egress.yaml'
    frozen = config_path.read_text()
    if (root / 'courseultra-recorder-guard/egress-config.sha256').read_text().strip() != receipt['recorderConfigSha256']:
        raise ValueError('Recorder frozen config fingerprint mismatch')
    config = parse_config(frozen)
    receipt['recorderPolicySha256'] = reviewed_config(config, descriptor['recorderPolicySha256'])
    validate_combined_cpu_policy(config, descriptor)
    receipt['recorderIsolationSupported'] = type(config.get('io_workers')) is int and config['io_workers'] == 1
    isolation_spec = importlib.util.spec_from_file_location('recorder_isolation', Path(__file__).with_name('recorder-isolation.py'))
    isolation = importlib.util.module_from_spec(isolation_spec)
    isolation_spec.loader.exec_module(isolation)
    journal = isolation.read(root)
    def inspect_recorder():
        return json.loads(run(['docker', 'inspect', worker['Id']]))[0]
    if journal and not receipt['recorderIsolationSupported']:
        raise ValueError('Isolation requires the reviewed single IO worker policy')
    if journal and not journal.get('signalAttempted') and not journal.get('restorePlan'):
        isolation.act(journal['intent'], worker, boot, root, inspect_recorder, run)
        worker = inspect_recorder()
    if receipt['recorderRunning']:
        if (worker.get('HostConfig', {}).get('NetworkMode') != 'host'
                or receipt['recorderImage'] != descriptor['recorderImage']
                or receipt['startupGuardSha256'] != descriptor['startupGuardSha256']):
            raise ValueError('Reviewed recorder process contract required')
        ports = [config['health_port'], config['prometheus_port']]
        owner = endpoint_owner(worker['Id'], ports, proc)
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), guard.NoCapacityRedirects())
        def get(port, path):
            with opener.open('http://127.0.0.1:' + str(port) + path, timeout=2) as response:
                body = response.read(4 * 1024 * 1024 + 1)
                if response.status != 200 or len(body) > 4 * 1024 * 1024:
                    raise ValueError('Complete current-process response required')
                return body.decode()
        get(ports[0], '/')
        admission = admission_metrics(get(ports[1], '/metrics'), allow_draining=journal is not None)
        if endpoint_owner(worker['Id'], ports, proc) != owner or config_path.read_text() != frozen:
            raise ValueError('Recorder changed during admission observation')
        # Includes a valid known-busy response. The provider may make the start
        # request wait; this proves current service/config, not a reserved slot.
        receipt['recorderAdmissionVerified'] = not admission.get('disabled', False) and not admission.get('terminating', False)
        receipt['recorderAcceptingRequests'] = admission['acceptingRequests']
        if journal:
            logs = run(['docker', 'logs', '--timestamps', '--since', state['StartedAt'], '--tail', '20000', worker['Id']])
            receipt['recorderIsolation'] = isolation.proof(root, worker, boot, admission, logs, proc, owner)

    if not state.get('Running'):
        # Absence/exit alone is insufficient: verify the existing persistent restart fence.
        if journal:
            receipt['recorderIsolation'] = isolation.proof(root, worker, boot, proc=proc)
        else:
            guard.verify_restart_fence(root, run=run)
            receipt['recorderExcluded'] = state.get('Status') == 'exited' and state.get('ExitCode') == 0 and state.get('OOMKilled') is False
    if receipt['recorderRunning']:
        # Use the existing half-minute cadence: a once-per-minute cache would
        # periodically expire the 60-second pool while its replacement is collected.
        spec = importlib.util.spec_from_file_location('recorder_capacity_footprint',
            Path(__file__).with_name('recorder-capacity-footprint.py'))
        footprint = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(footprint)
        receipt['recorderWork'] = footprint.observe_local(worker, boot, root, proc, excluded=bool(receipt.get('recorderIsolation', {}).get('excluded')))
    receipt['mediaReady'] = media[0].get('State', {}).get('Running') is True and guard.healthy(cloud[0]['privateIp'])
    return receipt


def container_identities(values):
    # Docker may return the same mount set in a different array order on each
    # inspect. Compare full mount facts canonically, not incidental ordering.
    return sorted((v['Id'], v['State']['StartedAt'], v['State']['Pid'], v['State']['Running'],
                   tuple(sorted(json.dumps(m, sort_keys=True) for m in v.get('Mounts', [])))) for v in values)


def report_summary(result, local, observed_at):
    # Log bounded reason codes, never arbitrary backend response text or work details.
    reason = result.get('holdReason')
    if reason is not None and (not isinstance(reason, str) or not re.fullmatch('[a-z][a-z0-9_]{0,79}', reason)):
        reason = 'unrecognized_hold'
    return dict(receiptAccepted=True, poolPublished=result.get('poolPublished') is True,
                recorderAdmissionVerified=local['recorderAdmissionVerified'], holdReason=reason,
                dropletId=local['dropletId'], observedAt=observed_at)


def main(settings_path):
    if os.geteuid() != 0:
        raise ValueError('Root collector required')
    path = Path(__file__).with_name('courseultra-media-drain-guard')
    if not path.exists():
        path = Path(__file__).with_name('media_drain_guard.py')
    loader = importlib.machinery.SourceFileLoader('fleet_drain_guard', str(path))
    guard = importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name, loader))
    loader.exec_module(guard)
    settings, descriptor = private_json(settings_path), private_json(PROFILE)
    began = dt.datetime.now(dt.timezone.utc).isoformat()
    opener = urllib.request.build_opener(guard.NoCapacityRedirects())
    def request(url, token, body=None, cloud=False):
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.fragment or not token:
            raise ValueError('Secure authority required')
        headers = {'Authorization': 'Bearer ' + token} if cloud else {'X-Capacity-Token': token, 'Content-Type': 'application/json'}
        req = urllib.request.Request(url, data=None if body is None else json.dumps(body).encode(), headers=headers)
        with opener.open(req, timeout=5) as response:
            data = response.read(4 * 1024 * 1024 + 1)
            if response.status != 200 or len(data) > 4 * 1024 * 1024:
                raise ValueError('Complete response required')
            return json.loads(data)
    fetch = lambda page: request('https://api.digitalocean.com/v2/droplets?per_page=200&page=' + str(page), settings['cloudToken'], cloud=True)
    cloud = cloud_inventory(fetch, settings, descriptor)
    with urllib.request.urlopen('http://169.254.169.254/metadata/v1/id', timeout=2) as response:
        own = response.read(64).decode().strip()
    boot_path = Path('/proc/sys/kernel/random/boot_id')
    boot = boot_path.read_text().strip()
    def run(args):
        result = subprocess.run(args, capture_output=True, text=True, check=True, timeout=5)
        if len(result.stdout) + len(result.stderr) > 4 * 1024 * 1024:
            raise ValueError('Container inventory exceeds bound')
        return result.stdout + ('\n' + result.stderr if args[:2] == ['docker', 'logs'] else '')
    def inspect():
        ids = run(['docker', 'ps', '-aq', '--no-trunc']).split()
        if len(ids) > 128 or any(not re.fullmatch('[a-f0-9]{64}', i) for i in ids):
            raise ValueError('Bounded container inventory required')
        return json.loads(run(['docker', 'inspect', *ids])) if ids else []
    before = inspect()
    local = local_receipt(own, boot, cloud, before, descriptor, guard, run)
    secrets = {}
    for line in (ROOT / 'secrets.env').read_text().splitlines():
        if line.startswith(('REDIS_PASSWORD=', 'MASTER_NODE_PRIVATE_IP=')):
            key, value = line.split('=', 1)
            secrets[key] = shlex.split(value)[0]
    redis = guard.Redis(secrets['MASTER_NODE_PRIVATE_IP'], secrets['REDIS_PASSWORD'])
    try:
        pairs, native_pairs = redis.call('HGETALL', 'nodes_openvidu'), redis.call('HGETALL', 'nodes')
        if len(native_pairs) % 2 or len(set(native_pairs[::2])) != len(native_pairs) // 2:
            raise ValueError('Native node inventory incomplete')
        native = dict(zip(native_pairs[::2], native_pairs[1::2]))
        registered = registrations(pairs, native, guard, dt.datetime.now(dt.timezone.utc).timestamp(),
                                   {n['privateIp'] for n in cloud if n['draining']})
    finally:
        redis.close()
    own_cloud = next(n for n in cloud if n['dropletId'] == own)
    local_nodes = [r['nodeId'] for r in registered if r['privateIp'] == own_cloud['privateIp']]
    if len(local_nodes) > 1:
        raise ValueError('Local provider identity ambiguous')
    local['nodeId'] = local_nodes[0] if local_nodes else None
    # Never stamp an old sample fresh: retain began and the original local timestamp.
    if boot_path.read_text().strip() != boot or container_identities(inspect()) != container_identities(before) or cloud_inventory(fetch, settings, descriptor) != cloud:
        raise ValueError('Fleet changed while collecting')
    result = request(settings['url'].rstrip('/') + '/webhooks/openvidu/capacity/fleet-observation', settings['token'],
                     dict(descriptor=descriptor, observedAt=began, cloud=cloud, registrations=registered, local=local))
    if not isinstance(result, dict) or result.get('receiptAccepted') is not True:
        raise ValueError('Receipt was not accepted')
    if local.get('recorderIsolation') or result.get('recorderAction'):
        spec = importlib.util.spec_from_file_location('recorder_isolation', Path(__file__).with_name('recorder-isolation.py'))
        isolation = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(isolation)
        def recorder():
            return json.loads(run(['docker', 'inspect', local['recorderContainerId']]))[0]
        def settlement_request(method, path, body):
            return request(settings['url'].rstrip('/') + '/webhooks/openvidu/capacity/' + path, settings['token'],
                           body if method == 'POST' else None)
        isolation.apply_response(result, local, boot, ROOT, recorder, run, settlement_request)
    print(json.dumps(report_summary(result, local, began)))


if __name__ == '__main__':
    try:
        if len(sys.argv) != 2:
            raise ValueError('Private settings path required')
        main(sys.argv[1])
    except Exception:
        raise SystemExit('Fleet observation held; new allocation remains unverified')
