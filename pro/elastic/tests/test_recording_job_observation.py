"""Job-scoped diagnostics must never become node-drain or release authority."""
import copy
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('job_observation',
    Path(__file__).resolve().parents[1] / 'recording-job-observation.py')
job = importlib.util.module_from_spec(spec)
spec.loader.exec_module(job)


def directory(path, inode):
    return dict(path=path, kind='directory', device=1, inode=inode, uid=1001, gid=0,
                mode=493, fileTypeBits=16384)


def process(pid, ticks):
    return dict(pid=pid, startedTicks=ticks, name='egress',
                cgroup='0::/system.slice/docker-' + 'a' * 64 + '.scope\n',
                sameRecorderContainer=True, birthRechecked=True,
                mountNamespace='mnt:[42]')


def socket(path, pid, ticks):
    return dict(path='/home/egress/tmp/' + path, kernelInode=pid,
                flags='00010000', type='0001', state='01',
                owners=[dict(pid=pid, startedTicks=ticks, mountNamespace='mnt:[42]')])


def samples():
    active = dict(recorder=dict(Id='a' * 64, Image=job.IMAGE,
        State=dict(Running=True, Restarting=False, OOMKilled=False, Paused=False,
                   Dead=False, StartedAt='2026-09-24T21:04:35Z'),
        Mounts=[dict(Type='bind', Source=job.STORAGE, Destination='/home/egress', RW=True)]),
        jobMapping=[dict(nodeID='NE_service', handlerID='EGH_a', egressID='EG_a')],
        processProvenance=[process(10, 100), process(20, 200)],
        observation=dict(bootId='boot', startedAt='2026-09-24T21:20:00Z',
            finishedAt='2026-09-24T21:20:01Z', elapsedSeconds=1,
            issues=['unresolved_file_type'],
            roots=[dict(name='tmp', identity=directory('', 1), entries=[
                directory('NE_service', 2), directory('EGH_a', 3), directory('EG_a', 4)]),
                dict(name='backup_storage', identity=directory('', 5), entries=[])],
            openFiles=[dict(pid=20, startedTicks=200, target='/home/egress/tmp/EG_a/output.mp4')],
            unixSockets=[socket('NE_service/service_ipc.sock', 10, 100),
                         socket('EGH_a/handler_ipc.sock', 20, 200)]))
    terminal = copy.deepcopy(active)
    terminal['observation'].update(startedAt='2026-09-24T21:36:23Z',
                                   finishedAt='2026-09-24T21:36:24Z', openFiles=[])
    terminal['observation']['roots'][0]['entries'].pop()
    terminal['observation']['unixSockets'].pop()
    terminal['processProvenance'].pop()
    return active, terminal


class JobObservationTest(unittest.TestCase):
    def test_serving_recorder_target_cleanup_is_diagnostic_only(self):
        result = job.compare(*samples(), 'EG_a')
        self.assertTrue(result['observedTargetCleanup'])
        self.assertTrue(result['diagnosticOnly'])
        self.assertFalse(result['settlementAuthorized'])
        self.assertFalse(result['nodeDeletionAuthorized'])

    def test_unrelated_active_job_not_mistaken_for_target_writer(self):
        active, terminal = samples()
        for sample in (active, terminal):
            sample['jobMapping'].append(dict(nodeID='NE_service', handlerID='EGH_b', egressID='EG_b'))
            sample['processProvenance'].append(process(30, 300))
            sample['observation']['roots'][0]['entries'].extend([directory('EGH_b', 6), directory('EG_b', 7)])
            sample['observation']['openFiles'].append(dict(pid=30, startedTicks=300,
                target='/home/egress/tmp/EG_b/output.mp4'))
            sample['observation']['unixSockets'].append(socket('EGH_b/handler_ipc.sock', 30, 300))
        self.assertTrue(job.compare(active, terminal, 'EG_a')['observedTargetCleanup'])

    def test_rejects_missing_or_conflicting_active_mapping(self):
        for mapping in ([], [dict(nodeID='NE_service', handlerID='EGH_other', egressID='EG_a'),
                             dict(nodeID='NE_service', handlerID='EGH_a', egressID='EG_a')]):
            active, terminal = samples()
            active['jobMapping'] = mapping
            with self.subTest(mapping=mapping), self.assertRaises(ValueError):
                job.compare(active, terminal, 'EG_a')

    def test_identity_and_inventory_uncertainty_hold(self):
        changes = [lambda s: s['observation'].update(bootId='other'),
            lambda s: s['recorder'].update(Id='b' * 64),
            lambda s: s['recorder']['State'].update(StartedAt='other'),
            lambda s: s['recorder']['State'].update(Running=False),
            lambda s: s['observation'].update(issues=['process_inventory_incomplete']),
            lambda s: s['observation'].update(elapsedSeconds=11),
            lambda s: s['observation']['roots'][0]['identity'].update(inode=999),
            lambda s: s['observation']['roots'][0]['entries'][1].update(inode=999),
            lambda s: s['processProvenance'][0].update(birthRechecked=False),
            lambda s: s['observation'].update(startedAt='2026-09-24T21:00:00Z')]
        for change in changes:
            active, terminal = samples()
            change(terminal)
            with self.subTest(change=change), self.assertRaises(ValueError):
                job.compare(active, terminal, 'EG_a')

    def test_remaining_files_sockets_writers_or_backup_hold(self):
        changes = [lambda s: s['observation']['roots'][0]['entries'].append(directory('EG_a', 4)),
            lambda s: s['observation']['roots'][0]['entries'].append(dict(path='EGH_a/output', kind='file')),
            lambda s: s['observation']['roots'][1]['entries'].append(dict(path='unknown', kind='file')),
            lambda s: s['observation']['openFiles'].append(dict(pid=99, startedTicks=900,
                target='/home/egress/tmp/EG_a/output.mp4 (deleted)')),
            lambda s: s['processProvenance'].append(process(20, 200)),
            lambda s: s['observation']['unixSockets'].append(socket('EGH_a/handler_ipc.sock', 20, 200))]
        for change in changes:
            active, terminal = samples()
            change(terminal)
            with self.subTest(change=change), self.assertRaises(ValueError):
                job.compare(active, terminal, 'EG_a')

    def test_active_socket_identity_required(self):
        active, terminal = samples()
        active['observation']['unixSockets'].pop()
        with self.assertRaises(ValueError):
            job.compare(active, terminal, 'EG_a')

    def test_invalid_job_and_missing_input_hold(self):
        for identity in ('../EG_a', 'EG_a/child', '', None):
            with self.subTest(identity=identity), self.assertRaises(ValueError):
                job.compare(*samples(), identity)
        with self.assertRaises(ValueError):
            job.compare({}, {}, 'EG_a')


if __name__ == '__main__':
    unittest.main()
