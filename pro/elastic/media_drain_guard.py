#!/usr/bin/env python3
"""Authorize a drain against live provider registration, not cloud VM/CPU readiness.

Runs on the media node using its existing private Redis connection and doctl
identity. A Redis reservation serializes competing capacity claims without a
new service or credential. Reservations deliberately do not expire while a long
class drains; they are discarded only once that native node unregisters.
"""
import argparse
import ipaddress
import json
import os
import pathlib
import re
import shlex
import socket
import stat
import subprocess
import sys
import time
import urllib.request
import urllib.parse


class Redis:
    def __init__(self, host, password):
        self.socket = socket.create_connection((host, 7000), timeout=5)
        self.stream = self.socket.makefile('rb')
        if self.call('AUTH', password) != b'OK':
            raise ValueError('Redis authentication failed')

    def close(self):
        self.stream.close()
        self.socket.close()

    def call(self, *args):
        values = [v if isinstance(v, bytes) else str(v).encode() for v in args]
        self.socket.sendall(b'*%d\r\n' % len(values) + b''.join(
            b'$%d\r\n' % len(v) + v + b'\r\n' for v in values))
        return self.read()

    def read(self):
        line = self.stream.readline(65537)
        if not line.endswith(b'\r\n'):
            raise ValueError('Incomplete Redis response')
        kind, value = line[:1], line[1:-2]
        if kind == b'+':
            return value
        if kind == b':':
            return int(value)
        if kind == b'$':
            size = int(value)
            if size == -1:
                return None
            if not 0 <= size <= 4_000_000:
                raise ValueError('Invalid Redis bulk length')
            data = self.stream.read(size + 2)
            if len(data) != size + 2 or not data.endswith(b'\r\n'):
                raise ValueError('Truncated Redis bulk response')
            return data[:-2]
        if kind == b'*':
            size = int(value)
            if not 0 <= size <= 10000:
                raise ValueError('Invalid Redis array length')
            return [self.read() for _ in range(size)]
        # Do not log AUTH errors, redirects or server-supplied data as secrets
        # and topology can be embedded in error responses. Cluster changes hold.
        raise ValueError('Redis command failed')


class NoCapacityRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('Capacity redirects are forbidden')


