#!/usr/bin/env bash
set -euo pipefail

readonly AWS_REGION="ap-south-1"
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly SPACES_ACCESS_ID_KEYCHAIN_SERVICE="${COURSEULTRA_SPACES_ACCESS_ID_KEYCHAIN_SERVICE:-courseultra-do-spaces-access-id}"
readonly SPACES_SECRET_KEY_KEYCHAIN_SERVICE="${COURSEULTRA_SPACES_SECRET_KEY_KEYCHAIN_SERVICE:-courseultra-do-spaces-secret-key}"

require_command() {
  command -v "$1" >/dev/null 2>&1 || {
    printf 'Required command is missing: %s\n' "$1" >&2
    exit 1
  }
}

require_value() {
  local value_name="$1"
  local value="$2"
  if [ -z "$value" ]; then
    printf 'Required credential is empty: %s\n' "$value_name" >&2
    exit 1
  fi
}

keychain_value() {
  security find-generic-password -w -a "$USER" -s "$1"
}

ssm_value() {
  aws ssm get-parameter \
    --region "$AWS_REGION" \
    --name "$1" \
    --with-decryption \
    --query 'Parameter.Value' \
    --output text
}

cleanup() {
  unset TF_VAR_doToken TF_VAR_autoscalerToken TF_VAR_openviduLicense
  unset TF_VAR_spacesAccessId TF_VAR_spacesSecretKey
  unset COURSEULTRA_DO_PROVISIONING_TOKEN COURSEULTRA_DO_AUTOSCALER_TOKEN
}

clear_terraform_debug_environment() {
  local variable_name
  while IFS= read -r variable_name; do
    unset "$variable_name"
  done < <(compgen -v TF_LOG)
}

trap cleanup EXIT HUP INT TERM

require_command terraform

if [ "$#" -eq 0 ]; then
  printf 'Usage: %s <terraform arguments...>\n' "$0" >&2
  exit 2
fi

# Terraform plans and state necessarily contain bootstrap material because the
# upstream stack embeds credentials in cloud-init. Keep debug logging disabled
# and rely on the encrypted remote backend configured for this deployment.
clear_terraform_debug_environment

# State outputs are used by routine webhook and recovery helpers after the
# temporary provisioning credentials have been revoked. Terraform can read
# those outputs through the existing AWS backend identity alone.
if [ "$1" = "output" ]; then
  cleanup
  cd "$SCRIPT_DIR"
  exec terraform "$@"
fi

require_command aws
require_command security

# Keep lookup and export separate. Bash reports `export NAME="$(failing-command)"` as successful,
# which would otherwise let plan/apply continue with empty infrastructure credentials.
COURSEULTRA_DO_PROVISIONING_TOKEN="$(keychain_value courseultra-do-terraform-token)"
COURSEULTRA_DO_AUTOSCALER_TOKEN="$(ssm_value /beinghealer/prod/openvidu/digitalocean/autoscaler-token)"
TF_VAR_spacesAccessId="$(keychain_value "$SPACES_ACCESS_ID_KEYCHAIN_SERVICE")"
TF_VAR_spacesSecretKey="$(keychain_value "$SPACES_SECRET_KEY_KEYCHAIN_SERVICE")"
TF_VAR_openviduLicense="$(ssm_value /beinghealer/prod/openvidu/pro-license)"

require_value "DigitalOcean provisioning token" "$COURSEULTRA_DO_PROVISIONING_TOKEN"
require_value "DigitalOcean autoscaler token" "$COURSEULTRA_DO_AUTOSCALER_TOKEN"
require_value "Spaces access ID" "$TF_VAR_spacesAccessId"
require_value "Spaces secret key" "$TF_VAR_spacesSecretKey"
require_value "OpenVidu PRO license" "$TF_VAR_openviduLicense"

TF_VAR_doToken="$COURSEULTRA_DO_PROVISIONING_TOKEN"
TF_VAR_autoscalerToken="$COURSEULTRA_DO_AUTOSCALER_TOKEN"
export COURSEULTRA_DO_PROVISIONING_TOKEN COURSEULTRA_DO_AUTOSCALER_TOKEN
export TF_VAR_doToken TF_VAR_autoscalerToken TF_VAR_openviduLicense
export TF_VAR_spacesAccessId TF_VAR_spacesSecretKey

cd "$SCRIPT_DIR"
terraform "$@"
