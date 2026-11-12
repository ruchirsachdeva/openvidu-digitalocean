# CourseUltra OpenVidu Elastic Deployment

## Recorder observation and recovery-alert compatibility — November 12

Recorder endpoint ownership now tolerates unrelated host processes disappearing
and non-listening descriptors closing during enumeration. Both original listening
sockets must still belong to one live process with unchanged PID birth and
container identity at the final check; dead/reused owners and changed or closed
endpoints hold readiness. Fleet logs include the original observation time,
Droplet ID and bounded backend hold reason to distinguish a superseded frame
from incomplete recorder evidence, without logging work or credential details.

Autoscaler alerts now include integer epoch-millisecond `observedAt`, as required
by the backend's ordered incident/recovery contract. Missing source time previously
caused recovery delivery to fail even after a successful readiness check. Deploy
the shared backend's source-time handling before the Function update. The existing
six-code safety fixture checks that paired payload strictly. Allocation, action
parameters, recorder configuration and lifecycle authority remain unchanged. These
changes do not resolve an unknown or active recording's capacity hold.
These changes are locally verified source candidates, not a live migration.
The representative bootstrap fixture retains at least 1KiB of reviewed headroom
under the provider's hard 64KiB limit. Render the complete actual private profile
and credentials before any action update and require the same 1KiB margin; the
fixture alone does not qualify arbitrary live settings.

## Compatible false-alarm mitigation qualification — October 28

The deployed backend `145afac8` already accepts the six alert codes used by the
read-resilience Function at `d631570`. A narrowly reviewed Function-only update
can therefore classify failed pre-dispatch provider reads as readiness waits and
retry safe GETs without first moving production traffic or changing that backend.
Its existing process-local debounce handles `READINESS_UNAVAILABLE` and silently
consumes `READINESS_RECOVERED`. This is a limited false-alarm mitigation, **not**
shared incident delivery, paired recovery email, or full cluster-release sign-off.
Do not point the live Function at an isolated backend/database to gain those features.

Keep the complete live Function configuration and opaque media startup payload
byte-for-byte, preserving the backend target, credentials, profile, quotas, fleet
tags and placement. Change only the existing action's reviewed executable source;
do not run a broad Terraform apply or alter scheduled triggers, limits or hosts.
Check its exact current source hash before and after any separately authorized
update. Observe subsequent scheduled checks rather than manually invoking the
autoscaler. Missing/unknown creation outcomes still require explicit reconciliation.

The four legacy-contract checks and 59 extracted autoscaler tests pass locally.
The separately journalled October 28 rollout installed only this compatible
executable source as action version `0.0.11`; its rendered source hash is
`d8ae13780c3b7e1d5cb9c97cf5b19172139411b43472276eaf7f8676cb6cc287`.
Three subsequent scheduled checks held the existing ready fleet without
creation or alert-delivery failure. Configuration was preserved. No real
incident/recovery email delivery is certified by those healthy checks. The later
`c9343a5` quota/capacity recovery codes and `041c591` source-time protocol remain
backend-first: deploy shared backend handling before those Function revisions.
The complete recovery fix is not available from this compatibility checkout.

## Bounded provider reads and readiness recovery — October 15

The autoscaler now retries only DigitalOcean GET reads after HTTP 429/5xx or a
transport timeout: at most three attempts, four-second attempt timeouts and a
12-second per-read scheduling budget, with bounded jitter. A fresh 115-second
monotonic budget is reset for every warm Function invocation; reads leave 20
seconds for outcome/alert calls, and a low remaining budget holds before consuming
a dispatch claim. Existing outbound-call timeouts are capped by that remaining
budget. The provider's 120-second Function limit is unchanged; these are bounded
client scheduling/socket timeouts, not an absolute deadline for a slow-dribbling
HTTP response. Error bodies are closed without another diagnostic read.

Missing inventory/account/CPU evidence is a pre-dispatch readiness wait, not
`PROVISIONING_FAILED`, and cannot create or claim a machine. A permanent 403 is
held without retries. Known zero account-quota headroom uses the existing capacity
waiting/quota-pressure alerts. `READINESS_RECOVERED` requires the current complete
read/valid-authority-claim family and is suppressed for any provisioning error or
unknown creation outcome; it does not resolve provisioning-failure alerts.
Provisioning/readiness signals are attempted before quota/waiting notices when
the remaining alert budget is tight; undelivered notices remain visible.

Cloud POST/DELETE/tag changes and capacity-backend POSTs remain single-attempt.
Durable dispatch intent, outcome observation, active-creation protections and
recording-safe drains are unchanged. Deploy the companion backend's readiness
notification handling before updating the Function; keep outstanding intents for
reconciliation, never force a create retry. This entry describes locally tested
changes, not a live rollout or a new capacity qualification. No Terraform resource,
dependency, profile, placement or node-bootstrap contract is changed.

## Readiness alerts and short preparation cleanup — October 1

An explicit HTTP 503 from the pre-dispatch claim endpoints is a readiness wait,
not `PROVISIONING_FAILED`. Report wait/recovery to the backend; repeated waits
spanning at least eight minutes produce a readiness alert. Unknown cloud outcomes,
timeouts and failed outcome receipts remain provisioning failures. Debounce state
is backend-process-local; deploying/restarting it restarts that observation window.

If a cancelled, never-admitted preparation ended before active provenance was
captured, the existing watcher may use two whole-recorder idle observations at
least 30 seconds apart. Exact boot/container/process/storage identities, successful
provider output and no remaining writers, files or backups are required. Recheck
before submission and retain an immutable receipt for retries. This never stops
processes, deletes recordings or relaxes ordinary admitted-class settlement.
Mount identity comparison is order-independent because Docker may reorder the
same mount list; changing any mount binding still retains the reservation.

Activated October 1: backend `a74d10d9`, collector changes `71b6459` and
`48fc959`. All 389 backend capacity tests and 326 infrastructure tests passed;
20 environment-dependent infrastructure tests skipped. A live preparation was
cancelled before active provenance was captured; the scheduled watcher released
its reservation using `IDLE_PREPARATION` proof, without manual release or restart.
Existing managed recordings remained READY, and test schedule/working hours were
restored. No extra server was created. This is lifecycle verification, not a new
capacity or media-quality qualification.

Deploy the companion backend first. Install the matching collector and update
future-node bootstrap together. Only full-line comments from the job settlement
helper are omitted from bootstrap transport; offline tests compare Python ASTs.
Render the actual credential-bearing payload privately and check its 64KiB limit.
Rollback collectors/autoscaler before reverting backend support; unresolved work
remains protected. No placement policy, node count or database migration changes.

## Retain nodes carrying peer signaling — September 24

The focused occupied-drain run found that shutting down a node with no local room
or tracks but remaining peer-room signaling clients disconnected four users in the
surviving class. Native automatic SDK reconnect is deliberately disabled pending
safe fresh-admission recovery; room ownership elsewhere does not guarantee continuity.
Restore the nonzero-client shutdown veto even with an application drain claim and
a verified peer room map. No forced timeout is introduced: existing connections
finish naturally, then the ordinary watcher can retry. This can retain a draining
node longer and costs idle capacity, but must not interrupt another class. The
original failure is retained; this correction is locally tested, not live-qualified.

## Explicit production bootstrap eligibility — September 24

The legacy-named `isolatedRecorderGuard` can now be selected outside the exact
qualification stack only with capacity reservations enabled, a nonblank dedicated
backend credential, an HTTPS authority without embedded credentials/query/fragment,
and a JSON descriptor matching the selected profile fingerprint, node type and
region. The backend/runtime still validate the complete approved descriptor;
Terraform eligibility is not operating-profile approval. Defaults remain disabled,
and fresh-node startup/arming code is unchanged. Existing production nodes must not
be replaced merely to apply this validation change. The release manifest records
the resolved-descriptor and separate rollout requirements.

## Shared-server combined CPU release candidate — September 24

This supersedes the proposal below to introduce separate recording workers. The
candidate keeps the current shared-server architecture and existing scaler. Its
new explicit backend profile option `roomCpuIncludesRecording=true` applies only
to `POOL_ADMISSION_V1`: charge the measured combined classroom/recorder CPU once,
not combined CPU plus a second recorder CPU allowance. Non-CPU recording resources
are still separate, and the provider's2-core startup estimate is unchanged.

`python3 capacity-benchmark.py --node c-4 --people 202 --combined-cpu` emits the
unqualified CPU assessment: measured combined peak3482m rounded to3500m, budget
3600m with explicit10% physical headroom. This is not the earlier20% additive
policy and not a guarantee of all future peak loads. Add `--profile` only with a
matching reviewed c-4 template; non-CPU values are preserved, not inferred.
The output fingerprint includes the accounting flag. Existing calibration and
old profiles keep their old arithmetic; no active reservation is migrated.

Both first-start arming and ongoing fleet receipts require whole-host CPU
monitoring, cpuload recording selection, utilization threshold<=80% and composed
recording startup estimate>=2 cores matching the profile's recording CPU field
for the combined profile. This rejects a
process-only CPU monitor or binpacking policy even if their config was hashed.
Readiness receipts and recording-start confirmation remain distinct; instantaneous
CPU is not expected-enrollment reservation or a guarantee of later recorder load.

