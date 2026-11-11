# Enrollment capacity candidate — infrastructure contract v5

Status: disabled local candidate, not placement-enforced or capacity-qualified. Do not enable
before backend admission/provider integration and measured qualification. The backend currently
rejects openvidu.capacity.enabled=true at startup to prevent accidental partial activation.

September 23 update: the historical no-scale-in statements below describe prior revisions.
Reservation mode now optionally delivers a backend-selected idle drain through the existing
automatic-scale-in switch. `/claim-drain` atomically excludes one incarnation, preserves
the requested minimum and current reservation/recording headroom, and replays that target
after uncertain delivery. The scaler only changes lifecycle tags; final deletion still
requires the on-node guard and `/exclude-idle`. This wiring is locally tested, not enabled
or live-qualified. See `pro/elastic/COURSEULTRA.md` for the current delivery contract.

## Change from v1

### Observed recording placement (September 23)

The existing media watcher now invokes `report-recording-locations.py` only when
capacity mode is configured. It reads the authenticated, paginated backend work
list and matches exact EG jobs to NE/EGH identities in the current pinned recorder's
structured logs. It verifies local provider identity, boot, container and storage
mount before reporting. Missing/rotated or ambiguous evidence retains unknown
ownership; reporting is bounded to 45 seconds with a five-second kill allowance.

`GET /recording-locations` and `POST /recording-location` use the existing scoped
machine token. The backend matches the native room and recording attempt, requires
a fresh pool observation containing that exact Droplet/incarnation, and stores
observed placement without releasing any obligation. Reassignment is rejected.
This evidence is historical job ownership, **not** recorder readiness, completed
upload, storage settlement or authorization to delete. The fleet-readiness and
physical-settlement paths are separate from location reporting. Successful-path
settlement is now wired through the existing final drain check; fleet readiness
and live acceptance remain required. This path
is locally tested but not live-qualified or enabled in production.

Removed stateless push floors. An invocation containing the old capacity object is rejected
before cloud access. The existing four-minute trigger keeps its empty body. In capacity mode it
pulls durable backend claims and bypasses CPU/minimum fallback provisioning and ALL automatic
scale-in. Disabled mode retains existing CPU/minimum behavior and drain/finalization protection.

## Contract

POST <capacityBackendUrl>/webhooks/openvidu/capacity/claim with dedicated X-Capacity-Token sends
profileFingerprint, nodeType, stack, allocatedDropletIds, maximum. nodeType is the scaler's configured
provider size and must match the qualified backend plan/intent. The exact ID set includes media and
draining VMs, with dual-tagged machines included once. A scalar count is no longer accepted.
Inventory failure or additional unconsumed pages holds. Response: createAllowed (boolean),
intentId, nodeName, nodeType (also required on no-deficit responses).

Before issuing a new grant, backend requires this identity set to equal its fresh authoritative
allocation snapshot, an actual remaining capacity deficit, and room under its configured maximum.
Stale or equal-count/different-node inventories hold; no CPU/minimum fallback is allowed.
Existing outstanding intents stay observation-only while differing inventories reconcile.

Backend commits a single grant first. Only its true recipient may create, using
stack-capacity-<UUID>. Replays inspect that name. Lost claim/create responses never expire into
another grant. Duplicate matching VMs, malformed receipts, allocation limit and unavailable
authority hold. The ledger is not a provider idempotency key: it prevents automatic retries,
deliberately retaining ambiguous outcomes for manual recovery.

After observing a matching numeric Droplet id, exact name and `size_slug` matching the claim and
configured size, POST intentId and dropletId to /observed. Missing/wrong-size receipts retain the
unknown intent without an observation callback or replacement create.
Empty successful response is accepted. Observation is NOT serving/recording readiness.
Only backend qualified telemetry can clear the intent; fresh allocation must precede another
grant. No production telemetry/placement adapter is supplied in this candidate.

HTTPS is mandatory; redirects are forbidden so credentials are not forwarded. Authority failures
do not log response bodies or credentials. Protect action/state artifacts: sensitive Terraform
input and base64 are not encryption. Use a scoped machine token, not provider/cloud credentials.

Configuration (inactive defaults):

- capacityReservationsEnabled=false
- capacityProfileFingerprint=""
- capacityBackendUrl="" (HTTPS base URL, including application base path if present)
- capacityBackendToken="" (sensitive)

