#!/usr/bin/env bash
set -euo pipefail

readonly AWS_REGION="ap-south-1"
readonly EXPECTED_AWS_ACCOUNT="408669273539"

cleanup() {
  unset PROVISIONING_TOKEN AUTOSCALER_TOKEN
}
trap cleanup EXIT HUP INT TERM

for command_name in aws curl jq security terraform; do
  command -v "$command_name" >/dev/null 2>&1 || {
    printf 'Required command is missing: %s\n' "$command_name" >&2
    exit 1
  }
done

AWS_ACCOUNT="$(aws sts get-caller-identity --query Account --output text)"
if [ "$AWS_ACCOUNT" != "$EXPECTED_AWS_ACCOUNT" ]; then
  printf 'Unexpected AWS account: %s\n' "$AWS_ACCOUNT" >&2
  exit 1
fi

PROVISIONING_TOKEN="$(security find-generic-password -w -a "$USER" -s courseultra-do-terraform-token)"
AUTOSCALER_TOKEN="$(aws ssm get-parameter \
  --region "$AWS_REGION" \
  --name /beinghealer/prod/openvidu/digitalocean/autoscaler-token \
  --with-decryption \
  --query Parameter.Value \
  --output text)"

check_digitalocean_token() {
  local token_name="$1"
  local token_value="$2"
  local response_code
  response_code="$(curl -sS -o /dev/null -w '%{http_code}' \
    -H "Authorization: Bearer $token_value" \
    https://api.digitalocean.com/v2/droplets?per_page=1)"
  if [ "$response_code" != "200" ]; then
    printf '%s token failed DigitalOcean authentication (HTTP %s)\n' \
      "$token_name" "$response_code" >&2
    exit 1
  fi
}

check_digitalocean_token "Provisioning" "$PROVISIONING_TOKEN"
check_digitalocean_token "Autoscaler" "$AUTOSCALER_TOKEN"

aws ssm get-parameters \
  --region "$AWS_REGION" \
  --names \
    /beinghealer/prod/openvidu/pro-license \
    /beinghealer/prod/openvidu/digitalocean/autoscaler-token \
  --query '{Present:Parameters[].{Name:Name,Type:Type,Version:Version},Missing:InvalidParameters}' \
  --output table

printf 'Preflight authentication checks passed.\n'
