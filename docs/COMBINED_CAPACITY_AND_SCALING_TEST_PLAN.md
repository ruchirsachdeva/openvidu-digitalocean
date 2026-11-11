# Dedicated 4-CPU boundary and scaling verification

Status: partially executed September 23; paid test infrastructure removed. See
`COMBINED_CAPACITY_RESULT_2026_09_23.md` for actual intervals, failures, deviations
and unfinished automatic-scaling gates. The plan below is preserved as the original
intention, not a claim that every item passed. It does not qualify a production profile,
authorize an unbounded spend, or enable mixed-size automatic provisioning.

## Focused drain follow-up — September 24

Implementation follow-up: the node guard now permits nonzero signaling clients
only when the existing application drain authority is configured, local rooms
and tracks are zero, and a fresh complete Redis room map places every room on
another freshly registered serving node. Missing/empty/malformed maps, stale
owners, local work and legacy drains without the authority still hold. Application
exclusion, minimum-ready-peer claims, recording settlement and once-only graceful
signals remain mandatory. This correction is locally tested, not live-qualified.

The saved 12:25:23 control snapshot has a valid pool/plan but marks the remaining
course node `secondaryChecksPassed=false`. The current selector refuses removal
when any node is ineligible. Its 12:24:32 metrics show about 6 GiB available memory
and 40.7 GB disk, above configured minimums; the remaining secondary condition is
the load-average limit. Do not disable that protection to manufacture a drain
pass. A small healthy-peer case is the next appropriate operational verification.

This follow-up does not authorize another fleet, a paid-window extension, a guard
waiver or a production change. Preserve the original benchmark plan below.

### Observed stages, not a combined scale-in pass

In campaign `cu-native-v3-isolated-20260924-a7f8251c`, the coordinator confirmed
200 course students retained after arrivals while the 50-student webinar remained
active. Both classes subsequently ended normally and both recordings were COMPLETE
and downloaded/full-decoded. These attendance/recording results do not establish
automatic removal with an active peer.

- At approximately 12:25 UTC the scaler returned **No idle capacity drain
  authorized**. That is a selection-stage hold; the active-peer graceful drain did
  not execute. Preserve the exact capacity-control/reservation snapshot and claim
  response to determine why selection refused. Do not attribute this response to
  a downstream node guard that had not run.
- At 12:24:32 UTC the ended webinar's node `603296891` / `ND_EaJT4Vp2MHsb`
  reported rooms=0, clients=102, tracks-in=0, tracks-out=0; the active course's
  node `603302611` / `ND_T3aaneg2hyAh` reported rooms=1, clients=203,
  tracks-in=6, tracks-out=1212. Heartbeats were approximately 1.24 seconds old.
- At 12:26:26, after all 52 webinar browser contexts closed, the first node still
  reported 102 clients. After the course contexts closed, both nodes reported zero
  rooms/clients by 12:31:45. This strongly supports remote-room signaling ownership,
  but aggregate counts alone do not identify each of the 102 connections.
- The current node guard independently requires all four counters to be zero.
  Therefore the nonzero client count is a second, downstream obstacle even if
  automatic selection succeeds. Manual terminal teardown is not that qualification.

Evidence is preserved privately under that campaign directory:
`provider-node-counter-timeline.jsonl`, `capacity-timeline.private.jsonl`,
`autoscaler-activations*.private.json` and `final-provider-*.private.json` (full
provider logs/image identities). Keep raw credentials and participant traces out
of this repository. The late-frame correction `658767d7` was not deployed during
this run; scheduled provisioning on the corrected candidate remains a live gate.

### Provider contract and remaining uncertainty

Public OpenVidu LiveKit tag `3.8.0` resolves to
`f2e5cda2b3977f7a322f146ba374a47f2e9b0fc4`:

