"""Recorder-only lifecycle fault tests; synthetic containers and private files only."""
import copy
import datetime as dt
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('isolation', Path(__file__).resolve().parents[1] / 'recorder-isolation.py')
isolation = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(isolation)


class RecorderIsolationTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        control = self.root / 'courseultra-recorder-guard'
        control.mkdir(mode=0o700)
        self.lock = control / 'start.lock'
        self.lock.touch(mode=0o640)
        self.worker = dict(Name='/egress', Id='a' * 64, Image=isolation.IMAGE,
            State=dict(Running=True, Restarting=False, StartedAt='2026-11-11T10:00:00Z'),
            HostConfig=dict(RestartPolicy=dict(Name='unless-stopped', MaximumRetryCount=0)))
        self.intent = dict(id='00000000-0000-4000-8000-000000000001', generation='00000000-0000-4000-8000-000000000002',
            nodeId='ND_a', dropletId='1', containerId=self.worker['Id'], startedAt=self.worker['State']['StartedAt'], action='EXCLUDE')
        self.owner = self.lock.open('rb')
        fcntl.flock(self.owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
        self.addCleanup(self.owner.close)
        self.calls = []

    def inspect(self):
        return copy.deepcopy(self.worker)

    def command(self, args):
        self.calls.append(args)
        if args[:2] == ['docker', 'update']:
            self.worker['HostConfig']['RestartPolicy']['Name'] = args[2].split('=', 1)[1]

    def act(self, intent=None, **kwargs):
        isolation.act(intent or self.intent, self.inspect(), self.intent['generation'], self.root, self.inspect, self.command, **kwargs)

    def log(self, **changes):
        item = dict(nodeID='NE_exact')
        item.update(changes)
        return '2026-11-11T11:00:01.123456789Z 2026-11-11T11:00:01.123Z\tINFO\tegress\tserver/server.go:151\tdraining\t' + json.dumps(item)

    def test_exact_console_and_json_acknowledgement_reject_handler_stale_and_unrelated_text(self):
        start = '2026-11-11T11:00:00Z'
        self.assertTrue(isolation.post_deregister(self.log(), 'NE_exact', start))
        self.assertTrue(isolation.post_deregister('2026-11-11T11:00:01Z ' + json.dumps(dict(msg='draining', caller='server/server.go:151', nodeID='NE_exact')), 'NE_exact', start))
        for log in [self.log(handlerID='EGH_other'), self.log(egressID='EG_other'), self.log(nodeID='NE_other'),
                    self.log().replace('server/server.go', 'pipeline/pipeline.go'), self.log().replace('\tINFO\t', '\tERROR\t'),
                    self.log().replace('\tdraining\t', '\trequest received\t'), 'draining ' + self.log(),
                    self.log().replace('11:00:01.123456789Z', '10:59:59Z'), self.log(msg='draining')]:
            with self.subTest(log=log): self.assertFalse(isolation.post_deregister(log, 'NE_exact', start))

    def test_intent_same_inode_restart_fence_and_single_graceful_signal(self):
        inode = self.lock.stat().st_ino
        self.act()
        self.assertEqual(inode, self.lock.stat().st_ino)
        self.assertEqual(isolation.marker(self.intent), self.lock.read_bytes())
        self.assertEqual([['docker', 'update', '--restart=no', self.worker['Id']],
                          ['docker', 'kill', '--signal=SIGQUIT', self.worker['Id']]], self.calls)
        self.act()
        self.assertEqual(1, sum(args[1] == 'kill' for args in self.calls))
        self.assertTrue(all(args[-1] == self.worker['Id'] for args in self.calls))

    def test_journal_only_crash_recovers_original_locked_inode_and_partial_intent_holds(self):
        original = isolation.os.write
        with patch.object(isolation.os, 'write', side_effect=OSError('before marker write')):
            with self.assertRaises(OSError): self.act()
        self.assertEqual(b'', self.lock.read_bytes())
        self.assertIsNotNone(isolation.read(self.root))
        self.assertEqual([], self.calls)
        self.act()
        self.assertEqual(isolation.marker(self.intent), self.lock.read_bytes())
        self.lock.write_bytes(b'recorder-isolation-v1\n{partial')
        previous = list(self.calls)
        with self.assertRaises(ValueError): self.act()
        self.assertEqual(previous, self.calls)
        self.assertIn(b'partial', self.lock.read_bytes())

    def test_visible_marker_is_flushed_again_after_lost_durability_ack_before_signal(self):
        original = isolation.os.fsync
        inode = self.lock.stat().st_ino
        def fail(fd):
            if os.fstat(fd).st_ino == inode: raise OSError('marker flush not acknowledged')
            original(fd)
        with patch.object(isolation.os, 'fsync', fail):
            with self.assertRaises(OSError): self.act()
        self.assertEqual(isolation.marker(self.intent), self.lock.read_bytes())
        self.assertEqual([], self.calls)
        events = []
        def flush(fd):
            if os.fstat(fd).st_ino == inode: events.append('marker flushed')
            original(fd)
        command = self.command
        def observed(args):
            self.assertIn('marker flushed', events)
            command(args)
        with patch.object(isolation.os, 'fsync', flush), patch.object(self, 'command', observed): self.act()
        self.assertEqual(1, sum(args[1] == 'kill' for args in self.calls))

    def test_journal_only_recovery_rejects_lost_lifetime_lock(self):
        with patch.object(isolation.os, 'write', side_effect=OSError('before marker write')):
            with self.assertRaises(OSError): self.act()
        self.owner.close()
        with self.assertRaises(ValueError): self.act()
        self.assertEqual([], self.calls)

    def test_disabled_terminating_without_post_deregister_ack_is_not_exclusion(self):
        self.act()
        journal = isolation.read(self.root)
        journal['signalAttempted'] = '2026-11-11T11:00:00Z'
        isolation.save(self.root, journal)
        admission = dict(disabled=True, terminating=True, acceptingRequests=False, nodeId='NE_exact')
        proof = lambda logs='', owner=('123', '456'): isolation.proof(self.root, self.worker, self.intent['generation'], admission, logs, owner=owner)
        self.assertFalse(proof()['excluded'])
        self.assertTrue(proof(self.log())['excluded'])
        self.assertTrue(proof()['excluded'])  # Rotation preserves exact service/PID birth binding.
        self.assertFalse(proof(owner=('123', '457'))['excluded'])
        admission['terminating'] = False
        self.assertFalse(proof(self.log())['excluded'])

    def test_lost_signal_ack_is_never_retried_and_does_not_fabricate_proof(self):
        normal = self.command
        def fail(args):
            normal(args)
            if args[1] == 'kill': raise OSError('ack lost')
        with patch.object(self, 'command', fail):
            with self.assertRaises(OSError): self.act()
        self.act()
        self.assertEqual(1, sum(args[1] == 'kill' for args in self.calls))
        admission = dict(disabled=True, terminating=False, acceptingRequests=False, nodeId='NE_exact')
        self.assertFalse(isolation.proof(self.root, self.worker, self.intent['generation'], admission, owner=('1', '2'))['excluded'])

    def test_restore_waits_original_expiry_and_does_not_redrain_new_incarnation(self):
        self.act()
        intent = dict(self.intent, action='RESTORE', restoreRequestedAt='2026-11-11T11:00:00Z',
                      restoreNotBefore=(dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=1)).isoformat())
        restored = []
        self.act(intent, restore=lambda *args: restored.append(args))
        self.assertEqual([], restored)
        self.assertEqual(intent['restoreNotBefore'], isolation.read(self.root)['intent']['restoreNotBefore'])
        intent['restoreNotBefore'] = '2026-11-11T11:01:00Z'
        self.worker['State'].update(Running=False, Status='exited', ExitCode=0, OOMKilled=False)
        with patch.object(isolation, 'stopped_clear', return_value=True): self.act(intent, restore=lambda *args: restored.append(args))
        self.assertEqual(1, len(restored))
        previous = list(self.calls)
        self.worker['State'].update(Running=True, StartedAt='2026-11-11T11:02:00Z')
        self.act(intent, restore=lambda *args: self.fail('Restored twice'))
        self.assertEqual(previous, self.calls)

    def test_restore_response_skips_node_work_list_that_its_backend_fence_no_longer_authorizes(self):
        self.act()
        self.worker['State']['Running'] = False
        intent = dict(self.intent, action='RESTORE', restoreRequestedAt='2026-11-11T11:00:00Z',
            restoreNotBefore=(dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=1)).isoformat())
        local = dict(nodeId='ND_a', dropletId='1', recorderRunning=False, recorderIsolationSupported=True,
                     recorderIsolation=dict(excluded=True, storageClear=True))
        def no_longer_authorized(*args): self.fail('RESTORE attempted NODE settlement work list')
        isolation.apply_response(dict(recorderAction=intent), local, intent['generation'], self.root,
                                 self.inspect, self.command, no_longer_authorized)
        self.assertEqual('RESTORE', isolation.read(self.root)['intent']['action'])

    def test_unknown_journal_version_or_action_holds_before_any_control_call(self):
        with self.assertRaises(ValueError): self.act(dict(self.intent, action='UNKNOWN'))
        with self.assertRaises(ValueError): self.act(dict(self.intent, action='RESTORE'))
        self.assertEqual([], self.calls)
        self.act()
        previous = list(self.calls)
        journal = isolation.read(self.root)
        for version in (2, True):
            journal['version'] = version; isolation.save(self.root, journal)
            with self.assertRaises(ValueError): self.act()
            with self.assertRaises(ValueError): isolation.proof(self.root, self.worker, self.intent['generation'])
            self.assertEqual(previous, self.calls)

    def test_changed_boot_container_start_or_unknown_marker_never_proves_exclusion(self):
        self.act()
        for key, value in [('Id', 'b' * 64), ('Image', 'sha256:' + 'c' * 64)]:
            worker = self.inspect(); worker[key] = value
            with self.assertRaises(ValueError): isolation.proof(self.root, worker, self.intent['generation'])
        worker = self.inspect(); worker['State']['StartedAt'] = '2026-11-11T11:02:00Z'
        with self.assertRaises(ValueError): isolation.proof(self.root, worker, self.intent['generation'])
        with self.assertRaises(ValueError): isolation.proof(self.root, self.worker, 'other')
        self.lock.write_bytes(b'unknown')
        with self.assertRaises(ValueError): isolation.proof(self.root, self.worker, self.intent['generation'])