Backend stack/maximum must match the scaler. No numeric node capacity or attendance multiplier
exists here. Backend owns whole-peak reservations; host policy owns its opaque workload version.
See the backend document with this name for detailed state, scheduling and activation contracts.
Backend now offers read-only mixed-size schedule projections with resource-budget-based room sharing and
serialized preparation deadlines, but this scaler still creates only its configured size. Do not
translate a mixed-size projection into its scalar deficit. Mixed-size execution, qualified per-size
measurements and production forecasting/telemetry wiring remain integration gates.

## Verification and limitations

Local autoscaler tests cover one-use creation, replay observation, unknown creation, duplicate
names, maximum limits, authority failure, HTTPS/redirects, empty observations, partial inventory,
rejected push floors, no scale-in/CPU fallback, plus inherited CPU/drain safeguards. Cloud calls
are faked: these tests do not establish actual placement or node readiness.
The identity-contract tests also check active/draining ID propagation and no creation on a
backend inventory disagreement. Backend replica-set tests cover rejection of stale, duplicate
or missing IDs, legacy plans, and matching inventories with no deficit or no allocation headroom.
Node-type tests verify request/response agreement, missing/wrong type rejection and wrong-size receipt
holds. No operational sizing values or qualification workloads were introduced.

Current release gates: complete the trusted ready/recording/restart/unmanaged-work
inventory and defensible operating profile, then verify ready-add, recorded drain,
retry and rollout/rollback in a focused live acceptance run. Native room placement
and pooled recorder placement are distinct. The historical four-hour/broad 600-user
campaign below is not a requirement to rerun that ladder: preserve existing evidence
and qualify only the integration/configuration changes still unverified.

Automatic drain selection/delivery and successful recording settlement now exist in
the disabled candidate; they are not proved safe live by local tests or a node-count
floor. Unknown creations still require outcome reconciliation, not timeout release
or deleting the durable intent to force a new create.

## September 16: concentration-safe candidate and restart evidence

This is the next proposed contract, **not an enabled v5 implementation**. Native room
selection is distinct from recorder allocation. For a homogeneous pool, investigate a
global maximum M of starting/active/finalizing/unknown recording obligations and reserve
M times the measured recorder envelope on every actual recorder-eligible node, alongside
its full-enrollment room reservations. The first isolated measurement objective is M=2
on one larger c8 candidate; neither M nor that size is production-qualified. No mixed-size
pool, guessed recorder cost or CPU-based discount is authorized by this hypothesis.

Before operational use, every actual egress candidate must meet the envelope before
registration, including first installation and restarts. Post-start backend readiness,
cloud tags or read-only node inventory cannot enforce that ordering.

Local source inspection (no infrastructure created or generated installer executed):

- The public 3.8.0 media wrapper matches the existing reviewed SHA-256
  `8d79aa04f303ef5ace2abda8233960480441591cb130fd48460770f071d41c71`.
  It pulls the installer image by tag and executes its generated script. The wrapper
  checksum does **not** transitively pin the generator or deployed service images.
- A retained local ARM64 renderer at digest
  `sha256:b2cebd08741e4d7e13bebf54f8758fae7eb5c9dfccf7e65df578806d88157f37`
  generated media-role files with networking disabled, no image pull, no host socket,
  read-only container filesystem and inert test inputs. This establishes template
  behavior for that renderer, not the deployed AMD64 image/config provenance.
- Generated media Compose sets `restart: unless-stopped` on OpenVidu, egress and
  ingress. Its systemd unit requires Docker, has `Restart=always`, runs Compose down
  before foreground Compose up, and the generated installation script enables the unit
  without starting it by default. Current user-data explicitly starts it afterwards.
- Therefore a systemd pre-start check alone does not cover Docker daemon/container
  restart. Conversely, simply disabling Docker restart is insufficient recovery:
  foreground Compose may stay alive while one critical container exits. Do not use
  an all-container abort that lets an ancillary/one-shot exit kill healthy classes.

Next operational work must provide a reviewed, fail-closed first-start/restart path
and bounded per-service failure recovery without forced interruption of healthy rooms
or recordings. Verify merged Compose, existing container restart settings, correct
architecture image digests, retained disk obligations and actual provider registration
ordering. Keep these gates separate from the small M2 measurement: that isolated
single-node experiment can measure startup/concentration without claiming dynamic
pool admission or restart enforcement. No production configuration changed here.

## Opt-in recorder process guard — September 16

`pro/elastic/recorder-startup-guard.sh` and its separate Compose overlay are a
**local candidate, default-disabled and not deployed**. They address
one part of the restart gap: the recorder entrypoint itself checks on every launch,
including independent Docker restarts, without controlling the shared stack.
This does not certify the full recorder pool, hardware capacity, or serving readiness.

