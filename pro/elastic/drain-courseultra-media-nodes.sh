#!/usr/bin/env bash
set -euo pipefail

readonly AWS_REGION="ap-south-1"
readonly ACTIVE_TAG="courseultra-openvidu-media-node-tag"
readonly DRAINING_TAG="courseultra-openvidu-draining"
readonly DO_API="https://api.digitalocean.com/v2"
readonly IDS_FILE="${1:-/tmp/courseultra-openvidu-old-media-node-ids}"

cleanup() {
  unset AUTOSCALER_TOKEN
  if [ -n "${RESPONSE_FILE:-}" ] && [ -f "$RESPONSE_FILE" ]; then
    rm -f "$RESPONSE_FILE"
  fi
}
trap cleanup EXIT HUP INT TERM

for COMMAND in aws curl jq mktemp; do
  command -v "$COMMAND" >/dev/null 2>&1 || {
    printf 'Required command is missing: %s\n' "$COMMAND" >&2
    exit 1
  }
done

if [ ! -s "$IDS_FILE" ]; then
  printf 'Media-node ID file is missing or empty: %s\n' "$IDS_FILE" >&2
  exit 1
fi

AUTOSCALER_TOKEN="$(aws ssm get-parameter \
  --region "$AWS_REGION" \
  --name /beinghealer/prod/openvidu/digitalocean/autoscaler-token \
  --with-decryption --query Parameter.Value --output text)"
RESPONSE_FILE="$(mktemp)"
chmod 600 "$RESPONSE_FILE"

api_request() {
  local method="$1"
  local url="$2"
  local body="${3:-}"
  local arguments=(
    -sS
    -o "$RESPONSE_FILE"
    -w '%{http_code}'
    -X "$method"
    -H "Authorization: Bearer $AUTOSCALER_TOKEN"
  )
  if [ -n "$body" ]; then
    arguments+=(
      -H 'Content-Type: application/json'
      -d "$body"
    )
  fi
  curl "${arguments[@]}" "$url"
}

validate_droplet() {
  local node_id="$1"
  jq -e --arg id "$node_id" '
    (.droplet | type) == "object"
    and (.droplet.id | tostring) == $id
    and (.droplet.tags | type) == "array"
  ' "$RESPONSE_FILE" >/dev/null || {
    printf 'DigitalOcean returned an invalid droplet response for %s\n' "$node_id" >&2
    return 1
  }
}

has_tag() {
  local tag="$1"
  jq -e --arg tag "$tag" '.droplet.tags | index($tag) != null' \
    "$RESPONSE_FILE" >/dev/null
}

PROCESSED=0
while IFS= read -r NODE_ID; do
  [ -n "$NODE_ID" ] || continue
  [[ "$NODE_ID" =~ ^[0-9]+$ ]] || {
    printf 'Invalid media-node ID: %s\n' "$NODE_ID" >&2
    exit 1
  }
  PROCESSED=$((PROCESSED + 1))

  HTTP_CODE="$(api_request GET "$DO_API/droplets/$NODE_ID")"
  case "$HTTP_CODE" in
    200) validate_droplet "$NODE_ID" ;;
    404)
      printf 'Media node %s is already absent; skipping.\n' "$NODE_ID"
      continue
      ;;
    *)
      printf 'Unable to read media node %s (HTTP %s); no tags changed.\n' \
        "$NODE_ID" "$HTTP_CODE" >&2
      exit 1
      ;;
  esac

  if ! has_tag "$ACTIVE_TAG"; then
    if has_tag "$DRAINING_TAG"; then
      printf 'Media node %s is already draining.\n' "$NODE_ID"
      continue
    fi
    printf 'Media node %s has neither managed lifecycle tag; refusing to modify it.\n' \
      "$NODE_ID" >&2
    exit 1
  fi

  BODY="$(jq -cn --arg id "$NODE_ID" \
    '{resources:[{resource_id:$id,resource_type:"droplet"}]}')"

  if ! has_tag "$DRAINING_TAG"; then
    HTTP_CODE="$(api_request POST "$DO_API/tags/$DRAINING_TAG/resources" "$BODY")"
    case "$HTTP_CODE" in
      2??) ;;
      *)
        printf 'Unable to mark media node %s as draining (HTTP %s); active tag retained.\n' \
          "$NODE_ID" "$HTTP_CODE" >&2
        exit 1
        ;;
    esac

    HTTP_CODE="$(api_request GET "$DO_API/droplets/$NODE_ID")"
    case "$HTTP_CODE" in
      200)
        validate_droplet "$NODE_ID"
        has_tag "$DRAINING_TAG" || {
          printf 'Draining tag was not confirmed for media node %s; active tag retained.\n' \
            "$NODE_ID" >&2
          exit 1
        }
        ;;
      404)
        printf 'Media node %s finished deleting after it was marked draining.\n' "$NODE_ID"
        continue
        ;;
      *)
        printf 'Unable to confirm draining tag for media node %s (HTTP %s); active tag retained.\n' \
          "$NODE_ID" "$HTTP_CODE" >&2
        exit 1
        ;;
    esac
  fi

  HTTP_CODE="$(api_request DELETE "$DO_API/tags/$ACTIVE_TAG/resources" "$BODY")"
  case "$HTTP_CODE" in
    2??)
      printf 'Media node %s is draining and no longer accepts new sessions.\n' "$NODE_ID"
      ;;
    *)
      # A watcher may delete the node between tag confirmation and untagging.
      HTTP_CODE="$(api_request GET "$DO_API/droplets/$NODE_ID")"
      if [ "$HTTP_CODE" = "404" ]; then
        printf 'Media node %s finished deleting during drain.\n' "$NODE_ID"
      else
        printf 'Unable to remove the active tag from media node %s; retry later.\n' \
          "$NODE_ID" >&2
        exit 1
      fi
      ;;
  esac
done < "$IDS_FILE"

if [ "$PROCESSED" -eq 0 ]; then
  printf 'Media-node ID file contained no usable IDs: %s\n' "$IDS_FILE" >&2
  exit 1
fi

rm -f "$IDS_FILE"
printf 'All recorded media nodes are absent or safely draining.\n'
