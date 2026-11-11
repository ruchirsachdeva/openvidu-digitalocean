# Focused two-class scaling check — 24 September 2026

## Later combined c-4 run: 09:02–10:32 UTC window

Campaign `cu-native-v3-isolated-20260924-9e42b6f0`, approved $20 maximum.
This result supersedes no historical failure and is **not a release pass**.
Production was untouched.

- Tested backend `92df2938`, frontend `c798a06b`, infrastructure `6f213769`.
  The frontend was rebuilt with local test configuration after the original
  production asset origin was blocked by the isolation guard, before login.
  The amendment, original artifact and hashes are preserved.
- Existing scheduled demand processing and the scaler automatically created two
  dedicated c-4 nodes and assigned the expected 202-person course and 52-person
  webinar to distinct ready nodes. Their colocated 720p recordings were both
  admitted. Neither installer required manual repair; media installation took
  approximately 158 and 170 seconds. Both had about 38.2 GiB available after
  installation, above the isolated profile's 34 GiB storage gate.
- The backend became ready after the scheduled prewarm due time; catch-up demand
  provisioned both nodes before course start. This does not prove a complete
  fifteen-minute predictive lead or production readiness. Master installation
  took about 738 seconds; application transfer and test packaging also consumed
  setup time. None reset the paid clock.
- The webinar held 50 students and two teachers. All 51 measured joins succeeded,
  longest 4.384 seconds. In the settled 09:40–09:44 window, 1,200 receiver samples
  across all 50 students showed one additional lost audio packet, 268 concealed
  audio samples, no video packet loss, no dropped frames and no new video freezes.
  These are receiver counters, not a subjective audio-quality assessment.
- The 200-student course **failed**. Most join checks briefly succeeded, then the
  learner page destroyed its live component. Provider logs recorded browser-requested
  departure, not node-capacity rejection. A pass-through browser trace proved:
  join → attendance completion → completion event → enclosing hierarchy refresh
  → routed classroom teardown. Transient successful join checks are not sustained
  attendance and cannot qualify capacity.
- Frontend fix `7acd67ef` keeps live completion as an in-place projection update.
  All 83 related tests and a local-config build passed. It was installed on two
  viewer workers, leaving teacher assets/backend/provider unchanged. Twelve
  students then remained with both teachers; deliberate leave/rejoin succeeded.
  Their 09:56–09:57 receiver deltas showed no new packet loss or freezes. The third
  worker's artifact transfer timed out; it retained the old served build and its
  retry still disconnected. Do not count that actor or call this a 200-person pass.
- In 09:40–09:44, mean host CPU was 30.67% on the webinar c-4, 26.23% on the
  failed-course c-4, 6.33% on master, 3.27% on backend, and 9.64–11.11% on viewer
  workers. No UDP receive-buffer errors increased. The failed course's low CPU
  does not establish 200-person capacity because students did not stay connected.
- Both normal End actions completed recordings; managed copies were archived and
  fully decoded with 1280×720 video and audio (about 657 and 1,243 seconds).
  Webinar student replay before scheduled end still showed waiting after reload;
  this run does not verify that replay experience.
- Automatic scale-in **did not pass**. The ended webinar retained a FINALIZING
  reservation while the other course remained active. Source investigation and
  a failing automatic-selector regression confirmed a circular eligibility veto:
  excluding the worker removed its recorder allowance before cleanup could settle
  its obligation. Backend fix `df9f46a4` (source commit `5106da15`) is consolidated
  locally, with 151 passing planner/transactional tests reported by its worker.
  It permits initial exclusion only; admission and final storage/deletion guards
  remain intact. It was not deployed in this run. Normal provisioning may still
  conservatively request replacement capacity until settlement.

All evidence, configuration amendments, provider/HTTP/browser traces, per-host and
container metrics, database snapshot and recording hashes are preserved privately
under this campaign's directory. The narrow remaining live gate is the consolidated
course fix plus scheduled drain/settlement/removal with an active peer—not another
engine or broad capacity benchmark campaign. Production rollout remains separate.

### Terminal cleanup boundary

All classes ended by 09:57:20 UTC. Both recordings were COMPLETE and archived before
writers were stopped. The scaler was removed at 09:58:58; after the 120-second
in-flight window, exact owned media containers were restart-fenced and signaled
gracefully once. Terminal storage proofs retained all recovery safeguards. With
all media stopped, ListRooms returned 503: terminal cleanup uses the fresh pre-fence
empty-room/terminal-recording snapshot plus current physical stopped-writer proofs,
not a restart or a relaxation of normal scale-in. This manual campaign teardown is
not an automatic-removal pass. Final cleanup inventory is recorded in the campaign
receipts.

At 10:08:17 UTC, all three test droplets and their temporary networking/namespace
were verified removed; production droplets `579063522` and `599974294` remained.
All six AWS workers and their security groups were removed. Playback CDN/storage/IAM
were removed after archiving; the temporary recording-source reader was revoked.
Local test processes were stopped. Retained source recordings and their original
storage credentials were preserved. This finished within the approved window.
The disposable provisioning token was also revoked and verified rejected with
HTTP401 at 10:12:31 UTC; no production credential was changed.

## Earlier eight-person functional run (preserved)

Campaign: `cu-native-v3-isolated-20260924-74a016cd`. Private evidence is in the
same-named directory under the operator's `.codex/private-backups` directory.
Approved window: 23:05:07–00:35:07 UTC, $8 maximum. Production was not deployed.

## Candidate and scope

