# Enrollment-based live capacity — delegated implementation plan

Status: design/implementation handoff; enforcement and numeric capacity unqualified.
Parent task retains scale qualification, measured capacity approval and integration.

## Current integration boundary — September 23

Focused dynamic campaign `cu-native-v3-isolated-20260923-b2a17c84` found two
collector defects before classroom admission: DigitalOcean includes (and may
repeat) the master's reserved public IP, and Docker reorders identical mount
arrays between inspections. The collector now canonicalizes those facts while
retaining strict media-node identity and actual mount/process change checks.
The isolated master accepts the corrected receipt. This is not a scaling pass:
with zero media nodes both native ListRooms and ListEgress return HTTP503, leaving
the pool held as `provider_work_unavailable` and preventing the first provision
claim. The capacity task is investigating durable minimum-node bootstrap without
relaxing admission or deletion checks. A teacher start in this state returned500;
that needs clean unavailable/retry handling. Production is unchanged.
The rejected Terraform collector-update plan would have replaced the master and
was NOT applied. Only the exact isolated Function's embedded bootstrap and the
owned master's collector were updated, with original bytes and hashes preserved.
Verification: 271 local infrastructure tests completed (251 passed, 20 skips).
Focused collector tests cover reserved/duplicate address normalization, mount
ordering, real mount changes and process replacement. Live receipt acceptance
confirms these collector corrections, not provider readiness or scale-out.

The sections below preserve the original delegation context, not today's test queue.
The subsequent 606-participant campaign and current operating-profile assessment are
recorded in `LIVE_CAPACITY_PROFILE_ASSESSMENT.md`. Do not restart the old four-hour
ladder or three-screen workload solely because they appear in this historical plan.

Consolidation uses `ruchir/live-scaling-release` in the backend and infrastructure
repositories. Successful recording settlement is implemented in backend `67a737fd`
and infrastructure `fff854b`; secondary-load veto handling is integrated in backend
`0a8c42d7`. Fleet receipt ingestion is integrated in backend `2fa7f12e`, with
out-of-order node facts corrected in `02a3f1e0`. Infrastructure `817e409` adds the
producer and guarded first-start sequence; `c9a0722` and `3a8dd13` bound reporting
cadence and metadata lookup within the existing watcher. These are local changes,
not production deployment evidence. Capacity activation stays off pending the
operating profile and focused real-node checks.

Latest preparation (September 23): maximum recorded duration is confirmed as four
hours including overrun; see the candidate storage allowance in the assessment.
Backend `14a31002` permits only the guarded isolated application test to activate
capacity, and `9a126907` permits explicitly unmodeled all-zero network dimensions
without relaxing CPU/memory/disk budgets. Infrastructure `b06aab3` binds collector
VPC/region to the actual Terraform deployment, retaining the settlement scripts.
Harness commits `6c43e80` and `8caac5c` add the strict capacity-enabled application
bundle and restricted loopback machine relay. Verification:47 backend tests,
27 infrastructure tests plus Terraform format/validation, and83 harness tests pass.
These are **local preparation results**, not a cloud or release pass.

The September23 focused attempt integrated the dynamic runner and cleanup
(harness `5b121e7`/`3af8d7c`) and backend-before-node bootstrap (`1dc0037`). The
explicit two-room/eight-person functional profile and ordinary webinar authority
were independently reviewed; these do not establish production numeric capacity.
The attempt stopped **before any classroom or recording started**: DigitalOcean
rejected master startup user data above 64 KiB; the current credential also returned
403 for Functions inventory and restricted Spaces-key creation. Do not describe
this as a browser or scaling pass.

Infrastructure `9996160` compresses and checksums startup transport with provider
size guards; `1487918` adds the missing stack ownership tag on dynamic nodes.
Duplicate-helper correction `8f22452` must be included too: actual private
configuration exceeded the media limit until identical drain-helper bytes were
installed once and copied to the second required path. Verify the actual rendered
payload, not merely the synthetic fixture, before another attempt. Rendering with
the candidate's private profile/credentials and synthetic resource identities
produced 63,255-byte master and 54,703-byte media payloads; this is not a live boot.
The final infrastructure suite reported OK: 270 tests, including 20 skips. Harness
`89ae4a5` checks Functions access and the live restricted import key before paid
setup; readable inventory alone does not prove namespace/action write authority.

