"""Offline CPU calibration for the existing additive capacity planner, not a scaler.

Never publishes fleet evidence, marks a profile qualified, or changes cloud resources.
Use a full measured room envelope: these experiments do not establish a linear
per-student slope, nor the capacity of several small rooms packed together.
"""
import argparse
import hashlib
import json
from pathlib import Path

EVIDENCE = Path(__file__).with_name('capacity-benchmark-20260923.json')
DIMENSIONS = {'cpuMillis', 'memoryBytes', 'ingressBytesPerSecond',
              'egressBytesPerSecond', 'packetsPerSecond', 'diskBytes'}


def recording_storage(policy, durations_minutes):
    """Planning allowance, not a provider-enforced bitrate or a timer-based release.

    Retain the reviewed reference rate without rounding it down. Each recording
    includes its own overrun buffer; the node reserve is charged once. Existing
    files/system usage must still be accounted for separately by live admission.
    """
    if not durations_minutes or any(type(v) is not int or v <= 0 for v in durations_minutes):
        raise ValueError('Positive scheduled minutes required for every recording')
    total = policy['nodeReserveBytes']
    reference = policy['referenceDurationSeconds']
    for minutes in durations_minutes:
        seconds = (minutes + policy['overrunBufferMinutes']) * 60
        copy_bytes = (policy['bytesPerCopy'] * seconds + reference - 1) // reference
        total += copy_bytes * policy['copiesPerObligation']
    return total


def recommend(expected_people, workload_id, *, room_count=1, recording_jobs=1,
              recording_durations_minutes=None):
    """Evidence-led hardware review, deliberately separate from admission arithmetic.

    Charge the maximum permitted media profile, not currently muted devices. Total
    node CPU already includes recording: adding another recording cost to these
    observed percentages would double-count it. The allocator's independent minimum
    remains visible below; empirical headroom does not silently override that rule.
    """
    if any(type(v) is not int or v < 1 for v in (expected_people, room_count, recording_jobs)):
        raise ValueError('Positive integer full attendance, room and recording counts required')
    evidence = json.loads(EVIDENCE.read_text())
    model = evidence['empiricalModel']
    result = dict(evidenceVersion=evidence['evidenceVersion'], expectedPeakPeople=expected_people,
                  qualified=False, automaticProvisioningEnabled=False, recommendedNodeType=None,
                  decision='workload_not_benchmarked', unresolvedGates=evidence['unresolvedGates'])
    if workload_id != model['workloadId']:
        return result
    result.update(sustainedEvidence=model['sustainedEvidence'], arrivalEvidence=model['arrivalEvidence'],
                  concurrentOverload=model['concurrentOverload'])
    storage = model['recordingStoragePolicy']
    # Audience/CPU evidence can still be reviewed without a schedule, but never
    # silently turn a missing duration into a four-hour disk reservation.
    if recording_durations_minutes is not None and len(recording_durations_minutes) != recording_jobs:
        raise ValueError('Supply one scheduled duration per recording')
    result['recordingStorageAllowanceBytes'] = (recording_storage(storage, recording_durations_minutes)
                                               if recording_durations_minutes is not None else None)
    result['recordingStorageStatus'] = ('scheduled_duration_plus_buffer' if recording_durations_minutes is not None
                                        else 'schedule_duration_required')
    result['scheduledRecordingMinutes'] = recording_durations_minutes
    result['storagePolicy'] = storage
    # We measured separate-room overhead and concentrated recorder overload, not a
    # linear per-participant curve. Even two small rooms need a separate packing review.
    if room_count != 1 or recording_jobs != 1:
        result['decision'] = 'concurrent_room_or_recording_placement_review_required'
        return result
    band = next((b for b in model['planningBands'] if expected_people <= b['maxPeople']), None)
    if band is None:
        result['decision'] = 'audience_exceeds_evidence_ceiling'
        return result
    node_type = band['nodeType']
    assessment = calibrate(node_type, expected_people)
    result.update(recommendedNodeType=node_type, bandCeilingPeople=band['maxPeople'],
                  decision='hardware_candidate_not_admission_permission',
                  basis=model['bandMeaning'], allocatorAssessment=assessment,
                  recordingAccountingConflict=not assessment['cpuArithmeticFits'],
                  measuredStages=[s for s in model['stages'] if s['nodeType'] == node_type])
    return result


