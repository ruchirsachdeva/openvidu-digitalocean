"""Stopped-service preservation primitive for the existing qualification owner.

Deliberately no operational CLI or automatic recovery loop. The caller MUST supply
a fresh exclusion/settlement verifier, including operator control, exact historical
NE/EGH/EG ownership, retained outputs, current boot/container/mount provenance and
absence of writers. Neither a manifest nor flock alone establishes those facts.
This module never stops/starts a service, releases capacity, or deletes artifacts.
"""
import ctypes
import fcntl
import json
import os
from pathlib import Path
import re
import stat
import sys
import uuid

MAX_BYTES = 65536
MAX_ARTIFACTS = 64
MAX_OPERATIONS = 32


def identity(value):
    # Rename changes ctime, so it cannot be a stable crash/retry identity. These
    # candidates contain no regular-file data: exact inode/type/owner and child
    # sets are revalidated instead, under caller-established writer exclusion.
    return dict(device=value.st_dev, inode=value.st_ino, mode=value.st_mode,
                uid=value.st_uid, gid=value.st_gid, links=value.st_nlink)


def encode_plan(plan):
    if set(plan) != {'version', 'operationId', 'binding', 'artifacts'} or plan['version'] != 1:
        raise ValueError('Unknown preservation contract')
    if str(uuid.UUID(plan['operationId'])) != plan['operationId']:
        raise ValueError('Canonical operation identity required')
    binding = plan['binding']
    if set(binding) != {'bootId', 'containerId', 'imageDigest', 'configSha256',
                        'serviceNodeId', 'startedTicks', 'evidenceSha256'}:
        raise ValueError('Exact provenance required')
    uuid.UUID(binding['bootId'])
    for key in ('containerId', 'configSha256', 'evidenceSha256'):
        if not re.fullmatch('[0-9a-f]{64}', binding[key]):
            raise ValueError('Invalid provenance identity')
    if not re.fullmatch('sha256:[0-9a-f]{64}', binding['imageDigest']):
        raise ValueError('Pinned image identity required')
    if type(binding['startedTicks']) is not int or binding['startedTicks'] <= 0:
        raise ValueError('Prior process birth required')
    if not re.fullmatch('NE_[A-Za-z0-9]+', binding['serviceNodeId']):
        raise ValueError('Explicit service identity required')
    artifacts = plan['artifacts']
    if not isinstance(artifacts, list) or not 1 <= len(artifacts) <= MAX_ARTIFACTS:
        raise ValueError('Bounded exact artifact list required')
    names = set()
    for artifact in artifacts:
        if set(artifact) != {'name', 'recordingId', 'identity', 'socket'} or artifact['name'] in names:
            raise ValueError('Ambiguous artifact')
        name = artifact['name']
        names.add(name)
        if name == binding['serviceNodeId']:
            if artifact['recordingId'] is not None or artifact['socket'] is None:
                raise ValueError('Exact service socket required')
        elif not (re.fullmatch('EGH_[A-Za-z0-9]+', name)
                  and re.fullmatch('EG_[A-Za-z0-9]+', artifact['recordingId'] or '')
                  and artifact['socket'] is None):
            raise ValueError('Explicit retired handler-to-recording identity required')
        for value, kind in ((artifact['identity'], stat.S_IFDIR), (artifact['socket'], stat.S_IFSOCK)):
            if value is None:
                continue
            if (set(value) != {'device', 'inode', 'mode', 'uid', 'gid', 'links'}
                    or any(type(number) is not int or number < 0 for number in value.values())
                    or stat.S_IFMT(value['mode']) != kind or value['mode'] & 0o022
                    or value['inode'] == 0 or value['links'] == 0
                    or (kind == stat.S_IFSOCK and value['links'] != 1)):
                raise ValueError('Unsafe artifact identity')
    if binding['serviceNodeId'] not in names:
        raise ValueError('Service generation must accompany handler residue')
    body = json.dumps(plan, sort_keys=True, separators=(',', ':')).encode() + b'\n'
    if len(body) > MAX_BYTES:
        raise ValueError('Preservation intent exceeds bound')
    return body


def open_directory(path):
    path = Path(path)
    if not path.is_absolute() or '..' in path.parts:
        raise ValueError('Canonical absolute directory required')
    fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in path.parts[1:]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        return fd
    except BaseException:
        os.close(fd)
        raise


def owned(value):
    if value.st_uid != os.geteuid() or value.st_mode & 0o022:
        raise ValueError('Caller-owned non-writable control path required')


def names(fd):
    values = set()
    with os.scandir(fd) as entries:
        for entry in entries:
            values.add(entry.name)
            if len(values) > MAX_ARTIFACTS + 1:
                raise ValueError('Inventory exceeds preservation bound')
    return values


