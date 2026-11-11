# Focused release regression result — 24 September 2026

## Decision

Course admission/attendance regression passed in this bounded run. Automatic
scaling is not yet a complete pass, so this is not production rollout approval.
Do not repeat the broad capacity ladder to verify the remaining scaling defects.

## Exact tested setup

- Backend `df9f46a4424825fba5bfe76827a3429e8badd582`, frontend
  `7acd67efd077887989dd1c9fde7c258d62e2d126`, infrastructure
  `ea84d8333b52dfc01aadb7b5912fe90190bca469`.
- Isolated OpenVidu 3.8/Pion, two automatically created dedicated four-vCPU
  media nodes; a separate shared-CPU master. Each room and its recording were
  on its own media node. Six distributed AWS backend/browser machines.
- Course: 200 students and two teachers. Webinar: 50 students and two teachers.
  Two 640x360/15fps cameras with microphones, one 1080p/15fps shared screen with
  audio, composed recording at 720p. No change to production.
- Approval: $20 total, 90 minutes, testing stops by minute 60. Paid window began
  11:30:49 UTC; classes ended before 12:30, both recordings were COMPLETE by
  12:30:07. Infrastructure cleanup verified at 12:42:19, within the window.

## Results

| Check | Observed result |
| --- | --- |
| Course admissions | All 200 first attempts succeeded in 1.838–3.352 seconds; five-person batches over approximately 100 seconds, full media already publishing. |
| Completion-triggered disconnect regression | All 200 student browser states connected without notices in two independent checks, including beyond the previous failure window. Provider attendance 202; later spot checks retained attendance. Mass return to Join session did not recur. |
| Existing webinar during course ramp | All 50 students plus two teachers remained connected until normal host end. |
| Deliberate reloads | Course students recovered in 2.408 and 2.321 seconds; webinar student in 1.932 seconds. These were test actions, not crashes. |
| Concurrent teacher preparation | One recording per room, not duplicate recordings. |
| Settled course media | 9,696 receiver samples across 202 actors, 12:21–12:29, with no new sampled audio-loss or freeze-counter increments. New-track startup is excluded. |
| Course-node CPU | 58.43% average across four cores during that eight-minute interval; 0.007% steal and no sampled UDP input-error increments. Backend 7.75%, master 7.38%; browser workers 65.30–68.53%. |
| Recording | Both jobs COMPLETE; both archived files fully decoded, SHA-256 verified, H.264 1280x720 with AAC audio. Course 687.43 seconds; webinar 1,921.04 seconds. |

While both classes were active, 12:21–12:22 container averages were 1.206 cores
for course forwarding and 1.062 for its recording; webinar forwarding 0.436 and
recording 1.028 cores. These are averages, not peaks or safe reservation minima.
The webinar ended during the longer CPU interval; do not use that interval as
a sustained two-class aggregate load result.

## Scaling findings

1. Both media nodes installed without manual package repair. First ready around
   11:49:46. The second was created by a scheduled scaler tick at 12:13:08 and
   verified ready around 12:17:30. Separate-room placement worked.
2. Timely prewarming did not pass. The test's reverse SSH relay stalled before
   the course prewarm time (12:00:31). Repairing only that owned relay with
   keepalives restored fleet observations. Scheduled reservation followed at
   12:07:24; no manual prewarm service invocation or manual VM creation replaced it.
3. A real backend defect also erased a valid pool/plan when unchanged fleet
   reports arrived out of order. One fenced manual scaler invocation and scheduled
   attempts held before a later scheduled attempt succeeded. The second node was
   ready after the scheduled 12:15:31 class start, not before it. Initial teacher
   preparation correctly waited for verified capacity; normal retry succeeded.
4. Correction `658767d7` was independently reviewed and integrated as backend
   **`1a4a3cef`**, on `ruchir/live-scaling-release`. All **170 local tests passed**,
   including 95 real-Mongo integration tests, with zero skips/errors/failures.
   It preserves only an unchanged, independently reconciled valid snapshot and
   never extends expiry. It was **not deployed** during this run.
5. Automatic removal with an active peer remains unverified. At 12:25 the scaler
   returned `No idle capacity drain authorized`: no selected-node drain ran.
   Saved control evidence also includes missing/invalidated pool observations
   and an active node's failed secondary health check; diagnose the exact selector
   refusal rather than attributing it to one presumed cause.
6. Independently, the former webinar node had zero rooms/tracks but 102 clients,
   still present after all webinar contexts closed and gone after the course
   closed. This supports remote-room signaling contributing to the provider's
   client count. The downstream drain guard currently treats that count as local
   media occupancy. Its correction needs exact local-room ownership evidence and
   a focused signaling-reconnect test, not a blind counter waiver. See the bounded
   follow-up in `COMBINED_CAPACITY_AND_SCALING_TEST_PLAN.md`.

## Coverage limits

This was a focused regression run, not another hour-long 200-person qualification
or 600-person test. Earlier benchmark failures remain intact. Webinar arrivals
preceded screen transmission; full visible camera/screen reception began at
11:58. A duplicate-tab helper used the wrong webinar route, so that case is
unverified, not an application failure. Webinar student replay was not shown
before its scheduled end. Full recording decoding does not replace in-app replay
or visual-layout checks. Terminal cleanup after both rooms ended is not an
automatic scale-in pass. No new engine comparison or production claim is made.

## Preservation and cleanup

Evidence is retained privately at
`/Users/ruchirs/.codex/private-backups/cu-native-v3-isolated-20260924-a7f8251c`:
browser observations, per-node/container metrics, provider logs/image identities,
capacity timeline, both recordings, backend database/log archive and cleanup
receipts. Do not commit raw credentials or participant traces.

All six AWS instances/security groups, three test droplets, test networking,
autoscaler namespace and managed-playback resources were removed. Production
droplets 579063522 and 599974294 and the original Spaces recording source were
preserved. Both temporary provisioning tokens were revoked and independently
returned HTTP 401; the disposable source-reader key was revoked (404), and the
owned revoked Keychain entry was removed. Original credentials were untouched.
Conservative compute estimate is under $7.52 using approved hourly rates and
charging every resource for the entire elapsed campaign; storage/network invoice
charges are not yet verified. No automatic extension or new paid run is authorized.

## Remaining release work

- Finish the narrow scale-in selector/remote-signaling correction using preserved
  evidence and local regressions; preserve recording settlement safeguards.
- Verify that correction and the integrated late-frame fix in a separately
  authorized small two-node scheduled-addition/active-peer-removal check. No new
  broad attendance ladder is needed for these operational gates.
- Review consolidated production configuration/rollback and perform the short
  rollout smoke check. The tested build and the newer local candidate must remain
  distinguishable; production is unchanged.