The profile is a RELEASE CANDIDATE FOR TESTING, not production activation. Review
memory, actual free disk/four-hour recovery allowances and network treatment, then
test staggered and simultaneous recording starts followed by student arrivals,
automatic scheduled prewarm, and idle removal while another class remains active.
Retain failures without forcing deletion or clearing protected obligations. No
claim of per-node recorder pinning, one-recorder limit or automatic mixed-size
selection is made. Paired backend/infrastructure rollback must retain compatible
profile meanings and finish outstanding recording settlement first.

## Evidence-led hardware review — September 24

### Earlier strict-accounting assessment (superseded for combined-CPU candidate)

The recommendation is not yet an admissible production c-4 profile. Code tracing
confirmed two distinct constraints: (1) the additive forwarding/recording budgets
exceed c-4, and (2) provider recorder selection is independent of room placement.
`can_accept_request` is an instantaneous observation, not a reserved job slot.
Do not resolve this by lowering the two-core floor, assuming one job per node,
assigning a larger profile fingerprint to smaller hardware, or removing the
production startup guard. An eight-CPU exception alone does not solve arbitrary
recording concentration either.

If separate recording capacity is approved, reuse the existing inventory, planner,
prewarm and scaler rather than a second scheduler: distinguish classroom-capable
and recorder-capable nodes, retain guarded recorder exclusion on classroom-only
nodes across restart, and prohibit classroom assignment to recording workers.
Role-specific profiles and worst-case recording concentration/storage must remain
explicit. This path is NOT implemented or qualified; disabling a recorder today
also makes that node ineligible for classroom placement, so it is not a config fix.

The focused operational check must use `app.scheduling.enabled=true` on its isolated
designated backend (with isolated credentials/database), and observe the existing
timer creating reservations before teachers start. Manual `/prewarm` calls cannot
substitute for this proof. End one room and retain a publishing/recording room on
the other node through exclusion, recording settlement and actual cloud deletion;
verify no new assignments to the draining node, bounded retries, continued media
and intact output. The previous functional test only deleted after both rooms
ended. No new paid window has started and neither remaining live gate is marked
passed by local tests or this checklist.

TODO(engine-benchmark, non-release-blocking): compare Pion and mediasoup for
simultaneous 25/50-student rooms on the same dedicated c-4 node, with identical
two-camera/one-screen/audio/720p-recording workload. Record actual recording
placement, per-core forwarding and recorder CPU, admission delays, audio loss and
freezes; repeat the useful boundary rather than the old capacity ladder. Keep
separate versioned engine profiles; never apply the vendor's multi-room 2x claim
as a CourseUltra multiplier. The related backend integration-contract TODO also
tracks the tentative OpenVidu 3.10 multi-threaded mediasoup feature: verify shipping
status before revisiting large-room performance. Neither follow-up blocks Pion.

The benchmark utility now separates **empirical hardware choice** from **allocator
admission**. This corrects treating the additive recording reservation conflict as
proof that a 200-student class physically requires eight CPUs. It does not weaken
the allocator or activate a production profile.

Run `python3 capacity-benchmark.py --people 202 --recommend-workload
pion-3.8-two-360p15-cameras-one-1080p15-screen-audio-720p-recording` (one line).
Full attendance includes teachers; the bands are at 202 and 402 total people,
not students alone. The exact profile assumes dedicated regular c-series hardware,
OpenVidu 3.8/Pion and the resolutions/frame rates stated in the evidence JSON.

- Up to 202 people: c-4 hardware-review candidate. The September 21 full-cohort
  observation lasted about 129 minutes across three rooms/four c-4 nodes, including
  one colocated room/recorder. Brief freezes, isolated loss and alternating cameras
  remain caveats. September 23 adds whole-node CPU measurements, with its initial
  generator issue preserved rather than counted as a clean receiver pass.
- 203–402 people: c-8 hardware-review candidate. The 203 boundary is conservative
  policy, not a measured failure at 203. c-4 at 300 students consumed 67.4% mean
  with one camera versus 80.4% with two; at 400 it repeatedly stalled. A muted
  student does not earn capacity credit when their camera/microphone may return.
  The c-8 clean 400-student hold was ten minutes, not long-duration qualification.
- Above 402, multiple rooms or multiple recording obligations: no automatic
  hardware recommendation from this dataset. The 400+100+100 c-8 overload is
  explicitly retained. Fifty-person rooms are not assumed to cost one quarter of
  a 200-person room. Evaluate rooms separately; this is not a mixed-size scheduler.
- Arrivals retain their actual patterns: two students/second/room in the later
  comparison and five/second ten-second bursts with class starts offset twenty
  seconds in the earlier run. Neither is an enforced throttle or proof of an
  optimal rate. CPU headroom and application join latency are separate signals.
- Recording storage reports the existing four-hour planning allowance: 24 GiB
  per unresolved recording obligation plus 8 GiB per node. Installed usage and
  retained recovery files must be deducted from actual disk free space; these
  allowances are not observed maxima or a four-hour recording proof.

The output includes the unchanged allocator assessment and its c-4 accounting
conflict, not just a recommended node. Observed whole-node CPU already includes
recording; do not add recording CPU to that measured percentage again. Conversely,
those averages/P95 values are not substitutes for peak reservations. Resolving the
production recording eligibility/budget contract remains necessary. This change
does not claim live placement integration, node creation or release approval.

Functional scaling gates are updated separately: September 24 demonstrated ready
node creation, placement and eventual idle removal. Scheduled prewarming and removal
while another node still hosts a class remain distinct, as does production rollout.
No broad benchmark rerun or new infrastructure is required by this offline update.

## Fresh package-source fix — September 24

Fresh master, fixed-media and autoscaled-media bootstrap now replace only the exact
DigitalOcean Ubuntu mirror URI with the official Ubuntu archive before the first
package update. The September 23 nodes failed on inconsistent DEP11 metadata from
that mirror; manual repair is now represented in the provisioning source. Original
source files are backed up once. Suites, components, security repositories and
signature verification remain unchanged. Already-installed nodes are not repaired
by this helper. A changed `user_data` can cause Terraform replacement: review the
plan and never apply a master replacement to production as a routine patch.
Installer versions/checksums, Redis persistence and recording guards are unchanged.
Local tests do not establish live bootstrap success; the focused check must do so.

## Benchmark calibration — September 24

`capacity-benchmark.py` evaluates the September 23 dedicated c-4/c-8 measurements
against the existing `POOL_ADMISSION_V1` arithmetic. This is an offline preparation
tool, not a second scheduler or a live configuration change. Supply full enrollment
plus teachers/other attendees using `--people`; no no-show discount is applied.
The default 20% CPU headroom is an explicit conservative planning assumption, not
a measured safety guarantee. It can be varied for review without altering production.

Examples: `python3 capacity-benchmark.py --node c-4 --people 202` exposes the
existing 2,232m forwarding + 2,000m recording conflict. Adding more c-4 nodes does
not make that colocated envelope fit. `--node c-8 --people 402` fits CPU arithmetic:
6,400m budget minus 3,255m full-room forwarding minus 2,000m recording = 1,145m.
The recorder allowance is reserved once per node by the existing admission mode.
Another room cannot use that already-charged room budget, even if only a few people
are currently connected. Smaller rooms conservatively use the same full envelope;
these measurements do not establish a linear slope or safe small-room packing.

Optional `--profile existing-profile.json` emits the existing profile format with
only CPU/ceiling/evidence fields recalibrated. All non-CPU fields are retained for
review, **not validated or qualified by this tool**. Hardware and recorder allowance
must match the template. Output always has `qualified=false`; its fingerprint changes
when its content changes. Do not modify live reservations to adopt it.

The physical/default media size remains unchanged. Neither the 600-person overload
nor a short 400-person success activates a production profile. Automatic mixed-size
selection is not implemented by this utility. See `docs/COMBINED_CAPACITY_RESULT_2026_09_23.md`
for quality caveats and the remaining live-scaling gates.

TODO(benchmark-refresh): after changing CPU model/size, engine/version, camera/screen
resolution or frame rate, recording preset/layout, or colocating other work, gather
new matched forwarding/recording peaks and user-visible quality. Version the evidence
JSON, re-evaluate the fixed envelope, recording floor, headroom and non-CPU budgets,
then review a new fingerprint. Never scale these numbers proportionally by vCPU count
or erase earlier worse measurements with a newer lower average.

Capacity-created media nodes now carry the exact stack ownership tag in addition
to their media tag, matching isolated inventory and cleanup ownership checks.
Legacy CPU-mode node tags are unchanged. This does not retroactively tag nodes.

## Startup payload transport — September 23

Master, fixed media and autoscaled media startup scripts now use a gzip/base64
shell envelope. The envelope verifies SHA-256 before execution, retains the child
exit status and removes the private decoded temporary file on normal exit.
Compression is not encryption; user data and Terraform state remain sensitive.
Capacity helpers use quoted literal here-documents so compression can reuse common
source text; tests verify their exact installed content and delimiter safety.

