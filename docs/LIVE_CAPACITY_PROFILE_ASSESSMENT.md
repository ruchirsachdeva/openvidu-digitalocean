# Initial capacity profile: evidence assessment, September 23

Status: **not qualified for activation**. This is a limitation of the available
evidence and current additive capacity model, not a claim that the observed classes
failed to run. Do not repeat the broad load campaign merely to fill missing fields.

September24 RC update: the additive calculation below remains correct for existing
forwarding-only profiles. A new explicit `roomCpuIncludesRecording` candidate with
provider-admission accounting instead uses the measured joint mixed-node CPU peak
3,482m, rounded to3,500m, against a3,600m budget (10% physical headroom). Recording
CPU must not be added again to that joint measurement. This is an explicit policy
change, not a claim that the old2,232m forwarding measurement included recording.
The provider2,000m startup estimate and separate non-CPU recording allowances remain.
Shared-node recordings still have no pinned destination or fixed job-count promise.
The profile remains unqualified until its full configuration and focused live
behavior are checked; see `../pro/elastic/COURSEULTRA.md` for the paired RC contract.

September 24 update: the combined September 23 run and reproducible CPU calibration
are recorded in `COMBINED_CAPACITY_RESULT_2026_09_23.md` and
`../pro/elastic/capacity-benchmark.py`. The earlier c-4 forwarding peak below remains
part of the envelope; the newer lower peak does not supersede it. The measured c-8
400-student forwarding peak is 3,255m, rounded up from two-second samples. With an
explicit 20% planning headroom and the existing recording floor, its CPU arithmetic
fits, but this does not resolve non-CPU profile review or automatic scaling gates.

## Confirmed duration and candidate storage budget

The product owner confirmed **four hours including overrun** on September 23.
This is the supported sizing horizon, not an automatic recording/class cutoff.
At the documented nominal 3,000,000-bit/s video rate, four hours represents
5,400,000,000 bytes of video before audio, container overhead and bitrate variation.
Do not extrapolate the unusually small observed final file as a storage guarantee.

For the focused isolated check, use **8 GiB per full-copy obligation** and budget
three copies (working output, failed-upload backup, retained recovery): **24 GiB per
recording obligation**, plus **8 GiB node free-space reserve** outside that charge.
These are explicit conservative test allowances, not measured maximums. Confirm the
actual simultaneous-copy paths and free disk after image installation; do not count
a nominal disk label or eventual Spaces upload as free local capacity. Existing
retained recovery files consume additional capacity and are never deleted to fit.
Two possible colocated recording obligations therefore require at least 56 GiB of
available recording/reserve space before other explicit room/system allowances.
If measured use exceeds the allowance, retain evidence and stop new allocation;
do not stop an active class merely because its scheduled duration elapsed.

September 24 source-path review: `preserve-recorder-ipc.py` does **not** create a
third media-file copy. It accepts empty retired handler directories and an exact
service socket, rejects other contents, and uses same-filesystem `renameat2`.
Therefore the 24 GiB allowance is a conservative planning assumption, not three
copies demonstrated by this helper. The inspected recorder file sink uploads its
working file and can fall back to local backup storage, but source/image provenance
and peak simultaneous storage still need confirmation before reducing the allowance.
Do not count this finding as a production profile pass: two 3 GiB recording memory
allowances plus the 2 GiB room allowance also exceed the 6 GiB allocatable c-4 budget.

Account API preflight on September 23 confirmed regular `c-8` available in `blr1`:
8 dedicated vCPUs, 16,384 MiB RAM, 100 GiB disk, $0.25/hour. No qualification
Droplets were allocated during this check. Recheck availability/cost before apply.
This is a candidate for the focused check, not a new 200-person certification.

## Evidence retained

Source bundle: `cu-native-v3-isolated-20260921-4a8f61b2` in the operator's private
qualification evidence archive. Relevant files: `QUALIFICATION_REPORT.md`,
`candidate.tfvars.json`, `core-recording-node-observation.json`,
`preserved-media-node-{1,2,3,4}-193331.tar.gz`, and recording verification reports.
The capacity task verified all 16 archived host/container stream sizes and SHA-256
values against snapshot manifests (eight nonempty streams, eight empty suffixes).