Cleanup of that attempt is complete: the sole AWS backend and its security group,
six partial DigitalOcean cloud resources, two inert Terraform lifecycle markers
and all unused managed-playback resources were removed. No Function deployment
ran because it depended on the rejected master. Retained Spaces recordings and
the four retained Terraform resource types are unchanged; production droplets
579063522 and 599974294 remain active. Local fixtures/evidence are preserved.

Next: correct DigitalOcean credential access, use a fresh frozen setup/clock, and
run only the focused addition/placement/recording/removal sequence. The restricted
relay still needs live verification through the test master's HTTPS route; no
public application API or disabled TLS is needed. Production rollout/rollback
smoke remains gated on that result, not on another broad capacity campaign.

Bootstrap order verified by code inspection: a complete master-only observation
can publish an empty eligible pool; a real due schedule then creates demand and
the scaler requests the first node. In capacity mode min=1 is a drain floor,
not an independent startup request: do not wait for a node before creating the
due schedule. This sequence still needs the focused live proof. Network evidence
must be captured externally in that proof: the present secondary collector checks
free memory/disk and load average, not actual network/drop headroom.

Existing regression `capacityStaleReadinessDoesNotInterruptApprovedAudienceOrHostEndAndRetirement`
already covers an approved classroom continuing admission and allowing End when the
capacity source becomes unavailable. Ordinary joins after classroom admission starts
do not repeat the global schedule/capacity snapshot. Do not add another admission
layer or claim that every student join traverses the fleet forecast.

Remaining acceptance is focused: complete readiness reporting, defensible operating
profile, ready-node addition, recorded drain/finalization, retry/restart behavior, then
rollout/rollback smoke verification. A busy-but-known recorder must not invalidate
the whole inventory; it remains charged and cannot receive new placement when vetoed.

## Worktrees and bases
- beinghealer-server: /Users/ruchirs/worktrees/courseultra-capacity-backend
  branch ruchir/live-enrollment-capacity, base 995a7b3f4ab7cfcf909adf1138c5e7047a30cb72.
- openvidu-digitalocean: /Users/ruchirs/worktrees/courseultra-capacity-infra
  branch ruchir/live-enrollment-capacity, base f64b4588e02e269369ba1f5585746c50a2c53c6e.
  Infrastructure base already contains the isolated 3.8 candidate/safety history.
  Capacity changes must be new separate commits; do not fold migration into them or
  describe this branch as a 3.7 rollback target.
- No operations branch needed initially: courseultra-openvidu-operations owns
  cross-provider recovery, NOT DigitalOcean Terraform or application admission.
  Consult /Users/ruchirs/workspace/personal/courseultra-openvidu-operations/AGENTS.md
  before proposing changes there. Report any justified extra repo scope to parent.
- Backend clean base excludes the dirty qualification/recording candidate. Read
  /Users/ruchirs/worktrees/courseultra-live-recovery-20260910/backend for context only.
  Existing detailed design: src/main/docs/live-media-capacity-reservations.md in that
  recovery worktree. Preserve its probe evidence; do not copy the whole dirty bundle.
  Record shared dependencies rather than implementing conflicting replacement fixes.

## Goal and invariants
A room stays on one media node. Reactive CPU autoscaling cannot rescue that room by
moving half its participants. Admission must reserve expected PEAK before creation.
Use existing runtime/locks/scheduling/autoscaler owners, not an independent scheduler.

1. Required demand: full distinct eligible enrollment for exact scheduled class/cohort,
   expected teachers/guests, supported extra device/transport demand, publishing/media
   profile, recording overhead and explicit qualified headroom. No no-show discount.
   Do not count cancelled/historical enrollment or unrelated cohorts. Unknown attendance
   cannot mean zero. Webinar registration/caps remain separately resolved.
2. Node available budget = qualified safe resource budget minus all starting/running
   room reservations and relevant outstanding recording obligations on that node.
   Count expected peak, not connected attendance. Include fixed per-room overhead.
   Preserve organization commercial quotas as separate checks, not hardware budgets.