def artifact_matches(parent, artifact):
    value = os.stat(artifact['name'], dir_fd=parent, follow_symlinks=False)
    if identity(value) != artifact['identity']:
        raise ValueError('Artifact identity changed')
    child = os.open(artifact['name'], os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
    try:
        if identity(os.fstat(child)) != artifact['identity']:
            raise ValueError('Artifact changed during open')
        expected = {'service_ipc.sock'} if artifact['socket'] else set()
        if names(child) != expected:
            raise ValueError('Unknown artifact contents')
        if expected and identity(os.stat('service_ipc.sock', dir_fd=child, follow_symlinks=False)) != artifact['socket']:
            raise ValueError('Socket filesystem identity changed')
    finally:
        os.close(child)


def rename_noreplace(source_fd, name, destination_fd):
    if sys.platform != 'linux':
        raise RuntimeError('Preservation requires Linux renameat2')
    libc = ctypes.CDLL(None, use_errno=True)
    rename = libc.renameat2
    rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    rename.restype = ctypes.c_int
    if rename(source_fd, os.fsencode(name), destination_fd, os.fsencode(name), 1):
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error))


def write_all(fd, body):
    while body:
        count = os.write(fd, body)
        if count <= 0:
            raise OSError('Incomplete durable write')
        body = body[count:]


