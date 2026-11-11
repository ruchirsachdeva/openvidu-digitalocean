import copy
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
import socket
import sys


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).resolve().parents[1] / file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


guard = load('settlement_guard_test', 'media_drain_guard.py')
settlement = load('recording_settlement_test', 'settle-recordings.py')
probe = load('recording_settlement_probe_test', 'recorder-storage-probe.py')


class RecordingSettlementTest(unittest.TestCase):
    @unittest.skipUnless(sys.platform == 'linux', 'Requires real Linux process/socket evidence')
    def test_real_retired_socket_is_not_data_but_live_socket_and_files_hold(self):
        with tempfile.TemporaryDirectory() as folder:
            storage = Path(folder)
            service = storage / 'tmp/NE_one'
            service.mkdir(parents=True)
            (storage / 'backup_storage').mkdir()
            (storage / 'tmp/EGH_one').mkdir()
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
                listener.bind(str(service / 'service_ipc.sock'))
                listener.listen(1)
                with self.assertRaises(ValueError):
                    guard.verify_retired_ipc_observation(probe.observe(storage))
            guard.verify_retired_ipc_observation(probe.observe(storage))
            (storage / 'tmp/EGH_one/output.mp4').write_bytes(b'preserve recording')
            with self.assertRaises(ValueError):
                guard.verify_retired_ipc_observation(probe.observe(storage))
            self.assertEqual(b'preserve recording', (storage / 'tmp/EGH_one/output.mp4').read_bytes())

    def observation(self):
        return dict(bootId='boot', issues=['unresolved_file_type'], processes=[], openFiles=[], unixSockets=[],
                    startedAt='start', finishedAt='end', elapsedSeconds=1, complete=False,
                    roots=[dict(name='tmp', identity={'inode': 1}, entries=[
                        dict(path='NE_one', kind='directory'),
                        dict(path='NE_one/service_ipc.sock', kind='special', specialType='socket'),
                        dict(path='EGH_one', kind='directory')]),
                           dict(name='backup_storage', identity={'inode': 2}, entries=[])])

    def proof(self):
        return {'containers': {'a': {'Id': 'a', 'Name': '/egress', 'Image': settlement.IMAGE,
                                    'State': {'StartedAt': 'one'}, 'Mounts': []}}, 'storage': self.observation()}

    def candidate(self):
        return dict(runtimeId='class', generation=1, nativeGeneration='native', creationAttemptId='create',
                    recordingAttemptId='record', partId='part', roomSid='RM_one', egressId='EG_one', assetId='asset',
                    nodeId='ND_one', nodeGeneration='boot', dropletId='123')

    def test_preparation_scope_is_explicit_and_cannot_claim_a_managed_asset(self):
        with tempfile.TemporaryDirectory() as folder:
            candidate = dict(self.candidate(), assetId=None, preparationOnly=True)
            result = settlement.receipt(Path(folder) / 'receipts', candidate, self.proof())
            self.assertTrue(result['preparationOnly'])
            self.assertIsNone(result['assetId'])
            with self.assertRaises(ValueError):
                settlement.receipt(Path(folder) / 'receipts', dict(candidate, preparationOnly=False), self.proof())
            with self.assertRaises(ValueError):
                settlement.receipt(Path(folder) / 'receipts', dict(candidate, assetId='asset'), self.proof())

    def test_only_data_free_residue_is_accepted(self):
        guard.verify_retired_ipc_observation(self.observation())
        for entry in [dict(path='EGH_one/recording.mp4', kind='file'),
                      dict(path='empty-file', kind='file'), dict(path='link', kind='symlink'),
                      dict(path='NE_one/unknown.sock', kind='special', specialType='socket'),
                      dict(path='other', kind='directory')]:
            observed = self.observation()
            observed['roots'][0]['entries'].append(entry)
            with self.subTest(entry=entry), self.assertRaises(ValueError):
                guard.verify_retired_ipc_observation(observed)

    def test_missing_partial_live_and_backup_evidence_hold(self):
        for key, value in [('issues', ['process_inventory_incomplete']), ('processes', [{'pid': 3}]),
                           ('openFiles', [{'deleted': True}]), ('unixSockets', [{'owners': []}])]:
            observed = self.observation()
            observed[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                guard.verify_retired_ipc_observation(observed)
        observed = self.observation()
        del observed['issues']
        with self.assertRaises(ValueError):
            guard.verify_retired_ipc_observation(observed)
        observed = self.observation()
        observed['roots'][1]['entries'] = [dict(path='EGH_one', kind='directory')]
        with self.assertRaises(ValueError):
            guard.verify_retired_ipc_observation(observed)

    def test_receipt_replay_is_stable_and_bound_to_incarnation(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / 'receipts'
            first = settlement.receipt(root, self.candidate(), self.proof())
            changed_time = self.proof()
            changed_time['storage']['finishedAt'] = 'later'
            self.assertEqual(first, settlement.receipt(root, self.candidate(), changed_time))
            self.assertTrue(first['storageReceipt'].startswith('node-storage-v1:'))
            self.assertEqual(1, len(list(root.iterdir())))
            os.link(next(root.iterdir()), root / '.settlement-crash-alias')
            self.assertEqual(first, settlement.receipt(root, self.candidate(), changed_time))
            changed = self.proof()
            changed['containers']['a']['State']['StartedAt'] = 'replacement'
            with self.assertRaisesRegex(ValueError, 'incarnation'):
                settlement.receipt(root, self.candidate(), changed)

    def test_corrupt_or_public_receipt_does_not_get_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / 'receipts'
            settlement.receipt(root, self.candidate(), self.proof())
            file = next(root.iterdir())
            file.write_text('{')
            with self.assertRaises(ValueError):
                settlement.receipt(root, self.candidate(), self.proof())
            self.assertEqual('{', file.read_text())
            file.chmod(0o644)
            with self.assertRaisesRegex(ValueError, 'Private'):
                settlement.receipt(root, self.candidate(), self.proof())

    def test_failed_delivery_retries_same_receipt_after_reobservation(self):
        calls = []
        identity = dict(nodeId='ND_one', generation='boot', dropletId='123')
        def request(method, path, body):
            if method == 'GET':
                return [self.candidate()]
            calls.append(copy.deepcopy(body))
            if len(calls) == 1:
                raise TimeoutError('uncertain response')
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(TimeoutError):
                settlement.deliver(request, identity, self.proof, Path(folder) / 'receipts')
            self.assertEqual(1, settlement.deliver(request, identity, self.proof, Path(folder) / 'receipts'))
            self.assertEqual(calls[0], calls[1])

    def test_foreign_candidate_and_failed_physical_check_never_post(self):
        for foreign in (True, False):
            calls = []
            def request(method, path, body):
                calls.append(method)
                return [dict(self.candidate(), nodeId='other') if foreign else self.candidate()]
            def failed():
                raise ValueError('retained recording bytes')
            with tempfile.TemporaryDirectory() as folder, self.assertRaises(ValueError):
                settlement.deliver(request, dict(nodeId='ND_one', generation='boot', dropletId='123'),
                                   failed, Path(folder) / 'receipts')
            self.assertEqual(['GET'], calls)


if __name__ == '__main__':
    unittest.main()
