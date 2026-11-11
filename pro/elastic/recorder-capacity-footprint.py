"""Physical capacity footprint only. Never imports, settles or deletes a recording."""
import datetime as dt
import importlib.util
import json
import os
import re
import stat
import subprocess
from pathlib import Path
import tempfile


def load(name):
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), Path(__file__).with_name(name + '.py'))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


jobs = load('settle-recording-jobs')
check = jobs.check


def complete(sample, excluded=False):
    recorder, observed, roots, entries, processes = check.snapshot(sample)
    rows = {(r['egressID'], r['handlerID'], r['nodeID']) for r in sample['jobMapping']}
    mappings = {job: handler for job, handler, _ in rows}
    check.require(len(mappings) == len(rows) == len(set(mappings.values())))
    service = sample['recorderServiceId']
    check.require(check.re.fullmatch('NE_[A-Za-z0-9]+', service)
                  and all(row[2] == service for row in rows))
    check.require(all(check.re.fullmatch('EG_[A-Za-z0-9]+', job)
                      and check.re.fullmatch('EGH_[A-Za-z0-9]+', handler) for job, handler in mappings.items()))
    known = {service, *mappings, *mappings.values()}
    check.require(excluded or not roots['backup_storage']['entries'])
    check.require(all(path.split('/')[0] in known and entry['kind'] in ('directory', 'file', 'special')
                      and (entry['kind'] != 'special' or entry['fileTypeBits'] == 49152)
                      for path, entry in entries.items()))
    main = check.owner(observed, processes, '/home/egress/tmp/' + service + '/service_ipc.sock', recorder['Id'])
    workers = set()
    for job, handler in mappings.items():
        if job in entries or handler + '/handler_ipc.sock' in entries:
            _, worker = jobs.active_owner(sample, job)
            workers.add(worker[0])
    by_pid = {p['pid']: p for p in processes.values()}
    for key, process in processes.items():
        check.require(process['birthRechecked'] is True and process['sameRecorderContainer'] is True
                      and process['cgroup'] == '0::/system.slice/docker-' + recorder['Id'] + '.scope\n')
        if key == main or process['name'] in ('tini', 'pulseaudio') and process['startedTicks'] < main[1]:
            continue
        visited, pid = set(), process['pid']
        while pid not in workers:
            check.require(pid in by_pid and pid not in visited and pid != main[0])
            visited.add(pid)
            pid = by_pid[pid]['parentPid']
    # Even unlinked files and recovery data count. Unknown paths make this node
    # unavailable; neither filenames nor empty active-egress lists erase usage.
    prefixes = [base + '/tmp/' + root for base in (check.STORAGE, '/home/egress') for root in known]
    if excluded:
        prefixes.extend(base + '/backup_storage' for base in (check.STORAGE, '/home/egress'))
    check.require(all(any(check.under(f['target'].removesuffix(' (deleted)'), root) for root in prefixes)
                      for f in observed['openFiles']))
    check.require(all(any(check.under(s['path'], root) for root in prefixes) for s in observed['unixSockets']))
    return sorted(mappings)


def same_idle(first, current):
    a, ao, ar, ap = jobs.idle_recorder(first)
    t, to, tr, tp = jobs.idle_recorder(current)
    check.require(all(a[k] == t[k] for k in ('Id', 'Image', 'State'))
                  and sorted(a['Mounts'], key=lambda m: m['Destination']) == sorted(t['Mounts'], key=lambda m: m['Destination'])
                  and ao['bootId'] == to['bootId'] and ap == tp
                  and first['recorderServiceId'] == current['recorderServiceId'])
    check.require(all(check.identity(ar[n]['identity']) == check.identity(tr[n]['identity']) for n in ar))
    parse = lambda v: dt.datetime.fromisoformat(v.replace('Z', '+00:00'))
    check.require(parse(ao['startedAt']) <= parse(ao['finishedAt'])
                  and (parse(to['startedAt']) - parse(ao['finishedAt'])).total_seconds() >= 30
                  and parse(to['startedAt']) <= parse(to['finishedAt']))