3. Serialize reservations/creation/drain across app replicas with existing lifecycle
   and organization lock ordering and conditional revisions. Scope to room generation,
   not tab/reconnect/recording segment. Deduplicate simultaneous teacher starts.
4. Eligible node must be ready, not draining, matching measured profile, within
   per-room ceiling and all resource budgets. CPU/network/load/memory/disk are
   secondary vetoes. Missing/stale/unknown inventory or capacity cannot allow new
   placement. Do not disconnect existing classes because profile validation fails.
5. Reserve BEFORE creating, verify actual selected node BEFORE admitting. Account for
   creation timeout/unknown outcome, retries, orphaned reservation, node restart and
   out-of-band rooms. App bookkeeping without enforced provider selection isn't safety.
6. No node fits: request new capacity once via existing provisioning workflow, wait
   for true registration/serving/recording readiness, create then admit. Bound waiting
   and show clear recovery; no silent fallback placement or infinite queues.
7. Scheduled prewarm reuses existing scheduler ownership; lead time derives from
   measured provisioning latency plus margin. Handle schedule edits/cancel/late
   enrollment, concurrent starts, cap/budget limits and restart recovery.
8. A class larger than the qualified single-room ceiling needs a larger qualified node
   or explicit admission handling, not more nodes. Late growth after room assignment
   must fit that existing node; do not silently move an active room.
9. Release only after genuinely finished class/room and relevant recording settlement,
   never scheduled end or temporary empty room. Unknown finalization remains protected.
   Coordinate reservation and draining exclusion; preserve replacement-readiness guards.
   Prewarmed/recording nodes must not be removed by low-CPU scale-in.

## Supported placement is a gate, not an assumption
Existing Sept12 empty-room probes (installed 3.7 compatibility integration) found:
- Native-first CreateRoom then compatibility creation returned conflict and did not
  retain requested compatibility recording-part name.
- Compatibility-first assigned the room before subsequent native CreateRoom.
- Legacy mediaNode.id pointed to an absent node still placed on the available node.
- Later native override to absent node returned success but retained existing assignment.
These reject those implementations; they do not prove all supported APIs impossible.
Seek official supported creation+metadata contract and inspect 3.8 code/docs. Never
write provider Redis directly, clone undocumented metadata, swallow 409 as success,
or claim HTTP200 alone proves node placement. Two-node browser/recording proof needs
parent-approved infrastructure. Local mocks can test orchestration, not provider truth.
If unresolved, deliver useful disabled implementation/tests plus precise blocker,
not a fake guarantee or a new unsanctioned gateway/provider fork.

## Capacity formula and qualification
No safe numeric node capacity has been established for broad release.
Use a versioned resource-envelope profile, not vCPU-linear participant multiplication.
A calibrated model may use per-room fixed overhead + measured upper-bound per-viewer
demand; use piecewise envelopes if needed. Account for hottest forwarding thread,
aggregate CPU, bytes/sec, packets/sec, memory, recording startup/finalization and disk.
Deduct headroom once, not multiple times. Enforce single-room ceiling separately.

Fingerprint provider/region, server/CPU family/network, engine/version, codec/simulcast,
resolution/fps, publishing workload and recorder/layout/config. TODO/runbook:
changing those invalidates the affected profile; remeasure boundary/bursts/mixed rooms,
soak and scaling before new admissions. Unknown profile must not get a guessed default.

Qualification owner has two 100-student Pion short-hold passes, but not full release
qualification. Mediasoup one pass + one audio-loss failure at 10m23s. Both actual ~15fps.
No observed average CPU or vendor 1000-viewer example is a safeNodeCapacity constant.
Parent benchmark stays THREE publishing people each with camera/screen/mic/screen audio
plus recording, even while separate host-policy task reduces normal product visuals.

## Recording / autoscaler integration
Reuse existing provider and recording services, lifecycle locks and runtime generation.
Separate media room placement from recorder placement where allocator differs.
Reserve recording startup/finalization headroom and verify actual acceptance; don't
lower egress CPU cost simply to force a second recording to start.
Preserve idempotent sequential starts, native fallback/unknown status and recovery.
Disk budget includes temporary capture, failed upload, logs and upgrade reserve.

