import copy
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('benchmark', Path(__file__).resolve().parents[1] / 'capacity-benchmark.py')
benchmark = importlib.util.module_from_spec(spec)
spec.loader.exec_module(benchmark)


class BenchmarkTest(unittest.TestCase):
    workload = 'pion-3.8-two-360p15-cameras-one-1080p15-screen-audio-720p-recording'

    def test_empirical_four_cpu_choice_retains_accounting_conflict(self):
        result = benchmark.recommend(202, self.workload)
        self.assertEqual('c-4', result['recommendedNodeType'])
        self.assertTrue(result['recordingAccountingConflict'])
        self.assertFalse(result['qualified'])
        self.assertFalse(result['automaticProvisioningEnabled'])
        self.assertEqual(129, result['sustainedEvidence']['fullCohortMinutes'])
        self.assertEqual(4, result['sustainedEvidence']['dedicatedFourCpuNodes'])
        self.assertIsNone(result['recordingStorageAllowanceBytes'])
        self.assertEqual('schedule_duration_required', result['recordingStorageStatus'])
        self.assertIn('confounded', result['measuredStages'][0]['finding'])

    def test_band_boundaries_are_policy_not_interpolated_cpu(self):
        for people, expected in [(52, 'c-4'), (202, 'c-4'), (203, 'c-8'), (302, 'c-8'), (402, 'c-8')]:
            with self.subTest(people=people):
                result = benchmark.recommend(people, self.workload)
                self.assertEqual(expected, result['recommendedNodeType'])
                self.assertEqual(0, result['allocatorAssessment']['perPersonDemandCpuMillis'])
                self.assertFalse(result['qualified'])
        self.assertIsNone(benchmark.recommend(403, self.workload)['recommendedNodeType'])

    def test_cannot_pack_rooms_or_concentrate_recorders_from_single_room_evidence(self):
        for rooms, jobs in [(2, 2), (3, 3), (1, 2), (2, 1)]:
            with self.subTest(rooms=rooms, jobs=jobs):
                result = benchmark.recommend(102, self.workload, room_count=rooms, recording_jobs=jobs,
                                             recording_durations_minutes=[60] * jobs)
                self.assertIsNone(result['recommendedNodeType'])
                self.assertEqual('concurrent_room_or_recording_placement_review_required', result['decision'])
                self.assertEqual((6 * jobs + 8) * 1024**3, result['recordingStorageAllowanceBytes'])
                self.assertEqual([402, 102, 102], result['concurrentOverload']['roomPeople'])

    def test_changed_media_engine_or_hardware_workload_is_not_blessed(self):
        for workload in ['mediasoup', 'shared-cpu', '1080p-recording', '', None]:
            with self.subTest(workload=workload):
                self.assertEqual('workload_not_benchmarked', benchmark.recommend(202, workload)['decision'])

    def test_storage_correction_does_not_approve_two_recorders(self):
        result = benchmark.recommend(202, self.workload, recording_jobs=2, recording_durations_minutes=[60, 120])
        self.assertEqual(24 * 1024**3, result['recordingStorageAllowanceBytes'])
        self.assertEqual(30, result['storagePolicy']['overrunBufferMinutes'])
        self.assertEqual(2, result['storagePolicy']['copiesPerObligation'])
        self.assertFalse(result['qualified'])
        self.assertFalse(result['automaticProvisioningEnabled'])
        self.assertIsNone(result['recommendedNodeType'])
        self.assertEqual('concurrent_room_or_recording_placement_review_required', result['decision'])

    def test_duration_buffer_and_rounding_never_discount_longer_classes(self):
        one = benchmark.recommend(202, self.workload, recording_durations_minutes=[60])
        self.assertEqual(14 * 1024**3, one['recordingStorageAllowanceBytes'])
        four = benchmark.recommend(202, self.workload, recording_durations_minutes=[240])
        self.assertEqual(26 * 1024**3, four['recordingStorageAllowanceBytes'])
        policy = one['storagePolicy']
        rounded = benchmark.recording_storage(policy, [1]) - policy['nodeReserveBytes']
        self.assertGreaterEqual(rounded * 14400, 8589934592 * 31 * 60 * 2)
        self.assertGreater(benchmark.recording_storage(policy, [300]), four['recordingStorageAllowanceBytes'])
        for durations in [[], [0], [-1], [True], [1.5], [60, 60]]:
            with self.subTest(durations=durations), self.assertRaises(ValueError):
                benchmark.recommend(202, self.workload, recording_durations_minutes=durations)

    def test_invalid_recommendation_input(self):
        for people, rooms, jobs in [(True, 1, 1), (0, 1, 1), (202, 0, 1), (202, 1, False), (202, 1, 1.5)]:
            with self.subTest(people=people, rooms=rooms, jobs=jobs), self.assertRaises(ValueError):
                benchmark.recommend(people, self.workload, room_count=rooms, recording_jobs=jobs)

    def test_cli_review_cannot_accidentally_emit_live_profile(self):
        command = [sys.executable, str(Path(benchmark.__file__)), '--people', '202',
                   '--recommend-workload', self.workload]
        result = subprocess.run(command, capture_output=True, text=True, timeout=10)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual('c-4', json.loads(result.stdout)['recommendedNodeType'])
        for extra in [['--profile', 'unused.json'], ['--node', 'c-8'], ['--headroom-percent', '1']]:
            rejected = subprocess.run(command + extra, capture_output=True, text=True, timeout=10)
            self.assertEqual(2, rejected.returncode)
            self.assertEqual('', rejected.stdout)

    def test_cli_duration_is_explicit_and_validated_for_each_recording(self):
        command = [sys.executable, str(Path(benchmark.__file__)), '--people', '202',
                   '--recommend-workload', self.workload, '--recordings', '2']
        result = subprocess.run(command + ['--duration-minutes', '60', '--duration-minutes', '120'],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(24 * 1024**3, json.loads(result.stdout)['recordingStorageAllowanceBytes'])
        for durations in [['--duration-minutes', '60'], ['--duration-minutes', '0', '--duration-minutes', '60']]:
            result = subprocess.run(command + durations, capture_output=True, text=True, timeout=10)
            self.assertEqual(2, result.returncode)
            self.assertEqual('', result.stdout)

    def test_evidence_preserves_media_transition_and_arrival_patterns(self):
        model = json.loads(benchmark.EVIDENCE.read_text())['empiricalModel']
        stages = [s for s in model['stages'] if s['nodeType'] == 'c-4' and s['people'] == 302]
        self.assertEqual([1, 2], [s['cameras'] for s in stages])
        self.assertEqual([67.4, 80.4], [s['meanCpuPercent'] for s in stages])
        result = benchmark.recommend(202, self.workload)
        self.assertEqual(2, len(result['arrivalEvidence']))
        self.assertIn('offset20', result['arrivalEvidence'][0]['pattern'])

    def test_four_cpu_does_not_hide_existing_recording_accounting_conflict(self):
        result = benchmark.calibrate('c-4', 202)
        self.assertEqual(2232, result['fixedRoomDemandCpuMillis'])
        self.assertEqual(3200, result['cpuBudgetMillis'])
        self.assertEqual(-1032, result['remainingCpuMillis'])
        self.assertFalse(result['cpuArithmeticFits'])
        self.assertFalse(result['qualified'])

    def test_combined_cpu_is_explicit_and_does_not_remove_recording_estimate(self):
        result = benchmark.calibrate_combined('c-4', 202)
        self.assertTrue(result['cpuArithmeticFits'])
        self.assertTrue(result['roomCpuIncludesRecording'])
        self.assertEqual(3500, result['fixedRoomDemandCpuMillis'])
        self.assertEqual(3600, result['cpuBudgetMillis'])
        self.assertEqual(100, result['remainingCpuMillis'])
        self.assertEqual(2000, result['recordingDemandCpuMillis'])
        self.assertFalse(result['qualified'])
        self.assertFalse(benchmark.calibrate_combined('c-4', 203)['cpuArithmeticFits'])
        self.assertFalse(benchmark.calibrate_combined('c-4', 202, 20)['cpuArithmeticFits'])
        self.assertFalse(benchmark.calibrate_combined('c-4', 202, 10, 3600)['cpuArithmeticFits'])
        with self.assertRaises(ValueError):
            benchmark.calibrate_combined('c-8', 402)
        with self.assertRaises(ValueError):
            benchmark.calibrate_combined('c-4', 202, 10, 1999)

    def test_combined_candidate_preserves_non_cpu_and_gets_distinct_fingerprint(self):
        profile = dict(qualified=True, nodeType='c-4', recordingCapacityMode='POOL_ADMISSION_V1')
        for key in ('resourceBudgets', 'fixedRoomDemand', 'perPersonDemand', 'recordingDemand'):
            profile[key] = dict.fromkeys(benchmark.DIMENSIONS, 0)
        profile['recordingDemand'].update(cpuMillis=2000, diskBytes=24 * 1024**3)
        profile['resourceBudgets']['memoryBytes'] = 6 * 1024**3
        result = benchmark.candidate(profile, benchmark.calibrate_combined('c-4', 202))
        self.assertTrue(result['roomCpuIncludesRecording'])
        self.assertFalse(result['qualified'])
        self.assertEqual(24 * 1024**3, result['recordingDemand']['diskBytes'])
        self.assertEqual(6 * 1024**3, result['resourceBudgets']['memoryBytes'])
        self.assertIn('combined-v1', result['fingerprint'])

    def test_eight_cpu_uses_fixed_measured_envelope_not_mean_or_student_slope(self):
        result = benchmark.calibrate('c-8', 402)
        self.assertTrue(result['cpuArithmeticFits'])
        self.assertEqual(3255, result['fixedRoomDemandCpuMillis'])
        self.assertEqual(1145, result['remainingCpuMillis'])
        self.assertEqual(0, result['perPersonDemandCpuMillis'])
        self.assertFalse(result['automaticProvisioningEnabled'])
        small = benchmark.calibrate('c-8', 52)
        self.assertEqual(result['fixedRoomDemandCpuMillis'], small['fixedRoomDemandCpuMillis'])

    def test_failed_or_unmeasured_sizes_are_not_promoted(self):
        for node, people in [('c-4', 302), ('c-4', 402), ('c-8', 403), ('c-8', 606)]:
            with self.subTest(node=node, people=people):
                self.assertFalse(benchmark.calibrate(node, people)['cpuArithmeticFits'])
        with self.assertRaises(ValueError):
            benchmark.calibrate('s-4vcpu-8gb', 202)

    def test_invalid_input_and_lower_recording_allowance_rejected(self):
        for kwargs in [dict(expected_people=True), dict(expected_people=0), dict(expected_people=202, headroom_percent=0),
                       dict(expected_people=202, headroom_percent=100), dict(expected_people=202, recording_cpu_millis=1999)]:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                benchmark.calibrate('c-4', **kwargs)

    def test_candidate_preserves_other_dimensions_and_never_activates(self):
        profile = dict(qualified=True, nodeType='c-8', recordingCapacityMode='POOL_ADMISSION_V1',
                       resourceBudgets=dict(cpuMillis=8000, diskBytes=123),
                       fixedRoomDemand=dict(cpuMillis=1, memoryBytes=456),
                       perPersonDemand=dict(cpuMillis=10), recordingDemand=dict(cpuMillis=2000, diskBytes=789))
        for key in ('resourceBudgets', 'fixedRoomDemand', 'perPersonDemand', 'recordingDemand'):
            profile[key] = {**dict.fromkeys(benchmark.DIMENSIONS, 0), **profile[key]}
        original = copy.deepcopy(profile)
        candidate = benchmark.candidate(profile, benchmark.calibrate('c-8', 402))
        self.assertEqual(original, profile)
        self.assertFalse(candidate['qualified'])
        self.assertEqual(402, candidate['maxSingleRoomPeople'])
        self.assertEqual(6400, candidate['resourceBudgets']['cpuMillis'])
        self.assertEqual(123, candidate['resourceBudgets']['diskBytes'])
        self.assertEqual(789, candidate['recordingDemand']['diskBytes'])
        changed = benchmark.candidate(profile, benchmark.calibrate('c-8', 402, headroom_percent=25))
        self.assertNotEqual(candidate['fingerprint'], changed['fingerprint'])
        with self.assertRaises(ValueError):
            benchmark.candidate(profile, benchmark.calibrate('c-4', 202))
        profile['nodeType'] = 'c-4'
        with self.assertRaises(ValueError):
            benchmark.candidate(profile, benchmark.calibrate('c-8', 402))

    def test_incomplete_non_cpu_template_is_not_invented(self):
        profile = dict(nodeType='c-8', recordingCapacityMode='POOL_ADMISSION_V1',
                       resourceBudgets=dict(cpuMillis=8000))
        with self.assertRaises(ValueError):
            benchmark.candidate(profile, benchmark.calibrate('c-8', 402))


if __name__ == '__main__':
    unittest.main()
