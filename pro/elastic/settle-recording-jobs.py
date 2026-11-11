"""Bounded, non-destructive recording settlement from the location watcher."""
# Never stop writers, remove data or change provider jobs. Ordinary recording
# settlement still requires active provenance; only unadmitted preparations may
# use repeated whole-recorder idle proof when that provenance was missed.
import datetime as dt
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import time
import urllib.parse


def load(name):
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), Path(__file__).with_name(name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


check = load('recording-job-observation')
settlement = load('settle-recordings')
probe = load('recorder-storage-probe')


def save_once(folder, name, value):
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = folder.lstat()
    if folder.is_symlink() or info.st_uid != os.geteuid() or info.st_mode & 0o077:
        raise ValueError('Private job evidence directory required')
    body = settlement.canonical(value)
    if len(body) > 4 * 1024 * 1024:
        raise ValueError('Bounded job evidence required')
    path = folder / (name + '.json')
    fd, temporary = tempfile.mkstemp(prefix='.job-', dir=folder)
    try:
        with os.fdopen(fd, 'wb') as out:
            out.write(body)
            out.flush()
            os.fsync(out.fileno())
        try:
            os.link(temporary, path, follow_symlinks=False)
        except FileExistsError:
            pass
        directory = os.open(folder, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        os.unlink(temporary)
    return settlement.private_json(path, published=True)


def capture(inspect, jobs, service, proc=Path('/proc')):
    before = inspect()
    observation = probe.observe(seconds=6)
    processes = []
    # Include every process in this recorder, not only the probe's named workers.
    # Parent identities let unrelated handlers keep running without hiding a
    # detached or unknown writer behind a familiar process name.
    deadline = time.monotonic() + 3
    for entry in proc.iterdir():
        if not entry.name.isdecimal():
            continue
        if time.monotonic() > deadline:
            raise ValueError('Process provenance budget exhausted')
        try:
            group = (entry / 'cgroup').read_text()
        except FileNotFoundError:
            raise ValueError('Process inventory changed')
        if group != '0::/system.slice/docker-' + before['Id'] + '.scope\n':
            continue
        fields = (entry / 'stat').read_text().rpartition(')')[2].split()
        birth = int(fields[19])
        if fields[0] == 'Z':
            # Reaped-later Chrome children have no mount namespace. A proven
            # zombie cannot execute or retain open files; do not confuse it with
            # an unobserved live writer. PID reuse or any uncertainty still holds.
            if any((entry / 'fd').iterdir()):
                raise ValueError('Zombie still has file descriptors')
            # A dead thread-group leader can still have live sibling threads.
            if {task.name for task in (entry / 'task').iterdir()} != {entry.name}:
                raise ValueError('Zombie leader still has other threads')
            rechecked = (entry / 'stat').read_text().rpartition(')')[2].split()
            if rechecked[0] != 'Z' or int(rechecked[19]) != birth:
                raise ValueError('Zombie process identity changed')
            continue
        processes.append(dict(pid=int(entry.name), startedTicks=birth, parentPid=int(fields[1]),
            name=(entry / 'comm').read_text().strip(), cgroup=group,
            sameRecorderContainer=True,
            birthRechecked=int((entry / 'stat').read_text().rpartition(')')[2].split()[19]) == birth,
            mountNamespace=os.readlink(entry / 'ns/mnt')))
    after = inspect()
    for field in ('Id', 'Image', 'State', 'Mounts'):
        left, right = before[field], after[field]
        if field == 'Mounts':
            left, right = sorted(left, key=lambda m: m['Destination']), sorted(right, key=lambda m: m['Destination'])
        if left != right:
            raise ValueError('Recorder changed during observation')
    sample = dict(recorderServiceId=service, recorder={k: before[k] for k in ('Id', 'Image', 'State', 'Mounts')},
        observation=observation, processProvenance=processes,
        jobMapping=[dict(nodeID=service, handlerID=handler, egressID=job) for job, handler in jobs.items()])
    check.snapshot(sample)
    return sample


def active_owner(sample, job):
    recorder, observed, roots, entries, processes = check.snapshot(sample)
    mappings = {(r['nodeID'], r['handlerID']) for r in sample['jobMapping'] if r['egressID'] == job}
    check.require(len(mappings) == 1)
    service, handler = next(iter(mappings))
    check.require(entries[job]['kind'] == entries[handler]['kind'] == 'directory')
    main = check.owner(observed, processes, '/home/egress/tmp/' + service + '/service_ipc.sock', recorder['Id'])
    worker = check.owner(observed, processes, '/home/egress/tmp/' + handler + '/handler_ipc.sock', recorder['Id'])
    check.require(main != worker)
    return main, worker


def complete_proof(active, current, candidate):
    result = check.compare(active, current, candidate['egressId'])
    recorder, observed, roots, entries, processes = check.snapshot(current)
    old_processes = {check.process_id(p): p for p in active['processProvenance']}
    rows = {(r['egressID'], r['handlerID'], r['nodeID']) for r in current['jobMapping'] if r.get('handlerID')}
    mappings = {job: handler for job, handler, _ in rows}
    check.require(len(mappings) == len(rows) == len(set(mappings.values())))
    services = {service for _, _, service in rows}
    check.require(len(services) == 1)
    service = next(iter(services))
    known_roots = {service, *mappings, *mappings.values()}
    check.require(all(path.split('/')[0] in known_roots for path in entries))
    main = check.owner(observed, processes, '/home/egress/tmp/' + service + '/service_ipc.sock', recorder['Id'])
    allowed_handlers = set()
    for other in mappings:
        if other == candidate['egressId'] or other not in entries:
            continue
        _, worker = active_owner(current, other)
        allowed_handlers.add(worker[0])
    by_pid = {p['pid']: p for p in processes.values()}
    for key, process in processes.items():
        check.require(process['birthRechecked'] is True and process['sameRecorderContainer'] is True)
        if key == main:
            continue
        if (process['name'] in ('tini', 'pulseaudio') and key in old_processes
                and process['startedTicks'] < main[1]):
            continue
        visited, pid = set(), process['pid']
        while pid not in allowed_handlers:
            check.require(pid in by_pid and pid not in visited and pid != main[0])
            visited.add(pid)
            pid = by_pid[pid]['parentPid']
    # The backend independently rechecks exact COMPLETE, closed room and READY
    # managed asset under its existing fences. Hashes bind locally retained full
    # observations without sending browser filenames or large process inventories.
    return dict(containers={'recorder': dict(Name='/egress', StartedAt=recorder['State']['StartedAt'],
        **{k: recorder[k] for k in ('Id', 'Image')})},
        storage={'bootId': observed['bootId']}, kind='JOB',
        job=dict(kind='JOB', egressId=candidate['egressId'], handlerId=result['handlerId'],
            activeObservedAt=active['observation']['finishedAt'],
            activeSha256=hashlib.sha256(settlement.canonical(active)).hexdigest(),
            terminalSha256=hashlib.sha256(settlement.canonical(current)).hexdigest(),
            targetCleanupVerified=True, backupEmpty=True))


def idle_recorder(sample):
    """Physical idleness only; does not settle a job or convey ownership."""
    recorder, observed, roots, entries, processes = check.snapshot(sample)
    rows = {(r['egressID'], r['handlerID'], r['nodeID']) for r in sample['jobMapping'] if r.get('handlerID')}
    check.require(len({r[0] for r in rows}) == len(rows) == len({r[1] for r in rows}))
    services = {r[2] for r in rows}
    if sample.get('recorderServiceId'):
        services.add(sample['recorderServiceId'])
    check.require(len(services) == 1)
    service = next(iter(services))
    check.require(check.re.fullmatch('NE_[A-Za-z0-9]+', service))
    handlers = {r[1] for r in rows}
    check.require(all(check.re.fullmatch('EGH_[A-Za-z0-9]+', h) for h in handlers))
    ipc = service + '/service_ipc.sock'
    # Empty retired handler directories are harmless. Any job directory, media,
    # backup, unknown entry or remaining handler socket keeps the reservation.
    check.require(not roots['backup_storage']['entries'])
    for path, entry in entries.items():
        check.require((path in handlers | {service} and entry['kind'] == 'directory')
                      or (path == ipc and entry['fileTypeBits'] == 49152))
    main = check.owner(observed, processes, '/home/egress/tmp/' + ipc, recorder['Id'])
    for key, process in processes.items():
        check.require(process['birthRechecked'] is True and process['sameRecorderContainer'] is True
                      and process['cgroup'] == '0::/system.slice/docker-' + recorder['Id'] + '.scope\n'
                      and process['mountNamespace'] == processes[main]['mountNamespace'])
        check.require(key == main or process['name'] in ('tini', 'pulseaudio') and process['startedTicks'] < main[1])
    prefixes = (check.STORAGE + '/tmp', '/home/egress/tmp', check.STORAGE + '/backup_storage', '/home/egress/backup_storage')
    check.require(not any(any(check.under(f['target'].removesuffix(' (deleted)'), p) for p in prefixes)
                          for f in observed['openFiles']))
    check.require(not any(any(check.under(s['path'], p) for p in prefixes)
                          and s['path'] not in ('/home/egress/tmp/' + ipc, check.STORAGE + '/tmp/' + ipc)
                          for s in observed['unixSockets']))
    return recorder, observed, roots, processes


def idle_preparation(sample, candidate):
    """Require whole-recorder idleness and the exact managed preparation."""
    check.require(candidate.get('preparationOnly') is True and candidate.get('assetId') is None)
    targets = {r['handlerID'] for r in sample['jobMapping'] if r['egressID'] == candidate['egressId']}
    check.require(len(targets) == 1)
    return (*idle_recorder(sample), next(iter(targets)))


def idle_preparation_proof(first, current, candidate):
    a, ao, ar, ap, handler = idle_preparation(first, candidate)
    t, to, tr, tp, current_handler = idle_preparation(current, candidate)
    # Docker may reorder its mount list across identical inspections.
    check.require(all(a[k] == t[k] for k in ('Id', 'Image', 'State'))
                  and sorted(a['Mounts'], key=lambda m: m['Destination']) == sorted(t['Mounts'], key=lambda m: m['Destination'])
                  and ao['bootId'] == to['bootId'] == candidate['nodeGeneration']
                  and ap == tp and handler == current_handler)
    check.require(all(check.identity(ar[n]['identity']) == check.identity(tr[n]['identity']) for n in ar))
    parse = lambda v: dt.datetime.fromisoformat(v.replace('Z', '+00:00'))
    check.require(parse(ao['startedAt']) <= parse(ao['finishedAt'])
                  and (parse(to['startedAt']) - parse(ao['finishedAt'])).total_seconds() >= 30
                  and parse(to['startedAt']) <= parse(to['finishedAt']))
    return dict(kind='JOB', containers={'recorder': dict(Name='/egress', StartedAt=t['State']['StartedAt'],
                **{k: t[k] for k in ('Id', 'Image')})}, storage={'bootId': to['bootId']},
        job=dict(kind='IDLE_PREPARATION', egressId=candidate['egressId'], handlerId=handler,
                 idleObservedAt=ao['finishedAt'], terminalObservedAt=to['finishedAt'],
                 idleSha256=hashlib.sha256(settlement.canonical(first)).hexdigest(),
                 terminalSha256=hashlib.sha256(settlement.canonical(current)).hexdigest(),
                 recorderIdleVerified=True, targetCleanupVerified=True, backupEmpty=True))


def run(request, identity, observe, unchanged, folder):
    query = urllib.parse.urlencode(dict(nodeId=identity['nodeId'], generation=identity['nodeGeneration'],
        dropletId=identity['dropletId'], proofKind='JOB'))
    candidates = request('GET', 'settlement-candidates?' + query, None)
    if not isinstance(candidates, list) or len(candidates) > 100:
        raise ValueError('Bounded job work list required')
    sent, deadline = 0, time.monotonic() + 30
    for candidate in candidates:
        if time.monotonic() >= deadline:
            break
        if any(candidate.get(k) != identity[k] for k in ('nodeId', 'nodeGeneration', 'dropletId')):
            raise ValueError('Job belongs to another recorder')
        scope = {k: candidate[k] for k in settlement.FIELDS if k != 'assetId'}
        name = hashlib.sha256(settlement.canonical(scope)).hexdigest()
        path = folder / (name + '.json')
        if not candidate.get('assetId') and candidate.get('preparationOnly') is not True:
            if not path.exists():
                try:
                    sample = observe()
                    check.require(sample['observation']['bootId'] == identity['nodeGeneration'])
                    active_owner(sample, candidate['egressId'])
                except (ValueError, KeyError, OSError):
                    continue
                unchanged()
                save_once(folder, name, dict(scope=scope, sample=sample))
            continue
        try:
            if candidate.get('preparationOnly') is True and not path.exists():
                idle_path = folder / (name + '-idle.json')
                current = observe()
                idle_preparation(current, candidate)
                check.require(current['observation']['bootId'] == identity['nodeGeneration'])
                if not idle_path.exists():
                    unchanged()
                    save_once(folder, name + '-idle', dict(scope=scope, sample=current))
                    continue
                saved = settlement.private_json(idle_path, published=True)
                check.require(saved['scope'] == scope)
                idle_preparation_proof(saved['sample'], current, candidate)
                retained = save_once(folder, name + '-idle-terminal', current)
                proof = idle_preparation_proof(saved['sample'], retained, candidate)
                body = settlement.receipt(folder / 'receipts', candidate, proof)
                idle_preparation_proof(saved['sample'], observe(), candidate)
                unchanged()
                request('POST', 'settled', body)
                sent += 1
                break
            saved = settlement.private_json(path, published=True)
            check.require(saved['scope'] == scope)
            current = observe()
            complete_proof(saved['sample'], current, candidate)
            # One immutable terminal snapshot per attempt, including uncertain HTTP
            # retries. Repeated healthy observations must not grow a local archive.
            retained = save_once(folder, name + '-terminal', current)
            proof = complete_proof(saved['sample'], retained, candidate)
            body = settlement.receipt(folder / 'receipts', candidate, proof)
            # Do not let filesystem or HTTP preparation conceal a restarted recorder
            # or newly visible target writer. This is read-only; no mutation is replayed.
            complete_proof(saved['sample'], observe(), candidate)
            unchanged()
            request('POST', 'settled', body)
            sent += 1
        except (ValueError, KeyError, OSError):
            # Only this claim remains held. Unrelated active jobs and the node-wide
            # drain guard are not interrupted by an incomplete per-job observation.
            continue
        # One completed claim per watcher tick bounds local evidence and HTTP cost.
        break
    return sent