def footprint(sample, previous=None, excluded=False):
    recorder = sample['recorder']
    result = dict(observedAt=sample['observation']['startedAt'], containerId=recorder['Id'],
                  startedAt=recorder['State']['StartedAt'], complete=False,
                  jobIds=sorted({row['egressID'] for row in sample['jobMapping']}))
    try:
        result['jobIds'] = complete(sample, excluded)
        result['complete'] = True
        if previous is not None:
            try:
                same_idle(previous, sample)
                result['jobIds'] = []
            except (ValueError, KeyError, TypeError):
                pass
    except (ValueError, KeyError, TypeError):
        pass
    return result


def atomic_private(path, value):
    body = json.dumps(value, sort_keys=True).encode()
    check.require(len(body) <= 4 * 1024 * 1024)
    fd, temporary = tempfile.mkstemp(prefix='.capacity-footprint-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as out:
            out.write(body)
            out.flush()
            os.fsync(out.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


HISTORY_LIMIT = 4096


def binding(sample):
    recorder, observed, roots, entries, processes = check.snapshot(sample)
    service = sample['recorderServiceId']
    owner = check.owner(observed, processes, '/home/egress/tmp/' + service + '/service_ipc.sock', recorder['Id'])
    return dict(bootId=observed['bootId'], containerId=recorder['Id'], image=recorder['Image'],
                startedAt=recorder['State']['StartedAt'], serviceId=service, owner=list(owner),
                mounts=sorted(recorder['Mounts'], key=lambda m: m['Destination']),
                roots={name: list(check.identity(root['identity'])) for name, root in roots.items()})


def physical_job_roots(sample):
    observed = sample['observation']
    entries = next(root['entries'] for root in observed['roots'] if root['name'] == 'tmp')
    present = set()
    for entry in entries:
        root, separator, _ = entry['path'].partition('/')
        if root.startswith('EG_') or separator:
            present.add(root)
    prefixes = (check.STORAGE + '/tmp/', '/home/egress/tmp/')
    paths = [f['target'].removesuffix(' (deleted)') for f in observed['openFiles']]
    paths.extend(socket['path'] for socket in observed['unixSockets'])
    for path in paths:
        for prefix in prefixes:
            if path.startswith(prefix):
                present.add(path[len(prefix):].split('/')[0])
    return present


def publish(sample, unchanged, root, excluded=False):
    previous_path = root / '.courseultra-capacity-idle.json'
    history_path = root / '.courseultra-capacity-history.json'
    current_binding = binding(sample)
    try:
        history = jobs.settlement.private_json(history_path)
        check.require(history['version'] == 1)
    except FileNotFoundError:
        history = None
    if history is None or history['binding'] != current_binding:
        history = dict(version=1, binding=current_binding, jobs={}, cleared=[], observedAt=None)
    mappings, reverse = dict(history['jobs']), {}
    check.require(len(mappings) <= HISTORY_LIMIT and len(history['cleared']) <= HISTORY_LIMIT
                  and set(history['cleared']) <= mappings.keys())
    if history['observedAt'] is not None:
        parse = lambda v: dt.datetime.fromisoformat(v.replace('Z', '+00:00'))
        check.require(parse(sample['observation']['startedAt']) >= parse(history['observedAt']))
    for job, handler in mappings.items():
        check.require(re.fullmatch('EG_[A-Za-z0-9]+', job) and re.fullmatch('EGH_[A-Za-z0-9]+', handler)
                      and handler not in reverse)
        reverse[handler] = job
    for row in sample['jobMapping']:
        job, handler = row['egressID'], row['handlerID']
        check.require(row['nodeID'] == sample['recorderServiceId']
                      and re.fullmatch('EG_[A-Za-z0-9]+', job) and re.fullmatch('EGH_[A-Za-z0-9]+', handler)
                      and (job not in mappings or mappings[job] == handler)
                      and (handler not in reverse or reverse[handler] == job))
        mappings[job], reverse[handler] = handler, job
    # No eviction at the bound: forgetting unresolved work would invent capacity.
    check.require(len(mappings) <= HISTORY_LIMIT)
    sample = dict(sample, jobMapping=[dict(egressID=job, handlerID=handler, nodeID=sample['recorderServiceId'])
                                     for job, handler in sorted(mappings.items())])
    try:
        previous = jobs.settlement.private_json(previous_path)
    except FileNotFoundError:
        previous = None
    result = footprint(sample, previous, excluded)
    cleared = set(history['cleared'])
    # Cleanup credit never hides physical reappearance, even for a previously
    # cleared EG/handler. Truncated logs are not proof that an unresolved job ended.
    present = physical_job_roots(sample)
    cleared.difference_update({job for job in cleared if job in present or mappings[job] in present})
    if result['complete'] and not result['jobIds']:
        cleared.update(mappings)
    result['jobIds'] = sorted(set(mappings) - cleared)
    unchanged()
    history.update(jobs=mappings, cleared=sorted(cleared), observedAt=sample['observation']['startedAt'])
    # Persist provenance/cleanup knowledge before publishing capacity. Neither an
    # uncertain write nor a rotated log may turn an unresolved job into zero cost.
    atomic_private(history_path, history)
    atomic_private(root / '.courseultra-capacity-footprint.json',
                   dict(bootId=sample['observation']['bootId'], **result))
    try:
        jobs.idle_recorder(sample)
        if previous is None or not result['jobIds']:
            atomic_private(previous_path, sample)
        else:
            parse = lambda v: dt.datetime.fromisoformat(v.replace('Z', '+00:00'))
            if (binding(previous) != current_binding
                    or (parse(sample['observation']['startedAt']) - parse(previous['observation']['finishedAt'])).total_seconds() >= 30):
                atomic_private(previous_path, sample)
    except (ValueError, KeyError, TypeError):
        previous_path.unlink(missing_ok=True)


def _observe_local(worker, boot, root, proc, excluded=False):
    locations = load('report-recording-locations')
    boot_time = next(int(line.split()[1]) for line in (proc / 'stat').read_text().splitlines() if line.startswith('btime '))
    expected = locations.container_identity(worker, boot_time, root)
    tmp = root / 'data/egress_data/home/egress/tmp'
    check.require(not any(path.is_symlink() for path in (tmp, *tmp.parents)))
    services = [p for p in tmp.iterdir() if re.fullmatch(r'NE_[A-Za-z0-9]+', p.name)]
    check.require(len(services) == 1 and not services[0].is_symlink() and services[0].is_dir()
                  and stat.S_ISSOCK((services[0] / 'service_ipc.sock').lstat().st_mode))
    logs = subprocess.run(['docker', 'logs', '--since', worker['State']['StartedAt'], '--tail', '20000', worker['Id']],
                          capture_output=True, text=True, check=True, timeout=5)
    check.require(len(logs.stdout) + len(logs.stderr) <= 16 * 1024 * 1024)
    mapping = locations.logged_jobs(logs.stdout + '\n' + logs.stderr, services[0].name)

    def inspect():
        result = subprocess.run(['docker', 'inspect', worker['Id']], capture_output=True,
                                text=True, check=True, timeout=5)
        check.require(len(result.stdout) <= 4 * 1024 * 1024)
        return json.loads(result.stdout)[0]

    def unchanged():
        check.require((proc / 'sys/kernel/random/boot_id').read_text().strip() == boot
                      and locations.container_identity(inspect(), boot_time, root) == expected)

    sample = jobs.capture(inspect, mapping, services[0].name, proc)
    publish(sample, unchanged, root, excluded)
    # The machine receipt carries the exact sample, not a fabricated fresh cache timestamp.
    saved = jobs.settlement.private_json(root / '.courseultra-capacity-footprint.json')
    check.require(saved.pop('bootId') == boot)
    return saved


def observe_local(worker, boot, root, proc, excluded=False):
    began = dt.datetime.now(dt.timezone.utc).isoformat()
    try:
        return _observe_local(worker, boot, root, proc, excluded)
    except (OSError, ValueError, KeyError, TypeError, StopIteration, subprocess.SubprocessError):
        # No zero-cost fallback: incomplete proof cannot authorize pool capacity.
        # The enclosing fleet collector still rechecks boot/container/config identity.
        return dict(observedAt=began, containerId=worker['Id'], startedAt=worker['State']['StartedAt'],
                    complete=False, jobIds=[])
