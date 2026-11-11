# Final focused scaling check — September 24

**Result: not a release pass. A scheduled-start defect was found and isolated.**
Do not repeat the established large-class benchmarks to verify its correction.

## Exact test boundary

Campaign `cu-native-v3-isolated-20260924-f19c3a72` used infrastructure `095ec26c`,
backend `1a4a3cef` and frontend `7acd67ef`: OpenVidu 3.8/Pion, two automatically
created dedicated c-4 nodes, a separate master, and distributed AWS browsers.
The target was two eight-person rooms, not another 200/600-person capacity test.
The webinar transmitted two cameras/microphones, one 1080p screen with audio and
720p recording. The scheduled course never started; its eight opened browser
pages must not be counted as admitted participants.

## Outcomes

| Check | Outcome |
| --- | --- |
| Initial automatic media-node creation | Passed; no manual package repair |
| Start before verified capacity | Held without creating a room or recording |
| Concurrent webinar teacher starts | One room and one recording |
| Webinar student admission/reload | Six joins 2.154–3.458s; deliberate reload 1.866s |
| Scheduled discovery | Reservation created 5.289s after entering the 15-minute lead window |
| Scheduled automatic scale-out | New node created 14:12:26 UTC; installation approximately 194s |
| Readiness before scheduled start | Verified 14:17:28.405, 6m38.8s before 14:24:07.198 start |
| Capacity-plan retention | Desired capacity remained 2 across subsequent server reports |
| Scheduled course Start | **Failed:** both teachers received 500; no second room/job |
| Remote-signaling drain/peer continuity | **Not exercised**, blocked by course startup |
| Recording End/import/integrity | Sole webinar job COMPLETE, imported READY, full 720p decoding passed |

The occupied/reserved nodes were retained by the ordinary scaler. Final whole-fleet
cleanup was explicitly authorized teardown, not successful automatic scale-in.

## Confirmed cause and narrow correction

The course reservation was created at 14:09:12.487 with a 15-minute wait deadline
of 14:24:12.487. Both native-start requests at 14:24:29 failed in
`LiveCapacityReservationStore.reserve`: `Capacity wait expired; explicit retry required`.
The node was ready; advance prewarming had incorrectly consumed the teacher's
start-preparation allowance. No server saturation or browser-generator overload
explains this failure.

The correction initializes the deadline once from
`max(authoritative scheduled start, original request time) + existing maxWait`.
Polling, readiness changes and rescheduling do not extend that persisted deadline.
Expected capacity holds return 409 rather than a generic 500.

The failure also established that the previous “explicit retry” instruction had
no normal recovery route for an expired unbound course reservation. The paired
backend correction permits an authorized teacher Start to retire only a provably
unbound expired generation and reserve a fresh successor. It retains history and
rejects any room, dispatch, recording, storage, admission or uncertain-outcome
evidence. Background discovery cannot renew expired work. See the backend release
branch/changelog for implementation details; neither fix was deployed
into this frozen run, and its failed result is not relabeled.

Consolidated backend commits on `ruchir/live-scaling-release`:

- `1202e4de`: reviewed production fleet descriptor pin.
- `8bdce855`: scheduled preparation deadline and expected-hold response.
- `c96af2f9`: explicit Start recovery for expired, unbound preparation.

The implementation task's broad regression run passed 566 cases. Its final focused
run after missing-schedule validation passed 150 cases, including 104 real-database
reservation cases. Counts overlap; they are not 716 distinct tests or live evidence.
Concurrency, repeated Start after a lost response, fresh successor reservation/bind,
and uncertain recording/admission safeguards are covered. No migration commits were
squashed into these fixes.

After integration into the release branch, 31 focused production-activation,
activation-guard and native-controller tests passed with no failures/errors/skips.
The Java 11 release package built successfully from `c96af2f9`; JAR SHA256:
`0b9ebf40d120d6e988bc5766597f9da2b157c7488d98333c587699091485c74d`.

## Preserved quality and recording evidence

From 14:05 until normal End, 5,958 sampled inbound receiver records showed zero new
audio-loss, concealment or video-freeze increments. This is eight-person functional
evidence, not a new capacity certificate. An earlier node UDP receive-error jump
of 7,137 at 14:01:29 is retained; the settled counter did not increase. Lifetime UDP
errors must not be reported as zero.

The 27m25.741s recording is 1280×720, 197,167,098 bytes; full decoding passed.
SHA256: `faa3f5cf5da74bca56c23a5313865efc291a24cad7a3a7af2f4939b6ccdfcb4e`.
Original provider storage and independent local archives remain. Backend database,
logs, browser traces, host/container metrics and node-creation receipts are preserved.

Initial isolated master creation separately encountered a DigitalOcean pending-event
422 while assigning its already allocated reserved IP. The same IP/master were
reconciled, followed by a DNS-only plan. No master replacement occurred. This was
not a fully autonomous initial-cluster installation pass; media autoscaling is
reported separately above.

## Cleanup and remaining scope

All four AWS workers, three test Droplets and owned networking were removed by
14:38:53 UTC, before the testing cutoff. Fourteen temporary playback resources were
removed after archival. Disposable recording-reader and provisioning credentials
were revoked; the latter returned 401. Production nodes and retained source storage
were unchanged. No new paid window was opened.

The remaining live check is only corrected scheduled Start/retry, then automatic
idle-node removal while the other class/recording continues. Production still needs
the reviewed operating descriptor/configuration, data-preserving 3.8 rollout and a
short smoke check. Do not copy the functional sizing profile into production, claim
all permutations, or repeat the previous class-size ladder.
