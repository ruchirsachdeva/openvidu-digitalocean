# Live-session release candidate — handoff updated 29 September 2026

Status: selected live-session sources consolidated and locally verified,
**not a completed production release**. Cluster-runtime and coverage redesign are
outside this ship set. No production configuration is changed by this file.

## Current source handoff — September 29

The September 24 hashes below identify historical evidence, not the current paired
application candidate. Final local source pins after live-only reconciliation:

| Component | Source commit |
|---|---|
| Backend | `cbb0c041` |
| Frontend | `560820ef` |
| Infrastructure runtime | `7090459aa91f3d644d4f889f45a3a06bd31c7658` |

The application candidates retain the preceding reviewed native work and finished
upstream dashboard, workspace, image-editing and reader changes. Infrastructure
adds the missing exact JOB settlement producer, fresh-node archive recovery and
offline scheduled-storage calculation; existing drain safeguards remain intact.
No activation defaults changed. This manifest follow-up is documentation only.

Local backend package SHA-256 (`target/server-0.0.1-SNAPSHOT.jar`):
`1cc7db3c4f7fefaaa59c702742e46d0e2cb9f4d97b1f2d6ae6bfa58eb9dca9e1`.
Frontend `www` tree fingerprint (1,722 regular files):
`1fb22b743925800b5e6b82d86553679879cbf9f724f950f5e1d40753f4728de6`.
The latter is SHA-256 of compact JSON containing path-sorted
`[relativePath, sha256(file)]` pairs, not an archive checksum. These local outputs
can be overwritten by another build: verify/recompute checksums when packaging.
**Actual production artifact locations, private configuration version and rollback
deployment pins remain to be supplied and approved; these are not deployed pins.**

The backend `docs/LIVE_RELEASE_SHIP_SET_20260929.md` is the current branch disposition
and controlled rollout/rollback checklist. The older cross-task report is retained
as inventory, not today's live-only to-do list. Experimental packing and SDK 3.8
remain excluded; clustering and coverage work remain separate by owner instruction.
No clustering handoff is sent until after shipping. See also
`LIVE_RELEASE_RECONCILIATION_20260929.md` for infrastructure integration and gates.

Use the backend candidate's `docs/NATIVE_FULL_RELEASE_REVIEW_20260929.md` for the
whole-release findings and `docs/NATIVE_APPLICATION_ACTIVATION.md` for mode-specific
recording-off checks. Run the frontend `npm run test:live-release` gate. Before
deployment, approve the actual artifact locations and private configuration version
against the source pins above, and preserve the prior deployable rollback pair.
Do not deploy the older hashes below as if they included the September 29 changes.

The classroom release does not newly authorize automatic packing or scale-in. The
occupied-signaling drain follow-up remains unverified in the evidence recorded here;
local passing tests and the capacity campaign are not substitutes for that result.
No production configuration or infrastructure is changed by this handoff update.

Final local verification: backend 391 tests passed; frontend 973 native + 327
integration + 19 SDK checks passed; frontend production and backend package builds
passed. Infrastructure 327 tests ran, 307 passed and 20 platform checks skipped.
These checks do not replace the explicit JOB-settlement/occupied-peer-drain live
gates before new automatic capacity activation. Keep that activation off for the
initial classroom rollout. No repeat broad capacity campaign is required here.

## Historical disposition — September 24, final consolidation

The latest focused run passed scheduled prewarming, readiness, corrected teacher
Start, concurrent-start idempotency, student admissions, both recording completions
and course replay. These startup checks do not need another dedicated test stage.
It failed peer-class continuity: an otherwise idle media node still carried remote
signaling, and its shutdown disconnected four users of the other class.

See [the latest focused result](../../docs/FOCUSED_SCHEDULED_DRAIN_RESULT_2026_09_24.md).
The consolidated guard now retains any node with signaling clients. Its follow-up
live check is only occupied-client hold, then zero-client retry and safe removal.
All temporary servers and owned networking were removed; production was untouched.
The recording concentration policy and reviewed production rollout/smoke remain.
Historical sections below retain their original artifact boundaries; their older
"remaining" lists are not additional new testing requirements.

## Historical September 24 candidate versions

| Repository | Local branch | Commit | Evidence boundary |
| --- | --- | --- | --- |
| `edu-tech` | `ruchir/live-scaling-release` | `7acd67ef` | Unchanged frontend; prior 200-student course regression pass and current eight-person webinar pass |
| `beinghealer-server` | `ruchir/live-scaling-release` | `03554d8b` | Latest live run used `c96af2f9`; subsequent retryable-demand response passes 15 controller tests after integration, not yet live-verified |
| Recovered `openvidu-digitalocean` checkout | `ruchir/live-scaling-release` | `6aadea5` | Latest live run used `939a40a`; restored signaling-client veto and explicit production bootstrap eligibility are post-test corrections; 75 drain regression tests pass |

