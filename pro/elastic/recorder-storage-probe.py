"""Bounded read-only Linux recorder evidence. Never authorizes release or deletes files.

Run through the campaign's exact-owned-node SSH wrapper. The caller must bind this
sample to cloud/container/config identity and the complete historical recorder pool;
an empty directory is not evidence that an egress is terminal or its output is safe.
"""
import json
import os
from pathlib import Path
import re
import stat
import time
from datetime import datetime, timezone

STORAGE = Path('/opt/openvidu/data/egress_data/home/egress')
WORKER_NAMES = {'egress', 'tini', 'chrome', 'chromium', 'pulseaudio', 'Xvfb', 'ffmpeg'}


def read_unix_sockets(path, prefixes, bounded):
    """Read only relevant paths; kernel socket IDs are NOT filesystem inode IDs."""
    sockets = {}
    with path.open(encoding='utf-8', errors='surrogateescape') as stream:
        if stream.readline(4096).split() != ['Num', 'RefCount', 'Protocol', 'Flags', 'Type', 'St', 'Inode', 'Path']:
            raise ValueError('Unknown Unix socket table')
        while True:
            bounded()
            line = stream.readline(4096)
            if not line:
                break
            if not line.endswith('\n'):
                raise ValueError('Truncated Unix socket row')
            fields = line.rstrip('\n').split(None, 7)
            if len(fields) < 7:
                raise ValueError('Incomplete Unix socket row')
            inode = int(fields[6])
            for value in fields[1:6]:
                int(value, 16)
            if len(fields) == 8 and fields[7].startswith(prefixes):
                if inode in sockets:
                    raise ValueError('Ambiguous Unix socket identity')
                sockets[inode] = dict(kernelInode=inode, path=fields[7], flags=fields[3],
                                      type=fields[4], state=fields[5])
    return sockets


