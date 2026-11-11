import base64
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from test_recording_job_observation import samples, process, directory, socket

spec = importlib.util.spec_from_file_location('job_settlement',
    Path(__file__).resolve().parents[1] / 'settle-recording-jobs.py')
jobs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(jobs)


class JobSettlementTest(unittest.TestCase):
    def test_idle_preparation_mount_order_is_not_identity_but_changed_mount_is(self):
        first = samples()[1]
        first['recorder']['Mounts'].append(dict(Destination='/etc/egress.yaml', Type='bind', Source='/config/egress.yaml', RW=False))
        later = copy.deepcopy(first)
        later['recorder']['Mounts'].reverse()
        later['observation'].update(startedAt='2026-09-24T21:37:23Z', finishedAt='2026-09-24T21:37:24Z')
        candidate = dict(self.candidate(), preparationOnly=True)
        self.assertEqual('IDLE_PREPARATION', jobs.idle_preparation_proof(first, later, candidate)['job']['kind'])
        later['recorder']['Mounts'][0]['Source']='/config/changed.yaml'
        with self.assertRaises(ValueError): jobs.idle_preparation_proof(first, later, candidate)

    def test_short_preparation_settles_after_two_idle_observations_without_active_sample(self):
        first = samples()[1]
        later = copy.deepcopy(first)
        later['observation'].update(startedAt='2026-09-24T21:37:23Z', finishedAt='2026-09-24T21:37:24Z')
        with tempfile.TemporaryDirectory() as folder:
            sent = []
            candidate = dict(self.candidate(), preparationOnly=True)
            self.assertEqual(0, self.run_pass(folder, candidate, first, sent))
            self.assertEqual(0, self.run_pass(folder, candidate, first, sent))
            self.assertEqual(1, self.run_pass(folder, candidate, later, sent))
            document = json.loads(base64.urlsafe_b64decode(sent[0]['storageReceipt'].split(':')[2]))
            self.assertEqual('IDLE_PREPARATION', document['observation']['kind'])
            self.assertNotIn('activeSha256', document['observation'])
            self.assertTrue(document['observation']['recorderIdleVerified'])
            self.assertEqual(1, self.run_pass(folder, candidate, later, sent))
            self.assertEqual(sent[0], sent[1])

    def test_idle_preparation_never_accepts_writers_files_backups_or_changed_identity(self):
        mutations = [
            lambda s: s['processProvenance'].append(dict(process(99, 900), name='chrome')),
            lambda s: s['processProvenance'].append(dict(process(99, 900), name='pulseaudio')),
            lambda s: s['observation']['roots'][0]['entries'].append(directory('EG_a', 7)),
            lambda s: s['observation']['roots'][1]['entries'].append(dict(path='output.mp4', kind='file')),
            lambda s: s['observation']['openFiles'].append(dict(target='/home/egress/tmp/EG_a/output.mp4 (deleted)')),
            lambda s: s['observation']['unixSockets'].append(socket('EGH_a/handler_ipc.sock', 20, 200)),
            lambda s: s['recorder'].update(Id='b' * 64),
            lambda s: s['observation'].update(bootId='other'),
            lambda s: s['observation']['roots'][0]['identity'].update(inode=99),
        ]
        for mutate in mutations:
            first = samples()[1]
            later = copy.deepcopy(first)
            later['observation'].update(startedAt='2026-09-24T21:37:23Z', finishedAt='2026-09-24T21:37:24Z')
            mutate(later)
            with self.subTest(mutate=mutate), tempfile.TemporaryDirectory() as folder:
                sent = []
                candidate = dict(self.candidate(), preparationOnly=True)
                self.run_pass(folder, candidate, first, sent)
                self.assertEqual(0, self.run_pass(folder, candidate, later, sent))
                self.assertEqual([], sent)

    def test_idle_preparation_rechecks_before_sending_and_retries_exact_receipt(self):
        first = samples()[1]
        later = copy.deepcopy(first)
        later['observation'].update(startedAt='2026-09-24T21:37:23Z', finishedAt='2026-09-24T21:37:24Z')
        occupied = copy.deepcopy(later)
        occupied['processProvenance'].append(dict(process(99, 900), name='chrome'))
        candidate = dict(self.candidate(), preparationOnly=True)
        with tempfile.TemporaryDirectory() as folder:
            sent = []
            self.run_pass(folder, candidate, first, sent)
            def request(method, path, body):
                if method == 'GET': return [candidate]
                sent.append(body)
                raise ValueError('Outcome unknown')
            self.assertEqual(0, jobs.run(request, self.identity(), Mock(side_effect=[later, occupied]), lambda: None, Path(folder)))
            self.assertEqual([], sent)
            self.assertEqual(0, jobs.run(request, self.identity(), lambda: later, lambda: None, Path(folder)))
            self.assertEqual(1, self.run_pass(folder, candidate, later, sent))
            self.assertEqual(sent[0], sent[1])

    def test_collector_rechecks_process_birth_and_container_without_mutation(self):
        active, _ = samples()
        with tempfile.TemporaryDirectory() as folder:
            proc = Path(folder)
            entry = proc / '10'
            (entry / 'ns').mkdir(parents=True)
            (entry / 'cgroup').write_text(process(10, 100)['cgroup'])
            fields = ['S', '1'] + ['0'] * 17 + ['100']
            (entry / 'stat').write_text('10 (egress) ' + ' '.join(fields))
            (entry / 'comm').write_text('egress\n')
            (entry / 'ns/mnt').symlink_to('mnt:[42]')
            with patch.object(jobs.probe, 'observe', return_value=active['observation']):
                captured = jobs.capture(lambda: copy.deepcopy(active['recorder']), {'EG_a': 'EGH_a'}, 'NE_service', proc)
                self.assertEqual(100, captured['processProvenance'][0]['startedTicks'])
                self.assertEqual(1, captured['processProvenance'][0]['parentPid'])
                self.assertTrue(captured['processProvenance'][0]['birthRechecked'])
                changed = copy.deepcopy(active['recorder'])
                changed['Id'] = 'b' * 64
                with self.assertRaises(ValueError):
                    jobs.capture(Mock(side_effect=[active['recorder'], changed]), {'EG_a': 'EGH_a'}, 'NE_service', proc)

    def candidate(self, ready=False):
        return dict(runtimeId='runtime', generation=1, nativeGeneration='native', creationAttemptId='create',
            recordingAttemptId='record', partId='part', roomSid='RM_a', egressId='EG_a',
            nodeId='ND_a', nodeGeneration='boot', dropletId='123', assetId='asset' if ready else None)

    def test_confirmed_zombie_without_descriptors_needs_no_mount_namespace(self):
        active, _ = samples()
        with tempfile.TemporaryDirectory() as folder:
            proc = Path(folder)
            entry = proc / '20'
            (entry / 'fd').mkdir(parents=True)
            (entry / 'task/20').mkdir(parents=True)
            (entry / 'cgroup').write_text(process(20, 200)['cgroup'])
            fields = ['Z', '1'] + ['0'] * 17 + ['200']
            (entry / 'stat').write_text('20 (chrome) ' + ' '.join(fields))
            with patch.object(jobs.probe, 'observe', return_value=active['observation']):
                sample = jobs.capture(lambda: copy.deepcopy(active['recorder']), {}, 'NE_service', proc)
                self.assertEqual([], sample['processProvenance'])
                (entry / 'task/21').mkdir()
                with self.assertRaisesRegex(ValueError, 'other threads'):
                    jobs.capture(lambda: copy.deepcopy(active['recorder']), {}, 'NE_service', proc)
                (entry / 'task/21').rmdir()
                (entry / 'fd/1').touch()
                with self.assertRaisesRegex(ValueError, 'file descriptors'):
                    jobs.capture(lambda: copy.deepcopy(active['recorder']), {}, 'NE_service', proc)

    def test_zombie_pid_reuse_or_live_process_without_namespace_still_holds(self):
        active, _ = samples()
        with tempfile.TemporaryDirectory() as folder:
            proc = Path(folder)
            entry = proc / '20'
            (entry / 'fd').mkdir(parents=True)
            (entry / 'task/20').mkdir(parents=True)
            (entry / 'cgroup').write_text(process(20, 200)['cgroup'])
            (entry / 'comm').write_text('chrome\n')
            def stat(state, birth):
                return '20 (chrome) ' + ' '.join([state, '1'] + ['0'] * 17 + [str(birth)])
            original = Path.read_text
            for changed in (stat('S', 200), stat('Z', 201)):
                values = iter([stat('Z', 200), changed])
                def read(path, *args, **kwargs):
                    return next(values) if path == entry / 'stat' else original(path, *args, **kwargs)
                with patch.object(jobs.probe, 'observe', return_value=active['observation']), patch.object(Path, 'read_text', read):
                    with self.assertRaisesRegex(ValueError, 'identity changed'):
                        jobs.capture(lambda: copy.deepcopy(active['recorder']), {}, 'NE_service', proc)
            (entry / 'stat').write_text(stat('S', 200))
            with patch.object(jobs.probe, 'observe', return_value=active['observation']):
                with self.assertRaises(FileNotFoundError):
                    jobs.capture(lambda: copy.deepcopy(active['recorder']), {}, 'NE_service', proc)

    def identity(self):
        return dict(nodeId='ND_a', nodeGeneration='boot', dropletId='123')

    def run_pass(self, folder, candidate, sample, sent):
        def request(method, path, body):
            if method == 'GET':
                self.assertIn('proofKind=JOB', path)
                return [candidate]
            self.assertEqual(path, 'settled')
            sent.append(body)
        return jobs.run(request, self.identity(), lambda: copy.deepcopy(sample), lambda: None, Path(folder))

    def test_active_capture_then_full_job_receipt_without_node_drain(self):
        active, terminal = samples()
        with tempfile.TemporaryDirectory() as folder:
            sent = []
            self.assertEqual(0, self.run_pass(folder, self.candidate(), active, sent))
            self.assertEqual([], sent)
            self.assertEqual(1, self.run_pass(folder, self.candidate(True), terminal, sent))
            prefix, digest, body = sent[0]['storageReceipt'].split(':')
            self.assertEqual('job-storage-v1', prefix)
            document = json.loads(base64.urlsafe_b64decode(body))
            self.assertEqual('JOB', document['observation']['kind'])
            self.assertTrue(document['observation']['targetCleanupVerified'])
            self.assertEqual('EG_a', document['scope']['egressId'])
            self.assertEqual(1, self.run_pass(folder, self.candidate(True), terminal, sent))
            self.assertEqual(sent[0], sent[1])

    def test_preparation_completion_needs_prior_active_proof_and_is_not_an_asset(self):
        active, terminal = samples()
        candidate = dict(self.candidate(), preparationOnly=True)
        with tempfile.TemporaryDirectory() as folder:
            sent = []
            self.assertEqual(0, self.run_pass(folder, candidate, terminal, sent))
            self.assertEqual(0, self.run_pass(folder, self.candidate(), active, sent))
            self.assertEqual(1, self.run_pass(folder, candidate, terminal, sent))
            self.assertIsNone(sent[0]['assetId'])
            self.assertTrue(sent[0]['preparationOnly'])
            prefix, digest, body = sent[0]['storageReceipt'].split(':')
            self.assertEqual('job-storage-v1', prefix)
            document = json.loads(base64.urlsafe_b64decode(body))
            self.assertEqual('JOB', document['observation']['kind'])
            self.assertTrue(document['observation']['targetCleanupVerified'])
            self.assertEqual('EG_a', document['scope']['egressId'])
            self.assertEqual(1, self.run_pass(folder, candidate, terminal, sent))
            self.assertEqual(sent[0], sent[1])

    def test_terminal_without_saved_active_identity_never_submits(self):
        with tempfile.TemporaryDirectory() as folder:
            sent = []
            self.assertEqual(0, self.run_pass(folder, self.candidate(True), samples()[1], sent))
            self.assertEqual([], sent)

    def test_unknown_writer_and_backup_retain_whole_claim(self):
        for mutation in (lambda s: s['processProvenance'].append(dict(process(99, 900), parentPid=10)),
                         lambda s: s['observation']['roots'][1]['entries'].append(dict(path='unknown', kind='file'))):
            active, terminal = samples()
            mutation(terminal)
            with tempfile.TemporaryDirectory() as folder:
                sent = []
                self.run_pass(folder, self.candidate(), active, sent)
                self.assertEqual(0, self.run_pass(folder, self.candidate(True), terminal, sent))
                self.assertEqual([], sent)

    def test_known_unrelated_handler_and_children_continue(self):
        active, terminal = samples()
        for sample in (active, terminal):
            sample['jobMapping'].append(dict(nodeID='NE_service', handlerID='EGH_b', egressID='EG_b'))
            sample['processProvenance'].extend([dict(process(30, 300), parentPid=10),
                                              dict(process(31, 310), name='chrome', parentPid=30)])
            sample['observation']['roots'][0]['entries'].extend([directory('EGH_b', 6), directory('EG_b', 7)])
            sample['observation']['unixSockets'].append(socket('EGH_b/handler_ipc.sock', 30, 300))
        proof = jobs.complete_proof(active, terminal, self.candidate(True))
        self.assertTrue(proof['job']['targetCleanupVerified'])

    def test_familiar_process_name_does_not_hide_post_service_writer(self):
        active, terminal = samples()
        for sample in (active, terminal):
            sample['processProvenance'].append(dict(process(99, 900), name='pulseaudio', parentPid=10))
        with self.assertRaises(ValueError):
            jobs.complete_proof(active, terminal, self.candidate(True))

    def test_retry_never_overwrites_active_history_and_rejects_different_scope(self):
        with tempfile.TemporaryDirectory() as folder:
            original = jobs.save_once(Path(folder), 'evidence', {'identity': 'one'})
            self.assertEqual(original, jobs.save_once(Path(folder), 'evidence', {'identity': 'two'}))

    def test_replaced_container_and_old_attempt_never_submit(self):
        for changed_scope in (False, True):
            active, terminal = samples()
            candidate = self.candidate(True)
            if changed_scope:
                candidate['recordingAttemptId'] = 'other-attempt'
            else:
                terminal['recorder']['Id'] = 'd' * 64
            with tempfile.TemporaryDirectory() as folder:
                sent = []
                self.run_pass(folder, self.candidate(), active, sent)
                self.assertEqual(0, self.run_pass(folder, candidate, terminal, sent))
                self.assertEqual([], sent)

    def test_real_log_rows_without_handler_do_not_invent_mapping(self):
        active, terminal = samples()
        for sample in (active, terminal):
            sample['jobMapping'].append(dict(nodeID='NE_service', egressID='EG_a'))
        self.assertTrue(jobs.complete_proof(active, terminal, self.candidate(True))['job']['targetCleanupVerified'])

    def test_post_capture_new_writer_prevents_submit(self):
        active, terminal = samples()
        with tempfile.TemporaryDirectory() as folder:
            sent = []
            self.run_pass(folder, self.candidate(), active, sent)
            changed = copy.deepcopy(terminal)
            changed['observation']['roots'][0]['entries'].append(directory('EG_a', 77))
            observations = iter([terminal, changed])
            def request(method, path, body):
                if method == 'GET': return [self.candidate(True)]
                sent.append(body)
            self.assertEqual(0, jobs.run(request, self.identity(), lambda: next(observations), lambda: None, Path(folder)))
            self.assertEqual([], sent)


if __name__ == '__main__':
    unittest.main()
