#!/usr/bin/env bash
set -euo pipefail

readonly AWS_REGION="ap-south-1"
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly TERRAFORM_WRAPPER="${TERRAFORM_WRAPPER:-$SCRIPT_DIR/courseultra-terraform.sh}"

cleanup() {
  unset SPACES_ACCESS_ID SPACES_SECRET_KEY OPENVIDU_URL LIVEKIT_API_SECRET
  if [ -n "${SECRETS_FILE:-}" ] && [ -f "$SECRETS_FILE" ]; then
    rm -f "$SECRETS_FILE"
  fi
}
trap cleanup EXIT HUP INT TERM

read_secret() {
  local key="$1"
  awk -v key="$key" 'index($0, key "=") == 1 { print substr($0, length(key) + 2) }' \
    "$SECRETS_FILE" | tail -1
}

SPACE_NAME="$($TERRAFORM_WRAPPER output -raw space_name)"
SPACE_REGION="$($TERRAFORM_WRAPPER output -raw space_region)"
EXPECTED_MASTER_PRIVATE_IP="$($TERRAFORM_WRAPPER output -raw master_private_ip)"
EXPECTED_MASTER_ID="$($TERRAFORM_WRAPPER output -raw master_droplet_id)"
SPACES_ACCESS_ID="$($TERRAFORM_WRAPPER output -raw spaces_access_id)"
SPACES_SECRET_KEY="$($TERRAFORM_WRAPPER output -raw spaces_secret_key)"
SECRETS_FILE="$(mktemp)"
chmod 600 "$SECRETS_FILE"

SECRETS_FOUND=false
for ATTEMPT in $(seq 1 120); do
  if AWS_ACCESS_KEY_ID="$SPACES_ACCESS_ID" \
    AWS_SECRET_ACCESS_KEY="$SPACES_SECRET_KEY" \
    aws s3 cp \
      "s3://$SPACE_NAME/secrets.env" \
      "$SECRETS_FILE" \
      --endpoint-url "https://$SPACE_REGION.digitaloceanspaces.com" \
      --region "$SPACE_REGION" >/dev/null 2>&1; then
    OPENVIDU_URL="$(read_secret OPENVIDU_URL)"
    LIVEKIT_API_SECRET="$(read_secret LIVEKIT_API_SECRET)"
    SPACE_MASTER_PRIVATE_IP="$(read_secret MASTER_NODE_PRIVATE_IP)"
    SPACE_MASTER_ID="$(read_secret MASTER_NODE_ID)"
    if [ -n "$OPENVIDU_URL" ] \
      && [ -n "$LIVEKIT_API_SECRET" ] \
      && [ "$SPACE_MASTER_ID" = "$EXPECTED_MASTER_ID" ] \
      && [ "$SPACE_MASTER_PRIVATE_IP" = "$EXPECTED_MASTER_PRIVATE_IP" ]; then
      SECRETS_FOUND=true
      break
    fi
  fi
  printf 'Waiting for OpenVidu secrets.env (%s/120)\n' "$ATTEMPT"
  sleep 10
done

if [ "$SECRETS_FOUND" != "true" ]; then
  printf 'OpenVidu did not publish secrets.env within 20 minutes\n' >&2
  exit 1
fi

for parameter_name in url elastic-url; do
  aws ssm put-parameter \
    --region "$AWS_REGION" \
    --name "/beinghealer/prod/openvidu/digitalocean/$parameter_name" \
    --type SecureString \
    --value "$OPENVIDU_URL" \
    --overwrite >/dev/null
done

aws ssm put-parameter \
  --region "$AWS_REGION" \
  --name "/beinghealer/prod/openvidu/digitalocean/username" \
  --type SecureString \
  --value OPENVIDUAPP \
  --overwrite >/dev/null

aws ssm put-parameter \
  --region "$AWS_REGION" \
  --name "/beinghealer/prod/openvidu/digitalocean/secret" \
  --type SecureString \
  --value "$LIVEKIT_API_SECRET" \
  --overwrite >/dev/null

aws ssm get-parameters \
  --region "$AWS_REGION" \
  --names \
    /beinghealer/prod/openvidu/digitalocean/url \
    /beinghealer/prod/openvidu/digitalocean/elastic-url \
    /beinghealer/prod/openvidu/digitalocean/username \
    /beinghealer/prod/openvidu/digitalocean/secret \
  --query 'Parameters[].{Name:Name,Type:Type,Version:Version}' \
  --output table