def observe(storage=STORAGE, proc=Path('/proc'), limit=20000, seconds=10):
    if limit < 1 or seconds <= 0:
        raise ValueError('Positive observation bounds required')
    storage, proc = Path(storage), Path(proc)
    started = time.monotonic()
    result = dict(version=1, startedAt=datetime.now(timezone.utc).isoformat(),
                  roots=[], processes=[], openFiles=[], unixSockets=[], issues=[])
    remaining = limit

    def issue(code):
        if code not in result['issues']:
            result['issues'].append(code)

    def bounded():
        nonlocal remaining
        remaining -= 1
        if remaining < 0 or time.monotonic() - started >= seconds:
            issue('observation_limit')
            raise RuntimeError('observation_limit')

    def identity(value):
        return dict(device=value.st_dev, inode=value.st_ino, bytes=value.st_size,
                    allocatedBytes=value.st_blocks * 512, uid=value.st_uid, gid=value.st_gid,
                    modifiedNs=value.st_mtime_ns, changedNs=value.st_ctime_ns,
                    links=value.st_nlink, mode=stat.S_IMODE(value.st_mode),
                    fileTypeBits=stat.S_IFMT(value.st_mode))

    def open_directory(path):
        # Traverse by descriptors: neither root ancestors nor changing child symlinks
        # may redirect privileged enumeration outside the configured storage tree.
        path = Path(path)
        if not path.is_absolute() or '..' in path.parts:
            raise ValueError('Absolute canonical root required')
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

    def directory(fd, relative, root_device, entries):
        before = os.fstat(fd)
        with os.scandir(fd) as children:
            for child in children:
                bounded()
                value = os.stat(child.name, dir_fd=fd, follow_symlinks=False)
                path = relative + '/' + child.name if relative else child.name
                kind = ('directory' if stat.S_ISDIR(value.st_mode) else
                        'file' if stat.S_ISREG(value.st_mode) else
                        'symlink' if stat.S_ISLNK(value.st_mode) else 'special')
                entry = dict(path=path, kind=kind, **identity(value))
                if kind == 'special':
                    # The live recorder leaves Unix IPC sockets under its recovery
                    # root. Describe the actual inode type, not its name/prefix;
                    # even a socket remains unresolved evidence, never safe cleanup.
                    entry['specialType'] = ('socket' if stat.S_ISSOCK(value.st_mode) else
                                            'fifo' if stat.S_ISFIFO(value.st_mode) else
                                            'characterDevice' if stat.S_ISCHR(value.st_mode) else
                                            'blockDevice' if stat.S_ISBLK(value.st_mode) else 'unknown')
                entries.append(entry)
                if value.st_dev != root_device:
                    issue('nested_mount')
                elif kind == 'directory':
                    nested = os.open(child.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                    try:
                        opened = os.fstat(nested)
                        if (opened.st_dev, opened.st_ino) != (value.st_dev, value.st_ino):
                            issue('directory_changed')
                        else:
                            directory(nested, path, root_device, entries)
                    finally:
                        os.close(nested)
                elif kind != 'file':
                    issue('unresolved_file_type')
        if identity(before) != identity(os.fstat(fd)):
            issue('directory_changed')

    try:
        boot = (proc / 'sys/kernel/random/boot_id').read_text().strip()
        if not boot:
            raise ValueError('Boot identity unavailable')
        result['bootId'] = boot
    except (OSError, ValueError):
        issue('boot_identity_unavailable')

    for name in ('tmp', 'backup_storage'):
        root = dict(name=name, entries=[])
        result['roots'].append(root)
        try:
            bounded()
            fd = open_directory(storage / name)
            try:
                root['identity'] = identity(os.fstat(fd))
                directory(fd, '', root['identity']['device'], root['entries'])
                after = os.stat(storage / name, follow_symlinks=False)
                if identity(after) != root['identity']:
                    issue('root_changed')
            finally:
                os.close(fd)
        except (OSError, ValueError, RuntimeError):
            issue('storage_inventory_incomplete')

    # Kernel fd links can retain storage after unlink. Include both host and container
    # path spellings; mount/config review by the caller must establish these aliases.
    prefixes = tuple(str(parent / name) + '/' for parent in (storage, Path('/home/egress'))
                     for name in ('tmp', 'backup_storage'))
    # Observe once per network namespace, then recheck. Do not use /proc/net/unix
    # alone: it describes the collector's namespace, not necessarily the worker's.
    unix_tables = {}

    def namespaces(base):
        values = tuple(os.readlink(base / 'ns' / name) for name in ('net', 'mnt'))
        if not all(re.fullmatch(kind + r':\[[0-9]+\]', value)
                   for kind, value in zip(('net', 'mnt'), values)):
            raise ValueError('Unknown process namespace')
        return values

    def socket_owners(base, pid, birth, descriptors):
        if not descriptors:
            return False
        try:
            net, mount = namespaces(base)
            if net not in unix_tables:
                rows = read_unix_sockets(base / 'net/unix', prefixes, bounded)
                observed = {inode: dict(row, netNamespace=net, owners=[])
                            for inode, row in rows.items()}
                unix_tables[net] = (base, rows, observed)
                result['unixSockets'].extend(observed.values())
            observed = unix_tables[net][2]
            matched = False
            for descriptor, target, inode in descriptors:
                if inode in observed:
                    matched = True
                    if os.readlink(base / 'fd' / descriptor) != target:
                        issue('socket_descriptor_changed')
                        continue
                    observed[inode]['owners'].append(dict(pid=pid, startedTicks=int(birth),
                                                          fd=descriptor, mountNamespace=mount))
            if (net, mount) != namespaces(base):
                issue('process_namespace_changed')
            return matched
        except (OSError, ValueError):
            issue('unix_socket_inventory_incomplete')
            return False

    process_count = 0
    try:
        with os.scandir(proc) as processes:
            for process in processes:
                if not process.name.isdecimal():
                    continue
                bounded()
                process_count += 1
                pid = int(process.name)
                base = proc / process.name
                try:
                    birth = (base / 'stat').read_text().rpartition(')')[2].split()[19]
                    name = (base / 'comm').read_text().strip()
                    matched = False
                    sockets = []
                    with os.scandir(base / 'fd') as descriptors:
                        for descriptor in descriptors:
                            bounded()
                            target = os.readlink(descriptor.path)
                            if target.startswith(prefixes):
                                matched = True
                                result['openFiles'].append(dict(pid=pid, startedTicks=int(birth),
                                    fd=descriptor.name, target=target, deleted=target.endswith(' (deleted)')))
                            socket = re.fullmatch(r'socket:\[([0-9]+)\]', target)
                            if socket:
                                sockets.append((descriptor.name, target, int(socket[1])))
                    matched = socket_owners(base, pid, birth, sockets) or matched
                    if birth != (base / 'stat').read_text().rpartition(')')[2].split()[19]:
                        issue('process_changed')
                    if matched or name in WORKER_NAMES:
                        result['processes'].append(dict(pid=pid, startedTicks=int(birth), name=name))
                except (OSError, ValueError, IndexError):
                    # Includes disappearing processes: report uncertainty, never silently call
                    # a partial /proc observation complete. A later stable sample can retry.
                    issue('process_inventory_incomplete')
    except (OSError, RuntimeError):
        issue('process_inventory_incomplete')
    for net, (base, rows, observed) in unix_tables.items():
        try:
            if namespaces(base)[0] != net:
                issue('process_namespace_changed')
            if read_unix_sockets(base / 'net/unix', prefixes, bounded) != rows:
                issue('unix_socket_inventory_changed')
        except (OSError, ValueError, RuntimeError):
            issue('unix_socket_inventory_incomplete')
        if any(not row['owners'] for row in observed.values()):
            issue('unix_socket_owner_unobserved')
    if process_count == 0:
        issue('process_inventory_empty')
    try:
        if (proc / 'sys/kernel/random/boot_id').read_text().strip() != result.get('bootId'):
            issue('boot_identity_changed')
    except OSError:
        issue('boot_identity_unavailable')
    result['finishedAt'] = datetime.now(timezone.utc).isoformat()
    result['elapsedSeconds'] = time.monotonic() - started
    # Local syscalls cannot be interrupted by the iteration budget. If the last
    # read took us past the deadline, do not report a complete bounded sample.
    if result['elapsedSeconds'] >= seconds:
        issue('observation_limit')
    result['complete'] = not result['issues']
    return result


if __name__ == '__main__':
    sample = observe()
    print(json.dumps(sample, sort_keys=True))
    raise SystemExit(0 if sample['complete'] else 1)