The overlay pins the inspected linux/amd64 egress manifest
`sha256:01a31780783080259b7f218f624e654dc30572be5b5f7999123ac0d98c259475`.
Its original `/entrypoint.sh` has SHA-256
`f2bdec0a85a20a4ee1954c69924549aba24c73b530029a5a8cc0e1579da38ca0`.
That script attempts EG_* backups but ignores copy errors before clearing tmp.
The candidate therefore refuses **any** tmp/backup-storage residue, hidden entries,
symlinks, unavailable inventory, unknown entrypoint, or mismatched config. It does
not delete, copy, repair, or declare recordings lost. A normal recorder restart may
remain held until an operator safely resolves retained artifacts. Do not automatically
enable this strict rule on occupied existing workers. It is not a past-loss diagnosis.

Successful checks `exec` the original entrypoint as `egress`, preserving PulseAudio
and `/tini -- egress`. The overlay retains independent `unless-stopped` restart and
existing recovery mounts, and does not replace nofile, Redis or operator overrides.
It adds a read-only **file** mount over `/config/egress.yaml`, backed by a reviewed,
root-controlled immutable snapshot, not the operator's mutable runtime-config file.
Required host files under `/opt/openvidu/courseultra-recorder-guard/` are `start.sh`,
`egress.yaml`, `egress-config.sha256` (one lowercase SHA-256 of that config), and
the persistent empty `start.lock` described below.
They must already exist; the mounts refuse automatic host-directory creation.
Bootstrap must also establish empty, real, readable/searchable `tmp` and
`backup_storage` directories under `/home/egress` safely before first launch.
The guard refuses missing directories and never initializes or empties them.
The snapshot contains credentials: never commit/log it, use restricted parent/file
permissions that still permit the container's non-root egress user to read it, and
qualify rotation before use. Read-only container mounts do not prevent host-side
writes: controlled snapshot production/rotation remains mandatory. Merely hashing
arbitrary config is not profile approval.

Before any operational activation, qualify guard/snapshot/overlay ordering **before**
recorder first-start, and prove the merged configuration on
every actual candidate, including the master and operator-managed replacements.
No authoritative reviewed-config producer or complete pool inventory exists here.
Preserve config-generation ordering; prove that nested read-only mounts behave as
rendered and operator updates cannot recreate an unguarded recorder. Retain a
single controlled recorder process per recovery directory: this guard does not lock
out an unrelated writer or solve concurrent/out-of-band access to the same disk.

Local tests execute an inert entrypoint, verify repeat-start/residue/config failure,
process identity, exit/signal propagation and render-only Compose invariance. They
do **not** run the actual vendor image, Docker restart, daemon/host reboot, Chrome,
or PulseAudio. Next proof must cover these on disposable Linux, with a healthy
co-resident forwarding process, guarded fresh/reboot ordering and preserved recovery
files. No all-container abort or full-stack restart is an acceptable replacement.

TODO(OpenVidu upgrade): re-inspect the exact AMD64 manifest, original script, user,
config and signal chain; repin only after tests. Do not drop preservation checks
merely because the provider fixes a recording-list or multithreading issue.

### Fresh isolated wiring, still unarmed

