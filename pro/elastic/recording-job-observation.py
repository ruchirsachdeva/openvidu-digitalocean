"""Compare saved Linux observations for one job; NOT settlement authority.

This diagnostic consumes the existing recorder probe plus same-container log and
process provenance. It does not fetch provider status, verify uploaded output,
authenticate evidence or prevent a later writer. Never submit its result to the
settlement endpoint or use it to authorize deletion. No remote calls or writes.
"""
from datetime import datetime
import re

IMAGE = 'sha256:01a31780783080259b7f218f624e654dc30572be5b5f7999123ac0d98c259475'
STORAGE = '/opt/openvidu/data/egress_data/home/egress'
IDENTITY = ('device', 'inode', 'uid', 'gid', 'mode', 'fileTypeBits')


def require(condition):
    if not condition:
        raise ValueError('Exact job observation is incomplete or still occupied')


def identity(entry):
    return tuple(entry[k] for k in IDENTITY)


def under(path, root):
    return path == root or path.startswith(root + '/')


def process_id(process):
    return process['pid'], process['startedTicks']


def snapshot(sample):
    recorder, observation = sample['recorder'], sample['observation']
    state = recorder['State']
    require(recorder['Image'] == IMAGE and re.fullmatch('[a-f0-9]{64}', recorder['Id']))
    require(state['Running'] is True and all(state.get(k) is False
        for k in ('Restarting', 'OOMKilled', 'Paused', 'Dead')))
    require(isinstance(observation['issues'], list)
        and not set(observation['issues']) - {'unresolved_file_type'})
    require(0 <= observation['elapsedSeconds'] < 10 and bool(observation['bootId']))
    mounts = [m for m in recorder['Mounts'] if m.get('Destination') == '/home/egress']
    require(len(mounts) == 1 and mounts[0]['Type'] == 'bind'
        and mounts[0]['Source'] == STORAGE and mounts[0]['RW'] is True)
    roots = {r['name']: r for r in observation['roots']}
    require(len(roots) == len(observation['roots']) == 2 and set(roots) == {'tmp', 'backup_storage'})
    entries = {e['path']: e for e in roots['tmp']['entries']}
    require(len(entries) == len(roots['tmp']['entries']))
    processes = {process_id(p): p for p in sample['processProvenance']}
    require(len(processes) == len(sample['processProvenance']))
    return recorder, observation, roots, entries, processes


def owner(observation, processes, path, container):
    # Accepted connections may repeat the path; use its unique listening socket.
    listeners = [s for s in observation['unixSockets'] if s['path'] == path
                 and s['flags'] == '00010000' and s['state'] == '01' and s['type'] == '0001']
    require(len(listeners) == 1 and len(listeners[0]['owners']) == 1)
    observed = listeners[0]['owners'][0]
    process = processes[process_id(observed)]
    require(process['name'] == 'egress' and process['birthRechecked'] is True
        and process['sameRecorderContainer'] is True
        and process['cgroup'] == '0::/system.slice/docker-' + container + '.scope\n'
        and process['mountNamespace'] == observed['mountNamespace'])
    return process_id(process)


def compare(active, terminal, egress_id):
    """Report observed cleanup only; uncertainty retains the existing full claim."""
    try:
        require(isinstance(egress_id, str) and re.fullmatch('EG_[A-Za-z0-9]+', egress_id))
        a, ao, ar, ae, ap = snapshot(active)
        t, to, tr, te, tp = snapshot(terminal)
        require(a['Id'] == t['Id'] and a['State']['StartedAt'] == t['State']['StartedAt']
            and ao['bootId'] == to['bootId'])
        require(sorted(a['Mounts'], key=lambda m: m['Destination'])
            == sorted(t['Mounts'], key=lambda m: m['Destination']))
        for name in ar:
            require(identity(ar[name]['identity']) == identity(tr[name]['identity']))
        parse = lambda value: datetime.fromisoformat(value.replace('Z', '+00:00'))
        require(parse(ao['startedAt']) <= parse(ao['finishedAt']) <= parse(to['startedAt'])
            <= parse(to['finishedAt']))
        mappings = {(r['nodeID'], r['handlerID']) for r in active['jobMapping']
                    if r.get('egressID') == egress_id and r.get('handlerID')}
        require(len(mappings) == 1)
        service, handler = next(iter(mappings))
        require(re.fullmatch('NE_[A-Za-z0-9]+', service)
            and re.fullmatch('EGH_[A-Za-z0-9]+', handler))
        # A handler must not have contradictory job provenance, including another job.
        for sample in (active, terminal):
            require(all(r.get('egressID') == egress_id and r.get('nodeID') == service
                for r in sample['jobMapping'] if r.get('handlerID') == handler))
        require(any(r.get('egressID') == egress_id and r.get('handlerID') == handler
                    and r.get('nodeID') == service for r in terminal['jobMapping']))
        service_path = '/home/egress/tmp/' + service + '/service_ipc.sock'
        service_owner = owner(ao, ap, service_path, a['Id'])
        require(owner(to, tp, service_path, t['Id']) == service_owner)
        handler_owner = owner(ao, ap, '/home/egress/tmp/' + handler + '/handler_ipc.sock', a['Id'])
        require(handler_owner != service_owner and handler_owner not in tp)
        require(ae[handler]['kind'] == te[handler]['kind'] == 'directory'
            and identity(ae[handler]) == identity(te[handler]))
        require(ae[egress_id]['kind'] == 'directory')
        require(not any(under(path, egress_id) or path.startswith(handler + '/') for path in te))
        # Backup filenames are not safely attributable by this diagnostic. Any backup
        # content holds; do not pretend a name-prefix filter proves ownership.
        require(not tr['backup_storage']['entries'])
        prefixes = tuple(base + '/' + name for base in (STORAGE + '/tmp', '/home/egress/tmp')
                         for name in (egress_id, handler))
        observed_owners = {handler_owner}
        for f in ao['openFiles']:
            if any(under(f['target'].removesuffix(' (deleted)'), p) for p in prefixes):
                observed_owners.add(process_id(f))
        require(not observed_owners.intersection(tp))
        require(not any(any(under(f['target'].removesuffix(' (deleted)'), p) for p in prefixes)
                        for f in to['openFiles']))
        require(not any(any(under(s['path'], p) for p in prefixes) for s in to['unixSockets']))
        return dict(egressId=egress_id, handlerId=handler, bootId=ao['bootId'],
            containerId=a['Id'], observedTargetCleanup=True, diagnosticOnly=True,
            settlementAuthorized=False, nodeDeletionAuthorized=False)
    except (KeyError, TypeError, AttributeError, IndexError, OverflowError) as error:
        raise ValueError('Exact job observation is incomplete or still occupied') from error
