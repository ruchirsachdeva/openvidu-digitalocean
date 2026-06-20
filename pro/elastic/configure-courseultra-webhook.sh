#!/usr/bin/env bash
set -euo pipefail

readonly AWS_REGION="ap-south-1"
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly TERRAFORM_WRAPPER="${TERRAFORM_WRAPPER:-$SCRIPT_DIR/courseultra-terraform.sh}"
readonly SSH_KEY_PATH="${1:-$HOME/.ssh/courseultra-openvidu-elastic.pem}"
readonly HOST_KEY_ACTION="${2:-}"
readonly KNOWN_HOSTS_PATH="${COURSEULTRA_KNOWN_HOSTS_PATH:-$HOME/.ssh/courseultra-openvidu-elastic.known_hosts}"
readonly WEBHOOK_ENDPOINT="${COURSEULTRA_WEBHOOK_ENDPOINT:-https://server.courseultra.com/webhooks/openvidu}"

cleanup() {
  unset WEBHOOK_TOKEN WEBHOOK_TOKEN_B64 WEBHOOK_ENDPOINT_B64
}
trap cleanup EXIT HUP INT TERM

if [ ! -f "$SSH_KEY_PATH" ]; then
  printf 'OpenVidu SSH key not found: %s\n' "$SSH_KEY_PATH" >&2
  exit 1
fi

if [ "$#" -gt 2 ] || { [ -n "$HOST_KEY_ACTION" ] && [ "$HOST_KEY_ACTION" != "--refresh-host-key" ]; }; then
  printf 'Usage: %s [ssh-key-path] [--refresh-host-key]\n' "$0" >&2
  exit 2
fi
if [ "$HOST_KEY_ACTION" = "--refresh-host-key" ] && ! command -v ssh-keygen >/dev/null 2>&1; then
  printf 'ssh-keygen is required to refresh the deployment host key\n' >&2
  exit 1
fi
if [[ ! "$WEBHOOK_ENDPOINT" =~ ^https://[^[:space:]]+$ ]]; then
  printf 'CourseUltra webhook endpoint must be a single HTTPS URL\n' >&2
  exit 2
fi

MASTER_IP="$("$TERRAFORM_WRAPPER" output -raw master_public_ip)"
WEBHOOK_TOKEN="$(aws ssm get-parameter \
  --region "$AWS_REGION" \
  --name /beinghealer/prod/openvidu/webhook-token \
  --with-decryption \
  --query Parameter.Value \
  --output text)"
WEBHOOK_TOKEN_B64="$(printf '%s' "$WEBHOOK_TOKEN" | base64 | tr -d '\n')"
WEBHOOK_ENDPOINT_B64="$(printf '%s' "$WEBHOOK_ENDPOINT" | base64 | tr -d '\n')"

mkdir -p "$(dirname "$KNOWN_HOSTS_PATH")"
touch "$KNOWN_HOSTS_PATH"
chmod 600 "$KNOWN_HOSTS_PATH"
if [ "$HOST_KEY_ACTION" = "--refresh-host-key" ]; then
  # This flag is intentionally explicit: use it only after Terraform and the
  # DigitalOcean control plane confirm that the reserved IP moved to a new master.
  ssh-keygen -R "$MASTER_IP" -f "$KNOWN_HOSTS_PATH" >/dev/null 2>&1 || true
fi

{
  printf '%s\n' "$WEBHOOK_TOKEN_B64"
  printf '%s\n' "$WEBHOOK_ENDPOINT_B64"
  cat <<'REMOTE_SCRIPT'
set -euo pipefail
umask 077

python3 - <<'PY'
import base64
import os
from pathlib import Path

path = Path("/opt/openvidu/config/cluster/master_node/v2compatibility.env")
if not path.is_file():
    raise SystemExit("OpenVidu v2 compatibility configuration is missing")
token = base64.b64decode(os.environ["TOKEN_B64"]).decode("utf-8")
endpoint = base64.b64decode(os.environ["ENDPOINT_B64"]).decode("utf-8")
updates = {
    "V2COMPAT_OPENVIDU_WEBHOOK": "true",
    "V2COMPAT_OPENVIDU_WEBHOOK_ENDPOINT": endpoint,
    "V2COMPAT_OPENVIDU_WEBHOOK_HEADERS": f"'[\"X-OpenVidu-Webhook-Token: {token}\"]'",
    "V2COMPAT_OPENVIDU_WEBHOOK_EVENTS": "recordingStatusChanged",
}

lines = path.read_text().splitlines()
result = []
seen = set()
for line in lines:
    key = line.split("=", 1)[0] if "=" in line else ""
    if key in updates:
        result.append(f"{key}={updates[key]}")
        seen.add(key)
    else:
        result.append(line)
for key, value in updates.items():
    if key not in seen:
        result.append(f"{key}={value}")

temporary = path.with_suffix(".env.tmp")
temporary.write_text("\n".join(result) + "\n")
temporary.chmod(0o600)
temporary.replace(path)
PY

unset TOKEN_B64 ENDPOINT_B64
systemctl restart openvidu
systemctl is-active --quiet openvidu
REMOTE_SCRIPT
} | ssh \
  -i "$SSH_KEY_PATH" \
  -o BatchMode=yes \
  -o StrictHostKeyChecking=accept-new \
  -o "UserKnownHostsFile=$KNOWN_HOSTS_PATH" \
  "root@$MASTER_IP" \
  'read -r TOKEN_B64; read -r ENDPOINT_B64; export TOKEN_B64 ENDPOINT_B64; bash -s'

printf 'OpenVidu v2-compatible recording webhook configured and service restarted.\n'
