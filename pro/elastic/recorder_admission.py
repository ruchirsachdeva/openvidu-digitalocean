"""Read-only admission evidence for the pinned OpenVidu 3.8 recorder.

The provider's `available` metric means idle, NOT capable of accepting work.
`can_accept_request` tests a Web request. It conservatively covers our browser
room-composite request only with reviewed Web cost >= room-composite cost and
no larger request-level EstimatedCpu override. This is a current observation,
not a slot reservation or proof of successful recording startup.
"""
import math
import re
import hashlib
import json
import os
from pathlib import Path
import subprocess


def parse_config(body, compose='/usr/local/bin/docker-compose'):
    """Reuse the installed YAML parser without interpolation or touching services."""
    if not isinstance(body, str) or len(body) > 65536:
        raise ValueError('Bounded recorder config required')
    wrapped = 'services: {}\nx-egress:\n' + ''.join('  ' + line + '\n' for line in body.splitlines())
    result = subprocess.run([compose, '-p', 'courseultra-recorder-policy', '-f', '-', 'config',
                             '--no-interpolate', '--format', 'json'], input=wrapped,
                            capture_output=True, text=True, timeout=5)
    if result.returncode or len(result.stdout) > 131072:
        raise ValueError('Private recorder config parsing failed')
    parsed = json.loads(result.stdout)
    if set(parsed) != {'name', 'services', 'x-egress'} or parsed['services'] != {}:
        raise ValueError('Unexpected recorder document')
    return parsed['x-egress']


