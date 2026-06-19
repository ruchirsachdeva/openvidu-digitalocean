#!/usr/bin/env bash
set -euo pipefail

readonly AWS_REGION="ap-south-1"
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly TERRAFORM_WRAPPER="$SCRIPT_DIR/courseultra-terraform.sh"

cleanup() {
  unset SPACES_ACCESS_ID SPACES_SECRET_KEY
}
trap cleanup EXIT HUP INT TERM

SPACES_ACCESS_ID="$($TERRAFORM_WRAPPER output -raw spaces_access_id)"
SPACES_SECRET_KEY="$($TERRAFORM_WRAPPER output -raw spaces_secret_key)"

aws ssm put-parameter \
  --region "$AWS_REGION" \
  --name "/beinghealer/prod/openvidu/digitalocean/spaces-access-id" \
  --type SecureString \
  --value "$SPACES_ACCESS_ID" \
  --overwrite >/dev/null

aws ssm put-parameter \
  --region "$AWS_REGION" \
  --name "/beinghealer/prod/openvidu/digitalocean/spaces-secret-key" \
  --type SecureString \
  --value "$SPACES_SECRET_KEY" \
  --overwrite >/dev/null

aws ssm get-parameters \
  --region "$AWS_REGION" \
  --names \
    "/beinghealer/prod/openvidu/digitalocean/spaces-access-id" \
    "/beinghealer/prod/openvidu/digitalocean/spaces-secret-key" \
  --query 'Parameters[].{Name:Name,Type:Type,Version:Version}' \
  --output table
