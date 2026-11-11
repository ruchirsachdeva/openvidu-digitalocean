"""Existing-watcher recorder-only exclusion. Never signal media or kill handlers."""
import datetime as dt
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import uuid


def load(name):
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), Path(__file__).with_name(name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


capacity = load('recorder-capacity-footprint')
require = capacity.check.require
IMAGE = capacity.check.IMAGE


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def read(root):
    try:
        value = capacity.jobs.settlement.private_json(root / '.courseultra-recorder-isolation.json')
        require(isinstance(value, dict) and type(value.get('version')) is int and value['version'] == 1
                and isinstance(value.get('intent'), dict))
        return value
    except FileNotFoundError:
        return None


def save(root, value):
    capacity.atomic_private(root / '.courseultra-recorder-isolation.json', value)


def marker(intent):
    return b'recorder-isolation-v1\n' + canonical({k: intent[k] for k in ('id', 'generation', 'containerId', 'startedAt')}) + b'\n'


def scope(intent, worker, boot):
    require(worker['Name'] == '/egress' and worker['Image'] == IMAGE
            and intent['generation'] == boot and intent['containerId'] == worker['Id']
            and intent['startedAt'] == worker['State']['StartedAt'])
    uuid.UUID(intent['id'])


def lock_file(root):
    path = root / 'courseultra-recorder-guard/start.lock'
    before = path.lstat()
    require(stat.S_ISREG(before.st_mode) and before.st_uid == os.geteuid()
            and before.st_nlink == 1 and not before.st_mode & 0o022 and before.st_size <= 65536)
    fd = os.open(path, os.O_RDWR | os.O_NOFOLLOW)
    require((before.st_dev, before.st_ino) == (os.fstat(fd).st_dev, os.fstat(fd).st_ino))
    return fd


def verify_fence(root, journal, worker):
    scope(journal['intent'], worker, journal['intent']['generation'])
    require(worker['HostConfig']['RestartPolicy']['Name'] == 'no')
    fd = lock_file(root)
    try:
        require(os.read(fd, 65537) == marker(journal['intent']))
        require(list((os.fstat(fd).st_dev, os.fstat(fd).st_ino)) == journal['lockIdentity'])
    finally:
        os.close(fd)


def post_deregister(logs, service, attempted):
    """Run logs this only after shutdown.Once's deregistration callback returns."""
    parse = lambda v: dt.datetime.fromisoformat(v.replace('Z', '+00:00'))
    for line in logs.splitlines():
        try:
            timestamp, body = line.split(' ', 1)
            if body.startswith('{'):
                item = json.loads(body)
            else:
                fields = body.split('\t')
                require(len(fields) == 6 and fields[1:3] == ['INFO', 'egress'])
                parse(fields[0])
                item = json.loads(fields[5])
                require(isinstance(item, dict) and 'msg' not in item and 'caller' not in item)
                item.update(caller=fields[3], msg=fields[4])
            if (parse(timestamp) >= parse(attempted) and item.get('msg') == 'draining'
                    and item.get('nodeID') == service and not item.get('handlerID') and not item.get('egressID')
                    and re.fullmatch(r'server/server.go:[0-9]+', item.get('caller', ''))):
                return True
        except (ValueError, TypeError, AttributeError):
            continue
    return False


def stopped_clear(root, journal, worker, proc=Path('/proc')):
    state = worker['State']
    require(state['Running'] is False and state['Restarting'] is False and state['Status'] == 'exited'
            and state['ExitCode'] == 0 and state['OOMKilled'] is False)
    history = capacity.jobs.settlement.private_json(root / '.courseultra-capacity-history.json')
    binding = history['binding']
    require(binding['bootId'] == journal['intent']['generation'] and binding['containerId'] == worker['Id']
            and binding['startedAt'] == state['StartedAt'] and binding['image'] == IMAGE
            and binding['mounts'] == sorted(worker['Mounts'], key=lambda m: m['Destination']))
    observed = capacity.jobs.probe.observe(root / 'data/egress_data/home/egress', proc=proc, seconds=6)
    require(observed['bootId'] == binding['bootId'])
    require(not set(observed['issues']) - {'unresolved_file_type'}
            and not observed['openFiles'] and not observed['unixSockets'])
    for process in observed['processes']:
        require(worker['Id'] not in (proc / str(process['pid']) / 'cgroup').read_text())
    roots = {r['name']: r for r in observed['roots']}
    require(set(roots) == {'tmp', 'backup_storage'} and not roots['backup_storage']['entries'])
    require(all(list(capacity.check.identity(r['identity'])) == binding['roots'][name] for name, r in roots.items()))
    service = binding['serviceId']
    handlers = set(history['jobs'].values())
    for entry in roots['tmp']['entries']:
        require((entry['path'] in handlers | {service} and entry['kind'] == 'directory')
                or (entry['path'] == service + '/service_ipc.sock' and entry['fileTypeBits'] == stat.S_IFSOCK))
    previous = journal.get('stoppedSample')
    journal['stoppedSample'] = observed
    save(root, journal)
    if previous is None:
        return False
    parse = lambda v: dt.datetime.fromisoformat(v.replace('Z', '+00:00'))
    require(parse(observed['startedAt']) >= parse(previous['finishedAt']))
    # Keep the first clean observation while waiting; do not stamp it fresh.
    if (parse(observed['startedAt']) - parse(previous['finishedAt'])).total_seconds() < 30:
        journal['stoppedSample'] = previous
        save(root, journal)
        return False
    require(previous['roots'] == observed['roots'])
    return True


def proof(root, worker, boot, admission=None, logs='', proc=Path('/proc'), owner=None):
    journal = read(root)
    if journal is None:
        return None
    intent = journal['intent']
    require(intent['generation'] == boot and intent['containerId'] == worker['Id'])
    if journal.get('restorePlan'):
        preservation = load('preserve-recorder-ipc')
        body = preservation.encode_plan(journal['restorePlan'])
        fd = lock_file(root)
        try:
            require([os.fstat(fd).st_dev, os.fstat(fd).st_ino] == journal['lockIdentity'])
            pending = os.read(fd, 65537)
            require(pending in (marker(intent), body, b''))
        finally:
            os.close(fd)
        if journal.get('restoreAttempted'):
            receipt = capacity.jobs.settlement.private_json(root / 'courseultra-recorder-guard/preserved' / intent['id'] / 'receipt.json')
            require(not pending and canonical(receipt) == canonical(journal['restorePlan']))
    if journal.get('restoreAttempted') and worker['State']['Running'] and worker['State']['StartedAt'] != intent['startedAt']:
        require(intent.get('restoreRequestedAt') and intent.get('restoreNotBefore') and admission and not admission['disabled'] and not admission['terminating'])
        require(dt.datetime.fromisoformat(worker['State']['StartedAt'].replace('Z', '+00:00'))
                > dt.datetime.fromisoformat(intent['restoreRequestedAt'].replace('Z', '+00:00'))
                and dt.datetime.fromisoformat(worker['State']['StartedAt'].replace('Z', '+00:00'))
                >= dt.datetime.fromisoformat(intent['restoreNotBefore'].replace('Z', '+00:00')))
        journal['returned'] = True
        save(root, journal)
        return dict(intentId=intent['id'], excluded=False, storageClear=False, returned=True)
    if intent.get('restoreRequestedAt') and journal.get('restorePlan'):
        require(not worker['State']['Running'] and worker['State']['StartedAt'] == intent['startedAt'])
        return dict(intentId=intent['id'], excluded=False, storageClear=False, returned=False, restoring=True)
    verify_fence(root, journal, worker)
    if worker['State']['Running']:
        if admission is not None:
            require(owner is not None and len(owner) == 2 and all(str(v).isdecimal() for v in owner))
        excluded = bool(journal.get('signalAttempted') and admission and admission['disabled'] and admission['terminating']
                        and not admission['acceptingRequests'] and (journal.get('ackService') == admission['nodeId']
                        and journal.get('ackOwner') == list(owner or ()) or post_deregister(logs, admission['nodeId'], journal['signalAttempted'])))
        if excluded:
            journal.update(ackService=admission['nodeId'], ackOwner=list(owner or ()))
            save(root, journal)
        return dict(intentId=intent['id'], excluded=excluded, storageClear=False, returned=False)
    try:
        clear = stopped_clear(root, journal, worker, proc)
    except (OSError, ValueError, KeyError):
        clear = False
    return dict(intentId=intent['id'], excluded=True, storageClear=clear, returned=False)


def settlement_proof(root, worker, boot, inspect, proc=Path('/proc')):
    journal = read(root)
    require(journal is not None and not journal['intent'].get('restoreRequestedAt'))
    verify_fence(root, journal, worker)
    require(journal['intent']['generation'] == boot and stopped_clear(root, journal, worker, proc))
    after = inspect()
    require(all(after[k] == worker[k] for k in ('Id', 'Image', 'State', 'Mounts')))
    return dict(containers={'recorder': {k: worker[k] for k in ('Id', 'Name', 'Image', 'State', 'Mounts')}},
                storage=journal['stoppedSample'])


def apply_response(result, local, boot, root, inspect, run, request):
    action = result.get('recorderAction')
    observed = local.get('recorderIsolation') or {}
    # RESTORE means owned obligations have cleared. Its backend fence no longer
    # authorizes NODE settlement; that unnecessary request must not block return.
    if (observed.get('excluded') and observed.get('storageClear') and not local['recorderRunning']
            and (action or {}).get('action') != 'RESTORE'):
        identity = dict(nodeId=local['nodeId'], generation=boot, dropletId=local['dropletId'])
        capacity.jobs.settlement.deliver(request, identity,
            lambda: settlement_proof(root, inspect(), boot, inspect), root / '.courseultra-recording-settlement')
    if action:
        require(local.get('recorderIsolationSupported') is True)
        act(action, inspect(), boot, root, inspect, run)


def act(intent, worker, boot, root, inspect, run, restore=None):
    """Only a fresh authenticated fleet response may drive an action."""
    if intent is None:
        return
    require(intent.get('action') in ('EXCLUDE', 'RESTORE')
            and (intent['action'] == 'RESTORE') == bool(intent.get('restoreRequestedAt')))
    journal = read(root)
    if journal is not None and journal['intent']['id'] != intent['id']:
        require(journal.get('returned') is True)
        journal = None
    if journal is None:
        scope(intent, worker, boot)
        require(worker['HostConfig']['RestartPolicy']['Name'] in ('no', 'always', 'unless-stopped'))
        journal = dict(version=1, intent=intent, originalRestart=worker['HostConfig']['RestartPolicy'], signalAttempted=None)
        fd = lock_file(root)
        try:
            require(os.read(fd, 65537) == b'')
            if worker['State']['Running']:
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    pass
                else:
                    raise ValueError('Running recorder does not hold its lifetime startup lock')
            journal['lockIdentity'] = [os.fstat(fd).st_dev, os.fstat(fd).st_ino]
            save(root, journal)
            # The live guarded launch owns flock for its lifetime. Root writes
            # durable intent to the SAME inode without waiting for that lifetime.
            # A competing guarded launch cannot acquire flock until it then sees
            # this nonempty intent. No inode replacement/unlink is allowed.
            os.lseek(fd, 0, os.SEEK_SET)
            os.write(fd, marker(intent))
            os.fsync(fd)
        finally:
            os.close(fd)
    # Recover a crash after journal publication and before writing the barrier.
    # Only an exact empty original inode is resumable; partial bytes stay held.
    fd = lock_file(root)
    try:
        current = os.read(fd, 65537)
        if not current and not journal.get('signalAttempted') and not journal.get('restorePlan'):
            actual = inspect()
            scope(intent, actual, boot)
            if actual['State']['Running']:
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    pass
                else:
                    raise ValueError('Lost lifetime startup lock')
            require([os.fstat(fd).st_dev, os.fstat(fd).st_ino] == journal['lockIdentity'])
            os.lseek(fd, 0, os.SEEK_SET)
            os.write(fd, marker(intent))
            os.fsync(fd)
            current = marker(intent)
        if not journal.get('restorePlan'):
            require(current == marker(journal['intent']))
            # A crash can leave complete visible bytes before their previous fsync.
            # Re-establish durability before changing restart policy or signaling.
            os.fsync(fd)
    finally:
        os.close(fd)
    if intent.get('action') == 'RESTORE':
        journal['intent'] = intent
        save(root, journal)
        if dt.datetime.now(dt.timezone.utc) < dt.datetime.fromisoformat(intent['restoreNotBefore'].replace('Z', '+00:00')):
            return
        worker = inspect()
        if worker['State']['StartedAt'] != intent['startedAt']:
            return  # Observe the actual new incarnation; never drain/restart it again.
        if not journal.get('restorePlan'):
            verify_fence(root, journal, worker)
            require(stopped_clear(root, journal, worker))
        (restore or (lambda j, w: restore_recorder(root, j, w, inspect, run)))(journal, worker)
        return
    worker = inspect()
    scope(intent, worker, boot)
    run(['docker', 'update', '--restart=no', worker['Id']])
    worker = inspect()
    verify_fence(root, journal, worker)
    if worker['State']['Running'] and not journal.get('signalAttempted'):
        journal['signalAttempted'] = dt.datetime.now(dt.timezone.utc).isoformat()
        save(root, journal)
        run(['docker', 'kill', '--signal=SIGQUIT', worker['Id']])
    # Lost acknowledgement is intentionally not retried or promoted to proof.


def restore_recorder(root, journal, worker, inspect, run, proc=Path('/proc')):
    """Move only exact stopped IPC residue with the existing preservation primitive."""
    preservation = load('preserve-recorder-ipc')
    intent = journal['intent']
    scope(intent, worker, intent['generation'])
    require(not worker['State']['Running'])
    history = capacity.jobs.settlement.private_json(root / '.courseultra-capacity-history.json')
    binding = history['binding']
    if not journal.get('restorePlan'):
        artifacts = []
        tmp = root / 'data/egress_data/home/egress/tmp'
        reverse = {handler: job for job, handler in history['jobs'].items()}
        for path in sorted(tmp.iterdir()):
            service = path.name == binding['serviceId']
            require(service or path.name in reverse)
            artifacts.append(dict(name=path.name, recordingId=None if service else reverse[path.name],
                identity=preservation.identity(path.lstat()),
                socket=preservation.identity((path / 'service_ipc.sock').lstat()) if service else None))
        plan = dict(version=1, operationId=intent['id'], binding=dict(bootId=intent['generation'],
            containerId=worker['Id'], imageDigest=IMAGE,
            configSha256=hashlib.sha256((root / 'courseultra-recorder-guard/egress.yaml').read_bytes()).hexdigest(),
            serviceNodeId=binding['serviceId'], startedTicks=int(binding['owner'][1]),
            evidenceSha256=hashlib.sha256(canonical(journal['stoppedSample'])).hexdigest()), artifacts=artifacts)
        preservation.encode_plan(plan)
        journal['restorePlan'] = plan
        save(root, journal)
    plan = journal['restorePlan']
    body = preservation.encode_plan(plan)
    fd = lock_file(root)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        require([os.fstat(fd).st_dev, os.fstat(fd).st_ino] == journal['lockIdentity'])
        pending = os.read(fd, 65537)
        require(pending in (marker(intent), body, b''))
        receipt = root / 'courseultra-recorder-guard/preserved' / intent['id'] / 'receipt.json'
        if pending == marker(intent) or not pending and not receipt.exists():
            os.lseek(fd, 0, os.SEEK_SET)
            os.ftruncate(fd, 0)
            # Root still owns flock. A partial plan is nonempty and blocks launch;
            # after a crash only this exact persisted plan can resume preservation.
            os.write(fd, body)
            os.fsync(fd)
    finally:
        os.close(fd)
    def verify(_):
        actual = inspect()
        scope(intent, actual, intent['generation'])
        state = actual['State']
        require(not state['Running'] and not state['Restarting'] and state['ExitCode'] == 0 and not state['OOMKilled'])
        observed = capacity.jobs.probe.observe(root / 'data/egress_data/home/egress', proc=proc, seconds=6)
        require(observed['bootId'] == intent['generation']
                and {r['name']: list(capacity.check.identity(r['identity'])) for r in observed['roots']} == binding['roots']
                and sorted(actual['Mounts'], key=lambda m: m['Destination']) == binding['mounts'])
        require(not set(observed['issues']) - {'unresolved_file_type'} and not observed['openFiles'] and not observed['unixSockets'])
        for process in observed['processes']:
            require(worker['Id'] not in (proc / str(process['pid']) / 'cgroup').read_text())
    preservation.preserve(root / 'data/egress_data/home/egress', root / 'courseultra-recorder-guard', plan, verify)
    # Durable preservation and backend expiry barrier precede every reopening.
    # No Compose/systemd restart and no timeout/kill fallback are permitted.
    journal['restoreAttempted'] = dt.datetime.now(dt.timezone.utc).isoformat()
    save(root, journal)
    policy = journal['originalRestart']
    require(policy['Name'] in ('no', 'always', 'unless-stopped'))
    run(['docker', 'update', '--restart=' + policy['Name'], worker['Id']])
    run(['docker', 'start', worker['Id']])