`isolatedRecorderGuard` defaults to false and is accepted only for the exact
`courseultra-openvidu-38-qualification` stack. When opted in, both master and media
cloud-init install an additional systemd condition **before** the vendor can enable
its unit. Following the installer (and the master's existing Redis preparation),
the helper checks the node's role. On media nodes, `prepare-fresh-recorder.py`
validates and merges the recorder override, preserves
all other rendered services, and creates restricted placeholder files with the
explicitly invalid fingerprint `UNARMED`. Only then does bootstrap write the
recorder-prepared marker and start the ordinary stack. That marker means guard
wiring finished, **not** readiness or permission to record. The guard refuses the
placeholder on every container restart, while the operator/init can generate its
normal runtime config separately. The pinned elastic master has no static recorder
service: its helper branch verifies that absence and leaves its override/data
untouched, rather than adding a recorder. The master must not gain a recorder in
this campaign; operator/out-of-band worker absence still requires live inventory.

With the switch off, both cloud-init templates remain byte-for-byte identical to
the preceding `85ea388` candidate. Local tests guard against introducing an
unintended default-path node replacement through whitespace or shell code.

Fresh preparation rejects any existing/stopped OpenVidu container, recorder data,
symlinked paths, custom recorder override or partial prior guard setup. It does not
migrate or discard anything. Local shell/config fixtures check ordering and rejection;
actual init independence, reboot ordering and the Linux mounts remain live gates.
The first live guarded bootstrap exposed an inherited-umask defect: cloud-init's
077 reduced requested recovery-directory mode0770 to0700, leaving root-owned tmp
unreadable to egress UID1001/GID0. Fresh preparation now explicitly sets the intended
mode on only its newly created empty recovery paths; a restrictive-umask regression
protects this. Existing trees still cause refusal, not recursive permission repair.
Do not turn this flag on for an existing cluster: Terraform may replace nodes when
user-data changes. The campaign must review an isolated create-only plan first.

After runtime config has been reviewed against the approved workload, the separate
`arm-fresh-recorder.py` helper can install the root-controlled snapshot and hash for
an exact stopped, guarded, unarmed recorder. It requires the independently reviewed
config fingerprint, original placeholder contents, exact guard source, pinned
container contract/read-only mounts and empty recovery directories; it rechecks
container identity/state before writing. It never stops, starts or deletes a
container or recording. The campaign must first prove ownership and absence of
workloads, stop only the unarmed recorder, and control competing operator actions.
This is a bounded isolated operation, not a distributed lock against host admins.
The campaign must then
**recreate only the target media-node egress container**. A restart alone keeps old
file bind-mount inodes. Neither missing config nor a placeholder can authorize it.
Local arming tests cover changed fingerprints, writable mounts, live containers,
identity changes, symlinks and recovery residue; actual runtime verification is pending.
Verify the guarded
entrypoint/mounts and provider recorder roster before admitting classrooms. Any
unexpected unguarded/operator-recreated worker holds campaign admission.

### Read-only storage evidence collector

Run `pro/elastic/recorder-storage-probe.py` through the campaign's existing
exact-owned-node SSH path. It never deletes files, changes containers,
calls provider APIs or authorizes capacity release. Keep actual samples private.
It enumerates **all** entries in both `tmp` and `backup_storage`, including hidden
and non-media files, with device/inode, ownership, size/allocated bytes and change
timestamps. Descriptor-relative traversal refuses symlink redirection; missing,
unreadable, changing, special-file and over-budget inventories remain incomplete.

The Linux process sample includes boot identity, relevant process birth identities
and open file descriptors under the reviewed host/container storage aliases. This
detects deleted files still held open despite an empty directory listing. It is not
a complete process/job mapping or an atomic no-writers proof: attach the retained
native room/egress/output correlation and process/job map, and verify actual cloud,
container, image, configuration and mount identities across the complete historical
recorder roster. A process appearing or changing outside the observation window
cannot be ruled out by a single sample.

`complete` means only that this bounded collection encountered no reported issue;
it does **not** mean empty storage, successful output, terminal recording or safe
release. Incomplete samples still emit JSON and exit nonzero; preserve them as
unknown evidence. Defaults cap enumeration at 20,000 entries/processes/descriptors
and ten seconds between checks. A blocked syscall still requires the caller's
outer SSH/process timeout; a final elapsed-time overrun is also incomplete.

Local verification: twelve collector regressions and the full 146-test infra suite
pass. An offline disposable Linux container, with no network, provider access or
host recording-data mounts, also detected an unlinked-but-open inert file and observed its
descriptor disappear after close. This verifies collector behavior, **not real
OpenVidu cleanup**. Completed recordings still need exact terminal evidence,
verified retained output, storage obligations reconciled and no remaining writer
on every relevant worker before any production release adapter can use this data.
No measured capacity profile or operational cleanup authorizer is added here.

### Guarded M2 outcome and bounded restart follow-up

The qualification owner's `GUARDED_M2_20260916.md` records a completed two-course,
two-recorder measurement, verified output preservation and removal of all owned
compute/network resources. It does **not** qualify automatic armed restart:
the first healthy recorder left a service IPC socket and the guard held its next
launch. A single independently reviewed manual preclass preservation operation
allowed measurement to continue. This is not an automatic recovery pass. Source
`4257e75` plus the documented empty-tmp permission repair ran live; the subsequent
fresh-bootstrap permission fix `3cdc767` was locally tested, not cold-booted there.

Final retained storage matters: there were two **empty `EGH_*` handler directories**
as well as `NE_*/service_ipc.sock`. During active jobs, handler sockets, Chrome
sockets and Chrome symlinks also existed inside recording-related trees. Therefore
an NE-only rule would not solve postclass restart, and accepting all sockets,
empty directories or matching prefixes would weaken recording preservation.
Neither terminal recordings nor successful file decode resolves every disk entry.

The collector now adds POSIX `fileTypeBits` and `specialType` for socket/FIFO/device
inodes. Existing `kind=special`, `unresolved_file_type`, `complete=false` and nonzero
exit behavior remain unchanged. A filename ending in `.sock` is not type evidence.
These are additive diagnostic fields, not a new cleanup policy or readiness state.
Older samples omitted the file-type bits and cannot be retroactively classified
from the filename alone. An actual Linux socket observation or retained full `lstat`
mode is needed. `openFiles=[]` is also **not** proof of no socket listener: Unix
socket descriptors use kernel `socket:[inode]` links, not the storage path prefixes
collected by the original regular-file descriptor observation.

Minimal proposed recovery contract, **not implemented or enabled**:

1. Keep the active preservation checks unchanged. The local cooperating-start lock
   below does not add recovery permission. Recovery is a distinct stopped-service
   operation under the existing host lifecycle owner, not an autonomous cleaner,
   second scheduler or browser-triggered retry. Establish exclusion against Docker,
   operator and host-reboot starts for the whole operation; two snapshots alone
   are not exclusion. The exact mechanism still needs offline proof.
2. Bind evidence to the exact prior boot/container/image/config and mount identities.
   Capture the prior service NE identity and handler EGH-to-recording EG mapping
   while the service is observable; do not reconstruct ownership from prefixes.
   The current collector does not produce this complete mapping.
3. Require no live handler/recorder or relevant Unix listener, with process birth,
   container and namespace evidence. Kernel socket inode and filesystem inode are
   not interchangeable. Unknown inspection, active-only absence or missing history
   holds recovery. All known recording/storage obligations must be reconciled;
   no EG tree, backup entry, upload sidecar or unrecognized artifact is disposable.
4. Only a positively identified stopped-service socket subtree or identified empty
   retired-handler directory is a candidate for preservation. Recheck exact entry
   set, types, ownership and dev/inodes under exclusion. Reject extra files, links,
   nested mounts, changed identity or destination collision. If admitted, preserve
   through collision-refusing same-filesystem rename outside vendor-cleaned roots,
   with durable intent/receipt and disk accounting. Never delete or overwrite.
   Retained socket metadata is required; ordinary tar does not preserve socket nodes.
5. Crash/retry must reconcile the one recorded move by identity, not select the next
   matching directory. Permission/disk failure, partial receipt or changed source
   remains held. Bound retained-artifact growth; moving files is not freeing space.
   This operation cannot release a classroom reservation or settle a recording.
6. Start only the recorder, then require the expected process chain, health endpoint,
   provider eligibility and stable forwarding identity. A new container timestamp
   alone is not recovery. Unexpected operator recreation holds admissions. Do not
   repeatedly move residue or retry until something appears healthy.

Offline-first verification order (no new fleet implied):

| Case | Required result |
| --- | --- |
| Real live and closed Unix socket | Accurate diagnostic type; incomplete, no cleanup authority |
| Regular file/symlink named like IPC | Retained under its actual type; no prefix/name allowance |
| Known service IPC plus known empty retired handler directories | Identity-bound preservation candidate only after stopped-service proof |
| Recording/backup residue, unknown EGH mapping or live listener | Hold; no mutation |
| Destination collision, inode swap, process/boot change or competing start | Hold; no overwrite or forwarding restart |
| Crash before/after move or before receipt completion | Reconcile exact prior intent; no repeat move or silent success |

The first two rows have local collector regressions. The remaining rows describe
future recovery tests, not implemented guarantees. After those pass, a separately
scoped real-node check must prove both empty-service and post-recording restart,
operator/daemon/host-reboot exclusion, retained output and uninterrupted forwarding.
Do not repeat the whole browser load campaign merely to test an IPC lifecycle fix.
If the host owner cannot establish exclusion and identity, retain the safe hold and
seek a supported provider fix instead of introducing another recovery controller.

Collector follow-up verification: fourteen focused tests pass on macOS and in an
offline restricted Linux container, including real live/closed Unix socket fixtures.
The Linux run also exposed an older test's directory-order assumption; assertions
now correlate by descriptor identity rather than list position. Metadata assertions
fail against the previous collector. Startup guards and release decisions are unchanged.

### Socket ownership evidence, not automatic recovery

The next collector change adds `unixSockets`: relevant Unix socket table rows joined
to process descriptors by **network namespace and kernel socket inode**, with PID,
process birth ticks, descriptor and mount namespace for each observed owner. It reads
`/proc/<pid>/net/unix`, not just the collector's own network namespace. Only paths
under the reviewed host/container recovery aliases are emitted; unrelated socket paths
and process command lines/configuration are not retained. Row size and enumeration use
the existing bounded collection budget. Relevant tables, descriptors and namespaces
are rechecked; unavailable/malformed/changing tables and unobserved owners make the
sample incomplete. Normal filesystem socket entries remain unresolved and preserved.

These are **positive diagnostic joins**, not a no-writers certificate. They do not
prove that a socket path in one mount namespace identifies the host filesystem inode.
A socket inherited across a network-namespace change, a relative socket path, an
unobserved process or activity between samples can still require separate evidence.
The caller must retain boot/container/image/config/mount provenance and the explicit
service/handler/recording correlation. Kernel inode and filesystem inode must never
be equated. Empty `unixSockets` or `openFiles` does not authorize preservation,
deletion, vendor startup, recording settlement or release.

Local Linux verification binds a real socket, observes its exact PID/descriptor/kernel
inode, closes it, and confirms that the listener disappears while the filesystem
socket remains unresolved. Fixture tests cover separate network namespaces sharing
an inode number, unavailable/malformed/oversized/duplicate tables, unknown owners,
changed descriptors/namespaces/tables and observation limits. Six initial regressions
failed against the previous collector. This changes no startup or admission policy.

The saved campaign logs do contain explicit NE/EGH/EG identity tuples, but the same
container ran successive NE generations. Container ID alone or the last matching log
line is insufficient: bind a log interval to actual process birth and boot identity.
The existing whole-stack systemd unit runs Compose down/up, so stopping that unit
cannot establish recorder-only exclusion while preserving classroom forwarding.
The operator also has Docker control. The cooperating-start lock below is not an
operator/reboot exclusion guarantee, and no automatic preservation operation is
enabled by these collector changes.

### Cooperating-start lock — local candidate only

Fresh opt-in preparation now creates one empty root-owned mode0640 `start.lock`
alongside the guard. A fourth read-only file bind exposes it to the non-root
UID1001/GID0 recorder. Arming rejects a missing, nonempty, hardlinked or writable
lock file and missing/writable/wrong-source lock mount. The guard opens it read-only
as FD9, then takes a nonblocking exclusive `flock` **before** enumerating recovery
storage. Contention or unavailable locking holds startup; all existing residue,
configuration and vendor-entrypoint checks remain in force. The original vendor
exec/signal chain is retained. No new service, scheduler, cleanup or retry is added.

The existing host lifecycle owner must use this **same inode** for any future
maintenance exclusion. Never replace, unlink, rotate or recreate it while any
guarded container exists: different inodes would create independent locks. This
cooperating lock does not constrain an operator/admin launching an unguarded image,
nor prove all handlers/writers have stopped when acquisition succeeds. Docker stop
completion, exact process/socket/recording identities and durable crash recovery
remain separate requirements. A reboot releases a kernel lock; unfinished future
preservation will also need a persistent intent/start barrier before any move.

The qualification owner tested the exact candidate guard bytes and pinned AMD64
image locally under emulation with no external network, provider credentials or
recording jobs. A root-owned 0:0 mode0640 empty read-only lock stayed exclusively held
through original entrypoint/PulseAudio/tini startup and healthy egress; egress's FD9
was inspected. A second actual guard failed on lock contention. Acquisition succeeded
after stopped-service exit, but a third actual guard still refused the retained IPC
artifacts. Tini closes its own duplicate after spawning; the actual egress child
retains the lock. This job-free proof uses read-only control/config directory volumes,
not the candidate's individual-file binds/bootstrap. It does not test recording-handler
inheritance, operator recreation, daemon restart or host reboot.
All temporary test containers/volumes were removed; only the downloaded image cache
remains. Earlier test ownership/telemetry and overly strict tini-parent assertions
were corrected, not represented as passing proofs.

Verification: full infrastructure suite 167 pass, one Linux-only test skipped on
macOS (168 discovered). The offline Linux recorder suite has 53 pass and only its
Compose-render test skipped (54 discovered); the real socket ownership test passes
there. Compose rendering passes in the macOS suite. Two lock regressions fail when
acquisition is removed in memory; six socket-evidence regressions failed before
implementation. The Linux shell-fixture run requires an executable ephemeral tmpfs;
initial noexec fixtures correctly failed before reaching vendor startup. No production
guard, backend/frontend behavior, measured capacity profile or qualification workload
was changed, and no new paid infrastructure was created.

At `2bacdd4`, automatic preservation/restart remained unimplemented. The following
local primitive advances that work; **operational automatic recovery remains
unimplemented and unqualified**. Do not relax the residue hold or substitute another
load campaign for lifecycle qualification.

### Durable IPC preservation primitive — not an operational recovery adapter

`pro/elastic/preserve-recorder-ipc.py` is a bounded, stopped-service operation for
the existing host/qualification owner. Its standalone CLI deliberately refuses to
run. The caller must provide a fresh verifier that raises on stale or unknown
exclusion/settlement evidence, including operator control, exact historical
NE/EGH-to-EG mapping, verified output, boot/container/mount provenance and absence
of writers. A manifest, old snapshot, successful lock or boolean is not that
authority. This primitive does not supply a production verifier, stop/start any
service, schedule retries, settle recordings or release reservations.

The exact plan binds an operation UUID, prior boot/container/image/config/process
generation, evidence fingerprint and explicit inode/type/ownership identities.
Candidates are the identified service directory containing exactly its socket,
plus explicitly mapped, empty retired-handler directories. Matching a prefix is
never sufficient. Any additional tmp entry, backup obligation, symlink, changed
inode, non-socket content or unknown mapping holds the operation. Cross-device
preservation is refused; **same-device bind mounts still require authoritative
external mount validation**. Bounded scanning limits one operation to 64 artifacts
and retained history to 32 operation directories; this is a guardrail, not capacity
sizing or a deletion policy.

Under the existing exclusive lock, the helper writes and fsyncs the canonical plan
into the **same** `start.lock` inode before any move. The guard now acquires flock,
checks opened-FD/path identity, then checks that FD for nonempty intent. This closes
the pre-lock check race and holds a restarted guard even when tmp is already empty.
Neither process loss nor reboot is permission to discard that intent. A malformed,
partial or different intent remains held for investigation.

Each exact subtree moves via Linux `renameat2(RENAME_NOREPLACE)` into the root-owned
`courseultra-recorder-guard/preserved/<operationId>/` directory outside vendor-cleaned
storage. Nothing is deleted, copied over or treated as freed disk. A new operation
rejects a pre-existing destination before writing intent. Retry reconciles only the
recorded source/destination partition by identity, not another matching filename.
Intent and directory durability are re-established on resume, including already
existing directories and already completed moves. Both source and destination
parents are fsynced before an exact, durable `receipt.json` and its parent are
flushed. Receipt identity/content and empty source are rechecked after final external
verification, then intent is truncated and fsynced without replacing its inode.

Failure before commit leaves pending intent and no permission to restart. There is
one explicit commit-point uncertainty: failure flushing the **final truncation** can
return an exception with an already empty lock, after archive and receipt are durable.
The caller must keep operator/recorder stopped and reconcile the exact completed
receipt using fresh authority; it must not restart on exception or fabricate a
rollback by rewriting intent. Partial receipt writes may finish only their exact
expected prefix after all archived identities are checked again. Completed retries
verify the exact receipt and artifacts without another move. An accepted receipt is
not provider readiness, successful recording output or a capacity-release decision.

Local verification: full host suite 188 discovered, 169 pass and 19 Linux-only skips;
restricted Linux recorder suite 74 discovered, 73 pass and one Compose-render skip.
Together these run all new tests, including real Linux sockets and renameat2.
Failure injection covers twelve post-fsync boundaries, eleven pre-fsync boundaries
with ordering assertions, interrupted renames, journal/receipt partial writes,
collisions, competing lock holders, changed identities, failed final verification
and commit-point uncertainty. Negative controls detect missing intent fsync and
moving the guard intent check back before locking. These are syscall-order/process
failure tests, **not a physical power-loss or provider-host reboot qualification**.

The qualification owner completed one bounded **job-free local real-process proof**
using the pinned AMD64 image under emulation, four individual read-only file binds,
root-owned mode0640 lock and one disposable filesystem. Original egress reached
health200; live NE/socket/process-birth provenance was captured, then its sole writer
was stopped. After actual renameat2, injected process exit before parent fsync left
tmp empty and intent nonempty. The actual guard refused unfinished preservation.
Resuming the exact plan verified original inode identities, durable receipt and the
unchanged lock inode; the same original container restarted once to health200 with a
new NE. The archive was outside all recorder mounts; inode equality was sampled
before restart, not a second time afterward. All exact-owned test containers/volumes
were removed; evidence and the previously downloaded image cache remain private.

That proof ran core SHA256 `58b14bb9cc85bcb48e59c73d0321ac6e011114077f371b1ff2186c6c51c01ceb`
and guard `8c972a477ff1fb79c3ca936bd8d6cab94ec3cab9c1f021a68ba6e7d9479f50ce`.
A subsequent Linux-tested hardening fsyncs an already-empty lock on completed-receipt
replay, closing prior final-truncation durability uncertainty; that completed-replay
branch was not exercised by the real-process proof's pending-intent resume. An initial
fixture-only failure lacked the root helper's required DAC_OVERRIDE capability; it
held at rename, was retained as failed evidence, and was corrected only on the
disposable fixture. No candidate permission rule was loosened to pass it.

Gates remaining before the September 16 cloud proof below: bind this primitive to
the existing lifecycle owner's authoritative verifier, prove operator/daemon/host-reboot
start paths cannot bypass pending intent, and qualify actual retired recording
handlers/output preservation. The local fixture
had no operator, provider credentials, recording jobs, active classes or host reboot;
its sole-orchestrator verifier is **not** an operational verifier. A separate bounded
host wrapper and adversarial tests are required before the one proposed real-node
campaign. No cloud creation or production deployment is implied by these tests.

### September 16 isolated cloud lifecycle results

The qualification owner exercised infrastructure `97a006554531517693d8f07c3679de0bb8c06ef9`
on one isolated OpenVidu 3.8/Pion master and one media node. Two distinct **job-free**
operations shared that fleet; no browser worker, classroom or recording was created.
The detailed evidence chronology is `RECORDER_RESTART_20260916.md` in the native-v3
qualification checkout. This is not capacity measurement or production activation.

- **Same-container recovery passed.** An actual process exit after the first real
  rename left durable intent and the original socket subtree in the archive. Exact
  resume produced a durable receipt and cleared the same lock inode; a separately
  authorized restart reached health 200. Archive inode identities were checked again
  after restart. The co-resident forwarding process identity stayed unchanged; with
  no active class, that is not media-continuity evidence.
- **Reboot startup protection passed.** A new operation was interrupted in the same
  way, then the media host rebooted once. Its ordinary Compose lifecycle replaced
  the recorder container. The replacement retained the guarded entrypoint and
  refused startup because preservation was unfinished. Intent bytes, lock inode
  and both operations' archived identities survived unchanged.
- **Post-reboot recovery remains held.** Fresh current-boot authority with unchanged
  historical evidence was rejected because the recorder container had changed.
  No identity was rewritten, intent cleared or replacement started to bypass that
  check. Explicitly verified replacement authority remains implementation work.
- Starting the original operator for a bounded observation did not recreate the
  recorder; **operator-driven replacement was not exercised**. A standalone Docker
  daemon restart, actual recording-handler cleanup/output preservation and automatic
  production recovery are also not qualified by this campaign.

The qualification wrapper needed two evidence-backed comparison corrections: accept
the exact successfully exited vendor setup helper with `on-failure` policy, and
canonicalize complete Docker mount records by unique destination. Neither changes
runtime configuration or accepts changed mount fields. The initial mount-order
failure happened before stopping services or moving data and remains recorded.
Forty focused wrapper/campaign tests passed independently on macOS and restricted
offline Linux. The core preservation primitive and startup guard were unchanged.

Selective teardown completed at 17:46 UTC, within the original two-hour limit.
Independent provider reads confirmed absence of both test servers, their dedicated
networking, SSH key, tags and DNS record. Production nodes remained active and
retained storage/key/state resources matched the pre-campaign values. Private
evidence and durable-record bytes remain available; no recording media was created.

## Rollback

The diagnostic-only follow-up performs no deployment, provisioning, push or workload change;
the separate isolated campaign's deployment and verified teardown are recorded above.
The lock candidate is not deployed to production. Revert guard, overlay, fresh
preparation and arming together; do not remove a live lock file or mutate existing
recovery storage as a rollback shortcut. Existing armed nodes require explicit migration review,
not in-place replacement of mounted guard/config/lock files. The default-disabled
cloud-init byte-equivalence test still passes.
The preservation primitive and post-lock intent guard must be reviewed together.
Before any future rollback of an exercised candidate, keep affected services stopped
and reconcile every pending intent/receipt; never truncate an intent or remove the
preserved directory to force startup. Existing recorded outputs are not rollback
targets. There is no database migration or backend/frontend contract change here.
Revert only the capacity commit: inherited 3.8 migration/safety history is separate and is not
a 3.7 rollback target. Following future activation, pause scaling/admissions and reconcile all
reservations, recording obligations and unknown intents first. Simply disabling capacity mode
would restore CPU scale-in and can endanger occupied reservations.
Integrate wire v5 on both sides together: old/missing node types fail closed. Legacy allocation plans
must refresh; outstanding legacy intents require outcome reconciliation, not deletion to force retry.
