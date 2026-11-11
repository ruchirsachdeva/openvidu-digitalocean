# Scheduled startup and occupied-node drain — September 24

**Result: scheduled startup passed; peer-class continuity during drain failed.**
No production change or release approval follows from this run.

## Frozen live candidate

| Component | Commit |
| --- | --- |
| Backend | `c96af2f971c1888e9227e3fc3ad2e7784b34c556` |
| Frontend | `7acd67efd077887989dd1c9fde7c258d62e2d126` |
| Infrastructure | `939a40a7e4139437c997c404863dace347eeacf7` |

Two eight-person recorded classrooms used OpenVidu 3.8/Pion, dedicated c-4 media
nodes, two cameras/microphones, one screen with audio, and 720p composed recording.
Distributed AWS browsers were lightly loaded. This was an operational regression
check, not another 200/600-person benchmark or physical-device qualification.

## What passed

- First-class preparation waited for verified capacity. Retrying concurrent teacher
  preparation produced one room and one recording, not duplicates.
- Native scheduled prewarming requested the second node at **16:11:57 UTC** for
  a **16:26:35** class. No manual prewarm invocation was used.
- Cloud creation occurred at16:13:28; native registration was observed by16:17:43;
  backend readiness/reservation by16:18:40, about eight minutes before class.
  Neither media node needed manual installation repair.
- The corrected reservation deadline was16:41:35, fifteen minutes after scheduled
  start. Both teachers successfully started after16:27, beyond the previous
  prewarm-relative expiry. Six student admissions took **1.82–3.10seconds**.
- The course room and its recorder were on the second node; the webinar and its
  recorder were on the first. Actual placement is not a future recorder guarantee.
- The webinar recording completed and imported as READY. After the failed drain
  experiment, the course recording also completed; student replay played in-app.
- Both managed files passed full-file decoding:225,900,065 and69,552,280bytes.
  Source recordings, local files, hashes, browser evidence and server logs are retained.

## Failure: remote signaling was still live work

After the webinar ended, its node had **zero rooms/tracks but five signaling
clients** for the course on the other node. At16:33:25 the scaler selected it for
drain. At **16:33:41.396–400**, four course browsers lost their sockets and became
disconnected. The host's microphone, camera and screen stopped. Four other users,
including the student publisher, remained connected; the recording remained active.

The native client deliberately sets `reconnectPolicy.nextRetryDelayInMs` to return
null: cached-token SDK reconnect can recreate an obsolete room before incarnation
fencing is qualified. Therefore graceful provider exit did **not** imply transparent
signaling migration. The application displayed its manual reconnect state.

All four affected users manually rejoined around16:35:24–25. Devices did not silently
restart; the host explicitly restored them. The course then had all eight users and
six tracks again, and ended normally at16:37:47. This is **manual recovery**, not an
automatic recovery pass. Zero packet-loss/freeze deltas before disconnection do not
erase the interruption or count absent post-disconnect streams as healthy.

The first node was absent from cloud inventory by16:39:56, after the course ended.
Thus automatic recorded-node settlement/deletion occurred, but **uninterrupted
removal while the peer class remains active did not pass**.

## Narrow corrections, separate from tested artifacts

1. `75ff06b`: restore the unconditional nonzero-client shutdown veto, including
   application-fenced nodes with verified nonlocal room ownership. Wait for those
   connections to finish; no forced timeout. This can retain a draining node longer.
   48 focused tests passed; full infra suite:283passed,20environment-dependent skips.
   Independently reviewed; not deployed/live-tested in this run.
2. `fc1c174f`: classify only missing/expired capacity demand as retryable HTTP503
   instead of500. End temporarily invalidated the plan; its automatic refresh and
   later scaler retry already worked. No freshness relaxation or changed scheduling.
   129 focused backend tests passed, including real-Mongo invalidation/refresh cases.
3. `d32cde5`: allow explicitly configured production guarded bootstrap rather than
   restricting the existing guard to the qualification stack name. No runtime
   startup/arming changes. This is eligibility, not operating-profile approval.

The proposed SDK reconnect redesign is intentionally **not** part of these fixes.
The next live check should test the conservative hold and subsequent zero-client
retry, not repeat established capacity stages.

## Production boundary

Production remains on its existing infrastructure. The c-4 combined-CPU candidate
still requires explicit non-CPU recording-policy resolution: provider-selected
recorder placement does not guarantee one job per node. The current two-recording
worst-case memory/storage allowance does not fit c-4. The three-copy disk allowance
is conservative, not a proven physical-copy requirement; verify the exact deployed
storage path before correcting it. Do not silently reduce it or substitute an
eight-core default. Network dimensions remain explicitly unmodeled.

A data-preserving paired production rollout and short smoke check remain separate
from this failed operational test. Migration commits remain independently revertible.

## Evidence and cleanup

Private run archive: `cu-native-v3-isolated-20260924-b83f2c10`. Do not commit its raw
logs, state, credentials or recordings. The approved window was90minutes/$8; browser
testing ended before minute60. Final cleanup receipts provide authoritative deletion
times and confirm preservation of production IDs579063522 and599974294.

Cleanup completed at **16:47:14 UTC**, within the approved window: zero test
droplets remained; all four AWS workers and their owned networking, disposable
playback infrastructure and temporary recording-reader credential were removed.
Production and retained source recording storage were preserved. Deleted test
compute cannot be recovered; the recordings and diagnostic archives remain.

The fixes were consolidated without conflicts on the existing
`ruchir/live-scaling-release` branches: infrastructure `7aebd17` and `6aadea5`,
backend `03554d8b`. These are post-test candidates, not a live verification pass.
