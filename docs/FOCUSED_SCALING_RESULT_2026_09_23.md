# Focused scaling result — 23 September 2026

## Decision

Not yet approved for production rollout. This bounded functional run established
two-room placement, fresh-node bootstrap and recording continuity, but automatic
idle deletion stopped at recorder settlement. Whole-fleet test cleanup is not a
substitute for that missing pass. No new 200/600-person capacity claim is made.

## Observed results

- OpenVidu 3.8/Pion; two fresh c-8 media nodes, unchanged isolated shared-CPU
  master; two real-browser classes with eight participants each. AWS browser
  workers were not CPU-bound. Recordings were 720p, not 1080p.
- The second node completed cold bootstrap in approximately three minutes and
  inherited repository-backed readiness fixes. Classes occupied different nodes.
- Five webinar arrivals completed in 2.070–2.141 seconds; six course arrivals in
  2.269–4.249 seconds. A deliberate reload/rejoin and microphone toggle succeeded.
- Concurrent teacher starts produced one recording, not duplicate recordings;
  the losing start request recovered from a temporary locked response.
- Both recordings reached EGRESS_COMPLETE without provider errors. Archived
  files passed SHA-256 verification and full-file decoding. Teacher playback
  passed for both; course-student playback passed. Webinar-student replay remained
  unavailable before its scheduled end, so that case was not counted as passed.
- Occupied removal was denied. The idle scale-in path selected and excluded a
  node and gracefully stopped its media processes (exit 0, no OOM). Physical
  recording/recovery storage proof passed after narrow helper corrections.
- Automatic deletion did not complete: the application rejected settlement.
  Local reproduction found an offset timestamp parsing defect and inappropriate
  dependence on a volatile pool observation after durable exclusion. Corrected
  backend regressions passed locally; live verification remains outstanding.

The final backend correction is commit
`650af2ee01f79631b578ef597153cf95589bd075` on `ruchir/live-scaling-release`
in `courseultra-scaling-release-backend`: 288 tests across 19 suites passed,
and the exact preserved producer attestation passed locally on Java 11. It was
not deployed in this window; the previously packaged jar must not be labelled
with this commit. Legacy exclusions without a durable binding still require
matching inventory; rollback must preserve all reservations and evidence.

## Corrections and limits

Infrastructure changes include fresh-node installation fixes, canonical mount
ordering for identity comparisons, and normalization of the systemd probe's
trailing newline. These do not relax identity, storage or restart-fence checks.
Backend recording-owner capture was corrected for concentration mode.

The playback harness initially blocked the test's own CDN. Its scoped origin
allowlist correction enabled playback verification; the initial failure remains
in evidence and is not presented as an application defect.

Prewarming was invoked through the authenticated existing service with unrelated
scheduled jobs disabled. This proves that service path, not automatic predictive
scheduling. The eight-person functional profile is not a production operating
limit. Four-hour recording storage was budgeted; recordings in this run were
short. Production activation safeguards and rollout still require review.

## Preservation and cleanup

All owned AWS test instances/security groups, DigitalOcean test compute/network,
autoscaler namespace and temporary managed-playback resources were removed.
Production droplets 579063522 and 599974294 and retained Spaces source recordings
were preserved. Local recordings, database archive, browser observations, metrics,
exact failed settlement proof and cleanup receipts are retained under:

`/Users/ruchirs/.codex/private-backups/cu-native-v3-isolated-20260923-b2a17c84`

Do not erase unsettled database reservations or label them settled to manufacture
a passing drain result. Next verification is only the corrected settlement and
automatic idle deletion, followed by reviewed production activation/rollback and
a short classroom/recording smoke check—not another broad capacity ladder.
