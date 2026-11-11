# September 23 combined capacity comparison

Status: measurements completed; this is not full automatic-scaling or production-release approval.

## Decision

Keep the four-CPU default distinct from the optional eight-CPU profile. The measured
dedicated four-CPU node had useful headroom at 200 students, substantially less at
300, and reproducibly failed at 400 with two transmitting cameras and colocated
recording. Eight dedicated CPUs materially improved that same 400-student workload.
However, three recorded classes totaling 600 students overloaded even that node.
Concurrent classes must be placed using expected workload and recording reservations;
reactive scale-out cannot split an already-running room between media nodes.

This run does **not** establish an exact maximum class size, a production guarantee
of 400, or three 200-student recorded classes on one four-CPU node.

## Frozen setup and provenance

- OpenVidu 3.8.0/Pion, Bangalore. Dedicated regular `c-4` (4 CPU/8 GiB/50 GiB)
  versus fresh `c-8` (8 CPU/16 GiB/100 GiB). Both reported Intel Xeon Platinum
  8280 at approximately 2.69 GHz. Shared-CPU master unchanged.
- Two teachers per class; host camera/microphone plus screen/audio; one approved
  student camera/microphone toggled. Both-camera windows are explicitly identified.
- Synthetic cameras 640×360 at 15 fps; moving synthetic screen 1920×1080 at 15 fps.
  Composed recordings 1280×720, H.264/AAC, on the same node as their rooms.
  Synthetic imagery does not prove equal capacity for every real classroom scene.
- Infrastructure `b57f74a33ed7a315899473665785c3969cb82fa2`, backend
  `650af2ee01f79631b578ef597153cf95589bd075`, frontend `ff761513`.
  Harness base `41e47cd`; private runner derivations and their hashes preserved.
- Ten AWS test machines: one backend, three publishers, six distributed viewer
  workers. No personal Chrome instances used for load generation.
- Approved three-hour/$50 window began 19:26:51 UTC. Classes ended by 21:31 UTC.
  Teardown is manual and must not be counted as an automatic scale-in pass.

## Dedicated four-CPU result

CPU is whole-node utilization, including recording. P95 is over two-second samples,
not a per-core percentile or a one-minute peak. Counts below exclude two teachers.

| Students | Transmitting cameras | Measured UTC interval | Mean CPU | P95 CPU |
|---:|---:|---|---:|---:|
| 200 | 2 | 19:52–19:59 | 64.4% | 70.3% |
| 250 | 1 | 20:21–20:22 | 60.1% | 70.2% |
| 300 | 1 | 20:23–20:29:30 | 67.4% | 75.8% |
| 300 | 2 | 20:30–20:32:20 | 80.4% | 89.5% |
| 350 | 2 | 20:33–20:38:10 | 87.9% | 93.9% |
| 400 | 2 | 20:38:50–20:39:55 | 94.6% | 96.5% |
| 400 | 1 | 20:40:30–20:48 | 79.7% | 88.1% |
| 400 | 2, repeated | 20:48:45–20:50:55 | 94.3% | 96.2% |

At 400, enabling the student camera/microphone twice caused widespread screen stalls
of roughly 80 seconds. Source outbound screen frames continued at 15 fps; sampled
kernel UDP receive errors did not grow during these incidents. Disabling the student
camera/microphone recovered delivery without rejoining the class. This is strong
evidence of a node-workload boundary, not proof of the exact internal scheduling cause.

The recording contains corresponding frozen screen content. A screen-only crop
detector found a 54.9-second unchanged interval and several additional intervals in
the first overload clip. The earlier 200-student baseline clip had none using the
same detector. Successful file decoding alone must not be treated as recording quality.

All measured admission batches succeeded at two students/second. The initial
200-student admission P95 was 2.23 seconds, maximum 3.27 seconds. The final 50-student
batch had P95 2.36 seconds, maximum 2.47 seconds. These are observed times, not an SLA.