def exclude_application_work(settings_path, own_id, own_nodes, root=pathlib.Path('/opt/openvidu'),
                             boot_path=pathlib.Path('/proc/sys/kernel/random/boot_id'), opener=None,
                             final_check=False):
    """Application exclusion is separate from provider shutdown and file disposal.

    Preserve the exact identity before shutdown unregisters the provider node. Never
    infer it from a reused IP, or reuse the receipt after a reboot. The fleet producer
    must use the Linux boot UUID for Node.generation. Every watcher retry rechecks
    obligations; a saved response is not permission to delete later.
    """
    def private_file(path):
        info = path.lstat()
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
                or info.st_mode & 0o077 or info.st_nlink != 1):
            raise ValueError('Private regular capacity file required')
        return json.loads(path.read_text())

    settings = private_file(pathlib.Path(settings_path))
    url, token = settings.get('url'), settings.get('token')
    parsed = urllib.parse.urlparse(url if isinstance(url, str) else '')
    if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password
            or parsed.query or parsed.fragment or not isinstance(token, str) or not token):
        raise ValueError('Capacity authority is not configured')
    boot = boot_path.read_text().strip()
    if not re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', boot):
        raise ValueError('Exact boot identity unavailable')
    receipt = root / '.courseultra-drain-capacity-identity.json'
    try:
        identity = private_file(receipt)
    except FileNotFoundError:
        if len(own_nodes) != 1:
            raise ValueError('First exclusion requires exact provider registration')
        identity = {'dropletId': own_id, 'nodeId': own_nodes[0].decode(), 'generation': boot}
        fd = os.open(receipt, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'w') as stream:
            json.dump(identity, stream, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        directory = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    if (identity.get('dropletId') != own_id or identity.get('generation') != boot
            or not isinstance(identity.get('nodeId'), str) or not identity['nodeId']
            or len(own_nodes) > 1 or own_nodes and own_nodes[0].decode() != identity['nodeId']):
        raise ValueError('Drain identity changed')
    action = 'exclude-idle' if final_check else 'begin-drain'
    request = urllib.request.Request(url.rstrip('/') + '/webhooks/openvidu/capacity/' + action,
        data=json.dumps(identity).encode(), method='POST',
        headers={'X-Capacity-Token': token, 'Content-Type': 'application/json'})
    transport = opener or urllib.request.build_opener(NoCapacityRedirects())
    with transport.open(request, timeout=10) as response:
        payload = response.read(65537)
        if response.status != 200 or len(payload) > 65536:
            raise ValueError('Application exclusion unavailable')
        result = json.loads(payload)
    if (not isinstance(result, dict) or result.get('applicationExcluded') is not True
            or final_check and result.get('applicationObligationsClear') is not True
            or any(result.get(key) != value for key, value in identity.items())):
        raise ValueError('Exact application exclusion was not confirmed')


def protobuf_fields(data):
    """Decode only protobuf wire framing; reject ambiguous/truncated fields.

    OpenVidu 3.7 stores livekit.Node in Redis: id=1, ip=2, stats=4,
    state=6; NodeStats.updated_at=2. Unknown fields remain forward compatible.
    No provider binary or additional protobuf package is needed on the VM.
    """
    offset = 0
    result = {}

    def varint():
        nonlocal offset
        value = 0
        for shift in range(0, 70, 7):
            if offset >= len(data):
                raise ValueError('Truncated node metadata')
            byte = data[offset]
            offset += 1
            value |= (byte & 127) << shift
            if not byte & 128:
                return value
        raise ValueError('Invalid node metadata integer')

    while offset < len(data):
        tag = varint()
        field, wire = tag >> 3, tag & 7
        if not field or field in result:
            raise ValueError('Ambiguous node metadata')
        if wire == 0:
            value = varint()
        else:
            size = varint() if wire == 2 else {1: 8, 5: 4}.get(wire)
            if size is None or offset + size > len(data):
                raise ValueError('Invalid node metadata field')
            value = data[offset:offset + size]
            offset += size
        result[field] = value
    return result


def serving(node_id, blob, node_ip, now):
    fields = protobuf_fields(blob)
    stats = protobuf_fields(fields.get(4, b''))
    updated = stats.get(2, 0)
    return (fields.get(1) == node_id and fields.get(2) == node_ip.encode()
            and fields.get(6, 0) == 1 and isinstance(updated, int)
            and 0 <= now - updated <= 10)


def private_ip(droplet, vpc):
    if droplet.get('vpc_uuid') != vpc:
        raise ValueError('Media inventory includes a different VPC')
    ips = [v['ip_address'] for v in droplet.get('networks', {}).get('v4', [])
           if v.get('type') == 'private']
    if len(ips) != 1 or not ipaddress.ip_address(ips[0]).is_private:
        raise ValueError('Media private address is ambiguous')
    return ips[0]


def healthy(address):
    try:
        with urllib.request.urlopen('http://' + address + ':7880/', timeout=2) as response:
            return response.status == 200 and response.read(32).strip() == b'OK'
    except Exception:
        return False


def ready_peers(droplets, registrations, native, own_id, active_tag, draining_tag, vpc, now, health=healthy):
    result = {}
    for droplet in droplets:
        tags = droplet.get('tags')
        if not isinstance(tags, list):
            raise ValueError('Missing lifecycle tags')
        if (str(droplet['id']) == own_id or droplet.get('status') != 'active'
                or active_tag not in tags or draining_tag in tags):
            continue
        address = private_ip(droplet, vpc)
        matches = [key for key, value in registrations.items()
                   if value.get('privateIp') == address and value.get('nodeId') == key.decode()]
        if len(matches) != 1:
            continue
        node_id = matches[0]
        node_ip = registrations[node_id].get('nodeIp')
        public_ips = [v.get('ip_address') for v in droplet.get('networks', {}).get('v4', [])
                      if v.get('type') == 'public']
        if node_ip not in public_ips:
            continue
        blob = native.get(node_id)
        if blob and serving(node_id, blob, node_ip, now) and health(address):
            result[node_id] = blob
    return result


def verify_idle_media(registrations, native, own_ip, public_ips, now=None, run=None,
                      room_nodes=None, application_fenced=False):
    """Veto an occupied first drain; this is not recording settlement proof.

    NodeStats fields 3..6 are rooms, clients, inbound and outbound tracks. Clients
    can include signaling for a peer's room, which is still live work. Proto3
    omits zero counters. A fresh, identity-bound heartbeat is still required: an
    absent registration is NOT an empty node. Retried drains may have unregistered,
    but only already cleanly stopped containers can take that path.
    A new arrival after this sample is handled by graceful shutdown, never force.
    The legacy room-map/fence arguments remain call-compatible but cannot waive
    client occupancy after the failed peer-continuity qualification.
    """
    nodes = media_containers(run or command)
    states = [node.get('State', {}) for node in nodes.values()]
    if all(state.get('Status') == 'exited' and state.get('ExitCode') == 0
           and state.get('OOMKilled') is False and state.get('Running') is False
           and state.get('Restarting') is False for state in states):
        return
    matches = [(key, value) for key, value in registrations.items()
               if value.get('privateIp') == own_ip]
    if len(matches) != 1:
        raise ValueError('Exact local media registration required for idle observation')
    identity, registration = matches[0]
    node_ip = registration.get('nodeIp')
    blob = native.get(identity)
    # Docker inspection can block: assess freshness after it, not at call entry.
    observed_at = time.time() if now is None else now
    if (registration.get('nodeId') != identity.decode() or node_ip not in public_ips
            or not blob or not serving(identity, blob, node_ip, observed_at)):
        raise ValueError('Fresh local serving identity required before initiating drain')
    stats = protobuf_fields(protobuf_fields(blob).get(4, b''))
    if any(type(stats.get(field, 0)) is not int or stats.get(field, 0) != 0
           for field in (3, 5, 6)):
        raise ValueError('Local media still owns rooms, participants or tracks')
    clients = stats.get(4, 0)
    if type(clients) is not int or clients < 0:
        raise ValueError('Invalid local client counter')
    if clients:
        # September 24 occupied-drain qualification: an empty local room map did
        # not make remote signaling disposable. Graceful exit disconnected four
        # users of a peer room; the native client intentionally requires fresh
        # admission instead of cached-token SDK reconnect. Retain this node until
        # clients finish. A room-map proof/application fence cannot waive this.
        # TODO: relax only after safe signaling migration is implemented and
        # live-qualified with unchanged publication/recording continuity.
        raise ValueError('Active signaling clients still depend on this media node')


# Compare the exact heartbeat/state snapshot again at the atomic claim. Two
# simultaneous watchers cannot both count the same spare server. An old claim
# is removable only after its native registration has gone, never by a timer.
CLAIM = """
local claims = redis.call('SMEMBERS', KEYS[2])
for _, id in ipairs(claims) do
  if redis.call('HEXISTS', KEYS[1], id) == 0 then redis.call('SREM', KEYS[2], id) end
end
local ready = 0
for i = 3, #ARGV, 2 do
  if redis.call('HGET', KEYS[1], ARGV[i]) == ARGV[i+1]
     and redis.call('SISMEMBER', KEYS[2], ARGV[i]) == 0 then ready = ready + 1 end
end
if ready < tonumber(ARGV[2]) then return 0 end
redis.call('SADD', KEYS[2], ARGV[1])
return 1
"""


DRAIN_DROPIN = pathlib.Path('/etc/systemd/system/openvidu.service.d/40-courseultra-drain.conf')
DRAIN_CONDITION = '[Unit]\nConditionPathExists=!/opt/openvidu/.courseultra-draining\n'


def command(args):
    return subprocess.run(args, capture_output=True, text=True, check=True, timeout=30).stdout.strip()


def stable_container(node):
    # Docker mount order is not identity: repeated inspect calls reorder an
    # unchanged stopped recorder. Preserve every mount field and duplicate;
    # only normalize ordering, never hide an actual binding/process change.
    mounts = node.get('Mounts')
    if mounts is not None and (not isinstance(mounts, list) or any(not isinstance(m, dict) for m in mounts)):
        raise ValueError('Container mount inventory unavailable')
    return {**node, **({'Mounts': sorted(mounts, key=lambda m: json.dumps(m, sort_keys=True))}
                      if mounts is not None else {})}


def media_containers(run):
    agents = run(['docker', 'ps', '-a', '--filter', 'label=openvidu-agent=true', '--format', '{{.Names}}']).splitlines()
    names = sorted(set(['openvidu', 'ingress', 'egress'] + agents))
    if any(not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', name) for name in names):
        raise ValueError('Media container names unavailable')
    nodes = json.loads(run(['docker', 'inspect', *names]))
    if (not isinstance(nodes, list) or len(nodes) != len(names)
            or {node.get('Name') for node in nodes} != {'/' + name for name in names}
            or any(not re.fullmatch('[0-9a-f]{64}', node.get('Id', '')) for node in nodes)):
        raise ValueError('Complete media container identities required')
    return {node['Id']: stable_container(node) for node in nodes}


def verify_drain_unit(unit, run):
    if unit.is_symlink() or unit.read_text() != DRAIN_CONDITION:
        raise ValueError('Installed media drain start barrier required')
    loaded = run(['systemctl', 'show', '--property=DropInPaths', '--value', 'openvidu.service']).split()
    if str(unit) not in loaded or run(['systemctl', 'show', '--property=NeedDaemonReload',
                                     '--value', 'openvidu.service']).strip() != 'no':
        raise ValueError('Media drain start barrier is not loaded')


def verify_restart_fence(root=pathlib.Path('/opt/openvidu'), unit=DRAIN_DROPIN, run=command):
    marker = root / '.courseultra-draining'
    info = marker.lstat()
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
            or info.st_mode & 0o022 or marker.read_text() != 'draining\n'):
        raise ValueError('Persistent media drain marker required')
    verify_drain_unit(unit, run)
    nodes = media_containers(run)
    if any(node.get('HostConfig', {}).get('RestartPolicy', {}).get('Name') != 'no' for node in nodes.values()):
        raise ValueError('Media automatic restart is not excluded')
    receipts = root / '.courseultra-drain-signals'
    try:
        info = receipts.lstat()
    except FileNotFoundError:
        return nodes
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o022:
        raise ValueError('Unknown drain signal directory')
    for receipt in receipts.iterdir():
        info = receipt.lstat()
        node = nodes.get(receipt.name)
        started = node.get('State', {}).get('StartedAt') if node else None
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o022
                or not started or receipt.read_text() != started + '\nattempted\nconfirmed\n'):
            raise ValueError('Uncertain shutdown signal or changed process; do not resend')
    return nodes