The infrastructure hash identifies runtime code, not this later report-only update.

### Bounded final removal check

Use two small recorded rooms on two dedicated c-4 nodes, existing distributed
browser tooling and 720p recording. No audience-size ladder. Capture node identity,
room ownership and actual signaling-client counters before changing anything.

1. End the first room normally and verify its recording completes. Keep the second
   room and its recorder active, with at least one known remote signaling client on
   the first node. A zero-client starting state does not exercise the correction.
2. Let the existing scaler/watcher attempt removal. Assert that the first node is
   retained, no shutdown signal is sent, and the peer room's publications and
   recording continue. Repeat the watcher attempt to check idempotent retention.
3. Deliberately leave only the identified remote observers, keeping the peer host,
   another viewer and recording active. Verify zero clients on the candidate node;
   do not erase counters or force provider state to manufacture that condition.
4. Verify the normal retry removes that node only after recording/storage checks,
   while the remaining room continues. If topology cannot supply this scenario,
   report it as unexercised, not a pass based on an already-empty node.
5. End the remaining room, archive/decode its recording and remove owned test
   resources within the approved window. Preserve production and source storage.

No automatic extension or repeated capacity campaign. The previous paid window is
closed; a fresh bounded window is required before provisioning. A successful drain
check does not by itself authorize a different recording policy or production
hardware replacement.

The later September24 combined run found and corrected two concrete regressions,
not a release pass. See `FOCUSED_SCALING_RESULT_20260924.md`. Its tested backend was
`92df2938`; do not attribute that run to the subsequent drain-selection fix.
The JAR hash and earlier suite counts below belong to that preceding candidate.
The consolidated `df9f46a4` Java11 package builds successfully; its JAR SHA256 is
`6ea3eb4d1961cc371f81d29f43364671868a1848c2d143d04631a200d11f53f6`.

RC verification:81 targeted backend tests passed, followed by the real-database
suite (89 existing cases passed; one new fixture failed). Its inventory fixture was
corrected to use the persisted snapshot; the final eight-case recheck passed,
including the new database test and seven benchmark/serialization tests. No
production guard was changed to pass these checks. Infrastructure suite:297 cases,
277 passed/20 platform-dependent skips; after the final estimate-matching refinement,
seven recorder-admission and eleven fleet-readiness tests passed. The15-case
benchmark suite also passed. Counts overlap and are not separate evidence of scale.

Built backend JAR SHA256:
`a2c22a36c3cc8f70d73ad6c1e89c9ad50869d4f0ced27802cd5adfa0654ab36f`.
The disposable local replica-set database was stopped after verification; no paid
resources were created. The candidate is ready for focused qualification, NOT
production release. The historical evidence below retains its original boundaries.

The infrastructure checkout's `origin` is a local recovery clone. These branches
and commits are local; this manifest does not assert a GitHub push, PR, merge or
operations-repository deployment-pin update. Keep migration history separate from
the latest drain correction. Do not squash those rollback boundaries together.

## What the preserved tests establish

The September 22 isolated campaign used OpenVidu 3.8/Pion, dedicated four-vCPU media
nodes, a separate shared master, a 32-vCPU application test server and distributed
AWS browser workers. Three classrooms reached 200 students plus two teachers each;
all nine recordings fully decoded at 720p. Admission improved substantially.

Placement was manual and servers were pre-provisioned. These results do not prove
dynamic scaling, production backend sizing, arbitrary recording placement, an
uninterrupted long soak, managed replay for every fixture or perceptually flawless
media. Preserve the failed/interrupted segments and intermittent impairment evidence.

The infrastructure correction passed 196 local tests with 19 skips, 95 overlapping
Linux tests, Terraform validation/formatting and whitespace checks. These are not
live provider shutdown/reboot or browser tests.

## Production observations, read-only

On September 22, the retained Bangalore master and media node were both shared
`s-4vcpu-8gb` machines. Authenticated SSH showed the master's OpenVidu operator,
dashboard and compatibility images tagged 3.7.0. The compatibility sessions API
reported zero sessions at observation time; this is not native inventory proof.
The remote production Terraform state is distinct from the isolated qualification
state and includes the retained master, Space, keys, networking and autoscaler.

Do not apply the consolidated candidate to production as though it were already
the tested 3.8/dedicated-CPU deployment. Review replacement actions and data-preserving
upgrade/rollback; never delete the retained recording storage or recovery files.