- [RTC service](https://github.com/OpenVidu/openvidu-livekit/blob/f2e5cda2b3977f7a322f146ba374a47f2e9b0fc4/pkg/service/rtcservice.go#L415)
  creates a signaling statistics collector on the WebSocket-serving node.
  [BytesSignalStats](https://github.com/OpenVidu/openvidu-livekit/blob/f2e5cda2b3977f7a322f146ba374a47f2e9b0fc4/pkg/rtc/signalanddatastats.go#L273)
  reports participant join/leave for signaling; media participation reports through
  the same reference-guarded telemetry. Consequently
  [NumClients](https://github.com/OpenVidu/openvidu-livekit/blob/f2e5cda2b3977f7a322f146ba374a47f2e9b0fc4/pkg/telemetry/prometheus/node.go#L157)
  is not an exclusively local-media participant count.
- [Stop(false)](https://github.com/OpenVidu/openvidu-livekit/blob/f2e5cda2b3977f7a322f146ba374a47f2e9b0fc4/pkg/service/server.go#L344)
  marks the router draining and waits on actual local room participants, rather
  than NumClients. The first termination signal is graceful; a second can force
  shutdown. Preserve the existing durable once-only signaling protection.
- [OpenVidu 3.8 administration](https://openvidu.io/3.8/docs/self-hosting/elastic/on-premises/admin/#removing-media-nodes-gracefully)
  documents graceful signaling of media services and waiting for them to stop.
  This does not establish interruption-free signaling migration for our deployment.
  The public tag has a `DrainConnections` method but no production caller for it;
  do not claim staggered connection migration. Verify installed PRO image/build
  provenance against the inspected public core before relying on implementation
  details beyond the documented contract.

### Minimal correction proposal and verification order

1. Diagnose the selection-stage refusal from preserved control/claim evidence.
   Review the initial-drain fix and late-frame fix together; do not change counts,
   shorten recording retention or manually settle reservations to obtain a pass.
2. Replace the client counter as a *local-media-empty proxy* only after adding
   independent, fresh, exact-node room ownership proof from the complete provider
   room-to-node map, together with the existing authoritative closed-room fence.
   Retain zero local room/track checks, ready-peer checks, restart fencing and
   durable once-only graceful signals. Treat clients as signaling-risk telemetry,
   not ignored data. Unknown or conflicting ownership must still hold.
3. Locally test missing/stale maps, local live rooms/tracks, changed incarnation,
   no ready peer and duplicate signals. Preserve recording finalization, stopped
   writers, physical storage proof and final deletion/release checks unchanged.
4. Only in a separately authorized small two-node follow-up, prove that viewers
   signal through the retiring node while their media room lives on its peer.
   End the retiring node's room and verify automatic selection, graceful stop,
   automatic signaling reconnect, unchanged peer room/participant identities,
   continuous media/recording, settlement and actual automatic deletion. Measure
   reconnect time and interruption; a reconnect possibility is not a continuity
   guarantee. No repeat of the broad capacity ladder is required for this gate.

Independent recorder placement still matters: if the ended class's recording is
on the active peer, physical settlement may need to wait for that worker; room
closure does not override it. Normal provisioning may conservatively request
replacement capacity during settlement. Preserve both limitations explicitly.

## Execution preparation — September 23, 18:58 UTC

Read-only account checks succeeded: AWS account 408669273539 is authenticated;
DigitalOcean shows only the two protected production droplets, with no qualification
compute remaining. Its live catalog lists c-4 (4 dedicated vCPUs, 8 GiB, 50 GiB disk)
in Bangalore at $0.125/hour and c-8 (8 dedicated vCPUs, 16 GiB, 100 GiB disk) at
$0.25/hour. Neither changes the existing production shared-CPU configuration.

AWS pricing API confirmed Mumbai Linux On-Demand rates: c6a.4xlarge $0.374/hour,
c6a.8xlarge $0.748/hour, c6a.16xlarge $1.496/hour. Proposed maximum generator fleet:
one backend c6a.8xlarge, three publisher c6a.4xlarge, six viewer c6a.16xlarge.
That is $10.846/hour, or $32.538 for three hours, before DigitalOcean and ancillary
costs. Up to four c-4 nodes add $1.50 for three hours; one conditional c-8 used
for the entire three-hour ceiling would add $0.75. Recheck master price and all
actual plan totals before provisioning. Approved cap: $40 compute plus $10 ancillary.
The user approved this fresh three-hour window; the expired smaller window is not reused.

Runner work must precede spend: current cohort/actor/authorization checks cap a
single load class at 200 students, and the four-c4 diagnostic uses pre-provisioned
nodes with capacity activation disabled. Extending only an arrival loop would
produce invalid admission or misleading scale-out results. Freeze a consistent
new cohort, actor mapping, per-room attendance bound, timed camera actions and
dynamic lifecycle contract with regression coverage before cloud execution.
Preserve historical manifests and source pins; do not weaken their checks.

## Questions to answer

1. Under the agreed classroom workload, what sustained audience can a dedicated
   4-CPU media node support with its own recording, and what headroom remains?
2. Does a reproducible boundary come from forwarding, recording, joins, network,
   or the test browsers? Does an 8-CPU node materially improve that exact case?
3. Does the application forecast demand, provision ready capacity, place rooms,
   preserve running media and safely remove idle recording nodes?

The existing default `s-4vcpu-8gb` is shared CPU. This comparison uses regular
dedicated `c-4`; neither result silently qualifies the other. Production remains
untouched. Preserve all prior evidence, including the unsuccessful September 23
automatic settlement. Backend correction 650af2ee and infrastructure b57f74a must
be included, with exact artifacts and current harness source frozen before spend.

## Workload and controls

- OpenVidu 3.8/Pion; same master configuration, region, browser versions, codecs,
  resolutions and bitrates in every comparison. Recording stays 720p.
- Two teachers; host camera/microphone and one screen with audio. Alternate a
  student camera/microphone for ten minutes on and ten minutes off, retaining
  separate results for the two-camera intervals. Also sustain two cameras at the
  suspected boundary; do not describe intermittent-camera results as always-on.
- Begin at 200 students plus two teachers, not a repeated 25/50/75 ladder.
  Use real application browsers on AWS workers, with publisher and viewer CPU,
  memory, scheduling delay and browser event-loop measurements. Add/shard browser
  capacity before declaring a media limit if the generator becomes constrained.
- Establish one isolated media/recorder node for the colocated measurement. Verify
  actual native room AND egress node identities; keep master egress ineligible via
  supported existing configuration. If colocation cannot be established, label the
  run accordingly rather than force unsupported placement or claim colocation.
- Compare forwarding-only and recorded windows on the same class when diagnosing
  recording contention. Stop recording normally, finalize, then start a sequential
  part; no duplicate jobs, forced termination, or altered recording CPU cost.

## One fleet, distinct measurement phases

### A. Find the 4-CPU operating boundary

Reach 200 students steadily, initially two joins/second. Then 250 -> 300 -> 350
-> 400, allowing approximately ten settled minutes at each informative level.
The 400-student ceiling bounds this experiment, not product support. If 400 remains
healthy, report "at least 400 for the observed workload/duration; limit not found"
rather than invent a cutoff. Do not recreate all smaller stages.

Separate arrivals from settled windows. Capture policy/heartbeat/API latency so an
admission bottleneck is not reported as a forwarding limit. On quality flags, stop
increasing load, not the class: continue observing recovery for at least ten minutes
where safe. Brief startup freezes alone do not end the test. Reduce attendance to
the previous level and repeat the suspect transition once to check reproducibility.

Retain the existing per-stream quality flags unchanged. Before launching, freeze
the run's quality-summary rules: affected-viewer fraction, interruption durations,
audio concealment/loss, recurrence, recovery without reload and time to recover.
Show distributions and incident timelines, not merely binary pass/fail. A claimed
operating limit needs stable media AND measured headroom; high CPU alone is not
proof of failure and low average CPU is not proof of health.

For attribution, compare source outbound quality with receivers, forwarding versus
egress CPU, per-core saturation, steal/scheduling delay, UDP drops and network rate.
If disabling recording restores quality at fixed attendance, repeat that comparison
with a new recording part. Correlation alone is not a proved cause.

### B. Provisioning, arrivals and concurrent classes

Keep a healthy class running on the first node. Use the existing scheduler, not
manual prewarm, to introduce a second scheduled class whose reservation cannot fit
on the first node. Observe schedule -> demand -> one creation claim -> Droplet ->
provider registration -> recorder readiness -> placement -> recording -> admission.
Record each timestamp, first-class quality and master/backend performance.

Use only a justified test operating profile; do not reduce the recording minimum or
mark an unqualified 200-person profile qualified to make this phase start. Today the
4-CPU additive profile conflict remains real: 2232m sampled forwarding plus the
2000m recording allowance exceeds 4000m. Empirical capacity diagnosis and admission
model acceptance are separate gates. If unresolved, run the scaling mechanism with
an explicitly bounded small functional workload and report that limitation; do not
claim combined 200-person reservation qualification.

Reuse browser capacity across classes to reach up to 600 simultaneous participants
only if the measured per-node boundary, generator capacity and authorized window
permit it. This is not 600 participants on one node. Reuse matched join patterns
(steady two/second and five every two seconds) while recording queue delay, joins,
existing publishers and recovery. Do not repeat patterns already explained by a
proven application defect unless verifying its correction.

Exercise:
- enrollment increase before start and full reservations despite initial no-shows;
- simultaneous teacher starts/retries -> one room/recording attempt;
- arrivals while a node starts -> bounded waiting, no assignment to an unready node;
- repeated scheduler/scaler requests -> no duplicate provisioning;
- startup/readiness failure -> existing classes unaffected; no false usable capacity;
- global node/recording limits -> explicit wait/recovery, not overbooking;
- ended schedule with an ongoing class -> reservation retained.

### C. Safe removal on the same fleet

While another ready node serves its class, request scale-in against an occupied node:
expect refusal. End that class normally, retain the finalizing recording obligation,
exclude new assignments, gracefully drain, verify storage/import and settle using
the corrected backend. Then observe actual automatic cloud deletion, not manual
test cleanup. Confirm the remaining class, recording and arrivals stay healthy.

Repeat an acknowledgement/reconciliation request to establish idempotency. Exercise
missing evidence and a disposable recovery-file fixture: deletion must hold; remove
only the owned synthetic fixture afterward, never real recording/recovery files.
Preserve clean-exit, boot/container identity, application clearance, final storage
proof and deletion receipts. Verify minimum ready capacity prevents last-node removal.

### D. Conditional 8-CPU comparison

Only if A identifies a reproducible server-side boundary, create a fresh dedicated
c-8 and repeat the identical audience, workload and recording-location conditions.
Do not resize an occupied node, move a running room, change master/engine, or silently
switch recording to another server. Repeat the suspect condition and a recovery
window; report whether 8 CPUs improved the actual bottleneck. It may not improve a
network, application or source problem. Mixed-size automatic selection is not
implemented by this experiment; current scaler size remains explicitly configured.

## Timing, budget, safety and handoff

Prepare scripts/artifacts/credentials locally first. Plan a bounded 2–3-hour cloud
window, including setup, finalization and cleanup; reserve the final 20–30 minutes
for preservation and cleanup. Verify live regional prices, availability, browser
worker counts and disk budget, then establish an explicit total cap before creation.
Do not recycle or silently extend an expired campaign clock. If the conditional
comparison does not fit, preserve the discovered boundary and report it outstanding.

Check installed c-4 free disk against four-hour recording/recovery allowances before
accepting it for release. Short test recordings do not validate a four-hour storage
guarantee. Keep capacity to archive recordings; a cleanup deadline never permits
discarding unresolved data. End normally, verify full-file decode/playback, preserve
logs/metrics/database/proofs, then remove owned non-production infrastructure and
temporary credentials only. No idle test fleet between coding iterations.

Deliver a measured range: last repeated healthy audience, first reproducibly degraded
audience (or limit not reached), exact recording placement/workload, remaining headroom,
and whether c-8 helped. Separately report scheduler, placement, recording admission,
occupied-drain, settlement, actual automatic deletion and remaining-class continuity.
Use these results to revise the operating profile; do not extrapolate linear
per-person CPU from one measurement or declare all permutations tested.