def preserve(storage, control, plan, verify_exclusion_and_settlement):
    """Preserve one reviewed plan; verifier raises on stale/unknown external facts.

    The verifier is mandatory and called under the lock before intent and each
    mutation phase. No adapter exists here that can manufacture that authority.
    Partial/invalid intent remains held for investigation, never reset on retry.
    """
    body = encode_plan(plan)
    plan = json.loads(body)
    if not callable(verify_exclusion_and_settlement):
        raise ValueError('Authoritative stopped-service verifier required')
    storage, control = Path(storage), Path(control)
    if storage == control or storage in control.parents or control in storage.parents:
        raise ValueError('Control must be separate from vendor recovery storage')
    descriptors = []
    tracked = []
    def retain(fd):
        descriptors.append(fd)
        return fd
    try:
        control_fd = retain(open_directory(control))
        owned(os.fstat(control_fd))
        tmp = retain(open_directory(storage / 'tmp'))
        backup = retain(open_directory(storage / 'backup_storage'))
        before_lock = os.stat('start.lock', dir_fd=control_fd, follow_symlinks=False)
        if not stat.S_ISREG(before_lock.st_mode):
            raise ValueError('Regular startup lock required')
        lock = retain(os.open('start.lock', os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=control_fd))
        lock_stat = os.fstat(lock)
        owned(lock_stat)
        if (identity(before_lock) != identity(lock_stat) or not stat.S_ISREG(lock_stat.st_mode)
                or lock_stat.st_nlink != 1 or lock_stat.st_size > MAX_BYTES):
            raise ValueError('Invalid durable startup lock')
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        def verify():
            if verify_exclusion_and_settlement(json.loads(body)) is not None:
                raise ValueError('Verifier must raise on uncertainty, not return a boolean')
            if identity(os.stat('start.lock', dir_fd=control_fd, follow_symlinks=False)) != identity(lock_stat):
                raise ValueError('Startup lock replaced')
            for path, fd in ((storage / 'tmp', tmp), (storage / 'backup_storage', backup), (control, control_fd)):
                current = open_directory(path)
                try:
                    if identity(os.fstat(current)) != identity(os.fstat(fd)):
                        raise ValueError('Recovery root replaced')
                finally:
                    os.close(current)
            for parent, name, opened in tracked:
                if identity(os.stat(name, dir_fd=parent, follow_symlinks=False)) != identity(os.fstat(opened)):
                    raise ValueError('Preservation destination replaced')
        verify()
        if names(backup):
            raise ValueError('Recording backup obligations remain')
        pending = os.read(lock, MAX_BYTES + 1)
        if pending and pending != body:
            raise ValueError('Different or partial preservation intent; hold')
        # Preserve the intent in the SAME inode mounted by every guard. A partial
        # write is deliberately nonempty and blocks startup after process/host loss.
        replay = not pending and not names(tmp)
        if not pending and not replay:
            try:
                existing = os.open('preserved', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=control_fd)
            except FileNotFoundError:
                existing = None
            if existing is not None:
                try:
                    owned(os.fstat(existing))
                    if plan['operationId'] in names(existing):
                        raise ValueError('Destination already exists for new intent')
                finally:
                    os.close(existing)
            if names(tmp) != {item['name'] for item in plan['artifacts']}:
                raise ValueError('New intent must match complete current residue')
            for item in plan['artifacts']:
                artifact_matches(tmp, item)
            write_all(lock, body)
        if not replay:
            # A complete visible intent may have survived process loss BEFORE its
            # previous fsync. Establish durability again before creating/moving.
            os.fsync(lock)
            try:
                os.mkdir('preserved', 0o700, dir_fd=control_fd)
            except FileExistsError:
                pass
            os.fsync(control_fd)
        archive = retain(os.open('preserved', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=control_fd))
        owned(os.fstat(archive))
        tracked.append((control_fd, 'preserved', archive))
        operation = plan['operationId']
        if operation not in names(archive) and len(names(archive)) >= MAX_OPERATIONS:
            raise ValueError('Preserved operation bound reached; operator review required')
        if not replay:
            try:
                os.mkdir(operation, 0o700, dir_fd=archive)
            except FileExistsError:
                if not pending:
                    raise ValueError('Destination already exists for new intent')
            os.fsync(archive)
        destination = retain(os.open(operation, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=archive))
        owned(os.fstat(destination))
        tracked.append((archive, operation, destination))
        if os.fstat(tmp).st_dev != os.fstat(destination).st_dev:
            raise ValueError('Preservation must remain on the same filesystem')
        def check_partition():
            source_names, target_names = names(tmp), names(destination) - {'receipt.json'}
            expected = {item['name'] for item in plan['artifacts']}
            if source_names & target_names or source_names | target_names != expected or names(backup):
                raise ValueError('Ambiguous move, unknown residue or backup obligation')
            for item in plan['artifacts']:
                artifact_matches(tmp if item['name'] in source_names else destination, item)
                if item['identity']['device'] != os.fstat(tmp).st_dev:
                    raise ValueError('Nested mount is not preservable')
            return source_names
        check_partition()
        if replay:
            before = os.stat('receipt.json', dir_fd=destination, follow_symlinks=False)
            if not stat.S_ISREG(before.st_mode):
                raise ValueError('Regular preservation receipt required')
            receipt = retain(os.open('receipt.json', os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=destination))
            value = os.fstat(receipt)
            owned(value)
            if (identity(before) != identity(value) or not stat.S_ISREG(value.st_mode) or value.st_nlink != 1
                    or value.st_size != len(body) or os.read(receipt, MAX_BYTES + 1) != body):
                raise ValueError('Completed receipt unavailable')
            # Reconcile a prior failure flushing final truncation; visibility of
            # an empty inode alone does not make the cleared intent durable.
            os.fsync(lock)
            return dict(operationId=operation, preserved=len(plan['artifacts']), receiptDurable=True, replayed=True)
        for item in plan['artifacts']:
            verify()
            if item['name'] in check_partition():
                rename_noreplace(tmp, item['name'], destination)
                os.fsync(tmp)
                os.fsync(destination)
        verify()
        if check_partition():
            raise ValueError('Incomplete preservation')
        # A resumed rename may have happened before its prior parent fsyncs.
        # Flush both parents even when every artifact is already at destination.
        os.fsync(tmp)
        os.fsync(destination)
        # Resume only an exact prefix of our deterministic receipt, after checking
        # every archived inode again. Never replace an existing receipt or artifact.
        try:
            receipt = retain(os.open('receipt.json', os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=destination))
        except FileExistsError:
            before = os.stat('receipt.json', dir_fd=destination, follow_symlinks=False)
            if not stat.S_ISREG(before.st_mode):
                raise ValueError('Regular preservation receipt required')
            receipt = retain(os.open('receipt.json', os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=destination))
            if identity(before) != identity(os.fstat(receipt)):
                raise ValueError('Receipt replaced')
        value = os.fstat(receipt)
        owned(value)
        if not stat.S_ISREG(value.st_mode) or value.st_nlink != 1 or value.st_size > len(body):
            raise ValueError('Unsafe preservation receipt')
        previous = os.read(receipt, MAX_BYTES + 1)
        if not body.startswith(previous):
            raise ValueError('Different preservation receipt')
        write_all(receipt, body[len(previous):])
        os.fsync(receipt)
        os.fsync(destination)
        tracked.append((destination, 'receipt.json', receipt))
        verify()
        if check_partition():
            raise ValueError('Source residue reappeared before commit')
        os.lseek(receipt, 0, os.SEEK_SET)
        if identity(os.fstat(receipt)) != identity(value) or os.read(receipt, MAX_BYTES + 1) != body:
            raise ValueError('Durable receipt changed before commit')
        # This is the commit point. If the following fsync fails, the receipt and
        # preserved data are durable but clearing the intent has uncertain crash
        # durability. Caller must keep services stopped and reconcile, not restart
        # on an exception or overwrite the journal with a fabricated rollback.
        os.ftruncate(lock, 0)
        os.fsync(lock)
        return dict(operationId=operation, preserved=len(plan['artifacts']), receiptDurable=True)
    finally:
        for fd in reversed(descriptors):
            os.close(fd)


if __name__ == '__main__':
    raise SystemExit('No standalone recovery authority: use the reviewed host lifecycle owner')