def calibrate(node_type, expected_people, headroom_percent=20, recording_cpu_millis=2000):
    if (type(expected_people) is not int or expected_people < 1
            or type(headroom_percent) is not int or not 1 <= headroom_percent < 100
            or type(recording_cpu_millis) is not int or recording_cpu_millis < 2000):
        raise ValueError('Positive full attendance, explicit headroom and two-core recording minimum required')
    evidence = json.loads(EVIDENCE.read_text())
    if node_type not in evidence['nodes']:
        raise ValueError('No matching dedicated hardware benchmark; shared CPU is not interchangeable')
    node = evidence['nodes'][node_type]
    cpu_budget = node['physicalCpuMillis'] * (100 - headroom_percent) // 100
    forwarding = node['forwardingEnvelopeCpuMillis']
    room_budget = cpu_budget - recording_cpu_millis
    # POOL_ADMISSION_V1 retains one recorder envelope per node, not per viewer.
    # A class that cannot fit an EMPTY node cannot be rescued by more identical nodes.
    fits = expected_people <= node['planningCeilingPeople'] and forwarding <= room_budget
    reason = ('audience_exceeds_evidence_ceiling' if expected_people > node['planningCeilingPeople']
              else 'forwarding_plus_recording_exceeds_budget' if forwarding > room_budget
              else 'cpu_arithmetic_fits_review_required')
    return dict(evidenceVersion=evidence['evidenceVersion'], nodeType=node_type,
                expectedPeakPeople=expected_people, planningCeilingPeople=node['planningCeilingPeople'],
                headroomPercent=headroom_percent, cpuBudgetMillis=cpu_budget,
                fixedRoomDemandCpuMillis=forwarding, perPersonDemandCpuMillis=0,
                recordingDemandCpuMillis=recording_cpu_millis,
                remainingCpuMillis=room_budget-forwarding,
                cpuArithmeticFits=fits, decision=reason, qualified=False,
                automaticProvisioningEnabled=False,
                unresolvedGates=evidence['unresolvedGates'])


