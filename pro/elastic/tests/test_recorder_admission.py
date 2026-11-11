"""Synthetic parsing/contract tests, not live recorder qualification."""
import unittest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from recorder_admission import admission_metrics, conservative_browser_cost, validate_combined_cpu_policy
import copy


class RecorderAdmissionTest(unittest.TestCase):
    def test_combined_policy_requires_global_load_balancing_and_startup_headroom(self):
        descriptor = {'operatingProfile': {'profile': {'roomCpuIncludesRecording': True, 'recordingDemand': {'cpuMillis': 2000}}}}
        config = {'openvidu': {'use_global_cpu_monitoring': True, 'allocation_strategy': 'cpuload'},
                  'cpu_cost': {'max_cpu_utilization': .8, 'room_composite_cpu_cost': 2, 'web_cpu_cost': 2}}
        validate_combined_cpu_policy(config, descriptor)
        for section, key, value in [('openvidu', 'use_global_cpu_monitoring', False),
                                    ('openvidu', 'allocation_strategy', 'binpack'),
                                    ('cpu_cost', 'max_cpu_utilization', .9),
                                    ('cpu_cost', 'max_cpu_utilization', float('nan')),
                                    ('cpu_cost', 'room_composite_cpu_cost', 1.5),
                                    ('cpu_cost', 'room_composite_cpu_cost', 3),
                                    ('cpu_cost', 'web_cpu_cost', 1)]:
            changed = copy.deepcopy(config); changed[section][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                validate_combined_cpu_policy(changed, descriptor)
        validate_combined_cpu_policy({}, {})  # Existing non-combined descriptors unchanged.
        descriptor['operatingProfile']['profile']['roomCpuIncludesRecording'] = 'true'
        with self.assertRaises(ValueError):
            validate_combined_cpu_policy(config, descriptor)

    def metrics(self):
        return '\n'.join(f'{name}{{cluster_id="",node_id="NE_test"}} {value}' for name, value in (
            ('livekit_egress_can_accept_request', 1), ('livekit_egress_is_disabled', 0),
            ('livekit_egress_is_terminating', 0)))

    def test_positive_same_service(self):
        self.assertEqual({'nodeId': 'NE_test', 'acceptingRequests': True}, admission_metrics('# test\n' + self.metrics()))

    def test_known_busy_is_not_missing_or_unhealthy_evidence(self):
        self.assertEqual({'nodeId': 'NE_test', 'acceptingRequests': False},
                         admission_metrics(self.metrics().replace('} 1', '} 0')))

    def test_idle_alone_is_not_admission(self):
        with self.assertRaises(ValueError):
            admission_metrics('livekit_egress_available{cluster_id="",node_id="NE_test"} 1')

    def test_disabled_or_terminating(self):
        for value in (self.metrics().replace('} 0', '} 1', 1),
                      self.metrics().rsplit('} 0', 1)[0] + '} 1'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                admission_metrics(value)

    def test_draining_metrics_are_separate_from_normal_admission_and_still_strict(self):
        draining = self.metrics().replace('} 1', '} 0').replace('is_disabled{cluster_id="",node_id="NE_test"} 0', 'is_disabled{cluster_id="",node_id="NE_test"} 1').replace('is_terminating{cluster_id="",node_id="NE_test"} 0', 'is_terminating{cluster_id="",node_id="NE_test"} 1')
        with self.assertRaises(ValueError): admission_metrics(draining)
        self.assertEqual(dict(nodeId='NE_test', acceptingRequests=False, disabled=True, terminating=True), admission_metrics(draining, allow_draining=True))
        with self.assertRaises(ValueError): admission_metrics(draining + '\n' + draining, allow_draining=True)

    def test_duplicate_mixed_service_stale_timestamp_and_unknown_labels(self):
        for value in (self.metrics() + '\n' + self.metrics(),
                      self.metrics().replace('NE_test', 'NE_other', 1),
                      self.metrics() + ' 1234567890',
                      self.metrics().replace('cluster_id=""', 'cluster_id="",extra="x"'),
                      self.metrics().replace('NE_test', 'EG_job'),
                      self.metrics().replace('} 1', '} NaN')):
            with self.subTest(value=value), self.assertRaises(ValueError):
                admission_metrics(value)

    def test_cost_contract(self):
        for web in (2, 3):
            self.assertTrue(conservative_browser_cost({'room_composite_cpu_cost': 2, 'web_cpu_cost': web}))
        for web in (1, True, 0, float('nan'), float('inf'), None):
            with self.subTest(web=web), self.assertRaises(ValueError):
                conservative_browser_cost({'room_composite_cpu_cost': 2, 'web_cpu_cost': web})


if __name__ == '__main__':
    unittest.main()