### Generator correction — do not erase the initial failure

Initially 25 browser contexts shared each Chrome process. A compositor thread reached
99.6% while total browser-worker CPU looked low. Around 20:18, viewers were redistributed
over 13 Chrome processes per worker, at most eight contexts/process. Presenters and
recording stayed continuous, but viewer attendance did not: the old contexts closed
and viewers rejoined. This is not a continuous attendance soak. The initial 200-person
CPU measurement remains useful, but its receiver quality is not an independent clean
pass. All original metrics remain preserved.

## Eight-CPU comparison and concurrent overload

| Workload | Measured UTC interval | Mean CPU | P95 CPU | Result |
|---|---|---:|---:|---|
| 400 students, 2 cameras, 1 screen, 1 recording | 21:05–21:15 | 43.5% | 50.8% | Clean measured full-attendance hold |
| 400+100+100 students, 2 cameras/class, 3 screens, 3 recordings | 21:17:45–21:19:50 | 94.0% | 95.5% | Severe overload |
| Same 600 students, student cameras/mics off | 21:21–21:24:30 | 80.8% | 88.8% | Long stall recovered; insufficient headroom |
| Back to 400, student camera/mic restored | 21:26–21:30:45 | 43.6% | 51.2% | Clean measured recovery hold |

The first 400-person hold lasted ten minutes; the recovery hold nearly five minutes.
No sampled packet-loss, video-freeze or nonadvancing-track flags occurred in those
holds. Three browser rendering probes had maximum callback gaps at most 250 ms.
That is a short controlled result, not long-duration or physical-device qualification.

All 399 viewer arrivals to the first room succeeded; batch maxima were 2.35 and
3.58 seconds. Then 99 viewers joined each additional room at two/second/room:
P95 2.92/2.83 seconds, maximum 4.21/3.97 seconds, none over 15 seconds. Each room
also had its publishing student and two teachers: 606 connected people in total.
Some transient HTTP 423 status-poll responses recovered without admission failures
or ejecting participants. The previous large admission failure did not recur here.

With all three classes fully publishing, the largest room's screen stalled for
approximately 85 seconds. All 597 viewer contexts recorded freeze changes; the
largest class's 399 viewers registered packet loss. Worst sampled audio concealment
was approximately 14–16%. Mean forwarding consumption was 4.12 CPU cores;
recording egress, Chrome and Xvfb together consumed another 3.25 cores, plus audio
and other system work. Master CPU was about 8.5% and backend about 22.6% in the
sampled overloaded minute: the media node, not the master, was the dominant limit.

Turning off the three student cameras/microphones recovered the long stall while
all 600 students and three recordings remained. CPU stayed around 81%, occasional
short pauses remained, and browser-worker CPU reached approximately 82–92%, with
one peak near 97%. Therefore small remaining rendering pauses are confounded by
generator headroom; this reduced workload is **not** a qualified 600-student limit.
During the severe earlier freeze the browser workers were only around 45–54% busy.

Both smaller classes then ended normally. The original 400-person class remained
connected throughout, recovered cleanly, and restored the student camera/microphone
without reloading. All recordings stayed active until their normal ends.

Recording startup produced 370 UDP receive-buffer errors for the first c8 recording
and 4,928 around concurrent recording startup. Steady overload windows had zero new
sampled receive-buffer errors. This is a separate retained startup finding, not a
proved explanation for the later long freeze.

The c8 large-room recording corroborates the overload: a 180-second screen-crop
sample contains detected unchanged-screen intervals totaling 134.8 seconds, including
50.1, 34.9 and 46.9 seconds. Baseline 400 and recovered 400 clips contain no detected
freezes of at least one second using the same synthetic-screen detector.

## Recording preservation and verification