Terraform guards fixed-node payloads and the autoscaler checks media payloads before
creation against 65,536 bytes. Offline synthetic capacity-enabled rendering currently
uses 61,563 bytes (master) and 52,639 (media). Media reuses the already-installed
drain helper via a copy rather than embedding its source twice; both destinations
retain the exact reviewed contents and permissions. Rendering with the September 23
campaign's private credentials/profile (synthetic resource IDs, no cloud creation)
passed at 63,255 and 54,703 bytes. Actual credentials/profile data change these sizes;
verify the actual rendered sizes before each campaign. No live bootstrap is
qualified by these tests; the campaign remains blocked on external access checks.
Reverting restores the oversized raw payload and can reintroduce provider rejection;
do not apply user-data changes to running nodes without reviewing replacement plans.

## Successful recording settlement during drain — September 23

Capacity-mode final drain checks now run `settle-recordings.py` before requesting
final application clearance. The existing guard verifies clean stopped media,
restart exclusion and complete Linux process/storage evidence. The backend supplies
only exact closed/imported parts for the durably excluded recorder. Receipts are
stored privately before delivery, bound to boot/container/recording identity, and
reused after uncertain HTTP outcomes. Nothing is deleted by the collector.

After a no-writer proof, empty NE/EGH directories and retired service socket inodes
are data-free residue rather than recordings. Regular files (including zero-byte
files), backup contents, preserved archives, unfinished intents or incomplete probes
still hold the server. Capacity-disabled storage checks retain their prior strict
empty-directory behavior. Unknown recording placement remains protected. This is
locally tested successful-path wiring, not live qualification or a failed-upload
cleanup mechanism; readiness/profile/rollout gates remain.

## Actual recorder location reporting — September 23

Capacity-enabled media watchers now report positive native recording placement using
the pinned current recorder's structured job/handler/service identities. The existing
machine credential, watcher and root-private settings are reused. Unknown or ambiguous
logs leave ownership protected, and a changed boot/container prevents reporting. Each
invocation is bounded so reporting cannot indefinitely prevent guarded drain attempts.

The backend pins the exact recording attempt to an inventoried recorder incarnation;
it does not assume the room server performs recording. An unrelated idle node can then
pass application clearance while the actual recorder remains protected. This reports
location only: it does not settle recordings, remove recovery files, assert recorder
readiness or authorize deletion. Capacity remains disabled pending the complete fleet
and physical-settlement producers, a defensible profile and focused live acceptance.

## Reservation-aware automatic drain delivery — September 23

When both existing capacity and automatic-scale-in switches are enabled, a no-create
provisioning response now leads to `/webhooks/openvidu/capacity/claim-drain`. The backend
selects and durably excludes one exact idle incarnation under its allocation fence.
It preserves the configured ready minimum, queued room demand and aggregate recording
headroom. The function verifies that the receipt identifies a current active Droplet
of the configured size/region, adds the draining tag, then removes the media tag.
Failed/lost tag responses do not undo exclusion or authorize another node. The same
pending target is returned on retry after the capacity plan has refreshed.

This starts only the existing guarded graceful drain. It does not delete a Droplet,
settle a recording, or replace final application/physical storage clearance. Default
switches and the backend activation guard remain unchanged. Operational reporting,
recording settlement and live acceptance are still required. No new scheduler, cloud
credentials, timer or participant-side work was introduced.

## Idle-node application exclusion — September 23

With the existing `capacityReservationsEnabled` switch, media bootstrap installs the
existing backend URL/credential into a root-private drain settings file. Initial mutating
drain-guard checks call `/webhooks/openvidu/capacity/begin-drain`; the final storage/restart
check calls `/exclude-idle` and requires `applicationObligationsClear=true` before deletion.
Beginning drain excludes new assignments but retains finalizing recording obligations
for confirmed-closed rooms. Final clearance still vetoes those obligations. Keeping
these separate avoids requiring settlement before the shutdown needed for its physical
verification. A begin acknowledgement is never final deletion clearance. HTTP failure,
redirect, mismatched identity or a changed boot holds the node; no saved successful
response substitutes for a new check. The guard durably saves only provider/Droplet/boot
identity, not credentials, before shutdown removes provider registration.

The trusted fleet producer must identify `Node.id` using provider registration and
`Node.generation` using `/proc/sys/kernel/random/boot_id`. An absent first registration
cannot acquire this exclusion. Do not erase the identity file or application exclusion
tombstone to force a retry after reboot. Existing ready-peer minimum, graceful one-shot
signals, restart fencing and recording-file preservation remain additional requirements.

This is not activation: reservation-mode scale-in requires the explicit existing switch,
and the backend startup guard remains. Complete trusted fleet/recording/storage inputs
and focused live acceptance are still required. Unknown pooled recorder placement holds
removal while a dispatched recording is unsettled; no cloud tag is treated as proof that
the provider has excluded new jobs. Capacity-disabled behavior remains unchanged.
No new production settings or paid infrastructure were applied. Roll back only with
capacity disabled and preserve all recording data and exclusion identities.

Local checks after the two-phase follow-up: 234 infrastructure tests ran (215 passed, 19 platform/tool skips);
the focused Linux drain/startup/preservation suite ran 96 (95 passed, one missing
Compose-tool skip). Terraform format/validation passed. These exercise local fake
provider/HTTP responses, not live scale-in or an enabled capacity deployment.

This migration branch is pinned to OpenVidu `3.8.0` for an isolated comparison; the
current production engine/version must be reverified before rollout. Do not use
the production backend/state for this candidate. Keep the upstream
Terraform structure intact. CourseUltra-specific changes are
limited to production safety and repeatability:

- the broad provisioning token is used only by Terraform;
- a separate scoped token is embedded in the autoscaler and draining media nodes;
- automatic scale-in is disabled by default without disabling scale-out; the legacy
  opt-in path uses 70% of the scale-out target but is not recording-safe qualification;
- SSH is restricted to configured operator CIDRs;
- Route53 is updated from Terraform and the master waits for DNS before requesting its certificate;
- Terraform state is kept in a private, encrypted, versioned S3 backend;
- helper scripts move secrets between Keychain, SSM, Terraform, and Spaces without printing them.
- the Terraform wrapper fails before planning when any Keychain or SSM lookup fails or is empty;
- cloud-init tracing is disabled and autoscaler request logs redact media-node user data.
- autoscaler deployment scripts use shell primitives supported by both macOS and Linux operators.
- Root-executed OpenVidu, AWS CLI, and doctl artifacts are downloaded over TLS and pinned to
  reviewed SHA-256 checksums.
- provider or monitoring uncertainty holds capacity; it never becomes a scaling signal.
- draining nodes retain firewall coverage, retry self-deletion, and lose their active tag only after
  the draining tag has been confirmed.
- a node carrying both lifecycle tags is excluded from usable capacity. The autoscaler may create a
  replacement to restore the minimum, but it defers further scale-in until that drain leaves the
  active-tag inventory.
- CPU utilization covers DigitalOcean's complete baseline mode set; an unexpected metric shape
  holds scaling until an operator reviews the provider change.
- a timed-out drain remains tagged and retries later; elapsed time never authorizes deletion while
  OpenVidu media containers are still active.
- media bootstrap accepts shared secrets only when their immutable master Droplet ID and private IP
  match the master in the current Terraform graph, preventing address reuse from admitting stale data.
- destroy ordering removes the autoscaler schedule first and waits out its maximum activation time
  before deleting dynamically created media nodes.
- generated credential files and root-operated bootstrap helpers are restricted to the root user.
- cleanup accepts only structurally valid DigitalOcean inventories; malformed successful responses
  fail closed instead of masquerading as empty infrastructure.
- DigitalOcean represents an empty Functions namespace inventory as either an empty array or
  `null`; cleanup normalizes those two provider shapes while still rejecting missing or malformed
  inventories.

The application continues to use OpenVidu's v2 compatibility API. This deployment does not require
a new CourseUltra session model or browser integration.

## Architecture decision

### Persistent drain and one-shot shutdown — 22 September 2026

The media bootstrap installs `media-drain-start-barrier.conf` before the vendor
installer. On an authorized drain the existing guard durably marks the node,
verifies that systemd has loaded the barrier and disables automatic restart for
the exact media/ingress/egress/agent containers. This does not stop active work;
the supported graceful signal remains responsible for excluding new provider work.
A cloud drain tag alone is not evidence that provider assignments have stopped.

Watcher retries now send SIGQUIT at most once per exact container/process. A
durable receipt is written before signaling and confirmed only on success. This
avoids depending on repeated signals being harmless: upstream LiveKit handles a
second shutdown signal as a forced stop. A lost signal acknowledgement, changed
process/container, changed barrier, non-clean exit, retained recovery artifacts or
missing ready peer holds deletion. The watcher never clears those obligations by
timeout. Restart exclusion and storage are checked again immediately before removal.