def fence_restarts(root=pathlib.Path('/opt/openvidu'), unit=DRAIN_DROPIN, run=command):
    """Prevent normal Docker/systemd reboot recovery from undoing a pending drain.

    This never stops live services or clears the barrier. A failed drain retains
    it for retry/operator reconciliation. Privileged manual Compose recreation
    is not authorized by this operation and remains outside this local fence.
    """
    if root.is_symlink() or not root.is_dir() or unit.is_symlink() or unit.read_text() != DRAIN_CONDITION:
        raise ValueError('Media drain barrier installation requires review')
    marker = root / '.courseultra-draining'
    try:
        fd = os.open(marker, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    except FileExistsError:
        info = marker.lstat()
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
                or info.st_mode & 0o022 or marker.read_text() != 'draining\n'):
            raise ValueError('Unknown media drain marker; preserve for review')
    else:
        with os.fdopen(fd, 'w') as stream:
            stream.write('draining\n')
            stream.flush()
            os.fsync(stream.fileno())
        directory = os.open(root, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    run(['systemctl', 'daemon-reload'])
    verify_drain_unit(unit, run)
    before = media_containers(run)
    run(['docker', 'update', '--restart=no', *sorted(before)])
    after = verify_restart_fence(root, unit, run)
    if before.keys() != after.keys():
        raise ValueError('Media containers changed while excluding restart')


def signal_gracefully_once(root=pathlib.Path('/opt/openvidu'), unit=DRAIN_DROPIN, run=command):
    """The second shutdown signal can force LiveKit to stop an occupied room.

    Persist the exact process attempt before sending. A lost acknowledgement or
    changed container/process requires review, never a blind watcher re-signal.
    The existing watcher flock plus exclusive receipt creation excludes duplicates.
    """
    nodes = verify_restart_fence(root, unit, run)
    receipts = root / '.courseultra-drain-signals'
    receipts.mkdir(mode=0o700, exist_ok=True)
    # Persist both a newly-created receipt directory and each request before I/O.
    for directory in (root, receipts):
        fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    for identity, node in sorted(nodes.items()):
        state = node.get('State', {})
        if state.get('Running') is False:
            continue
        started = state.get('StartedAt')
        if (state.get('Running') is not True or state.get('Restarting') is not False
                or not isinstance(started, str) or not re.fullmatch(r'[0-9TZ:.+-]{1,64}', started)):
            raise ValueError('Exact running process identity unavailable')
        receipt = receipts / identity
        try:
            fd = os.open(receipt, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        except FileExistsError:
            verify_restart_fence(root, unit, run)
            continue
        with os.fdopen(fd, 'w') as stream:
            stream.write(started + '\nattempted\n')
            stream.flush()
            os.fsync(stream.fileno())
        directory = os.open(receipts, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
        run(['docker', 'kill', '--signal=SIGQUIT', identity])
        fd = os.open(receipt, os.O_WRONLY | os.O_APPEND | os.O_NOFOLLOW)
        with os.fdopen(fd, 'w') as stream:
            stream.write('confirmed\n')
            stream.flush()
            os.fsync(stream.fileno())
    verify_restart_fence(root, unit, run)


def inspect_recorder():
    result = subprocess.run(['docker', 'inspect', 'egress'], capture_output=True,
                            text=True, check=True, timeout=10)
    nodes = json.loads(result.stdout)
    if not isinstance(nodes, list) or len(nodes) != 1:
        raise ValueError('Recorder identity unavailable')
    return stable_container(nodes[0])


def verify_retired_ipc_observation(observed):
    """Only data-free residues qualify, after a complete no-writer observation.

    A stopped Unix socket is not a recording file. Accepting its inode does not
    authorize deletion of media bytes, including zero-byte regular recovery files.
    """
    if (not isinstance(observed, dict) or not {'issues', 'processes', 'openFiles', 'unixSockets', 'roots', 'bootId',
            'startedAt', 'finishedAt', 'elapsedSeconds', 'complete'}.issubset(observed)
            or set(observed.get('issues', [])) - {'unresolved_file_type'}
            or not observed.get('bootId') or observed.get('processes') or observed.get('openFiles')
            or observed.get('unixSockets') or set(r.get('name') for r in observed.get('roots', [])) != {'tmp', 'backup_storage'}
            or len(observed['roots']) != 2):
        raise ValueError('Complete writer-free recording observation required')
    for root in observed['roots']:
        if not root.get('identity') or not isinstance(root.get('entries'), list):
            raise ValueError('Incomplete recovery storage inventory')
        entries = {entry.get('path'): entry for entry in root['entries']}
        if len(entries) != len(root['entries']) or root['name'] == 'backup_storage' and entries:
            raise ValueError('Backup or ambiguous recording storage remains')
        for path, entry in entries.items():
            if entry.get('kind') == 'directory' and re.fullmatch(r'(NE|EGH)_[A-Za-z0-9]+', path or ''):
                continue
            if (entry.get('kind') == 'special' and entry.get('specialType') == 'socket'
                    and re.fullmatch(r'NE_[A-Za-z0-9]+/service_ipc.sock', path or '')
                    and entries.get(path.split('/')[0], {}).get('kind') == 'directory'):
                continue
            raise ValueError('Recording data or unknown residue remains')


def verify_recording_storage(root=pathlib.Path('/opt/openvidu'), inspect=inspect_recorder, retired_ipc_observation=None):
    """Additional deletion veto, NOT recording-settlement or restart-exclusion proof.

    Clean process exit can leave failed uploads on disk. Inspect the actual stopped
    container's storage binding, not an assumed empty host path. The default path
    rejects every residue. Capacity settlement may supply a separately fenced,
    complete process/storage observation for data-free retired IPC only. Preserved
    archives still hold. This never declares a recording successfully saved.
    Provider finalization and new-work fencing remain separate activation gates.
    """
    root = pathlib.Path(root)
    if not root.is_absolute() or '..' in root.parts:
        raise ValueError('Canonical recording root required')
    storage = root / 'data/egress_data/home/egress'
    node = inspect()
    state = node.get('State', {})
    if (not node.get('Id') or node.get('Name') != '/egress'
            or state.get('Status') != 'exited' or state.get('ExitCode') != 0
            or state.get('Running') is not False or state.get('Restarting') is not False
            or state.get('OOMKilled') is not False):
        raise ValueError('Recorder has not exited cleanly')
    mounts = node.get('Mounts')
    if not isinstance(mounts, list):
        raise ValueError('Recorder storage bindings unavailable')
    relevant = []
    destinations = set()
    for mount in mounts:
        destination = mount.get('Destination')
        if not isinstance(destination, str) or not destination.startswith('/') or destination in destinations:
            raise ValueError('Recorder mount identity ambiguous')
        destinations.add(destination)
        if (destination == '/home/egress' or destination.startswith('/home/egress/')
                or '/home/egress'.startswith(destination.rstrip('/') + '/')):
            relevant.append(mount)
    if (len(relevant) != 1 or relevant[0].get('Type') != 'bind'
            or relevant[0].get('Destination') != '/home/egress'
            or relevant[0].get('Source') != str(storage) or relevant[0].get('RW') is not True):
        raise ValueError('Exact unshadowed recorder storage binding required')

    def real_directory(path):
        for ancestor in (path, *path.parents):
            if not stat.S_ISDIR(ancestor.lstat().st_mode):
                raise ValueError('Unknown or redirected recording directory')

    def empty_directory(path):
        real_directory(path)
        if next(path.iterdir(), None) is not None:
            raise ValueError('Retained recording artifacts require reconciliation')

    def present(path):
        # Path.exists may suppress permission/I/O failures. Only actual absence
        # permits an unguarded installation to omit the optional guard directory.
        try:
            path.lstat()
            return True
        except FileNotFoundError:
            return False

    if retired_ipc_observation is None:
        for name in ('tmp', 'backup_storage'):
            empty_directory(storage / name)
    else:
        verify_retired_ipc_observation(retired_ipc_observation)
        for name in ('tmp', 'backup_storage'):
            real_directory(storage / name)
    barrier = root / 'courseultra-recorder-guard'
    if present(barrier):
        real_directory(barrier)
        lock = barrier / 'start.lock'
        value = lock.lstat()
        if not stat.S_ISREG(value.st_mode) or value.st_size != 0:
            raise ValueError('Unresolved recorder preservation intent')
        archive = barrier / 'preserved'
        if present(archive):
            empty_directory(archive)
    after = inspect()
    if any(stable_container(after).get(key) != stable_container(node).get(key) for key in ('Id', 'State', 'Mounts')):
        raise ValueError('Recorder changed during storage observation')


def settlement_storage_evidence(root=pathlib.Path('/opt/openvidu')):
    """Read-only proof after graceful drain. No files, sockets or directories are removed."""
    import importlib.util
    probe_path = pathlib.Path(__file__).with_name('recorder-storage-probe.py')
    spec = importlib.util.spec_from_file_location('recorder_settlement_probe', probe_path)
    probe = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(probe)
    before = verify_restart_fence(root)
    for node in before.values():
        state = node.get('State', {})
        if (state.get('Status') != 'exited' or state.get('ExitCode') != 0 or state.get('Running') is not False
                or state.get('Restarting') is not False or state.get('OOMKilled') is not False):
            raise ValueError('All media writers must have stopped cleanly')
    observed = probe.observe(root / 'data/egress_data/home/egress')
    verify_recording_storage(root, retired_ipc_observation=observed)
    after = verify_restart_fence(root)
    if before != after or observed['bootId'] != pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip():
        raise ValueError('Stopped recorder incarnation changed')
    # Never persist Docker Config/Env: they can contain provider credentials.
    return {'containers': {key: {field: node.get(field) for field in ('Id', 'Name', 'Image', 'State', 'Mounts')}
                           for key, node in before.items()}, 'storage': observed}


def main():
    parser = argparse.ArgumentParser()
    for arg in ['master-id', 'master-ip', 'vpc', 'active-tag', 'draining-tag']:
        parser.add_argument('--' + arg, required=True)
    parser.add_argument('--minimum', type=int, required=True)
    parser.add_argument('--check-only', action='store_true')
    parser.add_argument('--verify-recording-storage', action='store_true')
    parser.add_argument('--fence-restarts', action='store_true')
    parser.add_argument('--verify-restart-fence', action='store_true')
    parser.add_argument('--signal-graceful', action='store_true')
    parser.add_argument('--require-idle-media', action='store_true')
    parser.add_argument('--capacity-settings')
    args = parser.parse_args()
    if args.check_only and (args.fence_restarts or args.signal_graceful):
        raise ValueError('Read-only check cannot change restart behavior')
    if args.minimum < 1:
        raise ValueError('A positive ready-server floor is required')
    secrets = {}
    for line in pathlib.Path('/opt/openvidu/secrets.env').read_text().splitlines():
        if line.startswith(('REDIS_PASSWORD=', 'MASTER_NODE_ID=', 'MASTER_NODE_PRIVATE_IP=')):
            key, value = line.split('=', 1)
            secrets[key] = shlex.split(value)[0]
    if (secrets.get('MASTER_NODE_ID') != args.master_id
            or secrets.get('MASTER_NODE_PRIVATE_IP') != args.master_ip):
        raise ValueError('Master generation does not match')
    with urllib.request.urlopen('http://169.254.169.254/metadata/v1/id', timeout=2) as response:
        own_id = response.read(64).decode().strip()
    if not own_id.isdecimal():
        raise ValueError('Invalid local Droplet identity')
    command = ['doctl', 'compute', 'droplet', 'list', '--output', 'json']
    droplets = json.loads(subprocess.run(command, capture_output=True, text=True,
                                        check=True, timeout=20).stdout)
    own = [d for d in droplets if str(d['id']) == own_id]
    if len(own) != 1 or args.draining_tag not in own[0].get('tags', []):
        raise ValueError('Local node is not explicitly marked for drain')
    own_ip = private_ip(own[0], args.vpc)
    redis = Redis(args.master_ip, secrets['REDIS_PASSWORD'])
    try:
        pairs = redis.call('HGETALL', 'nodes_openvidu')
        registrations = {pairs[i]: json.loads(pairs[i+1]) for i in range(0, len(pairs), 2)}
        own_nodes = [key for key, value in registrations.items() if value.get('privateIp') == own_ip]
        # A retry after shutdown has no native registration. Use an immutable
        # VM-specific claim in that case; it cannot masquerade as ready capacity.
        if len(own_nodes) > 1:
            raise ValueError('Local media registration is ambiguous')
        own_node = own_nodes[0] if own_nodes else ('droplet-' + own_id).encode()
        pairs = redis.call('HGETALL', 'nodes')
        native = dict(zip(pairs[::2], pairs[1::2]))
        if args.require_idle_media:
            public_ips = [address.get('ip_address') for address in own[0].get('networks', {}).get('v4', [])
                          if address.get('type') == 'public']
            verify_idle_media(registrations, native, own_ip, public_ips,
                              room_nodes=lambda: redis.call('HGETALL', 'room_node_map'),
                              application_fenced=bool(args.capacity_settings))
        if args.capacity_settings and not args.check_only:
            if args.verify_recording_storage:
                import importlib.util
                spec = importlib.util.spec_from_file_location('recorder_settlement',
                    pathlib.Path(__file__).with_name('settle-recordings.py'))
                settlement = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(settlement)
                settlement.settle(args.capacity_settings, sys.modules[__name__])
            # This network check may take seconds. Perform it before sampling and
            # claiming ready peers, never extend their heartbeat freshness window.
            exclude_application_work(args.capacity_settings, own_id, own_nodes,
                                     final_check=args.verify_recording_storage)
        peers = ready_peers(droplets, registrations, native, own_id, args.active_tag,
                            args.draining_tag, args.vpc, time.time())
        # Network probes may take time; never claim capacity using a heartbeat
        # that expired while we checked other nodes.
        peers = {key: blob for key, blob in peers.items()
                 if serving(key, blob, registrations[key]['nodeIp'], time.time())}
        if args.verify_recording_storage:
            if args.capacity_settings:
                settlement_storage_evidence()
            else:
                verify_recording_storage()
            # Docker/filesystem inspection must not extend the readiness sample.
            peers = {key: blob for key, blob in peers.items()
                     if serving(key, blob, registrations[key]['nodeIp'], time.time())}
        if args.verify_restart_fence:
            verify_restart_fence()
            peers = {key: blob for key, blob in peers.items()
                     if serving(key, blob, registrations[key]['nodeIp'], time.time())}
        if args.check_only:
            print(json.dumps({'readyPeers': len(peers), 'minimum': args.minimum,
                              'readOnly': True, 'floorMet': len(peers) >= args.minimum}))
            return len(peers) >= args.minimum
        claim_args = [item for pair in peers.items() for item in pair]
        allowed = redis.call('EVAL', CLAIM, 2, 'nodes',
                             '{nodes}:courseultra:' + args.master_id + ':drain-reservations',
                             own_node, args.minimum, *claim_args) == 1
        if allowed and args.fence_restarts:
            fence_restarts()
        if allowed and args.signal_graceful:
            signal_gracefully_once()
        return allowed
    finally:
        redis.close()


if __name__ == '__main__':
    try:
        allowed = main()
    except Exception:
        # Provider/command error text can contain credentials. A failed probe is
        # a hold, not permission to shut down or to expose its raw response.
        allowed = False
    print('Requested drain checks passed' if allowed else 'Drain held: capacity or recording safety could not be verified')
    raise SystemExit(0 if allowed else 1)