# Real Linux renameat2 and no-writer scans cover lifecycle recovery around the
# separately fault-tested preservation primitive, including the cleared barrier.
import socket
import sys


@unittest.skipUnless(sys.platform == 'linux', 'Linux process and renameat2 contract')
class RecorderRestoreTest(unittest.TestCase):
    def fixture(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        control = root / 'courseultra-recorder-guard'; control.mkdir(mode=0o700)
        lock = control / 'start.lock'; lock.touch(mode=0o640)
        (control / 'egress.yaml').write_text('reviewed synthetic config\n')
        storage = root / 'data/egress_data/home/egress'
        (storage / 'tmp/NE_exact').mkdir(parents=True)
        (storage / 'tmp/EGH_exact').mkdir()
        (storage / 'backup_storage').mkdir()
        with socket.socket(socket.AF_UNIX) as service:
            service.bind(str(storage / 'tmp/NE_exact/service_ipc.sock'))
        boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        worker = dict(Name='/egress', Id='a' * 64, Image=isolation.IMAGE, Mounts=[],
            State=dict(Running=False, Restarting=False, Status='exited', ExitCode=0, OOMKilled=False, StartedAt='2026-01-01T00:00:00Z'),
            HostConfig=dict(RestartPolicy=dict(Name='no', MaximumRetryCount=0)))
        intent = dict(id='00000000-0000-4000-8000-000000000001', generation=boot, containerId=worker['Id'],
            startedAt=worker['State']['StartedAt'], action='RESTORE', restoreRequestedAt='2026-01-02T00:00:00Z', restoreNotBefore='2026-01-02T00:01:00Z')
        observed = isolation.capacity.jobs.probe.observe(storage)
        binding = dict(bootId=boot, containerId=worker['Id'], startedAt=worker['State']['StartedAt'], image=isolation.IMAGE,
            mounts=[], roots={r['name']: list(isolation.capacity.check.identity(r['identity'])) for r in observed['roots']}, serviceId='NE_exact', owner=['123', '456'])
        isolation.capacity.atomic_private(root / '.courseultra-capacity-history.json', dict(binding=binding, jobs={'EG_exact':'EGH_exact'}))
        lock.write_bytes(isolation.marker(intent))
        journal = dict(version=1, intent=intent, lockIdentity=[lock.stat().st_dev, lock.stat().st_ino],
            originalRestart=dict(Name='unless-stopped', MaximumRetryCount=0), signalAttempted='2026-01-01T00:00:01Z', stoppedSample=observed)
        isolation.save(root, journal)
        calls = []
        def inspect(): return copy.deepcopy(worker)
        def command(args):
            calls.append(args)
            if args[1] == 'update': worker['HostConfig']['RestartPolicy']['Name'] = args[2].split('=', 1)[1]
            if args[1] == 'start': worker['State'].update(Running=True, Status='running', StartedAt=dt.datetime.now(dt.timezone.utc).isoformat())
        return root, lock, intent, worker, inspect, command, calls

    def test_restore_preserves_ipc_reopens_only_recorder_and_observes_new_incarnation(self):
        root, lock, intent, worker, inspect, command, calls = self.fixture()
        with patch.object(isolation, 'stopped_clear', return_value=True):
            isolation.act(intent, inspect(), intent['generation'], root, inspect, command)
        self.assertEqual(b'', lock.read_bytes())
        self.assertEqual([], list((root / 'data/egress_data/home/egress/tmp').iterdir()))
        self.assertTrue((root / 'courseultra-recorder-guard/preserved' / intent['id'] / 'NE_exact/service_ipc.sock').is_socket())
        self.assertEqual(['update', 'start'], [args[1] for args in calls])
        admission = dict(disabled=False, terminating=False, acceptingRequests=True, nodeId='NE_returned')
        self.assertTrue(isolation.proof(root, inspect(), intent['generation'], admission, owner=('321','654'))['returned'])
        isolation.act(intent, inspect(), intent['generation'], root, inspect, command)
        self.assertEqual(['update', 'start'], [args[1] for args in calls])

    def test_crashes_after_plan_publication_preservation_policy_and_start_resume_without_data_loss(self):
        class Crash(BaseException): pass
        for boundary in ('plan', 'preserved', 'policy', 'start'):
            with self.subTest(boundary=boundary):
                root, lock, intent, worker, inspect, command, calls = self.fixture()
                original_save = isolation.save
                fired = False
                def save(path, journal):
                    nonlocal fired
                    original_save(path, journal)
                    if not fired and ((boundary == 'plan' and journal.get('restorePlan'))
                            or boundary == 'preserved' and journal.get('restoreAttempted')):
                        fired = True; raise Crash()
                def fail_command(args):
                    command(args)
                    if (boundary == 'policy' and args[1] == 'update') or (boundary == 'start' and args[1] == 'start'): raise Crash()
                with patch.object(isolation, 'save', save), patch.object(isolation, 'stopped_clear', return_value=True):
                    with self.assertRaises(Crash): isolation.act(intent, inspect(), intent['generation'], root, inspect, fail_command)
                with patch.object(isolation, 'stopped_clear', return_value=True):
                    isolation.act(intent, inspect(), intent['generation'], root, inspect, command)
                self.assertTrue(worker['State']['Running'])
                self.assertEqual(1, sum(args[1] == 'start' for args in calls))
                self.assertEqual(b'', lock.read_bytes())
                self.assertTrue((root / 'courseultra-recorder-guard/preserved' / intent['id'] / 'receipt.json').is_file())

    def test_stopped_clean_exit_still_holds_real_data_backup_unknown_residue_and_unsettled_marker(self):
        root, lock, intent, worker, inspect, command, calls = self.fixture()
        for suffix in ('tmp/NE_exact/recording.mp4', 'backup_storage/upload', 'tmp/EGH_unknown'):
            path = root / 'data/egress_data/home/egress' / suffix; path.write_bytes(b'preserve')
            with self.assertRaises(ValueError): isolation.restore_recorder(root, isolation.read(root), inspect(), inspect, command)
            self.assertEqual(b'preserve', path.read_bytes()); self.assertEqual([], calls)
            path.unlink()
        lock.write_bytes(b'unknown')
        with self.assertRaises(ValueError): isolation.proof(root, inspect(), intent['generation'])
        self.assertEqual([], calls)
