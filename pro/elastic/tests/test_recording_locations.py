import importlib.util
import json
from pathlib import Path
import unittest


spec = importlib.util.spec_from_file_location('recording_locations', Path(__file__).resolve().parents[1] / 'report-recording-locations.py')
reporter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reporter)


class RecordingLocationsTest(unittest.TestCase):
    def job(self, job='EG_one', handler='EGH_one', service='NE_live'):
        return json.dumps({'nodeID': service, 'egressID': job, 'handlerID': handler})

    def candidate(self, job='EG_one'):
        return dict(runtimeId='class', generation=1, nativeGeneration='generation', creationAttemptId='creation',
                    recordingAttemptId='recording', partId='part', roomSid='RM_one', egressId=job)

    def test_only_same_service_structured_handler_mapping_is_accepted(self):
        logs = 'unstructured EG_wrong\n' + self.job(service='NE_previous') + '\n' + self.job()
        self.assertEqual({'EG_one': 'EGH_one'}, reporter.logged_jobs(logs, 'NE_live'))
        with self.assertRaisesRegex(ValueError, 'Ambiguous'):
            reporter.logged_jobs(self.job() + '\n' + self.job(handler='EGH_other'), 'NE_live')
        with self.assertRaises(ValueError):
            reporter.logged_jobs(self.job(job='../other'), 'NE_live')
        with self.assertRaisesRegex(ValueError, 'Ambiguous'):
            reporter.logged_jobs(self.job() + '\n' + self.job(job='EG_other'), 'NE_live')

    def test_reports_exact_candidate_without_settlement_or_scope_fields(self):
        calls, checked = [], []
        def request(method, path, body):
            calls.append((method, path, body))
            if method == 'GET':
                return {'candidates': [dict(self.candidate(), untrusted='ignore'), self.candidate('EG_elsewhere')], 'nextCursor': None}
            return {}
        self.assertEqual(1, reporter.publish(request, {'nodeId': 'ND_one', 'nodeGeneration': 'boot', 'dropletId': '1'},
                                             {'EG_one': 'EGH_one'}, lambda: checked.append(True)))
        self.assertEqual([True], checked)
        self.assertEqual('recording-location', calls[1][1])
        self.assertEqual(set(reporter.IDENTITY) | {'nodeId', 'nodeGeneration', 'dropletId', 'observedAt'}, set(calls[1][2]))

    def test_incarnation_change_prevents_post(self):
        def request(method, path, body):
            self.assertEqual('GET', method)
            return {'candidates': [self.candidate()], 'nextCursor': None}
        def changed():
            raise ValueError('changed')
        with self.assertRaisesRegex(ValueError, 'changed'):
            reporter.publish(request, {}, {'EG_one': 'EGH_one'}, changed)

    def test_repeated_cursor_and_missing_identity_hold(self):
        with self.assertRaisesRegex(ValueError, 'cursor'):
            reporter.publish(lambda *args: {'candidates': [], 'nextCursor': 'same'}, {}, {}, lambda: None)
        with self.assertRaisesRegex(ValueError, 'Incomplete'):
            reporter.publish(lambda *args: {'candidates': [{}]}, {}, {}, lambda: None)

    def container(self):
        return {'Name': '/egress', 'Id': 'a' * 64, 'Image': reporter.IMAGE,
                'Config': {'Image': 'docker.io/openvidu/egress@' + reporter.IMAGE},
                'State': {'StartedAt': '2026-09-23T12:00:00Z', 'Running': True, 'Restarting': False, 'Pid': 12},
                'Mounts': [{'Destination': '/home/egress', 'Source': '/opt/openvidu/data/egress_data/home/egress',
                            'Type': 'bind', 'RW': True}]}

    def test_container_requires_exact_image_boot_and_unshadowed_storage(self):
        reporter.container_identity(self.container(), 0)
        for mutation in ('image', 'boot', 'mount', 'stopped'):
            node = self.container()
            boot = 0
            if mutation == 'image': node['Image'] = 'other'
            if mutation == 'boot': boot = 2000000000
            if mutation == 'mount': node['Mounts'].append(dict(node['Mounts'][0], Destination='/home/egress/tmp'))
            if mutation == 'stopped': node['State']['Running'] = False
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                reporter.container_identity(node, boot)


if __name__ == '__main__':
    unittest.main()
