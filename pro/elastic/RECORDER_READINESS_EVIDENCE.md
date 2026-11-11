# Recorder readiness: local evidence and integration boundary

This is not live qualification or approval of a production capacity profile.

## Pinned implementation

The locally preserved OpenVidu 3.8 egress image digest is
`sha256:01a31780783080259b7f218f624e654dc30572be5b5f7999123ac0d98c259475`.
Its preserved egress binary SHA-256 is
`3faddc3e8d1698dbab6b364a495db7517e4f12732f42a2f432043ebe36361db5`.
Disassembly of `Monitor.promCanAcceptRequest` at `0x20d4240` constructs
`StartEgressRequest_Web` and calls `canAcceptRequestLocked` at `0x20cdb80`.
It then checks the service disabled state. This matches the selected function in
[the inspected provider source](https://github.com/OpenVidu/egress/blob/9a6c307fa3e00709ec104a6835eede4b71969200/pkg/stats/monitor_prom.go),
not an attestation that the entire image was reproducibly built from that source.

- `livekit_egress_available`: idle, **not** readiness.
- `livekit_egress_can_accept_request`: simulated Web-request admission at scrape time.
- `livekit_egress_is_disabled` and `livekit_egress_is_terminating`: must both be zero.

The inspected admission path applies memory, disk, Web/Pulse and CPU checks.
Web CPU cost must be at least the room-composite cost for the reviewed browser
recording request. A larger request-level `EstimatedCpu` cannot be inferred from
this metric. Freshness and matching service identity are essential. Positive
evidence does not reserve a recording slot or guarantee the next request succeeds.

The local pinned image contains `/usr/bin/curl`, verified using a temporary,
read-only, network-disabled container that was automatically removed. No recorder,
Redis service, paid server or live campaign was started by that inspection.

## Generated configuration

The reviewed installer template contains dynamic Redis connection details,
LiveKit credentials/URL, health port, and S3 credentials/endpoint/bucket/SSE.
A fleet-wide hash of the complete rendered configuration is therefore unsuitable.
The approval boundary should be the reviewed template plus approved nonsecret
policy, followed by a separately captured exact per-node rendered hash. Unknown
YAML must not become approved merely because it can be hashed.

The preserved template's admission defaults are Web and room-composite CPU cost
2.0 each, maximum CPU utilization 0.8, global CPU monitoring enabled, `cpuload`
allocation, overload killer enabled, and minimum free disk 512 MB. These are
vendor defaults, **not qualified CourseUltra limits**. The template has a health
port but no explicit Prometheus port. Recording resolution remains per-job.

## Implemented and integration requirements

`recorder_admission.py` implements strict metric parsing and the conservative CPU
cost comparison. Its six synthetic tests cover idle-only rejection, disabled or
terminating workers, duplicate/mixed identities, explicit old timestamps, extra
labels and invalid costs. A valid enabled/nonterminating worker reporting
`can_accept_request=0` is retained as known busy, not treated as missing fleet
evidence. Its lack of immediate admission is not a permanent recorder failure.
These tests do not exercise a running provider.

The collector now binds health and metrics listening sockets to the same recorder
PID, cgroup and process start time, checks them before and after the scrape, and
validates the frozen config against its exact guard hash and approved semantic
policy. It retains collection-start timestamps and rechecks boot, Docker identity
and full cloud inventory before reporting. No readiness is inferred from idle.

The authenticated backend retains per-node reports but publishes only a complete,
fresh, reconciled set. It checks current native room/egress ownership and unresolved
provisioning outcomes. Stopped workers retain only an already-fenced same-boot
identity for settlement; they cannot become assignable through missing heartbeats.
Neither an empty active-egress list nor absent provider registration releases work.

The supplied descriptor has only `vpcId` and `region` bound to Terraform's
created VPC UUID and deployment region. No fresh-stack UUID must be guessed;
the approved operating profile and recorder policy remain unchanged. This binding
depends on the VPC, not the master droplet, avoiding a master bootstrap cycle.
The existing minute-based tag watcher reports at startup and again 30 seconds
from startup in capacity mode on both roles. Each fleet report
has a 20-second timeout plus a two-second kill grace; the second completes by
52 seconds under normal scheduling. The subsequent metadata tag read is bounded
to three seconds in capacity mode, for a 55-second watcher budget. This leaves margin against the unchanged
60-second oldest-fact expiry. Stalls still hold readiness, not extend evidence.
All collector/admission regressions are in the normal suite:
`python3 -m unittest discover -s tests -q` from `pro/elastic`.
Bounded recording-location and fleet reports run concurrently under one watcher
lock, so a slow report cannot accumulate overlapping runs. The detached drain does
not retain that reporting lock. Legacy disabled startup templates are preserved.

First-start preparation runs only the reviewed config initializer, validates the
approved semantic policy, creates (does not start) the exact guarded recorder and
uses the existing fresh armer. Normal service startup follows. Existing containers,
nonempty recovery directories, unreviewed initializer access and changed settings
hold this first-start path; it is not automatic crash recovery.

Explicit inputs before the focused live check:

1. `capacityFleetDescriptorJson` contains `operatingProfile` (existing qualified
   profile plus measuredLead/maxWait/maximumScheduledClasses, no inventory), region,
   vpcId, mediaImage, recorderImage, recorderPolicySha256, startupGuardSha256,
   minimumFreeMemoryBytes, minimumFreeDiskBytes and maximumLoadAverage. No sizing or
   resource thresholds are generated. The collector can resolve an omitted
   masterDropletId only from a complete listing with exactly one stack-tagged master.
2. Review the shared master egress template, including explicit observation ports.
   Candidate `prometheus_port: 9094` is unallocated in the inspected pinned template
   (health9093, ingress9091/9092, Mimir9095, Loki9096). This is an integration candidate,
   not production approval. Use `config_policy_fingerprint` on the reviewed parsed
   config to obtain its approval artifact; hashing alone is not qualification.
3. Verify applied cloud firewalls deny incoming traffic to the metrics port, including
   broad, all-port and protocol-wide rules. Collection uses127.0.0.1, but the provider
   listener can bind all interfaces. This change does not open any port or add a
   firewall-management system.
4. Keep capacityReservationsEnabled off until the coordinator approves the measured
   profile and validates first boot, fresh receipts, scheduled prewarm, actual room
   placement, known-busy recorder admission, drain and storage settlement together.
   The current guarded bootstrap remains restricted to the isolated qualification
   stack. This commit is not permission to deploy it to existing production nodes.

Automatic capacity activation remains disabled. No measured limit is invented.

## Fresh template inheritance — September 23

Capacity-enabled master setup now adds the recorder metrics listener on 9094 to
the shared media template before publishing configuration. Fresh autoscaled nodes
therefore inherit the reviewed listener; disabled deployments are unchanged.
Repeated setup preserves one matching entry and rejects a conflicting port rather
than silently replacing an operator policy. This opens no firewall rule and does
not itself prove live readiness; actual process/config/socket checks still apply.