## Application integration follow-up

The backend follow-up introduces explicit opt-in `APPLICATION` mode alongside the
preserved isolated verification mode. Recorded course classes and webinars no longer
need a manual runtime/node list. Provider scheduling chooses the node; the backend
observes and persists the actual node/SID before readiness. Maintenance and recording
import discover paginated native history, including closed classes with outstanding
obligations. Classes explicitly configured without recording retain compatibility;
existing native history cannot silently revert to compatibility.

Application activation requires explicit attendance and teacher/guest bounds, 720p
recording and the existing read-only recording source. It does not enable the separate
enrollment allocator or certify hardware capacity. The backend activation document
describes configuration, quiesced provider migration, rollback and focused acceptance.
No production configuration or provider version has changed through this work.

Local backend verification: 1,124 broad regression tests passed, then 104 overlapping
focused tests passed with the final retry/import/routing cases. Both runs had zero
failures, errors and skips. The disposable local test database was removed; results
and rollout details are recorded in backend `docs/NATIVE_APPLICATION_ACTIVATION.md`.

## Completed application acceptance — do not repeat the ladder

Campaign `cu-native-v3-isolated-20260922-b41f9e03` tested the application candidate
without manual classroom/node mappings. Two simultaneous recorded rooms (course and
webinar, each two teachers and six students) exercised concurrent arrivals, reloads,
student and teacher approval/revocation, cancelled and confirmed screen replacement,
End, automatic recording import, authorized replay/seek and outsider rejection.
Seven concurrent arrivals per room took 1.8–3.4 seconds. Both 720p recordings fully
decoded. A same-build backend restart preserved both closed histories and READY parts.

Keep the limitations attached: webinar learner replay used an explicitly simulated
scheduled end in the disposable fixture; one replay refresh met the existing video
lease guard and later recovered. Transient control retries remained. This is not a
capacity, soak, physical-device or autoscaling result. The two media nodes in this
acceptance were dedicated **eight-vCPU** nodes, not the earlier four-vCPU campaign.

All seven temporary servers, owned networks, managed playback CDN/storage/IAM and
the temporary read-only recording-source key were removed/revoked after preservation.
Recordings, source objects and local evidence remain; production was unchanged.
Production needs its own scoped recording-source credential, not the revoked test key.

September 23 consolidation checks: the unchanged infrastructure runtime passed the
215-test local suite (196 passed, 19 platform/tool-dependent skips), then 83 focused
Linux storage/preservation/drain tests with no skips. The first Linux invocation
could not execute 11 shell fixtures because its temporary mount was non-executable;
the corrected container invocation passed all 83, without source changes. Terraform
format and validation checks passed. These are local regression checks, not live
scale-out/removal evidence. Only this manifest changed during this consolidation.

## September 24 focused scaling result

### Shared-server RC follow-up

The subsequent combined-CPU candidate is NOT the artifact used by the successful
September24 live check. Infrastructure `7d1fd83` adds matching startup/receipt
validation and a disabled combined-CPU profile generator. Backend adds an explicit
`roomCpuIncludesRecording` profile field; frontend remains `c798a06b`.
No separate recording pool is introduced and no production activation is claimed.

The candidate budgets3,500m combined CPU on a3,600m c-4 planning budget for up to
202 total attendees. The10% physical headroom is a changed planning assumption,
not a measured guarantee. Old additive profiles keep their old arithmetic. Full
non-CPU resource templates still need review; a CPU-only recommendation is not a
qualified profile. Actual recorder placement remains provider-selected.

Focused acceptance must exercise: real scheduled prewarm without manual endpoint
calls; ready-node addition; two recorded rooms with simultaneous/staggered starts
BEFORE viewers arrive; subsequent expected-attendance ramp while measuring actual
recording placement and host load; normal End/import; and safe idle-node removal
while the other classroom and its recording remain active. Keep failed quality
samples and recovery evidence; do not repeat the earlier broad25/50/75 ladder.
The recording-concentration case is material: currentCPU admission cannot reserve
future CPU on the provider's behalf. A local arithmetic pass does not prove it safe.

Rollback requires the paired old profile/artifacts after all outstanding reservations
and recording obligations settle. Do not reuse a fingerprint, clear durable control
state or remove the production guard to force activation. No paid infrastructure
was created for this RC preparation; the earlier paid window remains closed.

### Subsequent application consolidation (local; not deployed)

- Backend `c45b1585` merges current master `07648236` into the existing
  `ruchir/live-scaling-release` branch, retaining current production changes.
  Cleanup/activation/benchmark/loader selection passed 38 tests. Only the changelog
  required conflict resolution; provider cleanup preserves upstream managed-asset
  deletion as well as native lifecycle handling.
