import copy
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from test_recording_job_observation import samples, process, directory

spec = importlib.util.spec_from_file_location('capacity_footprint',
    Path(__file__).resolve().parents[1] / 'recorder-capacity-footprint.py')
capacity = importlib.util.module_from_spec(spec)
spec.loader.exec_module(capacity)


def sample_pair():
    active, idle = samples()
    for value in (active, idle):
        value['recorderServiceId'] = 'NE_service'
    return active, idle


class RecorderCapacityFootprintTest(unittest.TestCase):
    def test_active_and_finalizing_foreign_job_remains_charged(self):
        active, idle = sample_pair()
        self.assertEqual(['EG_a'], capacity.footprint(active)['jobIds'])
        self.assertTrue(capacity.footprint(active)['complete'])
        # One clean observation is not enough, regardless of provider status.
        self.assertEqual(['EG_a'], capacity.footprint(idle)['jobIds'])
        finalizing = copy.deepcopy(idle)
        finalizing['observation']['roots'][0]['entries'].append(directory('EG_a', 7))
        self.assertFalse(capacity.footprint(finalizing, idle)['complete'])
        self.assertEqual(['EG_a'], capacity.footprint(finalizing, idle)['jobIds'])

    def test_two_physical_idle_samples_clear_only_capacity_charge(self):
        _, first = sample_pair()
        later = copy.deepcopy(first)
        later['observation'].update(startedAt='2026-09-24T21:37:23Z', finishedAt='2026-09-24T21:37:24Z')
        result = capacity.footprint(later, first)
        self.assertTrue(result['complete'])
        self.assertEqual([], result['jobIds'])
        self.assertNotIn('settlementAuthorized', result)
        self.assertNotIn('assetId', result)
        self.assertEqual(['EG_a'], capacity.footprint(first, first)['jobIds'])

    def test_backup_unknown_paths_detached_processes_and_deleted_files_hold(self):
        mutations = [
            lambda s: s['observation']['roots'][1]['entries'].append(dict(path='recovery.mp4', kind='file')),
            lambda s: s['observation']['roots'][0]['entries'].append(directory('EG_unknown', 99)),
            lambda s: s['processProvenance'].append(dict(process(99, 900), name='chrome', parentPid=1)),
            lambda s: s['observation']['openFiles'].append(dict(target='/home/egress/backup_storage/lost (deleted)')),
        ]
        for mutate in mutations:
            active, _ = sample_pair()
            mutate(active)
            with self.subTest(mutation=mutate):
                self.assertFalse(capacity.footprint(active)['complete'])
                self.assertEqual(['EG_a'], capacity.footprint(active)['jobIds'])

    def test_proved_exclusion_localizes_backup_finalization_without_creating_cleanup_credit(self):
        active, idle = sample_pair()
        for sample in (active, idle):
            sample['observation']['roots'][1]['entries'].append(dict(path='pending.mp4', kind='file'))
            sample['observation']['openFiles'].append(dict(target='/home/egress/backup_storage/pending.mp4 (deleted)'))
            self.assertFalse(capacity.footprint(sample)['complete'])
            result = capacity.footprint(sample, excluded=True)
            self.assertTrue(result['complete'])
            self.assertEqual(['EG_a'], result['jobIds'])
        active['observation']['roots'][0]['entries'].append(directory('EG_unknown', 99))
        self.assertFalse(capacity.footprint(active, excluded=True)['complete'])

    def test_changed_recorder_cannot_reuse_idle_history(self):
        _, first = sample_pair()
        later = copy.deepcopy(first)
        later['observation'].update(startedAt='2026-09-24T21:37:23Z', finishedAt='2026-09-24T21:37:24Z')
        later['recorder']['State']['StartedAt'] = '2026-09-24T21:37:00Z'
        self.assertEqual(['EG_a'], capacity.footprint(later, first)['jobIds'])

    def test_local_publication_does_not_call_business_or_provider_apis(self):
        _, first = sample_pair()
        later = copy.deepcopy(first)
        later['observation'].update(startedAt='2026-09-24T21:37:23Z', finishedAt='2026-09-24T21:37:24Z')
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            capacity.publish(first, lambda: None, root)
            capacity.publish(later, lambda: None, root)
            result = capacity.jobs.settlement.private_json(root / '.courseultra-capacity-footprint.json')
            self.assertEqual([], result['jobIds'])
            self.assertEqual(first['observation']['bootId'], result['bootId'])

    def test_fresh_recorder_without_historical_jobs_can_prove_idle(self):
        _, idle = sample_pair()
        idle['jobMapping'] = []
        idle['observation']['roots'][0]['entries'] = [e for e in idle['observation']['roots'][0]['entries']
                                                     if e['path'].startswith('NE_service')]
        self.assertTrue(capacity.footprint(idle)['complete'])
        self.assertEqual([], capacity.footprint(idle)['jobIds'])

    def test_failed_physical_probe_reports_an_explicit_unavailable_worker(self):
        active, _ = sample_pair()
        with patch.object(capacity, '_observe_local', side_effect=ValueError('partial evidence')):
            result = capacity.observe_local(active['recorder'], 'boot', Path('/unused'), Path('/unused'))
        self.assertFalse(result['complete'])
        self.assertEqual([], result['jobIds'])
        self.assertEqual(active['recorder']['Id'], result['containerId'])

    def publish_result(self, root, sample):
        capacity.publish(sample, lambda: None, root)
        return capacity.jobs.settlement.private_json(root / '.courseultra-capacity-footprint.json')

    def at(self, sample, minute, second):
        result = copy.deepcopy(sample)
        result['observation'].update(startedAt=f'2026-09-24T21:{minute:02}:{second:02}Z',
                                     finishedAt=f'2026-09-24T21:{minute:02}:{second+1:02}Z')
        return result

    def rename(self, value):
        if isinstance(value, dict): return {k: self.rename(v) for k, v in value.items()}
        if isinstance(value, list): return [self.rename(v) for v in value]
        if isinstance(value, str): return value.replace('EGH_a', 'EGH_b').replace('EG_a', 'EG_b')
        return value

    def test_38_exact_image_and_provenance_guards(self):
        active, idle = sample_pair()
        self.assertEqual('sha256:01a31780783080259b7f218f624e654dc30572be5b5f7999123ac0d98c259475', idle['recorder']['Image'])
        self.assertTrue(capacity.footprint(idle)['complete'])
        self.assertTrue(capacity.footprint(active)['complete'])
        for image in ('sha256:cd624db686006ced0b176849e4acf5feb3094c57f9b130e6bc71f819ed0c62d3',
                      'sha256:' + 'f' * 64, 'openvidu/egress:3.8.0'):
            changed = copy.deepcopy(idle)
            changed['recorder']['Image'] = image
            self.assertFalse(capacity.footprint(changed)['complete'])
        changed = copy.deepcopy(idle)
        changed['recorder']['Mounts'][0]['Source'] = '/unreviewed/storage'
        self.assertFalse(capacity.footprint(changed)['complete'])

    def test_cleanup_survives_new_managed_job_and_log_rotation_without_losing_unresolved_work(self):
        active, idle = sample_pair()
        later = self.at(idle, 37, 23)
        managed = self.at(self.rename(active), 37, 30)
        managed['jobMapping'].append(copy.deepcopy(idle['jobMapping'][0]))
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.assertEqual(['EG_a'], self.publish_result(root, idle)['jobIds'])
            self.assertEqual([], self.publish_result(root, later)['jobIds'])
            result = self.publish_result(root, managed)
            self.assertTrue(result['complete'])
            self.assertEqual(['EG_b'], result['jobIds'])
            rotated = self.at(managed, 37, 35)
            rotated['jobMapping'] = []
            result = self.publish_result(root, rotated)
            self.assertTrue(result['complete'])
            self.assertEqual(['EG_b'], result['jobIds'])
            finalizing = self.at(self.rename(idle), 37, 45)
            finalizing['jobMapping'] = []
            self.assertEqual(['EG_b'], self.publish_result(root, finalizing)['jobIds'])
            self.assertEqual([], self.publish_result(root, self.at(finalizing, 38, 20))['jobIds'])
            # Physical reappearance invalidates even a previously proven cleanup credit.
            self.assertEqual(['EG_a'], self.publish_result(root, self.at(active, 38, 30))['jobIds'])

    def test_history_bound_does_not_evict_unresolved_or_cleared_jobs(self):
        active, idle = sample_pair()
        with tempfile.TemporaryDirectory() as folder, patch.object(capacity, 'HISTORY_LIMIT', 1):
            root = Path(folder)
            self.publish_result(root, idle)
            self.publish_result(root, self.at(idle, 37, 23))
            with self.assertRaises(ValueError):
                self.publish_result(root, self.at(self.rename(active), 37, 30))

    def test_cleanup_credit_never_crosses_container_incarnation_or_conflicting_mapping(self):
        active, idle = sample_pair()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.publish_result(root, idle)
            self.publish_result(root, self.at(idle, 37, 23))
            changed = self.at(idle, 37, 30)
            changed['jobMapping'][0]['handlerID'] = 'EGH_conflict'
            with self.assertRaises(ValueError): self.publish_result(root, changed)
            changed = self.at(idle, 37, 30)
            changed['recorder']['State']['StartedAt'] = '2026-09-24T21:37:00Z'
            self.assertEqual(['EG_a'], self.publish_result(root, changed)['jobIds'])

    def test_failed_observation_and_old_samples_cannot_erase_unsettled_history(self):
        active, idle = sample_pair()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.publish_result(root, active)
            incomplete = self.at(idle, 37, 23)
            incomplete['observation']['roots'][1]['entries'].append(dict(path='recovery.mp4', kind='file'))
            result = self.publish_result(root, incomplete)
            self.assertFalse(result['complete'])
            self.assertEqual(['EG_a'], result['jobIds'])
            with self.assertRaises(ValueError): self.publish_result(root, active)