Operational recovery is deliberate: preserve the marker, receipts, recordings and
logs; establish the actual process/provider outcome before resuming drain or
returning the node to service. Do not delete an uncertain receipt to retry a signal,
clear the marker on a timer or manually recreate containers during drain. Root-level
manual replacement is outside the guard's normal managed lifecycle.

**Deployment boundary:** this changes media-node user-data, not master user-data.
Existing nodes do not inherit it automatically. Review the Terraform replacement
plan and preserve occupied nodes and their recording/recovery files; do not run an
unreviewed apply. Reverting source alone does not undo a running drain or safely
restore container restart policies. These safeguards are independent of the 3.8
migration and do not require a frontend/backend deployment.

**Still unqualified:** a clean recorder exit and empty local recovery paths are
additional deletion vetoes, not proof that every provider recording has reached a
terminal state with durable output. Keep automatic scale-in disabled until that
obligation and the focused live drain/ready-node sequence are verified. No live
capacity or production scale-in claim follows from the local tests.

Verification: 215 macOS tests discovered, 196 passed and 19 environment-specific
skips; the overlapping offline Linux scaler/drain/preservation selection passed
all 95 tests. Terraform formatting/validation and whitespace checks passed. No
cloud mutation was performed for these checks.

### Agreed release scope and future benchmark refresh — 22 September 2026

Reuse the preserved qualification results for their exact hardware, provider/engine,
workload and recording placement. Do not repeat the broad capacity ladder. The
remaining focused scaling check must establish ready-node addition and safe idle-only
removal, not infer them from pre-provisioned load results. No additional vendor inquiry,
custom recorder fork or new scheduler is planned. The unqualified enrollment adapter
stays disabled; its conservative model is not a provider capacity limit or a reason
to block independent release checks.

Scale-in acceptance: exclude new assignments before the final idle check; account
for starting/running classes, pending starts, recording finalization and unresolved
recovery files. Unknown state retains the node and is reported. A timeout never
authorizes forced deletion. This is the agreed target, not a claim it is live-qualified.

Recording idempotency is **per classroom generation and recording part**, not a
one-recording limit across the fleet. Concurrent teachers, repeated clicks and lost
responses must converge on the same persisted start attempt. Reconcile an uncertain
provider result before issuing another start; a new request key alone cannot bypass
an existing recording. Allow sequential parts only after the previous recording has
definitively stopped. Keep concurrent classes independent. Reuse and verify the existing
native start-intent/dispatch safeguards rather than creating another locking system.

#### Planned follow-up: refresh operating limits using production evidence

**Status: backlog, not started; not a release gate.** Owner: live-session qualification
and infrastructure/capacity maintainers. No collection job, automation or new telemetry
service is enabled by this plan.

- Start from the preserved benchmark manifests and failures, retaining exact versions,
  node plan/CPU type, engine, workload and room-versus-recorder placement. Keep the
  previous three-camera/three-screen workload separate from the newer classroom policy.
- Reuse existing monitoring and application/provider events to summarize real classes:
  enrolled and actual peak attendance, concurrent rooms, active publishers/tracks,
  720p recording jobs and placement, arrival rate, join latency/failures, reconnects,
  interruption duration/recovery, per-core/node/master CPU, memory/network pressure,
  recording finalization/failures and scaling decision-to-ready/drain durations.
  Label missing measurements; do not introduce per-browser provider polling.
- Group comparable configurations; report class counts, observed hours, peak/p95
  loads and quality incidents with denominators. Keep failed classes in the sample;
  separate backend/admission, browser/network, forwarding and recording bottlenecks.
  Use aggregated or pseudonymous identifiers, existing retention/access controls,
  and no raw classroom audio/video, credentials or student names for this analysis.
- Review after a representative set of production classes spans the intended peak
  and concurrency range, and before any server size/CPU type, engine/version, media
  policy or recording setting change. Sparse low-attendance data cannot justify
  higher limits or a no-show discount. No invented sample count or calendar deadline.
- Deliver a versioned operating-profile update with evidence links, limits, headroom,
  readiness lead time, limitations and rollback to the prior profile. Require explicit
  review before changing live thresholds; no automatic limit increases from averages.
  Use targeted synthetic testing only for gaps or proposed limits beyond observed data.

### Recorder admission contract investigation — 22 September 2026

The exact cached AMD64 recorder image pinned by `prepare-fresh-recorder.py`
reports `egress version 1.12.0`. An offline binary check confirms that
`cpu_cost.max_concurrent_web` is silently ignored, even with a non-numeric value;
the recognized `max_pulse_clients` rejects that same invalid type. The deliberately
incomplete test configuration then fails at service startup without Redis. That is
a parser characterization, not successful recorder startup or a production failure.
Reproduce without cloud infrastructure or pulling a different image:

```sh
python3 pro/elastic/tests/check_recorder_admission_contract.py --runtime
```