def config_policy_fingerprint(config):
    """Compute a review artifact, NOT an approval to start this recorder.

    Only exact reviewed template leaves may vary as credentials/connection values.
    The frozen full config hash remains independently bound to this node's guard.
    """
    schema = {
        'redis': {'address', 'username', 'password', 'db', 'use_tls'},
        'backup': {'prefix'},
        'cpu_cost': {'max_cpu_utilization', 'room_composite_cpu_cost', 'audio_room_composite_cpu_cost',
                     'web_cpu_cost', 'audio_web_cpu_cost', 'participant_cpu_cost', 'track_composite_cpu_cost', 'track_cpu_cost'},
        'openvidu': {'allocation_strategy', 'use_global_cpu_monitoring', 'disable_cpu_overload_killer', 'min_disk_space_mb'},
    }
    base_fields = set(schema) | {'api_key', 'api_secret', 'ws_url', 'health_port', 'prometheus_port', 'storage'}
    if not isinstance(config, dict) or set(config) not in (base_fields, base_fields | {'io_workers'}):
        raise ValueError('Unreviewed recorder config fields')
    for key, fields in schema.items():
        if not isinstance(config[key], dict) or set(config[key]) != fields:
            raise ValueError('Unreviewed recorder config mapping')
    storage = config['storage']
    if not isinstance(storage, dict) or set(storage) != {'s3'} or not isinstance(storage['s3'], dict):
        raise ValueError('Exact reviewed storage contract required')
    s3 = storage['s3']
    if set(s3) != {'access_key', 'secret', 'region', 'endpoint', 'bucket', 'force_path_style', 'sse'} or not isinstance(s3['sse'], dict) or set(s3['sse']) != {'type', 'kms_key_id', 'kms_encryption_context'}:
        raise ValueError('Unreviewed recorder storage fields')
    # Legacy policy hashes remain valid for ordinary readiness. Recorder-only
    # isolation separately requires the qualified single-worker IO drain policy.
    if 'io_workers' in config and (type(config['io_workers']) is not int or config['io_workers'] != 1):
        raise ValueError('Only the qualified explicit single IO worker variant is supported')
    ports = [config[k] for k in ('health_port', 'prometheus_port')]
    if any(type(p) is not int or not 1 <= p <= 65535 for p in ports) or ports[0] == ports[1]:
        raise ValueError('Distinct explicit recorder observation ports required')
    conservative_browser_cost(config['cpu_cost'])
    # Explicit nonsecret controls participate in approval. Credentials and cluster
    # addresses differ without turning a reviewed policy into arbitrary YAML approval.
    policy = json.loads(json.dumps(config, allow_nan=False))
    # The exact qualified IO1 variant changes drain correctness, not capacity
    # policy. Normalize ONLY that leaf so legacy and fresh nodes can share the
    # same descriptor during idle replacement. Full config hashes still differ;
    # isolation capability is derived separately from the actual frozen config.
    policy.pop('io_workers', None)
    # Compose's YAML->JSON rendering emits whole-number costs as integers (2),
    # while a reviewed policy may use floats (2.0). Their capacity meaning is
    # identical; fingerprint numeric costs canonically, not by serialization.
    for key, value in policy['cpu_cost'].items():
        if type(value) not in (int, float) or not math.isfinite(value):
            raise ValueError('Finite numeric recorder CPU costs required')
        policy['cpu_cost'][key] = float(value)
    variable_paths = [('redis', 'address'), ('redis', 'password'), ('api_key',), ('api_secret',),
                      ('ws_url',), ('storage', 's3', 'access_key'), ('storage', 's3', 'secret')]
    for path in variable_paths:
        obj = policy
        for key in path[:-1]:
            obj = obj[key]
        if not isinstance(obj[path[-1]], str) or not obj[path[-1]] or '\n' in obj[path[-1]] or '\r' in obj[path[-1]]:
            raise ValueError('Explicit scalar connection values required')
        obj[path[-1]] = '<rendered-connection-value>'
    actual = hashlib.sha256(json.dumps(policy, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
    return actual


def reviewed_config(config, expected):
    """Require the separately approved fingerprint; no trust-on-first-use."""
    actual = config_policy_fingerprint(config)
    if not isinstance(expected, str) or not re.fullmatch('[a-f0-9]{64}', expected) or actual != expected:
        raise ValueError('Recorder configuration is not the approved semantic policy')
    return actual


def validate_combined_cpu_policy(config, descriptor):
    """The opt-in shared-node CPU model requires whole-host load-based admission.

    This does not reserve a static recorder slot or predict later room growth.
    Validate at first start AND each observation, alongside the reviewed config hash.
    """
    profile = descriptor.get('operatingProfile', {}).get('profile', {})
    combined = profile.get('roomCpuIncludesRecording', False)
    if combined is False:
        return
    if combined is not True:
        raise ValueError('Explicit boolean combined CPU contract required')
    cpu, ov = config['cpu_cost'], config['openvidu']
    limit, cost = cpu.get('max_cpu_utilization'), cpu.get('room_composite_cpu_cost')
    estimate = profile.get('recordingDemand', {}).get('cpuMillis')
    if (ov.get('use_global_cpu_monitoring') is not True or ov.get('allocation_strategy') != 'cpuload'
            or type(limit) not in (int, float) or not math.isfinite(limit) or not 0 < limit <= .8
            or type(cost) not in (int, float) or not math.isfinite(cost) or cost < 2
            or type(estimate) is not int or estimate < 2000 or cost * 1000 != estimate):
        raise ValueError('Combined CPU requires whole-host cpuload admission, at most80% threshold and a matching at-least2-core recording startup estimate')
    conservative_browser_cost(cpu)


def endpoint_owner(container, ports, proc=Path('/proc')):
    """Bind both host-network listening sockets to one exact recorder process."""
    if not re.fullmatch('[a-f0-9]{64}', container) or len(set(ports)) != 2:
        raise ValueError('Exact container and distinct endpoints required')
    def process(pid):
        if (pid / 'comm').read_text().strip() != 'egress':
            return None
        fields = (pid / 'stat').read_text().rsplit(')', 1)[1].split()
        if fields[0] in ('Z', 'X', 'x'):
            return None
        if not fields[19].isdecimal() or int(fields[19]) <= 0:
            raise ValueError('Live recorder process required')
        return fields[19], (pid / 'cgroup').read_text()

    def listeners(pid):
        found = set()
        for table in ('tcp', 'tcp6'):
            for line in (pid / 'net' / table).read_text().splitlines()[1:]:
                fields = line.split()
                if len(fields) >= 10 and fields[3] == '0A':
                    port = int(fields[1].rsplit(':', 1)[1], 16)
                    if port in ports:
                        found.add((port, 'socket:[' + fields[9] + ']'))
        return found

    owners = []
    for pid in proc.iterdir():
        if not pid.name.isdecimal():
            continue
        try:
            identity = process(pid)
            if identity is None or container not in identity[1]:
                continue
            endpoints = listeners(pid)
            owned = {}
            for fd in (pid / 'fd').iterdir():
                try:
                    target = os.readlink(fd)
                except FileNotFoundError:
                    # Closed connections are irrelevant only if BOTH original
                    # listeners retain their exact live owner at the final check.
                    continue
                if any(target == value for _, value in endpoints):
                    owned[fd] = target
            if {port for port, target in endpoints if target in owned.values()} == set(ports):
                owners.append((pid, identity, endpoints, owned))
        except FileNotFoundError:
            # A disappearing host task or non-owning egress handler cannot
            # substitute for the both-port owner positively rechecked below.
            continue
    if len(owners) != 1:
        raise ValueError('Exact recorder endpoint ownership unavailable')
    pid, identity, endpoints, owned = owners[0]
    try:
        if (any(os.readlink(fd) != target for fd, target in owned.items())
                or listeners(pid) != endpoints or process(pid) != identity):
            raise ValueError('Recorder endpoint ownership changed during observation')
    except FileNotFoundError:
        raise ValueError('Recorder endpoint ownership changed during observation') from None
    return pid.name, identity[0]


def admission_metrics(body, allow_draining=False):
    """Require one service identity and unambiguous, fresh scrape values.

    Callers must bind the scrape to the exact guarded container, recheck its identity
    afterwards and bind freshness to the beginning of collection. Exporter
    timestamps and extra labels are refused: neither may disguise old/other work.
    """
    if not isinstance(body, str) or len(body) > 4 * 1024 * 1024:
        raise ValueError('Bounded complete recorder metrics required')
    wanted = {'livekit_egress_can_accept_request': 1,
              'livekit_egress_is_disabled': 0, 'livekit_egress_is_terminating': 0}
    values, identities = {}, set()
    for line in body.splitlines():
        if not line or line.startswith('#'):
            continue
        name = re.split(r'[{\s]', line, maxsplit=1)[0]
        if name not in wanted:
            continue
        match = re.fullmatch(r'([a-z_]+)\{([^{}]+)\}\s+([01](?:\.0+)?)', line)
        if not match or name in values:
            raise ValueError('Ambiguous recorder admission metric')
        labels = re.findall(r'(\w+)="([^"\\]*)"', match[2])
        if ','.join(k + '="' + v + '"' for k, v in labels) != match[2]:
            raise ValueError('Unexpected recorder labels')
        mapped = dict(labels)
        if len(labels) != 2 or set(mapped) != {'node_id', 'cluster_id'} or not re.fullmatch(r'NE_[A-Za-z0-9]+', mapped['node_id']):
            raise ValueError('Exact recorder service identity required')
        identities.add((mapped['node_id'], mapped['cluster_id']))
        values[name] = float(match[3])
    if (set(values) != set(wanted) or len(identities) != 1
            or not allow_draining and (values['livekit_egress_is_disabled'] != 0 or values['livekit_egress_is_terminating'] != 0)):
        raise ValueError('Recorder admission observation is not usable')
    # A healthy, enabled recorder refusing one more job is known busy. Do not
    # erase the fleet or provision a replacement merely because it is working.
    result = {'nodeId': next(iter(identities))[0], 'acceptingRequests': values['livekit_egress_can_accept_request'] == 1}
    if allow_draining:
        result.update(disabled=values['livekit_egress_is_disabled'] == 1, terminating=values['livekit_egress_is_terminating'] == 1)
    return result


def conservative_browser_cost(cpu_cost):
    """Only call after the complete config matched the approved policy.

    Avoid Python bool-as-number and nonfinite values; this comparison is not
    itself config approval or a production capacity measurement.
    """
    room, web = cpu_cost.get('room_composite_cpu_cost'), cpu_cost.get('web_cpu_cost')
    if any(type(v) not in (int, float) or not math.isfinite(v) or v <= 0 for v in (room, web)) or web < room:
        raise ValueError('Web admission must conservatively cover room composite')
    return True
