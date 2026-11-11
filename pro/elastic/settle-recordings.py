"""Successful-recording settlement after an already fenced, clean media drain.

No stop/start/delete operation is performed here. Unknown output or real recovery
data retains the server. Receipts are durable before HTTP delivery so an uncertain
response retries the same evidence rather than inventing a new timestamp.
The receipt encoder is also reused by the separately verified JOB collector;
this module's node observation/delivery entry point still requires clean drain.
"""
import datetime as dt
import base64
import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile
import time
import urllib.parse
import urllib.request

IMAGE = 'sha256:01a31780783080259b7f218f624e654dc30572be5b5f7999123ac0d98c259475'
FIELDS = ('runtimeId', 'generation', 'nativeGeneration', 'creationAttemptId',
          'recordingAttemptId', 'partId', 'roomSid', 'egressId', 'assetId',
          'nodeId', 'nodeGeneration', 'dropletId')


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def private_json(path, published=False):
    value = path.lstat()
    if (not stat.S_ISREG(value.st_mode) or value.st_uid != os.geteuid()
            or value.st_mode & 0o077 or value.st_nlink not in ((1, 2) if published else (1,))
            or value.st_size > 4 * 1024 * 1024):
        raise ValueError('Private bounded receipt required')
    return json.loads(path.read_bytes())


def recorder_binding(proof):
    nodes = [v for v in proof['containers'].values() if v['Name'] == '/egress']
    if len(nodes) != 1 or nodes[0]['Image'] != IMAGE:
        raise ValueError('Pinned recorder required')
    return {'boot': proof['storage']['bootId'], 'recorder': nodes[0]}


def receipt(folder, candidate, proof):
    preparation = candidate.get('preparationOnly') is True
    if (preparation and candidate.get('assetId') is not None
            or any(key not in candidate or candidate[key] is None
                   for key in FIELDS if not (preparation and key == 'assetId'))):
        raise ValueError('Exact managed recording identity required')
    scope = {key: candidate.get(key) for key in FIELDS}
    if preparation:
        scope['preparationOnly'] = True
    binding = recorder_binding(proof)
    if binding['boot'] != scope['nodeGeneration']:
        raise ValueError('Recording boot changed')
    folder.mkdir(mode=0o700, exist_ok=True)
    info = folder.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o077:
        raise ValueError('Private settlement directory required')
    job = proof.get('kind') == 'JOB'
    path = folder / (('job-' if job else '') + hashlib.sha256(canonical(scope)).hexdigest() + '.json')
    try:
        # A crash after link publication but before removing the temporary name
        # can leave two links to the same private immutable metadata. Accept that
        # publication state; never rewrite it or relax credential-file checks.
        saved = private_json(path, published=True)
    except FileNotFoundError:
        evidence = {'version': 1, 'scope': scope, 'binding': binding, 'observation': proof['job'] if job else proof,
                    'verifiedAt': dt.datetime.now(dt.timezone.utc).isoformat()}
        body = canonical(evidence)
        if len(body) > 65536:
            raise ValueError('Settlement proof exceeds budget')
        # Atomic no-replace publication; a crash never exposes a partial receipt.
        fd, temporary = tempfile.mkstemp(prefix='.settlement-', dir=folder)
        try:
            with os.fdopen(fd, 'wb') as stream:
                stream.write(body)
                stream.flush()
                os.fsync(stream.fileno())
            try:
                os.link(temporary, path, follow_symlinks=False)
            except FileExistsError:
                pass
        finally:
            os.unlink(temporary)
        directory = os.open(folder, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
        saved = private_json(path, published=True)
    if saved.get('version') != 1 or saved.get('scope') != scope or saved.get('binding') != binding:
        raise ValueError('Settlement receipt incarnation changed')
    body = canonical(saved)
    if len(body) > 65536:
        raise ValueError('Settlement proof exceeds durable receipt budget')
    # Retain the attestation in the backend receipt, not only on a VM about to be
    # removed. The digest detects corruption; the machine credential authenticates it.
    return dict(scope, storageReceipt=('job-storage-v1:' if job else 'node-storage-v1:') + hashlib.sha256(body).hexdigest() + ':'
                + base64.urlsafe_b64encode(body).decode(),
                storageVerifiedAt=saved['verifiedAt'])


def deliver(request, identity, observe, folder):
    deadline = time.monotonic() + 45
    query = urllib.parse.urlencode(identity)
    candidates = request('GET', 'settlement-candidates?' + query, None)
    if not isinstance(candidates, list) or len(candidates) > 100:
        raise ValueError('Bounded settlement candidates required')
    sent = 0
    for candidate in candidates:
        if time.monotonic() >= deadline:
            raise ValueError('Settlement pass budget exhausted; retry retained work')
        if (not isinstance(candidate, dict) or candidate.get('nodeId') != identity['nodeId']
                or candidate.get('nodeGeneration') != identity['generation']
                or candidate.get('dropletId') != identity['dropletId']):
            raise ValueError('Candidate belongs to another recorder')
        proof = observe()
        body = receipt(folder, candidate, proof)
        # Receipt creation/HTTP work must not conceal a container restart or new writer.
        if recorder_binding(observe()) != recorder_binding(proof):
            raise ValueError('Recorder changed before settlement')
        if time.monotonic() >= deadline:
            raise ValueError('Settlement evidence budget exhausted')
        request('POST', 'settled', body)
        sent += 1
    return sent


def settle(settings_path, guard, root=Path('/opt/openvidu')):
    if os.geteuid() != 0:
        raise ValueError('Privileged node observation required')
    settings = private_json(Path(settings_path))
    identity = private_json(root / '.courseultra-drain-capacity-identity.json')
    boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    if set(identity) != {'nodeId', 'generation', 'dropletId'} or identity['generation'] != boot:
        raise ValueError('Exact persisted drain identity required')
    url, token = settings.get('url'), settings.get('token')
    parsed = urllib.parse.urlparse(url if isinstance(url, str) else '')
    if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password
            or parsed.query or parsed.fragment or not isinstance(token, str) or not token):
        raise ValueError('Capacity authority is not configured')
    opener = urllib.request.build_opener(guard.NoCapacityRedirects())

    def request(method, path, body):
        req = urllib.request.Request(url.rstrip('/') + '/webhooks/openvidu/capacity/' + path,
            data=canonical(body) if body is not None else None, method=method,
            headers={'X-Capacity-Token': token, 'Content-Type': 'application/json'})
        with opener.open(req, timeout=10) as response:
            data = response.read(4 * 1024 * 1024 + 1)
            if response.status != 200 or len(data) > 4 * 1024 * 1024:
                raise ValueError('Settlement response unavailable')
            return json.loads(data) if data else None

    return deliver(request, identity, lambda: guard.settlement_storage_evidence(root),
                   root / '.courseultra-recording-settlement')