DigitalOcean Terraform/function owns scale-out: audit current four-minute CPU history/
polling, cluster averaging and one-node-per-invocation behavior. Replace/extend narrow
decision path with demand/reservations; don't invent a second conflicting scaler.
Keep cross-provider AWS recovery untouched. Interim automatic scale-in disabled is
permitted as an explicitly limited candidate, not proof of safe occupied draining.
Finalization timeout is an incident/recovery condition, not fabricated COMPLETE.

## Execution / verification
A. Read repo/skill instructions, detailed design and current provider creation/scaler.
   Publish proposed minimal contract to parent/host task before overlapping edits.
B. Deterministic enrollment count and demand/profile tests; admission transactions:
   simultaneous starts, mixed rooms, late enrolment, cancellation, unknown capacity,
   stale inventory, node restart, failed create, retry dedup, room generation reuse.
C. Provider integration seam and readiness/prewarm/scaling tests with fakes; no cloud
   commands without approval. Record exactly what still requires real-node proof.
D. Drain/recording retention tests and failure-path/idempotency coverage.
E. Focused review/changelogs/runbook; local commits separated by repo. Deliver SHAs,
   API/state contract, test results, disabled/qualified status, dependencies, rollback.
F. Parent later runs supported two-node placement+recording proof, four-hour soak,
   600 warm vs dynamic including arrivals and master CPU/API metrics. Count total
   provision waiting; never reset join timer to conceal it.

## Coordination and authority
- Own capacity reservations, demand/prewarm/placement/readiness. Host task owns
  elected host and publishing approvals; do not redesign or merge its branch here.
- Exchange a versioned workload-description contract, no speculative duplicated fields.
  Parent resolves LiveSessionRuntime/Controller overlap through reviewed integration.
- Do not change test source/thresholds, engine baseline, production, cloud state,
  credentials, preserved logs/recordings, old dirty worktrees or other task branches.
- No provision/deploy/push/PR without approval. Local focused commits allowed.
- Follow implementation/review/commit skills, preserve attribution and changelogs.
  A provider gate is reported honestly while independent local work continues.

## September 23 first-node initializer correction

The focused live test created the first c-8 node through the existing scaler,
but 3.8's config initializer rejected the bounded recorder preparation because
`RUNNING_SYSTEMD=true` (normally supplied by `openvidu.service`) was missing.
Supply the same environment marker and media env-file path for that initializer.
The fresh-only, empty-recovery, reviewed-service/image/config and unarmed-recorder
checks remain intact; this does not restart an existing recorder or relax drain.
The failed first boot remains qualification evidence, not a successful cold start.

The subsequent live comparison found the rendered policy semantically identical
to the approved policy, but whole-number CPU costs were JSON integers rather than
floats. Fingerprint those numeric costs canonically (`2` equals `2.0`), retaining
the independent full-file hash and rejecting nonnumeric/nonfinite costs. Different
cost values and all other reviewed policy fields still change the fingerprint.

The next preparation step used unsupported `compose create --no-deps`. Use
`compose up --no-start --no-deps egress` to create only the stopped recorder.
The installed Compose help confirmed the former flag is absent; the latter
command must not omit `--no-start` or start dependencies before arming.
# 2026-09-23 stopped-recorder mount ordering

The focused two-class run reached clean exit (code 0, no OOM) for every media
container, but storage verification held because consecutive Docker inspections
returned the same mounts in a different order. Normalize only mount-list ordering
in drain identity snapshots. All mount fields, duplicates, process state, restart
fences and recording/recovery vetoes remain checked. Regression coverage includes
reordered mounts, changed source/read-write flags, duplicate bindings and changed
exit state. This correction alone is not successful automatic removal evidence.

The stopped-node fleet reporter exposed a second formatting mismatch: its command
runner retains stdout newlines, while the drain guard's default runner strips
them. Normalize the systemd `NeedDaemonReload` value before comparing with `no`;
`yes`, missing and mixed outputs still hold. Without this correction, a verified
restart fence was falsely rejected and the backend lacked a complete pool for
recording settlement. No evidence TTL or exclusion requirement is relaxed.