All four jobs reached `EGRESS_COMPLETE`. Files were downloaded, hashed and fully
decoded at 720p with AAC audio. The first file is about 67.6 minutes, the second
34 minutes, and the two smaller-class recordings about 9.7 minutes each. Their
content still includes the overload incidents described above.

Job IDs: `EG_9LHfKCoSvmU6`, `EG_kEjQcKrHsnkK`, `EG_nGLFLiigmAwS`,
`EG_VUMRCVpgghBU`. Private evidence is retained under
`/Users/ruchirs/.codex/private-backups/cu-native-v3-isolated-20260923-c04b7e29`.
The preservation receipt binds 37 files: four videos and verification reports,
13 node archives and fresh physical recording-storage proofs. It was independently
reviewed by the existing capacity task. Do not commit private archives or credentials.

This diagnostic mode did not qualify the complete managed recording-import/replay
experience. Keep that separate from provider completion and file-decoding evidence.

## Provisioning and scaling: what did not pass

1. Fresh nodes hit a DigitalOcean Ubuntu mirror metadata-size mismatch before the
   OpenVidu installer. They required an empty-node-only recovery to the official
   Ubuntu archive and re-execution of the checksum-verified installation transport.
   The fresh c8 registered after that repair. This is **not autonomous scale-out**.
2. Room placement for the hardware experiment was explicitly pinned, including the
   intentional three-room c8 overload. It did not exercise or falsify the production
   enrollment-reservation scheduler. No automatic mixed-size selection was enabled.
3. This run did not complete a matched pre-provisioned-versus-dynamic 600-person test,
   enrollment-change/no-show scenarios, automatic recording settlement/deletion, or
   the actual scheduled prewarm trigger. Earlier focused evidence remains separate
   in `FOCUSED_SCALING_RESULT_2026_09_23.md`; do not relabel it as this run's pass.
4. The candidate correction to settlement is included in the backend pin but was
   not proved by this manual recording-preserving teardown.

## Narrow next steps — no new broad capacity ladder

- Repair fresh-node package bootstrap in the existing infrastructure workflow,
  retaining installer verification and avoiding changes to running nodes.
- Feed these measured intervals into the existing capacity task. Keep forwarding
  and recording budgets separate; do not infer linear participants-per-vCPU or
  lower the provider's two-core recording allowance solely from mean observed CPU.
- Run one small functional scheduler/ready-node/placement/recording-settlement/
  safe-removal sequence against the exact consolidated candidate. Verify occupied
  and unresolved-recording nodes remain protected. No need to repeat 25/50/75 ladders.
- Do not advertise 600-person dynamic scaling until it has actually been exercised.
  Keep production rollout, rollback and classroom/recording smoke checks explicit.
- Future production benchmarking should collect room/recording placement, expected
  and actual attendance, media profile, per-core/whole-node CPU, queue/join latency,
  loss/freeze/recovery, disk backlog and scaling timestamps. Review anonymized
  distributions before changing limits; hardware, engine, codec, frame rate, recording
  layout or size changes invalidate blindly reusing this profile.

## Cleanup and spend

By 21:42 UTC all ten AWS instances were confirmed terminated, all ten owned security
groups removed, and no campaign-tagged AWS volumes remained. All three owned
DigitalOcean droplets, test DNS, reserved IP, firewalls, SSH key, tags and VPC were
removed through the checked selective plan. Production droplets 579063522 and
599974294 remained present. The recording bucket and its existing storage key were
retained, along with local recordings, database snapshots and metrics. The temporary
provisioning token and read-only recording-download key were revoked after cleanup.
Only the owned local fixture database was stopped; unrelated local development
servers and the user's Chrome session were left alone.

Compute ended about 2 hours 15 minutes into the three-hour authorization. The
estimated compute spend is below $26 using the verified hourly rates and a
conservative entire-fleet window; this is not an invoice. Storage/network charges
have not been billed or independently verified; the authorization reserved $10 for
them. Retained recording storage continues to incur its ordinary storage charges.
