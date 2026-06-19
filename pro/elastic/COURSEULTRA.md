# CourseUltra OpenVidu Elastic Deployment

This directory is pinned to OpenVidu `3.7.0` and deploys the CourseUltra production cluster on
DigitalOcean. Keep the upstream Terraform structure intact. CourseUltra-specific changes are
limited to production safety and repeatability:

- the broad provisioning token is used only by Terraform;
- a separate scoped token is embedded in the autoscaler and draining media nodes;
- scale-in occurs below 70% of the scale-out target to prevent node churn;
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

This decision trades Singapore-to-India latency against a simpler supported topology and lower
egress exposure. Revisit it using measured session quality and current provider pricing rather than
preserving historical cost estimates in source control.

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

## Fixed production shape

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

The existing AWS OpenVidu cluster remains a separate rollback target until the DigitalOcean
cluster has passed its soak period. Never destroy both deployments in one change.

Singapore is used because DigitalOcean currently disables new Spaces creation in BLR1. Keeping
compute and Spaces together in SGP1 avoids cross-region bootstrap and recording traffic. The Space
was created once through the control panel and is intentionally not destroyed with the cluster.
Its CDN is disabled because OpenVidu needs authenticated S3-compatible object storage, not a public
object-delivery endpoint.

The first failed BLR1 attempt caused DigitalOcean to create that region's default VPC. It is named
`default-blr1`, has no droplets, and is intentionally outside Terraform state because DigitalOcean
does not allow deleting a region's default VPC. It is unrelated to the managed SGP1 cluster and has
no standalone charge.

## Verified candidate status

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

The deployed master is Droplet `578687384`; the one-node media floor is Droplet `578688262`. The
former media node `578469816` was drained and deleted. The infrastructure is ready for an explicit
application cutover, but it is not the production application endpoint yet and the AWS rollback
deployment remains untouched.

## Secret boundaries

`courseultra-terraform.sh` loads values at execution time:

| Input | Source |
| --- | --- |
| Terraform DigitalOcean token | macOS Keychain service `courseultra-do-terraform-token` |
| Spaces bootstrap access ID | macOS Keychain service `courseultra-do-spaces-access-id` |
| Spaces bootstrap secret | macOS Keychain service `courseultra-do-spaces-secret-key` |
| Scoped autoscaler token | SSM `/beinghealer/prod/openvidu/digitalocean/autoscaler-token` |
| OpenVidu PRO license | SSM `/beinghealer/prod/openvidu/pro-license` |

Do not add these values to `*.tfvars`, Git, saved plans, shell tracing, tickets, or documentation.
The state itself is sensitive because OpenVidu cloud-init and the autoscaler require generated
credentials. The S3 backend must remain private and versioned.

## One-time workstation and state setup

Install Terraform `1.10` or newer and authenticate the AWS CLI to account `408669273539`. The
remote state bucket is `courseultra-terraform-state-408669273539-ap-south-1`; it must remain private,
AES-256 encrypted, versioned, TLS-only, and protected by the S3 public-access block. Then create
local files from the committed examples:

```bash
cp backend.hcl.example backend.hcl
cp courseultra.auto.tfvars.example courseultra.auto.tfvars
```

Set the real state bucket in `backend.hcl`. Replace the documentation CIDR in
`courseultra.auto.tfvars` with the current operator public IP as `/32`. The Terraform validation
rejects IPv4 and IPv6 `/0` routes so SSH cannot accidentally be reopened to the entire internet.
Neither local file is committed.

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

After the apply:

```bash
./persist-runtime-secrets.sh
./secure-bootstrap-artifacts.sh
./persist-openvidu-candidate.sh
./configure-courseultra-webhook.sh
```

The first command writes the generated, bucket-scoped Spaces credentials to SSM. The second
refreshes the Terraform-generated SSH key at `~/.ssh/courseultra-openvidu-elastic.pem` with mode
`0600` directly from encrypted state. Current cloud-init never uploads that private key to Spaces;
the script also removes the legacy bootstrap object when upgrading an older candidate.
`secrets.env` must remain private in Spaces because new autoscaled media nodes use it during
bootstrap.