- Infrastructure `c1361c5a44cbd3424ea0cc8241ba846f553240cc`: fresh-install APT
  mirror correction and offline benchmark tooling.
- Backend `650af2ee01f79631b578ef597153cf95589bd075`.
- Frontend `ff761513ff3842151ad0db1deac7370bd5a71644`.
- OpenVidu 3.8/Pion; two rooms, each two teachers and six students, distributed
  across three AWS browser workers. Two cameras/microphones, one screen with audio,
  and colocated 720p composed recording per room.
- Two dedicated c-8 media nodes with an explicitly functional eight-person profile.
  This was NOT a new capacity benchmark, a change to the default c-4 size, or proof
  of 200/600-person capacity. Do not use the intentionally conservative functional
  reservation weights as a production sizing formula.

## Established

1. The existing scheduled scaler created both media nodes without manual installation
   repair. Fresh media installation took about 156 and 147 seconds. The official
   Ubuntu mirror path was used. The first master installation took about 517 seconds.
2. Application demand/reservations caused a second node to be provisioned; the second
   room was assigned to that node, matching the provider room map. The second demand
   was recorded at 23:37:49; cloud creation occurred at 23:41:50 and service readiness
   around 23:44:50. This delay is why scheduled preparation matters.
3. Both classes reached 8/8. Concurrent arrivals took 2.091–3.288 seconds in the
   webinar and 1.846–3.322 seconds in the course. Deliberate reload/rejoin took 1.754
   and 1.775 seconds. Two concurrent teacher starts produced one recording, not two.
4. Expected publications were verified at the provider. Collected receiver samples
   showed no packet loss or accumulating freezes in the observed settled window.
   Browser workers were not persistently CPU-bound. This short functional check is
   not a sustained media-capacity qualification.
5. Normal End completed both recordings. Managed imports were available, manager
   playback ran, and both downloaded files passed complete decoding with 1280x720
   video and audio. Durations were approximately 1126 and 704 seconds. Student webinar
   replay before its scheduled end remained on the waiting page; do not label that
   experience verified by this run.
6. An occupied-node drain request yielded no candidate. After the first class ended,
   the scaler excluded its node and marked it draining. A fresh provider counter
   still showed four clients despite zero rooms/tracks; the guard retained it while
   the other class ran. After the second class ended, the idle check passed.
7. All three media processes exited cleanly at 00:02:39. Physical storage evidence
   accepted only the already-supported retired IPC residue, with no recording data
   discarded. The first reservation was RELEASED at 00:02:41.693 with its durable
   settlement receipt. The node was automatically deleted by 00:08:36.
   No manual node deletion, forced shutdown, guard relaxation or runtime code patch
   produced that result. Temporary incomplete-pool responses held final checks;
   retry recovered. This establishes eventual safe idle removal, not removal during
   an ongoing class on another node.

## Findings and limits retained

- Prewarm passes were triggered through the existing authenticated endpoint because
  background scheduling was disabled in the isolated backend. Autonomous production
  scheduled prewarming was not qualified. A missed driver pass temporarily left a
  provisioning intent pending; a normal successful pass cleared it.
- The second fixture's ordinary scheduling request correctly failed working-hours
  validation. Only that unopened disposable fixture's timestamps were subsequently
  amended and the receipt preserved. This is not an authoring API success.
- One concurrent-control conflict displayed a recoverable synchronization warning;
  media continued and Check classroom state cleared it. Brief recording-start lock
  responses recovered. Do not report every control permutation as passing.
- The four-client idle hold could reflect cross-node signaling or delayed cleanup;
  the cause was not proved. Do not waive the client counter based on this observation.
- Final removal checks temporarily rejected incomplete pool observations. They later
  succeeded without code changes. Investigate availability/coalescing from preserved
  logs before adding more locking, bypasses or infrastructure.
- Scoped cloud credentials allowed namespace creation/listing but returned 403 on
  namespace deletion. The exact temporary namespace was removed through the logged-in
  console; production namespace was retained. Fresh cleanup state was reconciled
  against the original reviewed resource set. Improve preflight permission checking.
- Initial AWS authentication expired during provisioning. Exact partial state was
  recovered without replaying the old plan or resetting the budget/deadline.
- Fresh-node hostname length produced a nonfatal warning; shorten generated hostnames
  separately if needed, preserving unique cloud resource identity.

## Release interpretation

This closes the focused evidence gap for ready-node creation, enrollment-aware
placement, two concurrent recordings, settlement and retry-safe idle deletion on
the tested candidate. It does not approve production operating profiles, prove
predictive scheduling, occupied cross-node removal, or verify a production rollout.
Keep historical capacity failures and the separately revertible 3.8 migration intact.
Use the existing benchmark evidence to finish the exact production configuration;
do not restart the broad capacity ladder for this result.

## Cleanup

At 00:18:47 UTC, the verified final DigitalOcean inventory contained no test droplets;
both production droplet identities remained. All four AWS workers and their security
groups were removed. The temporary namespace, DNS, reserved IP, firewalls, VPC and
SSH key were removed; playback CDN, managed test storage and IAM were removed after
archiving both recordings. The temporary read-only recording-source credential was
revoked, as was the temporary provisioning token. Retained source recordings and
their original bucket/key were unchanged.
Local test backend and Mongo processes were stopped; evidence and data files remain.

Cleanup finished within the original 90-minute deadline. The listed full-fleet
90-minute compute upper bound was approximately $3.67, below the $6 compute cap;
actual billing, storage and network charges are not claimed as invoiced amounts.
The functional run is complete; no replacement test fleet is left waiting.