- Backend `f470398e` separately adds the missing production configuration loading
  path: optional SecureString `/beinghealer/prod/live/application-json`, exported
  through the existing private environment as Spring's JSON property overlay.
  Eleven loader tests passed, including missing configuration, secret escaping and
  access-denied preservation. This does not create the parameter or enable features.
- Frontend `c798a06b` merges current main `ec3817a4` into the existing
  `ruchir/live-scaling-release` branch. All 946 native-classroom tests and the
  production build passed. The live-session import conflict retains both native
  outputs and upstream shared selectors. Build selector warnings remain.
- These commits are locally consolidated, not pushed, production-deployed or
  live-smoke-tested. The earlier live results belong to their exact frozen commits,
  not automatically to these merged artifacts. Migration commits remain in history
  rather than being squashed into unrelated application changes.

The production capacity guard remains qualification-only. The blocker is now a
specific operating-profile decision, not a reason to repeat the broad load ladder:
the current additive model reserves 2,232m forwarding plus the 2,000m recorder floor
for the observed 202-person workload, exceeding physical c-4 capacity before
headroom. Successful c-4 observations remain valid evidence, but do not satisfy
that model. There is no approved smaller-class interpolation or qualified separate
recorder pool. Do not silently change the c-4 default or weaken the guard.

An explicitly approved c-8 large-room exception would be a candidate, not automatic
release approval: review recorder concurrency/eligibility and non-CPU budgets too.
For example, the measured c-8 402-person forwarding envelope plus two concentrated
recorders is 3,255m + 4,000m, exceeding a 6,400m planning budget. The eight-person
functional profile must never be copied into the production large-class profile.
After selecting the supported profile, finish production activation review,
versioned configuration/rollback and one short paired-build classroom smoke test.
No production mutation or new paid infrastructure was made during consolidation.

See [FOCUSED_SCALING_RESULT_20260924.md](FOCUSED_SCALING_RESULT_20260924.md)
for the exact candidate and limitations. The bounded two-room run demonstrated
automatic fresh-node creation without package-mirror repair, reservation-directed
placement, simultaneous recordings, terminal 720p output, durable settlement and
eventual safe automatic idle-node deletion on retry. It did not establish a new
production capacity profile or scheduled-prewarm/occupied-cross-node removal proof.
The earlier checklist below is historical; do not repeat its now-demonstrated
node-creation/placement/settlement sequence as a broad capacity campaign.

## Earlier focused acceptance checklist (superseded by the result above)

1. Finish the operational enrollment allocator's missing connections: authoritative
   workload/profile and inventory, recording admission bound, and native reservation
   settlement. The current application uses provider-default placement; do not confuse
   successful application acceptance with enrollment-aware node assignment. Reuse the
   existing planner, prewarm timer and scaler; keep ordinary joins outside this work.
2. Verify the exact pinned recorder's supported graceful shutdown, terminal recording
   status, durable output and retained-file behavior. The drain marker and clean
   container exits alone are not that proof; uncertainty holds removal.
3. Run one bounded ready-node addition and safe-removal scenario with recorded
   classrooms. Include arrivals during readiness, no new work after exclusion,
   continued existing media, a drain retry/restart and recording verification.
   Do not recreate the 606-browser fleet for this check.
4. Review the exact production upgrade/configuration plan and rollback. Deploy only
   that reviewed scope, run a short browser smoke test, preserve results, and remove
   only the newly owned temporary test compute/networking.

Enrollment/predictive reservation activation stays separate and disabled. Future
production-data benchmark refresh is backlog in `COURSEULTRA.md`, not a release gate.

## September 24 production bootstrap validation amendment

The historical qualification-only variable restriction above prevented a real
production stack from selecting the same guarded fresh-node bootstrap. Validation
now accepts a non-qualification stack only with capacity reservations enabled, an
authenticated HTTPS backend authority, and explicit matching profile fingerprint,
node type and region in its fleet descriptor. Standalone guard activation outside
qualification remains rejected; defaults and startup/arming scripts are unchanged.
Offline Terraform tests cover accepted configurations and malformed/mismatched
configuration rejection. This is configuration eligibility, not capacity approval
or permission to replace a production node.

The backend must approve the **resolved** fleet descriptor (including Terraform's
actual VPC, region and master identity), not placeholder pre-creation values. Keep
the existing two-phase readiness hold and exact backend pin. Apply only through a
separately reviewed data-preserving production rollout; the active isolated live
verification remains on its frozen pre-amendment infrastructure commit.
