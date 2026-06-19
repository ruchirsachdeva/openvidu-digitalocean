#!/usr/bin/env bash
set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly TERRAFORM_WRAPPER="${TERRAFORM_WRAPPER:-$SCRIPT_DIR/courseultra-terraform.sh}"
readonly KEY_PATH="${1:-$HOME/.ssh/courseultra-openvidu-elastic.pem}"
readonly LEGACY_BOOTSTRAP_KEY="openvidu_ssh_key_elastic.pem"

cleanup() {
  unset SPACES_ACCESS_ID SPACES_SECRET_KEY
  if [ -n "${TEMP_KEY:-}" ] && [ -f "$TEMP_KEY" ]; then
    rm -f "$TEMP_KEY"
  fi
}
trap cleanup EXIT HUP INT TERM

for COMMAND in aws jq; do
  command -v "$COMMAND" >/dev/null 2>&1 || {
    printf 'Required command is missing: %s\n' "$COMMAND" >&2
    exit 1
  }
done

mkdir -p "$(dirname "$KEY_PATH")"
TEMP_KEY="$(mktemp "${KEY_PATH}.tmp.XXXXXX")"
chmod 600 "$TEMP_KEY"
"$TERRAFORM_WRAPPER" output -raw ssh_private_key_openssh >"$TEMP_KEY"
if ! grep -q '^-----BEGIN OPENSSH PRIVATE KEY-----$' "$TEMP_KEY"; then
  printf 'Terraform did not return a valid OpenSSH private key\n' >&2
  exit 1
fi
mv "$TEMP_KEY" "$KEY_PATH"
TEMP_KEY=""
chmod 600 "$KEY_PATH"

SPACE_NAME="$("$TERRAFORM_WRAPPER" output -raw space_name)"
SPACE_REGION="$("$TERRAFORM_WRAPPER" output -raw space_region)"
SPACES_ACCESS_ID="$("$TERRAFORM_WRAPPER" output -raw spaces_access_id)"
SPACES_SECRET_KEY="$("$TERRAFORM_WRAPPER" output -raw spaces_secret_key)"

legacy_key_count() {
  RESPONSE=$(AWS_ACCESS_KEY_ID="$SPACES_ACCESS_ID" \
    AWS_SECRET_ACCESS_KEY="$SPACES_SECRET_KEY" \
    aws s3api list-objects-v2 \
      --bucket "$SPACE_NAME" \
      --prefix "$LEGACY_BOOTSTRAP_KEY" \
      --endpoint-url "https://$SPACE_REGION.digitaloceanspaces.com" \
      --region "$SPACE_REGION" \
      --output json)
  printf '%s' "$RESPONSE" | jq -r --arg key "$LEGACY_BOOTSTRAP_KEY" \
    '[.Contents[]? | select(.Key == $key)] | length'
}

# Current deployments read the key directly from encrypted Terraform state and
# never upload it to Spaces. Remove the old bootstrap copy when upgrading, while
# treating an already-absent object as the expected idempotent state.
if [ "$(legacy_key_count)" -gt 0 ]; then
  AWS_ACCESS_KEY_ID="$SPACES_ACCESS_ID" \
  AWS_SECRET_ACCESS_KEY="$SPACES_SECRET_KEY" \
  aws s3 rm \
    "s3://$SPACE_NAME/$LEGACY_BOOTSTRAP_KEY" \
    --endpoint-url "https://$SPACE_REGION.digitaloceanspaces.com" \
    --region "$SPACE_REGION" >/dev/null
fi

if [ "$(legacy_key_count)" -ne 0 ]; then
  printf 'Legacy bootstrap SSH key still exists in Spaces\n' >&2
  exit 1
fi

printf 'SSH key refreshed with mode 0600; no bootstrap copy remains in Spaces: %s\n' "$KEY_PATH"