Configuration: OpenVidu 3.8/Pion; four dedicated DigitalOcean c-4 media nodes in
Bangalore; shared master; 32-vCPU test backend. Three classes of 200 students and
two teachers. Cameras 640×360 at 15 fps, screen 1920×1080 with audio, 720p H.264
composed recording. One/two cameras alternated in ten-minute intervals: this was
not continuous two-camera qualification for the entire observation. Placement was
pre-provisioned and controlled, not a dynamic-scaling proof.

Host/container analysis covers 17:01:22–19:33:00, including normal End/finalization,
at approximately two-second intervals. These are sampled maxima, not subsecond
peaks. Node 1 forwarded only; node 2 forwarded and recorded another room; node 3
forwarded and recorded its own room; node 4 recorded only.

## What the current planner can honestly accept

`POOL_ADMISSION_V1` reserves one recording envelope on each eligible media node.
For 202 people, observed peak forwarding was **2,232 mCPU**, rounded up from
2.231287 cores. OpenVidu support's recording recommendation and the current planner
require at least **2,000 mCPU** per composed recording. Their sum is **4,232 mCPU**,
already above the node's physical 4,000 mCPU before headroom. Do not substitute
average CPU or the observed 1.303378-core recorder peak simply to make it fit.

For illustration only, 20% headroom leaves 3,200 mCPU on c-4. This is not a selected
headroom policy and does not qualify another server size. More cores, separating
recorder eligibility, or a lower class ceiling need an explicit supported profile;
none should be silently inferred from these measurements.

| Dimension | Observed evidence | Missing before qualification |
| --- | --- | --- |
| CPU | Forwarder peak 2.231287 cores; recorder peak 1.303378; mixed host peak 3.482 | Envelope that fits the recording minimum, forwarding/control work and explicit headroom |
| Memory | Minimum physical 8,326,955,008 bytes; peak forwarding cgroup 917,487,616; recorder 1,872,609,280 | Duration/growth allowance; do not double-count cache or label cgroup usage as RSS |
| Ingress | Mixed peak 22,107,080 bytes/s across physical interfaces | Safe interface budget and isolation of recording startup traffic |
| Egress | Mixed peak 140,852,522 bytes/s; recorder-only 120,299,548 during finalization | Safe public/private/interface limits including upload bursts, not just steady-state averages |
| Packets | Mixed peak 62,336 packets/s | Defensible processing/network ceiling; recorded queue drops at low CPU remain a quality caveat |
| Disk | Minimum root free 39,549,767,680 bytes; largest 150-minute output 1,141,999,467 bytes | Four-hour horizon confirmed; verify local high-water and simultaneous working/backup/recovery copies against the candidate allowance above |

Root free space and final object size are not a temporary-storage budget. Network
throughput observed successfully is not a tested safe network ceiling. Dividing a
202-person peak by 202 does not establish a per-person slope. The existing schema
can represent a conservative fixed full-room envelope with zero incremental demand
up to a qualified audience ceiling, but that does not fix the current c-4 CPU conflict.

## Release boundary

### Published constraints checked September 23

DigitalOcean publishes a 2 Gbps inbound/outbound throughput ceiling for regular
Droplets and also warns of packet-rate limiting without a numeric PPS ceiling.
This supplies a vendor upper bound, not proof that our observed workload is safe
at that bound. [Droplet limits](https://docs.digitalocean.com/products/droplets/details/limits/).

The regular CPU-optimized c-8 plan is listed at 8 dedicated vCPUs, 16 GiB memory,
100 GiB disk, $0.25/hour and $168/month. It is the next candidate for the CPU
envelope above, not an approved production change or automatically qualified
200-person profile. Account/region availability must be rechecked before creation.
[Droplet pricing](https://www.digitalocean.com/pricing/droplets).

LiveKit documents `H264_720P_30` at nominal 3,000 kbps video. At 150 minutes that
alone is 3.375 GB, before audio/container overhead or failed-upload/recovery copies;
the much smaller observed output is not a safe storage-sizing substitute. This
nominal encoding rate is not a hard file-size bound. The four-hour horizon and
candidate recovery allowance are recorded above; no automatic class cutoff is
introduced. [Encoding presets](https://docs.livekit.io/reference/other/egress/api/).

Keep `qualified=false` and capacity activation disabled until the profile is
defensible. Recording-location reporting is implemented separately; it does not
supply fleet readiness or physical recording settlement. Those operational producers
and a focused ready-add / recorded-drain / retry test remain necessary before
automatic scale-out/in can be advertised as verified. Preserve historical failures
and the separately revertible migration. Do not provision an idle test fleet while
these prerequisites are incomplete.