The third command copies the generated v2-compatible URL, username, and secret into
`/beinghealer/prod/openvidu/digitalocean/*` candidate parameters. It does not overwrite the live
application parameters. The fourth command configures the existing authenticated CourseUltra
recording webhook on the new master and restarts OpenVidu. It stores host trust in the dedicated
`~/.ssh/courseultra-openvidu-elastic.known_hosts` file rather than changing the operator's ordinary
SSH trust store.

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

Record the current media-node IDs before applying the master replacement:

```bash
(
  set -euo pipefail
  AUTOSCALER_TOKEN="$(aws ssm get-parameter \
    --region ap-south-1 \
    --name /beinghealer/prod/openvidu/digitalocean/autoscaler-token \
    --with-decryption --query Parameter.Value --output text)"
  curl -fsS \
    -H "Authorization: Bearer $AUTOSCALER_TOKEN" \
    'https://api.digitalocean.com/v2/droplets?tag_name=courseultra-openvidu-media-node-tag&per_page=200' \
    | jq -er '.droplets | if length > 0 then .[].id else error("no active media nodes") end' \
    > /tmp/courseultra-openvidu-old-media-node-ids
  chmod 600 /tmp/courseultra-openvidu-old-media-node-ids
  printf 'Pre-replacement media nodes:\n'
  cat /tmp/courseultra-openvidu-old-media-node-ids
)
```

After the replacement master is healthy and has published its new `secrets.env`, drain only those
recorded nodes. The shared file carries both the master Droplet ID and private IP; new nodes reject
old files even when DigitalOcean reuses an address. The drain order is an invariant: add the
draining tag and confirm it before removing the active tag. The helper preserves that order, skips
nodes confirmed already deleted, and retains the ID file after any ambiguous failure so the same
command can be retried safely.

```bash
./drain-courseultra-media-nodes.sh \
  /tmp/courseultra-openvidu-old-media-node-ids
```

The helper deletes the ID file only after every recorded node is absent or safely draining. On
failure, fix the reported provider or response problem and rerun the same command; never remove the
active tag manually. The autoscaler creates replacements after the old nodes leave the active
inventory, and each new node waits until the Space contains the current master's Droplet ID and IP.

The reserved public IP survives a master replacement but the server host key does not. After the
Terraform apply and DigitalOcean control plane both confirm that the reserved IP belongs to the new
master, refresh only the dedicated trust entry while reconfiguring the webhook:

```bash
./configure-courseultra-webhook.sh \
  "$HOME/.ssh/courseultra-openvidu-elastic.pem" \
  --refresh-host-key
```

Do not use `--refresh-host-key` for a routine webhook rerun or before independently verifying the
replacement. Without the flag, a changed key fails closed.

When rotating the autoscaler token, every media node bootstrapped with the old token must be
drained and replaced before revoking it. A Terraform apply updates the Function and future
media-node bootstrap; it cannot rewrite credentials already stored on running Droplets.

## Application cutover

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

Rollback means restoring the recorded SSM versions and restarting the backend. The Route53 record
for `openvidu-do.courseultra.com` and the DigitalOcean cluster can remain available while the issue
is investigated; the old `openvidu.courseultra.com` deployment is not modified during cutover.

## Upgrade discipline

OpenVidu recommends redeploying DigitalOcean Elastic stacks for upgrades. Start each upgrade from
the new upstream tag, reapply the small CourseUltra patch deliberately, run `terraform validate`
and a full plan, and deploy side by side when the upgrade changes OpenVidu services or networking.
Re-download installer and CLI artifacts over HTTPS, review their release changes, and update pinned
SHA-256 checksums only after verification. Do not merge arbitrary upstream `main` changes into a
running production stack.
