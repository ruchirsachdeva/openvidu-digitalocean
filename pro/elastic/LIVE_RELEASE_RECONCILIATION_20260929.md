# Live infrastructure source reconciliation — 29 September 2026

## Readiness alert and short-cancel closeout — 1 October 02:30 UTC

Backend `a74d10d9c0597c1e0041c81631bb12eaf7dd2879` deployed successfully through
pipeline `c8c83fc6-0a23-4972-8cd4-1b29af27c01b`. The running backend accepted the
new authenticated readiness recovery signal without sending an email. Readiness
holds now use their own eight-minute debounce; actual/unknown provisioning errors
remain immediate. Debounce is process-local and restarts with the backend.

Infrastructure commits `71b6459` and `48fc959` are installed on the retained media
node and in future-node bootstrap. Autoscaler action SHA-256 is
`468e40a7ccb7225d05fcaf94fe48b7b8f1b06172b57490590f92375e94e1a40c`;
installed job-helper SHA-256 is
`e45c8f74475b70f093457b64f557b1863ddcfd60a544c244a0b2b89120531ae0`.
The actual bootstrap is 65,495 bytes, below the 65,536-byte provider limit;
future changes must re-render and check the actual private profile.

Live cancellation check: preparation began 02:16:41, recording became ACTIVE
02:16:51, and cancellation completed 02:16:54. No ordinary classroom admission
occurred. Job `EG_YD4Z2AMtokdm` reached COMPLETE. It had no saved active sample.
The first idle observation was 02:17:01.810272; the check exposed unordered Docker
mount-list comparison, which safely retained capacity. The corrective comparison
sorts exact mount bindings and has a changed-mount rejection regression. After its
installation, the normal scheduled watcher generated `IDLE_PREPARATION` proof
with terminal observation 02:23:01.473672 and verified time 02:23:01.501809.
All reservations were then released without manual settlement, node drain/reboot,
process termination or file deletion.

The two prior managed class recordings still read READY with 3,862,656 and
5,070,559 bytes. Test schedule and organization hours were restored; restoration
temporarily widened only the test organization's start hour because its original
historical schedule began before the restored 07:00 working-day start. Original
07:00–15:00 Asia/Kolkata hours are restored. The initial schedule harness wrongly
expected COMPLETED rather than SUCCEEDED; this was corrected without changing
application scheduling behavior or creating a second preparation.

Dispatch remains unpaused at revision 19. The normal 02:20:53 autoscaler activation
succeeded without an error or alert-delivery failure; account inventory remained
four Droplets against quota 25. No extra compute was created. Agreed shared110
placement limits, production servers and recording storage were unchanged.

Verification: 389 backend capacity tests passed, no skips/failures; 346
infrastructure tests ran, 326 passed and 20 environment-dependent tests skipped.
This closes the requested alert/short-cancel fixes, not media-quality or cluster
qualification. Roll back action/helper before backend support if needed; private
exact before/after artifacts are retained under
`/Users/ruchirs/.codex/private-backups/cu-sharing-20261001-p7pDuC`.

This is a source integration, not deployment or cloud qualification. Capacity
reservations and recorder guards keep their existing activation defaults. No
production setting, active server or stored recording was changed.

## Integrated missing source

- `0e8d1e6`: fresh-node dependency staging. Refresh signed Ubuntu metadata and
  download packages before a single cache-only install. Only an official Ubuntu
  archive 404 permits one refresh/re-download; authentication, hash, lock and
  other failures do not retry installation. Existing-installation markers veto
  staging. The normal fresh-bootstrap path changes, not existing machines.
- `d86a576` and `270940e`: exact per-recording observation and settlement producer,
  paired with the backend's existing `6727c2f4` / `2590d639` consumer and retry
  handling. The existing media watcher captures active process/container/boot
  provenance, then proves target cleanup without interrupting unrelated handlers.
  Unknown writers, recovery files, missing history or changed identity retain the
  claim. Private immutable receipts preserve retry identity. A JOB receipt never
  authorizes node deletion; the full-node signaling/storage drain veto remains.
- `0573dbb`: quoted single-line JSON settings inside the existing checksummed
  compressed bootstrap transport. This avoids redundant inner base64 while
  preserving literal credential characters. No credential values are recorded here.
- `b184aa3`, selectively: offline storage advice uses each scheduled duration plus
  30 minutes, upward rounding, two copies and one node reserve. Missing durations
  are explicitly unknown. Historical measured CPU/media facts were preserved;
  old candidate operational claims were not copied over newer failure evidence.

The existing conservative rate is a planning allowance, not measured MB/hour:
`reserve + sum(2 * ceil(8 GiB * (scheduledMinutes + 30) * 60 / 14400))`.
This does not alter active capacity profiles, release obligations on a timer,
qualify recorder concentration or implement unrecorded sizing.

## Preserved and excluded

The release already contains fleet readiness, recorder restart/storage protection
and occupied-peer-signaling drain guards. Integration used targeted patches, not
replacement of those newer files. The recording proof helpers match the reviewed
candidate logic; collector installation remains conditional on existing capacity
activation. No new scheduler was introduced.

Audience packing (`ce03678`, `af994a6`, paired backend `54e8f997` / `c52040fb`) and
benchmark fixtures remain separate candidates. Do not treat advisory learner
counts or a generated offline profile as authorization to place a room. Server
cluster-runtime work and its communications remain outside this release.

## Activation gates

1. Leave automatic capacity management off for the initial classroom rollout.
2. Before activating the job collector, exercise two simultaneous recordings:
   end one, import its exact output, settle only its claim while the other keeps
   running, retry the identical receipt, and prove the second claim stays held.
   Missed active provenance must fall back to existing node-wide settlement.
3. Before automatic removal, prove occupied peer signaling retains a candidate
   node, then normal retry removes it only after clients leave and obligations
   settle. Prior local tests are not this live result.
4. Render the exact proposed private Terraform configuration locally; check both
   transported user-data payloads against the provider's 65,536-byte limit. A
   synthetic render cannot approve a different credential/profile payload.
5. Fresh provisioning requires separate cloud authorization. Preserve the old
   infrastructure revision/configuration; never replay cloud-init on a live node
   as a rollback. Retain recording files and receipts until normal settlement.

No new paid campaign or production rollout is authorized by this document.

## Local verification

Final combined infrastructure discovery: 327 tests, 307 passed, 20 skipped for
platform/environment prerequisites, zero failures. The suite exercises APT
download-only retry guards, exact job identity/residue/writer failures, immutable
receipt retries, concurrent unrelated handlers, storage-duration arithmetic and
quoted settings/transport. Synthetic enabled renders: master 62,859 bytes, media
63,215 bytes; disabled renders: 18,475 and 22,723 bytes. These are not measurements
of the eventual private production configuration. Log:
`/tmp/cu-live-reconcile-infra-final-20260929.log`.

Backend paired contract tests include JOB attestation, recording duration, fleet
receipts and provisioning-controller tests. No live Linux job settlement or
fresh cloud bootstrap was executed during this reconciliation.