def candidate(profile, assessment):
    """Patch only the existing profile's CPU fields; retain reviewed non-CPU budgets.

    Output remains disabled even when the input was qualified. Changing hardware,
    workload or limits is a new profile, never an in-place edit of live reservations.
    """
    result = json.loads(json.dumps(profile, allow_nan=False))
    if not assessment['cpuArithmeticFits']:
        raise ValueError(assessment['decision'])
    if result.get('recordingCapacityMode') != 'POOL_ADMISSION_V1':
        raise ValueError('This calibration uses the existing per-node recorder admission model')
    for key in ('resourceBudgets', 'fixedRoomDemand', 'perPersonDemand', 'recordingDemand'):
        if (not isinstance(result.get(key), dict) or set(result[key]) != DIMENSIONS
                or any(type(v) is not int or v < 0 for v in result[key].values())):
            raise ValueError('Existing complete resource vectors required; non-CPU capacity is not inferred')
    if (result.get('nodeType') != assessment['nodeType']
            or result['recordingDemand']['cpuMillis'] != assessment['recordingDemandCpuMillis']):
        raise ValueError('Use a matching hardware/recording template; do not relabel another node profile')
    result.update(qualified=False, evidenceVersion=assessment['evidenceVersion'],
                  maxSingleRoomPeople=assessment['expectedPeakPeople'],
                  roomCpuIncludesRecording=assessment.get('roomCpuIncludesRecording', False))
    result['resourceBudgets']['cpuMillis'] = assessment['cpuBudgetMillis']
    result['fixedRoomDemand']['cpuMillis'] = assessment['fixedRoomDemandCpuMillis']
    result['perPersonDemand']['cpuMillis'] = 0
    result.pop('fingerprint', None)
    digest = hashlib.sha256(json.dumps(result, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
    result['fingerprint'] = assessment['evidenceVersion']+'-'+assessment['nodeType']+'-'+digest[:16]
    return result


def calibrate_combined(node_type, expected_people, headroom_percent=10, recording_cpu_millis=2000):
    """Reviewed joint CPU envelope; never remove provider recording-start checks.

    The separate recording vector still charges non-CPU resources. Like the existing
    admission mode this provisions aggregate headroom, not static recorder slots.
    """
    result = calibrate(node_type, expected_people, headroom_percent, recording_cpu_millis)
    evidence = json.loads(EVIDENCE.read_text())
    node = evidence['nodes'][node_type]
    if 'combinedEnvelopeCpuMillis' not in node:
        raise ValueError('No reviewed combined CPU envelope for this hardware')
    demand = node['combinedEnvelopeCpuMillis']
    fits = expected_people <= node['planningCeilingPeople'] and recording_cpu_millis <= demand <= result['cpuBudgetMillis']
    result.update(evidenceVersion=evidence['evidenceVersion'] + '-combined-v1', roomCpuIncludesRecording=True,
                  fixedRoomDemandCpuMillis=demand, remainingCpuMillis=result['cpuBudgetMillis'] - demand,
                  cpuArithmeticFits=fits, combinedEnvelopeBasis=node['combinedEnvelopeBasis'],
                  decision='combined_cpu_fits_review_required' if fits else 'combined_cpu_or_audience_exceeds_budget')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--node', choices=('c-4', 'c-8'))
    parser.add_argument('--recommend-workload', help='Exact benchmark workload ID; emits hardware review, not a live profile')
    parser.add_argument('--rooms', type=int, default=1)
    parser.add_argument('--recordings', type=int, default=1)
    parser.add_argument('--duration-minutes', type=int, action='append',
                        help='Scheduled recording minutes; repeat once per recording. Adds 30-minute overrun budget.')
    parser.add_argument('--combined-cpu', action='store_true', help='Use explicit measured combined CPU, not forwarding plus recorder CPU')
    parser.add_argument('--people', type=int, required=True, help='Full enrollment plus teachers/other attendees')
    parser.add_argument('--headroom-percent', type=int, help='Explicit policy:20%% additive,10%% combined by default; not a measured guarantee')
    parser.add_argument('--recording-cpu-millis', type=int, default=2000)
    parser.add_argument('--profile', type=Path, help='Optional existing profile; emits a disabled candidate only')
    args = parser.parse_args()
    if args.recommend_workload:
        if args.node or args.profile or args.combined_cpu or args.headroom_percent is not None or args.recording_cpu_millis != 2000:
            parser.error('Hardware review cannot override or emit an allocator profile')
        try:
            result = recommend(args.people, args.recommend_workload, room_count=args.rooms, recording_jobs=args.recordings,
                               recording_durations_minutes=args.duration_minutes)
        except ValueError as error:
            parser.error(str(error))
    else:
        if not args.node or args.rooms != 1 or args.recordings != 1 or args.duration_minutes is not None:
            parser.error('Calibration requires --node and the single-recorder model')
        calibration = calibrate_combined if args.combined_cpu else calibrate
        headroom = args.headroom_percent if args.headroom_percent is not None else (10 if args.combined_cpu else 20)
        result = calibration(args.node, args.people, headroom, args.recording_cpu_millis)
        if args.profile:
            result = candidate(json.loads(args.profile.read_text()), result)
    print(json.dumps(result, indent=2, allow_nan=False))
