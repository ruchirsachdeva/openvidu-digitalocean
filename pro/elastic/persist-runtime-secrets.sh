#!/usr/bin/env bash
set -euo pipefail

readonly AWS_REGION="ap-south-1"
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly TERRAFORM_WRAPPER="${TERRAFORM_WRAPPER:-$SCRIPT_DIR/courseultra-terraform.sh}"
readonly SSM_PREFIX="${COURSEULTRA_OPENVIDU_SSM_PREFIX:-/beinghealer/prod/openvidu/digitalocean}"
readonly SPACES_ACCESS_ID_PARAMETER="$SSM_PREFIX/spaces-access-id"
readonly SPACES_SECRET_KEY_PARAMETER="$SSM_PREFIX/spaces-secret-key"

case "$SSM_PREFIX" in
  /*) ;;
  *)
    printf 'COURSEULTRA_OPENVIDU_SSM_PREFIX must be an absolute SSM path\n' >&2
    exit 2
    ;;
esac

case "$SSM_PREFIX" in
  "/"|*/|*//*|*[!A-Za-z0-9_./-]*)
    printf 'COURSEULTRA_OPENVIDU_SSM_PREFIX contains an invalid SSM path\n' >&2
    exit 2
    ;;
esac

cleanup() {
  unset SPACES_ACCESS_ID SPACES_SECRET_KEY
}
trap cleanup EXIT HUP INT TERM

SPACES_ACCESS_ID="$($TERRAFORM_WRAPPER output -raw spaces_access_id)"
SPACES_SECRET_KEY="$($TERRAFORM_WRAPPER output -raw spaces_secret_key)"

aws ssm put-parameter \
  --region "$AWS_REGION" \
  --name "$SPACES_ACCESS_ID_PARAMETER" \
  --type SecureString \
  --value "$SPACES_ACCESS_ID" \
  --overwrite >/dev/null

aws ssm put-parameter \
  --region "$AWS_REGION" \
  --name "$SPACES_SECRET_KEY_PARAMETER" \
  --type SecureString \
  --value "$SPACES_SECRET_KEY" \
  --overwrite >/dev/null

aws ssm get-parameters \
  --region "$AWS_REGION" \
  --names \
    "$SPACES_ACCESS_ID_PARAMETER" \
    "$SPACES_SECRET_KEY_PARAMETER" \
  --query 'Parameters[].{Name:Name,Type:Type,Version:Version}' \
  --output table