Do **not** configure the historical upstream `max_concurrent_web` property as a
recording-count guarantee. In the inspected [OpenVidu recorder source](https://github.com/OpenVidu/egress/blob/5172055f74e35927b877b0bd0b006cf9508160cf/pkg/stats/monitor.go),
`max_pulse_clients` measures PulseAudio clients with a temporary admission hold,
not the lifetime of a recording including finalization/upload. CPU admission costs
also have a 15-second initial hold followed by measured usage. Raising the composed
recording cost above the configured CPU budget is not a one-job limit: unlike
upstream LiveKit, this OpenVidu source does not exempt the first job from that
budget, so the first recording can be rejected too. A nonzero request CPU estimate
can also override the configured cost. Source revision and image provenance have
not been matched; the version string alone must not be treated as that proof.

This closes off two unverified shortcuts; it does not unblock the scheduler. The
backend's current `POOL_CONCENTRATION_V1` budget charges the maximum outstanding
recording obligations on every eligible worker. Three obligations at its 2000m
planning minimum require 6000m on each worker and cannot fit on c4, regardless of
how many c4 workers are added. Do not lower the minimum, assume co-location, or
turn on the activation flag to hide this mismatch.

These findings limit the current strict reservation model. The subsequent agreed
release scope above does not pursue a custom image or another support inquiry and
does not make a per-worker recording-count guarantee a prerequisite for independent
release checks. Enrollment activation remains blocked on its own accurate model;
automatic removal remains disabled until its focused safety qualification passes.
This investigation changed no provider setting and provisioned no servers.

### Separate scale-out from unqualified removal — 22 September 2026

September 23 follow-up: the first drain attempt now checks the candidate's own
identity-bound, fresh native room/client/track counters before altering restart
behavior. Any occupied, missing or stale observation holds it. A retry after all
media containers have exited cleanly may continue without native registration.
This closes the missing occupied-media veto, not the separate recording/reservation
gate or the new-start exclusion race. Graceful one-shot shutdown and storage vetoes
remain necessary; automatic scale-in remains disabled until the complete path passes.

`automaticScaleInEnabled` defaults to false. Minimum recovery and CPU-driven scale-out
remain available; lowering the maximum never bypasses the removal switch. Capacity
mode still refuses automatic scale-in regardless of this legacy switch. This does not
enable the disabled enrollment adapter, establish a numeric safe class capacity, or
cancel existing drain tags/watchers. Inventory and reconcile those before rollout.

The final on-node drain guard now also inspects the stopped recorder's actual storage
bind and refuses deletion for retained tmp/backup entries, preservation intent/archive,
missing or redirected directories, abnormal exit or a changed recorder identity. It
does not delete artifacts or infer a successful upload from an empty directory. Even
empty retired job directories require review; expect some drains to remain held.

These are local safety fixes, **not completed idle-only scale-in**. Before enabling it,
the shared capacity owner must exclude new room and recording work, account for all
pending reservations and finalization, and verify provider settlement. Polling empty
directories or clean container exits is not that authority. Live placement, qualified
profiles and the focused creation-to-removal browser campaign remain required.

Apply neither this checkout nor user-data changes blindly to production: review the
exact Terraform plan for master/media replacement. Action-code updates can disable
new automatic drains without replacing nodes, but existing nodes need a separately
reviewed guard installation. Keep the 3.8 migration history separate. No infrastructure
was provisioned or changed to verify this patch; tests exercise rendered scaler code,
the real shell removal ordering with fake cloud commands, and temporary local storage.

Read-only production inventory on September 22 found the retained Bangalore master
and media node both on `s-4vcpu-8gb`. The deployed Functions action reports media size
`s-4vcpu-8gb`, minimum 1, maximum 4 and target CPU 50; its four-minute trigger is
enabled. This is not the dedicated-CPU 3.8/Pion qualification configuration. These
observations do not verify the running engine/version or authorize a production resize.

A later authenticated, read-only SSH check on September 22 confirmed the retained
master runs operator/dashboard/v2-compatibility images tagged **3.7.0**, and its
OpenVidu service is active. The compatibility sessions endpoint reported zero rooms
at the observation time. This does not establish the media engine or native room
inventory. The retained production cluster is not the isolated 3.8/Pion qualification
fleet; a production upgrade must be reviewed separately from the drain patch.

Verification of this patch: Terraform configuration validation and formatting pass;
the final macOS suite discovers 203 tests (184 pass, 19 skip), and the overlapping
offline Linux scaler/drain/preservation selection passes all 83 tests. The older
standalone autoscaler migration test cannot run in the recovered clone because its
historical baseline `7e93682` is absent. Do not replace that baseline with HEAD to
manufacture a migration pass; restore the exact history before claiming that coverage.

### Reject incomplete master topology before provisioning dependents — 21 September 2026

The master resource now requires a valid private IPv4 provider observation before
dependent media or autoscaler configuration can consume it. An isolated fresh
bootstrap returned a master ID with an empty private-IP attribute; both media
startup and drain templates consequently contained an empty expected IP. The
existing shared-secret generation check correctly refused startup. Keep that
immutable master-ID and IP check; do not substitute an unverified address.

This guard stops dependent work, not the already completed master creation. On
failure preserve state, confirm the exact created master and its VPC/API/metadata
address, refresh the provider observation, then review a new plan. Do not blindly
repeat creation, taint the master or remove recorder/drain protections. The guard
does not automatically recover a provider observation or repair existing nodes.

Offline `tests/test_master_topology.py` executes the actual lifecycle condition
with Terraform's built-in local resource and an initially unknown computed output.
It checks invalid/missing addresses block both consumers while retaining the
master, and a valid address permits them. No cloud resources are used. This adds
no user-data or recording-policy changes. Deployment and real-provider recovery
remain separately reviewed gates; reverting the guard does not repair any node.

### Redis 8.6.4 isolated compatibility candidate — 13 September 2026

The fresh preparation allowlist also accepts exact Redis 8.6.4-alpine, the default
in the inspected OpenVidu 3.8 master installer. Both Terraform installer checksums
and version now select 3.8 together; this is not deployment approval. The local runtime
test now accepts `--redis-version 8.6.4-alpine` and verifies the observed image ID.
Its default remains 8.6.2-alpine. Unknown versions remain rejected.

8.6.4 passed real Compose preparation, AOF/everysec verification, clean stop and
container recreation, and restoration of a stopped synthetic dataset copy. Tests
used local Docker Desktop ARM64, no host ports and no production data; they do not
qualify production AMD64, vendor-generated 3.8 Compose/entrypoint compatibility,
cross-version data migration/rollback, host loss or abrupt power failure. Re-run
those distinct gates before deploying; do not treat an image-tag allowlist as proof.

The additional `--runtime --upgrade-rollback` mode starts at 8.6.2, restores a
stopped synthetic copy, upgrades that copy to 8.6.4, writes another receipt and
snapshot, then cleanly stops and runs 8.6.2 against that same updated copy. Both
receipts survived the local ARM64 check. This is a narrow AOF-backed Redis result,
not an RDB-only migration, production AMD64 or whole-OpenVidu rollback qualification.
Never substitute a stale pre-upgrade backup for preservation of newer receipts.

```sh
python3 pro/elastic/tests/check_fresh_redis_runtime.py --runtime --redis-version 8.6.4-alpine
python3 pro/elastic/tests/check_fresh_redis_runtime.py --runtime --upgrade-rollback
```

### Preserve the qualified media socket-limit setting on fresh nodes

Fresh media bootstrap installs the media-only Compose override before invoking
the pinned vendor installer: nofile soft 65536, hard 524288. This carries forward
the socket-exhaustion protection from the qualification environment; it does not
solve the separate single-core media bottleneck or establish participant capacity.
An existing, different operator override refuses installation instead of being
overwritten. Existing nodes are not modified. Verify the rendered vendor Compose
and actual mediasoup child-process limits during fresh-node qualification, including
after an installer upgrade. A source-order test alone does not prove those limits.

### Guard vendor automatic startup during fresh installation

The inspected vendor installer enables openvidu.service before our fresh Redis
preparation. Repository restart checks alone cannot protect a reboot in that gap.
Fresh master bootstrap now installs a systemd ConditionPathExists drop-in before
the vendor installer and creates its private completion marker only after Redis
preparation succeeds. It reloads systemd before the first deliberate start.
Do not manufacture the marker after a failed preparation. This is fresh bootstrap,
not an existing-master migration, and changes master user data. Full Linux boot
qualification and real Terraform replacement review remain required. The marker
records successful preparation; it is not a continuous integrity/health check.

### Ready-floor and clean-exit drain protection — 13 September 2026

Before shutdown and again before self-deletion, the media watcher verifies enough
other nodes have matching cloud/native identities, serving state, recent heartbeats
and a healthy endpoint. A Redis claim excludes concurrently draining peers from
spare capacity. Claims do not expire by elapsed time; unregistered native nodes are
removed from the claim set. Unknown inventory, master identity or provider state
holds drain. The helper uses existing private Redis/doctl credentials and is embedded
in fresh media bootstrap; this does not update already-running nodes automatically.

Docker query/signal failures hold drain. Deletion requires every expected media and
agent container to have exited cleanly, without OOM; missing containers are not
proof of successful shutdown. The ten-minute watcher bound only ends an attempt,
never authorizes forced deletion. Held nodes can incur cost and require investigation.

These are necessary protections, NOT recording-finalization verification. Native
terminal recording status and durable output checks are still missing from the
deletion path, and occupied-class/drain qualification is incomplete. Do not deploy
this bundle as proof of recording-safe scale-in. Revalidate the 3.7 native registration
schema before any 3.8 migration. No image/version changes are included here.

### Autoscaler namespace lifecycle — 13 September 2026

Action-code changes redeploy the action without deleting its namespace. Namespace
teardown now belongs to a separate lifecycle resource with stable stack/region
triggers. Dependencies retain namespace cleanup before dynamic media cleanup on
stack destruction. Keep this split when reverting action code: reverting to the
old resource layout can destroy the namespace.

The local `tests/check_autoscaler_lifecycle.py` fixture retains the actual resource
and provisioner structure while replacing cloud commands with local event markers.
It exercises an old-state transition, another code update and stack destroy using
disposable Terraform state. It is not a production plan or cloud API verification.
Before deployment inspect the real plan: no master/media/bucket replacement or
namespace deletion is permitted for an action update. Do not apply these broader
bootstrap changes to production merely to install this lifecycle correction.

### Count retained draining servers — 13 September 2026

Autoscaling reads both active and draining tag inventories, deduplicates Droplet IDs,
and counts their union against the existing maximum for both minimum recovery and
CPU-driven provisioning. A newer drain listing overrides an older active listing.
Unknown inventories hold scaling. Any outstanding drain defers further scale-in.
This prevents draining-only servers held for recovery from disappearing from the
allocation count. It does not prove readiness or recording completion.

At the maximum, retained drains can block minimum-capacity recovery; investigate
the held drain instead of deleting it or silently exceeding the limit. Inventory
reads are not an atomic cross-invocation provisioning lock, so this is not a hard
concurrency guarantee. Deployment still requires the separately reviewed namespace
lifecycle split; applying this action-code change through the old destroy-on-update
resource is not approved. No OpenVidu or Redis version changes are included.

### Interrupted master installation guard — 13 September 2026

The shared master restart script now requires the existing marker to contain
`installation_complete`, not just exist. The installer writes `1` early; treating
that as completion could skip fresh Redis preparation after an interrupted install.
Incomplete or missing markers refuse before service/configuration changes. Inspect
the original bootstrap failure; do not manufacture a completion marker or wipe data.
Completed installations retain their stop/configuration-refresh/start sequence.
This guards the repository restart/retry path, not independent vendor systemd startup;
full Linux boot and interrupted-install qualification remain required before deployment.

### Installer release consistency — 12 September 2026

The `openvidu_installer_release` local in `tf-do-openvidu-elastic.tf` binds the master
version and both installer SHA-256 fingerprints together. This candidate selects **3.8.0**.
New media nodes reject a shared version that differs from this reviewed release before
downloading an installer. They still check the artifact checksum before execution.
Do not change `OPENVIDU_VERSION` in shared secrets alone to perform an upgrade.

For an upgrade, review and update all three values together, verify the customized browser
SDK, fresh-master Redis persistence/restore, and native readiness/drain contracts, then review
the full Terraform plan and data-preserving rollback before applying. These code changes are
not deployment approval. Changes to master user data can replace the master; this refactor
preserves the currently rendered master installer, but adds a media-bootstrap guard and
therefore changes the autoscaler's embedded bootstrap. Do not apply it independently of the
existing autoscaler lifecycle-safety review.

This change does not implement fresh-master Redis persistence, upgrade a running node,
restore missing recording history, or qualify classroom capacity. Those remain separate gates.

### Fresh-master Redis persistence candidate — 12 September 2026

Fresh installation prepares a persistent `/opt/openvidu/data/redis` bind mount before
the first `systemctl start openvidu`. The helper preserves existing Meet override text,
validates the effective Compose change is Redis-only, and enables AOF with `everysec`
plus graceful shutdown. It refuses existing OpenVidu/Redis containers (including stopped
ones), nonempty data, existing Redis customization, unsupported configuration shapes and
unreviewed Redis images. Refusal requires investigation; never delete data to pass this check.

This is **not an existing-master migration**. Applying changed Terraform master user data
may replace the master. Do not apply against production as a way to install this fix.
Existing recording state requires the separate stopped-snapshot, off-host backup and
staged RDB-to-AOF migration procedure. Persistent host storage does not survive master
deletion and `everysec` is not zero-loss or high availability.

Status: locally verified, not deployed. The 68-test infrastructure suite passed, including
13 preparation/refusal tests. A real isolated Docker test passed fresh startup, clean shutdown,
state survival across recreation, and restoration of a stopped dataset copy. The observed
Redis image ID matched `c5e375abb885e6b2021c0377879e4890bf76f9065b8922ffc113f2b226b9fc17`.
Full cloud-init on a fresh Linux master, interrupted-install/reboot behavior and a safe
Terraform replacement/rollback plan remain deployment gates.
TODO on every server upgrade: review the Redis entrypoint, image allowlist, data
mount, permissions and restart survival together; do not merely change the version check.

Repeatable local verification (Docker Desktop context only):

```sh
python3 pro/elastic/tests/check_fresh_redis_runtime.py
python3 pro/elastic/tests/check_fresh_redis_runtime.py --runtime
```

The first command validates real Compose rendering without a running engine; it does not
prove Redis persistence. The explicit runtime mode uses a uniquely named, network-isolated,
one-CPU/256-MiB test container with synthetic state and no host ports, verifies clean stop
and state survival across recreation and stopped-copy restore, then removes that project's
containers. Temporary data and the verification receipt remain for inspection. The runtime
check also enforces the reviewed image ID. These checks do not qualify cloud-init lifecycle,
automated off-host backups, full-disk behavior, host loss or occupied-class continuity.

### Regional topology

CourseUltra already uses OpenVidu's moderated WebRTC room, v2-compatibility API, recording lifecycle,
and in-place subscriber/publisher promotion. The DigitalOcean deployment keeps that application
contract and moves the complete Elastic cluster, including master and media nodes, into one region
and VPC. It was chosen to reduce media-egress exposure without introducing another playback product
or rewriting the live-session domain.

A hybrid AWS-master/DigitalOcean-media design was rejected. Cross-cloud control and media traffic
would add latency, egress, firewall, credential, and failure-recovery paths while departing from the
provider's ordinary colocated topology. Likewise, a separate IVS/HLS broadcast tier is not required
for launch: attendees currently remain room subscribers and one approved learner publishes at a
time. Broadcast-first delivery remains an application-level extension for a future, deliberately
chosen large-audience threshold; it is not an infrastructure shortcut to enable here.

This decision trades cross-region BLR-to-SGP recording staging against a simpler supported media
topology and lower viewer-egress exposure. Revisit it using measured session quality and current
provider pricing rather than preserving historical cost estimates in source control.

## Repository and release ownership

This repository is CourseUltra's fork of `OpenVidu/openvidu-digitalocean`. Upstream remains the
vendor source, while a CourseUltra release branch contains the reviewed overlay for one exact
OpenVidu tag. The Git commit and CourseUltra release tag are the reproducible desired configuration;
the encrypted remote Terraform state records the resources currently deployed.

Do not continuously merge upstream `main` into the deployed branch. For an OpenVidu upgrade, create
a new CourseUltra branch from the intended upstream release tag, reapply and review the small
CourseUltra overlay, update pinned artifact checksums deliberately, and deploy only after plan and
application verification. Tag every applied CourseUltra revision so disaster recovery does not
depend on an operator's uncommitted worktree. Frontend and backend releases consume this platform
through SSM and may ship independently unless their OpenVidu contract changes.

## Retired SGP candidate shape

- OpenVidu version: `3.7.0`
- DigitalOcean region: `sgp1`
- DigitalOcean Spaces region: `sgp1`
- Private Space: `courseultra-openvidu-space-634856ccf8`
- Private VPC: `10.10.20.0/24`
- RTC engine: `mediasoup`
- Modules: `observability`, `openviduMeet`, `v2compatibility`
- Master: `s-4vcpu-8gb`
- Media nodes: `s-4vcpu-8gb`, minimum 1, maximum 4
- Public endpoint: `https://openvidu-do.courseultra.com`
- Route53 zone: `courseultra.com`

These values describe the first acceptance candidate for audit purposes only. Its Terraform state
is empty and its provider resources were destroyed after the BLR production cutover. Do not apply
this profile as a production recovery path.

The original candidate kept compute and storage together in SGP1. Its Space was created through the
control panel and therefore sat outside Terraform ownership; decommissioning deleted it explicitly
after the Terraform stack. Its CDN remained disabled because OpenVidu needs authenticated
S3-compatible object storage, not a public object-delivery endpoint.

## Production BLR compute and SGP storage

Most CourseUltra live-session users are in India, so the production deployment moves the real-time
master and media path to BLR1 while using a new private SGP1 Space only for bootstrap material and
durable provider recordings:

- OpenVidu version: `3.7.0`
- DigitalOcean compute region: `blr1`
- DigitalOcean Spaces region: `sgp1`
- Private VPC: `10.10.30.0/24`
- RTC engine and modules: unchanged from the SGP candidate
- Master and media shape: unchanged, with one to four media nodes
- Production endpoint: `https://openvidu-blr.courseultra.com`
- Infrastructure SSM prefix: `/beinghealer/prod/openvidu/digitalocean-blr`

DigitalOcean does not offer Spaces creation in BLR1 for this account. This was rechecked on
2026-06-20: BLR1 and the `s-4vcpu-8gb` Droplet size were available, and Functions authentication
worked, but both Terraform and a direct signed S3 `CreateBucket` request returned `AccessDenied`.
The failed probe never created a Droplet; its free partial resources and temporary key were removed.

The cross-region storage path is deliberate. Live WebRTC media remains in BLR1. Only media-node
bootstrap reads and recording uploads use SGP1; successful CourseUltra migration copies recordings
to managed S3/CDN storage before provider cleanup removes the provider copy. The v2 compatibility
layer must use `V2COMPAT_OPENVIDU_PRO_RECORDING_STORAGE=s3`: configuring `EXTERNAL_S3_*` alone does
not change its default local recording store, and a master replacement could otherwise erase a
recording before the asynchronous CourseUltra migration sees it. BLR-to-SGP uploads consume the
pooled Droplet transfer allowance, and Singapore staging remains relevant to customers with strict
India-only processing requirements. Never share one Space between clusters because each master
publishes cluster-specific `secrets.env` at the same object key.

The first failed BLR1 attempt caused DigitalOcean to create that region's default VPC. It is named
`default-blr1`, has no droplets, and is intentionally outside Terraform state because DigitalOcean
does not allow deleting a region's default VPC. It is unrelated to the managed SGP1 cluster and has
no standalone charge.

## Verified SGP candidate status

On 2026-06-18 and 2026-06-19 the deployed candidate passed:

- master and media-node cloud-init with active OpenVidu services;
- Route 53 DNS and Let's Encrypt TLS;
- v2-compatible session creation, publisher credential creation, connection listing, and cleanup;
- scoped-token scale-out from one to two media nodes;
- tag-based graceful scale-in and media-node self-deletion back to the one-node floor;
- repeated warm autoscaler invocations without cross-run log accumulation;
- authenticated production webhook reachability;
- an initial drift check reporting `No changes`;
- a zero-session hardening apply that replaced the master and autoscaler Function, preserved the
  reserved IP, drained the old media node, and restored the one-node media floor;
- post-apply master and media-node cloud-init with active OpenVidu services;
- real browser-created webinar and curriculum recordings, including repeated-room `~1` recording
  identity, managed `FileAsset` migration, Files visibility, signed CDN range delivery, and retry
  recovery while provider metadata briefly preceded file visibility;
- provider cleanup of the repeated-room recording while its managed replay remained available; and
- a second post-apply drift check reporting `No changes`.

The tested master was Droplet `578687384`; its final media floor was Droplet `578688262`. On
2026-06-20, after the BLR production cutover and managed replay verification, this SGP candidate was
decommissioned. Terraform removed both Droplets, the autoscaler Function, firewalls, tags, reserved
IP, SSH and Spaces keys, and `openvidu-do.courseultra.com`. The external Space
`courseultra-openvidu-space-634856ccf8` and its sole bootstrap object were deleted separately, and
candidate-only SSM parameters were removed. DigitalOcean retains the empty SGP1 default VPC because
the provider rejects deletion of regional default VPCs; it has no standalone charge and is outside
Terraform state.

## Verified BLR candidate status

On 2026-06-20 the isolated BLR compute and SGP storage candidate passed:

- an initial Terraform apply with 17 additions, no changes, and no deletions against its dedicated
  state, while the SGP and AWS rollback deployments remained running;
- master `579056037` and media node `579056194` cloud-init, service, DNS, TLS, v2 API, restart
  recovery, autoscaler invocation, scale-out, and return to the one-node floor;
- private bucket-scoped access to the candidate Space
  `courseultra-openvidu-blr-space-82487d7f15`;
- a real two-browser creator/student session with camera and microphone fixtures, attendee join,
  hand raise, promotion, revocation, repeated refresh/rejoin, restored speaker video, explicit
  leave, duplicate-tab recovery, and creator end-session teardown;
- authenticated `started`, `stopped`, and `ready` recording webhooks delivered to an isolated
  backend, followed by managed `FileAsset` migration and signed CDN delivery;
- HTTP 206 range delivery with an MP4 `ftyp` signature for the 54,519,102-byte managed replay; and
- deletion of only its disposable provider recording and metadata from the SGP Space, followed by
  the same successful managed replay range request;
- a zero-session candidate-only apply that added durable v2 S3 recording storage, replaced master
  `579056037` with `579063522`, preserved reserved IP `144.126.253.222`, and left both rollback
  deployments untouched;
- generation-safe drain and deletion of media node `579056194`, followed by autoscaler creation of
  media node `579064416` against the replacement master's ID and private IP;
- the complete two-browser moderation and refresh/rejoin matrix on the replacement nodes;
- a new 54,386,960-byte provider recording, authenticated webhook delivery, managed `FileAsset`
  migration, provider deletion, and successful post-deletion CDN range playback; and
- a post-apply drift check reporting `No changes`, plus a warm autoscaler invocation with complete
  metrics and no error.

The acceptance webhook was restored to `https://server.courseultra.com/webhooks/openvidu` after
the test. The deployed BLR master is `579063522`, and its one-node media floor is `579064416`. The
BLR deployment remained side by side with both rollback deployments throughout validation; that
validation was not permission to delete either one. The later production cutover is recorded below.

## Production BLR cutover

On 2026-06-20 at 15:10 UTC, after both the AWS production provider and the BLR candidate reported
zero active sessions, the generic application SSM parameters were switched to the validated BLR
endpoint. The previous AWS values for `url`, `username`, and `secret` were labeled
`pre-blr-cutover-20260620`; `elastic-url` did not exist before the cutover and must be deleted when
rolling back. The backend regenerated its SSM-backed `.env`, restarted under systemd, and returned
`UP` through the production load balancer.

The production smoke test then proved the provider boundary rather than relying only on endpoint
health:

- the production backend created a room and a moderator webcam/screen credential bundle;
- the BLR provider reported that room while the AWS provider remained at zero rooms;
- a browser with synthetic camera and microphone media joined through the production frontend;
- OpenVidu produced a 32-second recording and sent the authenticated production webhook;
- CourseUltra migrated the part to a managed `FileAsset` without an error; and
- the signed managed replay returned HTTP `206`, `video/mp4`, and an MP4 `ftyp` signature.

The test room was ended and both providers returned to zero active sessions. No recording migration
or processing work remained; the normal delayed cleanup marker for the new provider copy remained
scheduled. AWS remains the independent rollback deployment. The acceptance-only SGP DigitalOcean
candidate was later removed as recorded above; it is not a rollback target.

## Secret boundaries

`courseultra-terraform.sh` loads values at execution time:

| Input | Source |
| --- | --- |
| Temporary Terraform DigitalOcean token | macOS Keychain service `courseultra-do-terraform-token` |
| Temporary generic Spaces bootstrap access ID | macOS Keychain service `courseultra-do-spaces-access-id` |
| Temporary generic Spaces bootstrap secret | macOS Keychain service `courseultra-do-spaces-secret-key` |
| Temporary BLR bootstrap access ID | macOS Keychain service `courseultra-do-blr-bootstrap-access-id` |
| Temporary BLR bootstrap secret | macOS Keychain service `courseultra-do-blr-bootstrap-secret-key` |
| Scoped autoscaler token | SSM `/beinghealer/prod/openvidu/digitalocean/autoscaler-token` |
| OpenVidu PRO license | SSM `/beinghealer/prod/openvidu/pro-license` |

Do not add these values to `*.tfvars`, Git, saved plans, shell tracing, tickets, or documentation.
The state itself is sensitive because OpenVidu cloud-init and the autoscaler require generated
credentials. The S3 backend must remain private and versioned.

The Terraform and bootstrap Keychain entries are intentionally absent between infrastructure
changes. Create short-lived credentials for a reviewed plan/apply/destroy, revoke them after the
operation, and remove their Keychain entries. The scoped autoscaler token and OpenVidu license are
the only long-lived entries in this table.

## One-time workstation and state setup

Install Terraform `1.10` or newer and authenticate the AWS CLI to account `408669273539`. The
remote state bucket is `courseultra-terraform-state-408669273539-ap-south-1`; it must remain private,
AES-256 encrypted, versioned, TLS-only, and protected by the S3 public-access block. For the current
BLR production state, create local files from the committed BLR/SGP examples:

```bash
cp backend.blr-sgp.hcl.example backend.hcl
cp courseultra.blr-sgp.tfvars.example courseultra.auto.tfvars
```

Set the real state bucket in `backend.hcl`. Replace the documentation CIDR in
`courseultra.auto.tfvars` with the current operator public IP as `/32`. The Terraform validation
rejects IPv4 and IPv6 `/0` routes so SSH cannot accidentally be reopened to the entire internet.
Neither local file is committed.

The generic examples describe the retired SGP profile and must not be applied as a production
recovery. For a future side-by-side candidate, use a separate worktree and choose a new backend
state key, stack name, VPC CIDR, Space, hostname, SSM prefix, SSH key, lifecycle tags, and
known-hosts file. Never point a candidate at the active BLR state or Space.

Replace the documentation SSH CIDR before planning. A new Space needs a short-lived full-access
Spaces key; store it under candidate-specific Keychain service names and select them only for the
candidate Terraform command:

```bash
COURSEULTRA_SPACES_ACCESS_ID_KEYCHAIN_SERVICE=courseultra-do-blr-bootstrap-access-id \
COURSEULTRA_SPACES_SECRET_KEY_KEYCHAIN_SERVICE=courseultra-do-blr-bootstrap-secret-key \
./courseultra-terraform.sh apply
```

After Terraform creates the required Space resources and permanent bucket-scoped key, delete the
full-access bootstrap key and its two Keychain entries. The generic Spaces Keychain service names
belonged to the retired SGP deployment and are intentionally absent.

The autoscaler token requires only the operations used by the runtime: Droplet read/create/update/
delete, Monitoring read, Tag read/create/delete, and the required Region, Size, Action, Image, VPC,
and SSH-key reads. It does not need Functions, Spaces, firewall, reserved-IP, or account-wide write
access. DigitalOcean token scopes cannot be changed after creation; regenerate an incorrectly
scoped or expired token and replace both its Keychain and SSM copies.

Initialize and validate:

```bash
./preflight.sh
./courseultra-terraform.sh init -backend-config=backend.hcl
terraform fmt -check -recursive
python3 -m unittest discover -s tests -v
./courseultra-terraform.sh validate
./courseultra-terraform.sh plan
```

Do not save a plan file: upstream cloud-init contains sensitive values. Review the terminal plan
and apply directly only when it contains the expected master, VPC, firewalls, private Space,
bucket-scoped Spaces key, Route53 record, Functions namespace, and autoscaling resources.

## Deployment

```bash
./courseultra-terraform.sh apply
```

The master waits for its reserved IP and the Route53 A record to agree before requesting the
Let's Encrypt certificate. The autoscaler runs every four minutes and creates media nodes until
the configured minimum is reached. Do not cut the application over while cloud-init or the first
media-node installation is still running.

After applying the BLR/SGP candidate, keep every generated artifact and SSM parameter isolated:

```bash
COURSEULTRA_OPENVIDU_SSM_PREFIX=/beinghealer/prod/openvidu/digitalocean-blr \
./persist-runtime-secrets.sh

./secure-bootstrap-artifacts.sh \
  "$HOME/.ssh/courseultra-openvidu-elastic-blr.pem"

COURSEULTRA_OPENVIDU_SSM_PREFIX=/beinghealer/prod/openvidu/digitalocean-blr \
./persist-openvidu-candidate.sh

COURSEULTRA_KNOWN_HOSTS_PATH="$HOME/.ssh/courseultra-openvidu-elastic-blr.known_hosts" \
./configure-courseultra-webhook.sh \
  "$HOME/.ssh/courseultra-openvidu-elastic-blr.pem"
```

The first command writes the generated, bucket-scoped Spaces credentials to SSM. The second
refreshes the Terraform-generated SSH key at `~/.ssh/courseultra-openvidu-elastic.pem` with mode
`0600` directly from encrypted state. Current cloud-init never uploads that private key to Spaces;
the script also removes the legacy bootstrap object when upgrading an older candidate.
`secrets.env` must remain private in Spaces because new autoscaled media nodes use it during
bootstrap.

The third command copies the generated v2-compatible URL, username, and secret into the selected
candidate SSM prefix. It does not overwrite the SGP candidate or live application parameters. The
fourth command configures the existing authenticated CourseUltra
recording webhook on the new master and restarts OpenVidu. It stores host trust in the dedicated
`~/.ssh/courseultra-openvidu-elastic.known_hosts` file rather than changing the operator's ordinary
SSH trust store.

For an isolated acceptance backend, override only the endpoint for that invocation. The helper
accepts a single HTTPS URL and still reads the shared webhook token from SSM; it never writes the
endpoint or token into Terraform state:

```bash
COURSEULTRA_WEBHOOK_ENDPOINT=https://temporary-tunnel.example/webhooks/openvidu \
COURSEULTRA_KNOWN_HOSTS_PATH="$HOME/.ssh/courseultra-openvidu-elastic-blr.known_hosts" \
./configure-courseultra-webhook.sh \
  "$HOME/.ssh/courseultra-openvidu-elastic-blr.pem"
```

Use this only while the isolated receiver is running. After acceptance, omit the override and run
the same command again to restore the production endpoint. Both invocations restart OpenVidu, so
first verify that the candidate has zero active rooms. Never point the production cluster at a
temporary tunnel.

After the complete application smoke matrix, recording flow, autoscaling, and rollback path have
passed, revoke the broad Terraform token and Spaces bootstrap key. Create fresh temporary
credentials and place them in the documented Keychain entries before any future plan, apply, or
destroy. Keep the scoped autoscaler token active and rotate it through SSM plus a Terraform apply.

`courseultra-terraform.sh output ...` is deliberately read-only and uses only the existing AWS
backend identity. Routine webhook and recovery helpers therefore continue to read state outputs
after temporary Keychain credentials are deleted. Every other Terraform subcommand retains the
full credential-loading path.

Always run Terraform through `courseultra-terraform.sh`. In addition to loading inputs, the wrapper
passes the current provisioning token to Functions cleanup and the current scoped autoscaler token
to dynamic-media cleanup. Cleanup fails on provider errors and verifies that namespaces and tagged
Droplets are gone. Token rotation is ignored as a `null_resource` lifecycle trigger so changing a
credential cannot accidentally execute destroy-time cleanup during an ordinary apply.

Changes to master cloud-init, including installer pin updates, replace the master Droplet. Inspect
the full plan and perform such updates only in a scheduled zero-active-session window. Changes to
the autoscaler source replace its Function deployment but do not delete active media nodes.
Because dynamic media nodes are outside Terraform state and store the master's private IP at
bootstrap, drain the pre-update media nodes after the replacement master is healthy. Let the new
autoscaler restore the configured floor, then verify the replacement nodes, scale-out, and graceful
scale-in before reopening rooms.

The durable v2 recording-storage setting is part of master cloud-init. Applying it to a candidate
that was originally installed with local recording storage therefore replaces that candidate's
master. Before this apply, finish or stop every candidate room, confirm the v2 API reports zero
active sessions, and preserve any disposable test evidence that is still needed. Apply only the
candidate state and require the plan to leave the SGP and AWS deployments untouched. The private
Space and already-migrated CourseUltra assets survive the replacement; the reserved public IP also
survives, but the SSH host key changes. Follow the media-node capture, replacement, host-key
refresh, and drain sequence below, then repeat the browser and recording-migration acceptance
matrix before considering application cutover.

Record the current media-node IDs before applying the master replacement:

```bash
(
  set -euo pipefail
  ACTIVE_TAG="courseultra-openvidu-blr-media-node-tag"
  AUTOSCALER_TOKEN="$(aws ssm get-parameter \
    --region ap-south-1 \
    --name /beinghealer/prod/openvidu/digitalocean/autoscaler-token \
    --with-decryption --query Parameter.Value --output text)"
  curl -fsS \
    -H "Authorization: Bearer $AUTOSCALER_TOKEN" \
    "https://api.digitalocean.com/v2/droplets?tag_name=$ACTIVE_TAG&per_page=200" \
    | jq -er '.droplets | if length > 0 then .[].id else error("no active media nodes") end' \
    > /tmp/courseultra-openvidu-blr-old-media-node-ids
  chmod 600 /tmp/courseultra-openvidu-blr-old-media-node-ids
  printf 'Pre-replacement media nodes:\n'
  cat /tmp/courseultra-openvidu-blr-old-media-node-ids
)
```

After the replacement master is healthy and has published its new `secrets.env`, drain only those
recorded nodes. The shared file carries both the master Droplet ID and private IP; new nodes reject
old files even when DigitalOcean reuses an address. The drain order is an invariant: add the
draining tag and confirm it before removing the active tag. The helper preserves that order, skips
nodes confirmed already deleted, and retains the ID file after any ambiguous failure so the same
command can be retried safely.

```bash
COURSEULTRA_MEDIA_NODE_ACTIVE_TAG=courseultra-openvidu-blr-media-node-tag \
COURSEULTRA_MEDIA_NODE_DRAINING_TAG=courseultra-openvidu-blr-draining \
  ./drain-courseultra-media-nodes.sh \
    /tmp/courseultra-openvidu-blr-old-media-node-ids
```

The helper deletes the ID file only after every recorded node is absent or safely draining. On
failure, fix the reported provider or response problem and rerun the same command; never remove the
active tag manually. The autoscaler creates replacements after the old nodes leave the active
inventory, and each new node waits until the Space contains the current master's Droplet ID and IP.
The helper defaults to the original SGP tags for backward compatibility. A side-by-side candidate
must pass both candidate-specific overrides shown above; unsupported tag characters fail before
any provider request, and a node without the selected active tag is never modified.

The reserved public IP survives a master replacement but the server host key does not. After the
Terraform apply and DigitalOcean control plane both confirm that the reserved IP belongs to the new
master, refresh only the dedicated trust entry while reconfiguring the webhook:

```bash
COURSEULTRA_KNOWN_HOSTS_PATH="$HOME/.ssh/courseultra-openvidu-elastic-blr.known_hosts" \
  ./configure-courseultra-webhook.sh \
    "$HOME/.ssh/courseultra-openvidu-elastic-blr.pem" \
    --refresh-host-key
```

Do not use `--refresh-host-key` for a routine webhook rerun or before independently verifying the
replacement. Without the flag, a changed key fails closed.

When rotating the autoscaler token, every media node bootstrapped with the old token must be
drained and replaced before revoking it. A Terraform apply updates the Function and future
media-node bootstrap; it cannot rewrite credentials already stored on running Droplets.

## Application cutover and rollback

Before changing production SSM:

1. Confirm there are no active CourseUltra live rooms.
2. Confirm OpenVidu recording migration and provider-cleanup queues have no pending work against
   the AWS cluster.
3. Record the current versions of `/beinghealer/prod/openvidu/url`, `elastic-url`, `username`, and
   `secret`; SSM version history is the rollback source.
4. Validate the DigitalOcean cluster through an isolated backend and frontend.

At cutover, update those four application parameters to the DigitalOcean URL, `OPENVIDUAPP`, and
the generated `LIVEKIT_API_SECRET`, then reload and restart the backend. The webhook token is
unchanged. Existing managed `FileAsset` recordings remain in CourseUltra storage and are not moved
to DigitalOcean.

The 2026-06-20 cutover is complete. Its supported rollback restores the AWS values labeled
`pre-blr-cutover-20260620` for `url`, `username`, and `secret`, deletes the generic `elastic-url`
parameter that did not exist before cutover, then reloads SSM and restarts the backend. Confirm zero
active BLR rooms and drain any recording migration/cleanup work before switching. The AWS
`openvidu.courseultra.com` deployment remains intact; the acceptance-only
`openvidu-do.courseultra.com` SGP deployment has been decommissioned and must not be used for
rollback.

## Upgrade discipline

### September 24 startup packaging correction

The combined-CPU candidate's actual private configuration rendered a66,139-byte
master startup payload, above DigitalOcean's65,536-byte limit, despite the
synthetic-credential test fitting. Only media-node watchers execute the local
recording-location reporter. Install that helper on media nodes only; the master
retains fleet reporting and its required dependencies. Helper bytes and drain,
recording and startup guards are unchanged. The same private configuration then
rendered63,035-byte master and57,919-byte media payloads. Render each deployment's
actual configuration before provisioning; synthetic tests now reserve2,000 bytes
for configuration variance. This is an offline packaging correction, not a live
scaling or production-release pass.

OpenVidu recommends redeploying DigitalOcean Elastic stacks for upgrades. Start each upgrade from
the new upstream tag, reapply the small CourseUltra patch deliberately, run `terraform validate`
and a full plan, and deploy side by side when the upgrade changes OpenVidu services or networking.
Re-download installer and CLI artifacts over HTTPS, review their release changes, and update pinned
SHA-256 checksums only after verification. Do not merge arbitrary upstream `main` changes into a
running production stack.


## Shared media capacity candidate

The paired backend/collector candidate uses physical worker holds for foreign work.
See [SHARED_MEDIA_CAPACITY.md](SHARED_MEDIA_CAPACITY.md) for accounting, rollout
requirements and the limits of observation-based admission. No deployed changes
are implied by this source change.
