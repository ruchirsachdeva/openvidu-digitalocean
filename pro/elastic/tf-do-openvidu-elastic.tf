resource "random_id" "bucket_suffix" { byte_length = 5 }

# -------------- VPC and Firewalls ----------------

resource "digitalocean_vpc" "openvidu_vpc" {
  name     = "${var.stackName}-vpc"
  region   = var.region
  ip_range = var.vpcIpRange
}

resource "digitalocean_tag" "media_node_tag" {
  name = "${var.stackName}-media-node-tag"
}

resource "digitalocean_tag" "draining_tag" {
  name = "${var.stackName}-draining"
}

# Firewall for Master Node - external access
resource "digitalocean_firewall" "master_firewall" {
  name = "${var.stackName}-master-firewall"

  droplet_ids = [digitalocean_droplet.openvidu_master_node.id]

  inbound_rule {
    protocol         = "tcp"
    port_range       = "22"
    source_addresses = var.sshAllowedCidrs
  }

  inbound_rule {
    protocol         = "tcp"
    port_range       = "80"
    source_addresses = ["0.0.0.0/0", "::/0"]
  }

  inbound_rule {
    protocol         = "tcp"
    port_range       = "443"
    source_addresses = ["0.0.0.0/0", "::/0"]
  }

  inbound_rule {
    protocol         = "tcp"
    port_range       = "1935"
    source_addresses = ["0.0.0.0/0", "::/0"]
  }

  inbound_rule {
    protocol         = "tcp"
    port_range       = "9000"
    source_addresses = ["0.0.0.0/0", "::/0"]
  }

  outbound_rule {
    protocol              = "tcp"
    port_range            = "1-65535"
    destination_addresses = ["0.0.0.0/0", "::/0"]
  }
  outbound_rule {
    protocol              = "udp"
    port_range            = "1-65535"
    destination_addresses = ["0.0.0.0/0", "::/0"]
  }
  outbound_rule {
    protocol              = "icmp"
    destination_addresses = ["0.0.0.0/0", "::/0"]
  }
}

# Firewall for Media Nodes - external access
resource "digitalocean_firewall" "media_firewall" {
  name = "${var.stackName}-media-firewall"

  # A draining node remains internet-facing until its watcher finishes a graceful
  # shutdown. Keep both lifecycle tags covered so scale-in never removes its firewall.
  tags = [digitalocean_tag.media_node_tag.name, digitalocean_tag.draining_tag.name]

  inbound_rule {
    protocol         = "tcp"
    port_range       = "22"
    source_addresses = var.sshAllowedCidrs
  }

  inbound_rule {
    protocol         = "tcp"
    port_range       = "7881"
    source_addresses = ["0.0.0.0/0", "::/0"]
  }

  inbound_rule {
    protocol         = "tcp"
    port_range       = "50000-60000"
    source_addresses = ["0.0.0.0/0", "::/0"]
  }

  inbound_rule {
    protocol         = "udp"
    port_range       = "443"
    source_addresses = ["0.0.0.0/0", "::/0"]
  }

  inbound_rule {
    protocol         = "udp"
    port_range       = "7885"
    source_addresses = ["0.0.0.0/0", "::/0"]
  }

  inbound_rule {
    protocol         = "udp"
    port_range       = "50000-60000"
    source_addresses = ["0.0.0.0/0", "::/0"]
  }

  outbound_rule {
    protocol              = "tcp"
    port_range            = "1-65535"
    destination_addresses = ["0.0.0.0/0", "::/0"]
  }
  outbound_rule {
    protocol              = "udp"
    port_range            = "1-65535"
    destination_addresses = ["0.0.0.0/0", "::/0"]
  }
  outbound_rule {
    protocol              = "icmp"
    destination_addresses = ["0.0.0.0/0", "::/0"]
  }
}

# Firewall for Media Nodes to Master Node internal communication
resource "digitalocean_firewall" "media_to_master_firewall" {
  name = "${var.stackName}-media-to-master-firewall"

  droplet_ids = [digitalocean_droplet.openvidu_master_node.id]

  inbound_rule {
    protocol         = "tcp"
    port_range       = "4443"
    source_addresses = [digitalocean_vpc.openvidu_vpc.ip_range]
  }

  inbound_rule {
    protocol         = "tcp"
    port_range       = "9080"
    source_addresses = [digitalocean_vpc.openvidu_vpc.ip_range]
  }

  inbound_rule {
    protocol         = "tcp"
    port_range       = "6080"
    source_addresses = [digitalocean_vpc.openvidu_vpc.ip_range]
  }

  inbound_rule {
    protocol         = "tcp"
    port_range       = "3100"
    source_addresses = [digitalocean_vpc.openvidu_vpc.ip_range]
  }

  inbound_rule {
    protocol         = "tcp"
    port_range       = "7880"
    source_addresses = [digitalocean_vpc.openvidu_vpc.ip_range]
  }

  inbound_rule {
    protocol         = "tcp"
    port_range       = "9009"
    source_addresses = [digitalocean_vpc.openvidu_vpc.ip_range]
  }

  inbound_rule {
    protocol         = "tcp"
    port_range       = "7000"
    source_addresses = [digitalocean_vpc.openvidu_vpc.ip_range]
  }

  inbound_rule {
    protocol         = "tcp"
    port_range       = "9100"
    source_addresses = [digitalocean_vpc.openvidu_vpc.ip_range]
  }

  inbound_rule {
    protocol         = "tcp"
    port_range       = "20000"
    source_addresses = [digitalocean_vpc.openvidu_vpc.ip_range]
  }
}

# Firewall for Master Node to Media Nodes internal communication
resource "digitalocean_firewall" "master_to_media_firewall" {
  name = "${var.stackName}-master-to-media-firewall"

  tags = [digitalocean_tag.media_node_tag.name, digitalocean_tag.draining_tag.name]

  inbound_rule {
    protocol         = "tcp"
    port_range       = "1935"
    source_addresses = [digitalocean_vpc.openvidu_vpc.ip_range]
  }

  inbound_rule {
    protocol         = "tcp"
    port_range       = "5349"
    source_addresses = [digitalocean_vpc.openvidu_vpc.ip_range]
  }

  inbound_rule {
    protocol         = "tcp"
    port_range       = "7880"
    source_addresses = [digitalocean_vpc.openvidu_vpc.ip_range]
  }

  inbound_rule {
    protocol         = "tcp"
    port_range       = "8080"
    source_addresses = [digitalocean_vpc.openvidu_vpc.ip_range]
  }
}

# --------------------- droplets -----------------------

# SSH key
resource "tls_private_key" "openvidu_ssh_key" {
  algorithm = "RSA"
  rsa_bits  = 4096
}

resource "digitalocean_ssh_key" "openvidu_ssh_key_do" {
  name       = "${var.stackName}-ssh-key"
  public_key = tls_private_key.openvidu_ssh_key.public_key_openssh
}

# Master Node
resource "digitalocean_droplet" "openvidu_master_node" {
  name   = "${var.stackName}-master-node"
  image  = "ubuntu-24-04-x64"
  region = var.region
  size   = var.masterNodeInstanceType

  ssh_keys = [digitalocean_ssh_key.openvidu_ssh_key_do.id]
  vpc_uuid = digitalocean_vpc.openvidu_vpc.id
  tags     = ["openvidu", var.stackName, "master-node"]

  user_data = local.user_data_master_transport

  lifecycle {
    precondition {
      condition     = length(local.user_data_master_transport) <= 65536
      error_message = "Encoded master startup exceeds the provider user-data limit."
    }
    # A provider create can return an ID before its private address is populated.
    # Do not bake an empty IP into media startup/drain or autoscaler user data.
    postcondition {
      condition     = can(cidrnetmask("${self.ipv4_address_private}/32"))
      error_message = "Master private IPv4 is unavailable or invalid. Reconcile the created master and refresh its provider observation before replanning; do not recreate it or bypass the media generation guard."
    }
  }
}

# Master Node IP
resource "digitalocean_reserved_ip" "master_public_ip" {
  droplet_id = digitalocean_droplet.openvidu_master_node.id
  region     = var.region
  depends_on = [digitalocean_droplet.openvidu_master_node]
}

# Media Nodes (when fixed mode is enabled)
resource "digitalocean_droplet" "openvidu_media_nodes" {
  count  = var.fixedNumberOfMediaNodes
  name   = "${var.stackName}-media-node-${count.index + 1}"
  image  = "ubuntu-24-04-x64"
  region = var.region
  size   = var.mediaNodeInstanceType

  ssh_keys = [digitalocean_ssh_key.openvidu_ssh_key_do.id]
  vpc_uuid = digitalocean_vpc.openvidu_vpc.id
  tags     = ["openvidu", var.stackName, "media-node", digitalocean_tag.media_node_tag.name]

  user_data = local.user_data_media_transport
  lifecycle {
    precondition {
      condition     = length(local.user_data_media_transport) <= 65536
      error_message = "Encoded media startup exceeds the provider user-data limit."
    }
  }
}

# Cleanup all media nodes on destroy (created by autoscaler outside Terraform state)
resource "null_resource" "cleanup_media_nodes" {
  count = var.fixedNumberOfMediaNodes > 0 ? 0 : 1
  triggers = {
    # Retained only to avoid replacing the existing cleanup guard during token
    # rotation. Destruction uses the current scoped token exported by the wrapper.
    do_token     = var.doToken
    media_tag    = digitalocean_tag.media_node_tag.name
    draining_tag = digitalocean_tag.draining_tag.name
  }

  lifecycle {
    ignore_changes = [triggers["do_token"]]
  }

  provisioner "local-exec" {
    when    = destroy
    command = <<-EOT
      set -eu

      TOKEN="$${COURSEULTRA_DO_AUTOSCALER_TOKEN:-}"
      [ -n "$TOKEN" ] || {
        echo "ERROR: use courseultra-terraform.sh so media cleanup receives the scoped autoscaler token" >&2
        exit 1
      }

      for COMMAND in curl jq sleep; do
        command -v "$COMMAND" >/dev/null 2>&1 || {
          echo "ERROR: $COMMAND is required for media cleanup" >&2
          exit 1
        }
      done

      # The Function resource is an explicit dependency, so Terraform removes
      # its schedule before reaching this cleanup. An activation already in
      # progress can still run for 120 seconds; wait it out before deleting the
      # nodes it could otherwise recreate behind this provisioner's back.
      sleep 130

      delete_and_verify_tag() {
        TAG="$1"
        curl -fsS -X DELETE \
          -H "Authorization: Bearer $TOKEN" \
          -H "Content-Type: application/json" \
          "https://api.digitalocean.com/v2/droplets?tag_name=$TAG" >/dev/null

        ATTEMPT=1
        while [ "$ATTEMPT" -le 30 ]; do
          RESPONSE=$(curl -fsS \
            -H "Authorization: Bearer $TOKEN" \
            "https://api.digitalocean.com/v2/droplets?tag_name=$TAG&per_page=200")
          COUNT=$(printf '%s' "$RESPONSE" | jq -er '
            if (.droplets | type) == "array" then
              .droplets | length
            else
              error("DigitalOcean response does not contain a droplets array")
            end
          ')
          if [ "$COUNT" -eq 0 ]; then
            echo "Verified removal of droplets tagged $TAG"
            return 0
          fi
          sleep 2
          ATTEMPT=$((ATTEMPT + 1))
        done

        echo "ERROR: droplets tagged $TAG still exist after cleanup" >&2
        return 1
      }

      delete_and_verify_tag "${self.triggers.media_tag}"
      delete_and_verify_tag "${self.triggers.draining_tag}"
    EOT
  }
}

# -------------- Autoscaler (DO Function) ----------------

resource "null_resource" "autoscaler_lifecycle" {
  count = var.fixedNumberOfMediaNodes > 0 ? 0 : 1
  # Code updates overwrite the existing action. Namespace destruction belongs
  # only to stack removal; tying it to code_hash interrupted scaling on updates.
  triggers = {
    stack_name = var.stackName
    region     = var.region
  }

  provisioner "local-exec" {
    when    = destroy
    command = <<-EOT
      set -eu

      DO_API="https://api.digitalocean.com/v2"
      TOKEN="$${COURSEULTRA_DO_PROVISIONING_TOKEN:-}"
      LABEL="${self.triggers.stack_name}-autoscaler"
      TRIGGER="${self.triggers.stack_name}-autoscale-cron"

      [ -n "$TOKEN" ] || {
        echo "ERROR: use courseultra-terraform.sh so Functions cleanup receives a current provisioning token" >&2
        exit 1
      }

      for COMMAND in curl jq base64; do
        command -v "$COMMAND" >/dev/null 2>&1 || {
          echo "ERROR: $COMMAND is required for Functions cleanup" >&2
          exit 1
        }
      done

      delete_allow_missing() {
        AUTH_HEADER="$1"
        URL="$2"
        HTTP_CODE=$(curl -sS -o /dev/null -w '%%{http_code}' -X DELETE \
          -H "$AUTH_HEADER" "$URL")
        case "$HTTP_CODE" in
          2??|404) return 0 ;;
          *)
            echo "ERROR: DELETE $URL returned HTTP $HTTP_CODE" >&2
            return 1
            ;;
        esac
      }

      echo "=== Destroying autoscaler function ==="
      echo "Looking for namespace with label: $LABEL"

      NS_LIST=$(curl -fsS -H "Authorization: Bearer $TOKEN" "$DO_API/functions/namespaces")
      printf '%s' "$NS_LIST" | jq -e \
        'has("namespaces")
          and ((.namespaces == null)
            or ((.namespaces | type) == "array"
              and all(.namespaces[];
                type == "object"
                and (.label | type) == "string"
                and (.namespace | type) == "string")))' >/dev/null || {
        echo "ERROR: DigitalOcean returned an invalid namespace inventory" >&2
        exit 1
      }
      NS_ID=$(printf '%s' "$NS_LIST" | jq -r --arg l "$LABEL" \
        '[(.namespaces // [])[] | select(.label == $l)] | .[0].namespace // empty')

      if [ -z "$NS_ID" ]; then
        echo "No namespace found with label $LABEL — nothing to destroy."
        exit 0
      fi

      echo "Found namespace: $NS_ID"
      NS_DETAIL=$(curl -fsS -H "Authorization: Bearer $TOKEN" "$DO_API/functions/namespaces/$NS_ID")
      NS_UUID=$(printf '%s' "$NS_DETAIL"  | jq -r '.namespace.uuid // empty')
      API_HOST=$(printf '%s' "$NS_DETAIL" | jq -r '.namespace.api_host // empty')
      API_KEY=$(printf '%s' "$NS_DETAIL"  | jq -r '.namespace.key // empty')

      # Delete cron trigger
      echo "Deleting trigger $TRIGGER ..."
      delete_allow_missing "Authorization: Bearer $TOKEN" \
        "$DO_API/functions/namespaces/$NS_ID/triggers/$TRIGGER"

      # Delete action + package via OpenWhisk API
      if [ -n "$API_HOST" ] && [ -n "$NS_UUID" ] && [ -n "$API_KEY" ]; then
        OW_AUTH=$(printf '%s:%s' "$NS_UUID" "$API_KEY" | base64 | tr -d '\n')
        echo "Deleting action autoscaler/check ..."
        delete_allow_missing "Authorization: Basic $OW_AUTH" \
          "$API_HOST/api/v1/namespaces/_/actions/autoscaler/check"
        echo "Deleting package autoscaler ..."
        delete_allow_missing "Authorization: Basic $OW_AUTH" \
          "$API_HOST/api/v1/namespaces/_/packages/autoscaler"
      else
        echo "OpenWhisk credentials unavailable; namespace deletion will remove its contents"
      fi

      # Delete the namespace itself
      echo "Deleting namespace $NS_ID ..."
      delete_allow_missing "Authorization: Bearer $TOKEN" \
        "$DO_API/functions/namespaces/$NS_ID"

      ATTEMPT=1
      while [ "$ATTEMPT" -le 30 ]; do
        NS_LIST=$(curl -fsS -H "Authorization: Bearer $TOKEN" "$DO_API/functions/namespaces")
        printf '%s' "$NS_LIST" | jq -e \
          'has("namespaces")
            and ((.namespaces == null)
              or ((.namespaces | type) == "array"
                and all(.namespaces[];
                  type == "object"
                  and (.label | type) == "string"
                  and (.namespace | type) == "string")))' >/dev/null || {
          echo "ERROR: DigitalOcean returned an invalid namespace inventory" >&2
          exit 1
        }
        MATCHES=$(printf '%s' "$NS_LIST" | jq -r --arg l "$LABEL" \
          '[(.namespaces // [])[] | select(.label == $l)] | length')
        if [ "$MATCHES" -eq 0 ]; then
          echo "Verified namespace removal: $LABEL"
          echo "=== Autoscaler function destroyed ==="
          exit 0
        fi
        sleep 2
        ATTEMPT=$((ATTEMPT + 1))
      done

      echo "ERROR: Functions namespace $LABEL still exists after cleanup" >&2
      exit 1
    EOT
  }

  depends_on = [
    null_resource.cleanup_media_nodes,
  ]
}


resource "null_resource" "deploy_autoscaler_function" {
  count = var.fixedNumberOfMediaNodes > 0 ? 0 : 1
  triggers = {
    code_hash = sha256(local.autoscaler_function_code)
    # Retained for a no-downtime transition from the upstream resource shape.
    # Runtime cleanup uses the current wrapper-provided credential instead.
    do_token   = var.doToken
    stack_name = var.stackName
    region     = var.region
  }

  lifecycle {
    ignore_changes = [triggers["do_token"]]
  }

  provisioner "local-exec" {
    environment = {
      DO_TOKEN    = var.doToken
      FN_CODE_B64 = base64encode(local.autoscaler_function_code)
    }

    command = <<-EOT
      set -e

      DO_API="https://api.digitalocean.com/v2"
      AUTH="Authorization: Bearer $DO_TOKEN"
      CT="Content-Type: application/json"
      LABEL="${var.stackName}-autoscaler"

      # Check dependencies
      for cmd in curl jq base64; do
        command -v "$cmd" >/dev/null 2>&1 || { echo "ERROR: $cmd is required but not installed"; exit 1; }
      done

      # Helper: curl with verbose error on failure
      do_curl() {
        HTTP_BODY=$(curl -sS -w "\n__HTTP_CODE__%%{http_code}" "$@")
        HTTP_CODE=$(printf '%s' "$HTTP_BODY" | tail -1 | sed 's/__HTTP_CODE__//')
        BODY=$(printf '%s' "$HTTP_BODY" | sed '$d')
        if [ "$HTTP_CODE" -lt 200 ] || [ "$HTTP_CODE" -ge 300 ]; then
          echo "ERROR: DigitalOcean API request returned HTTP $HTTP_CODE: $BODY" >&2
          exit 1
        fi
        printf '%s' "$BODY"
      }

      # === 1. Find or create Functions namespace ===
      NS_LIST=$(do_curl -H "$AUTH" "$DO_API/functions/namespaces")
      printf '%s' "$NS_LIST" | jq -e \
        'has("namespaces")
          and ((.namespaces == null)
            or ((.namespaces | type) == "array"
              and all(.namespaces[];
                type == "object"
                and (.label | type) == "string"
                and (.namespace | type) == "string")))' >/dev/null || {
        echo "ERROR: DigitalOcean returned an invalid namespace inventory" >&2
        exit 1
      }
      NS_ID=$(printf '%s' "$NS_LIST" | jq -r --arg l "$LABEL" \
        '[(.namespaces // [])[] | select(.label == $l)] | .[0].namespace // empty')

      if [ -z "$NS_ID" ]; then
        echo "Creating namespace $LABEL in region ${var.region} ..."
        NS_RESP=$(do_curl -X POST -H "$AUTH" -H "$CT" \
          -d "{\"region\":\"${var.region}\",\"label\":\"$LABEL\"}" \
          "$DO_API/functions/namespaces")
        NS_ID=$(printf '%s' "$NS_RESP"    | jq -r '.namespace.namespace // empty')
        NS_UUID=$(printf '%s' "$NS_RESP"  | jq -r '.namespace.uuid // empty')
        API_HOST=$(printf '%s' "$NS_RESP" | jq -r '.namespace.api_host // empty')
        API_KEY=$(printf '%s' "$NS_RESP"  | jq -r '.namespace.key // empty')
      else
        echo "Namespace exists: $NS_ID"
        NS_DETAIL=$(do_curl -H "$AUTH" "$DO_API/functions/namespaces/$NS_ID")
        NS_UUID=$(printf '%s' "$NS_DETAIL"  | jq -r '.namespace.uuid // empty')
        API_HOST=$(printf '%s' "$NS_DETAIL" | jq -r '.namespace.api_host // empty')
        API_KEY=$(printf '%s' "$NS_DETAIL"  | jq -r '.namespace.key // empty')
      fi

      [ -n "$NS_ID" ]   || { echo "ERROR: could not get namespace ID";  exit 1; }
      [ -n "$NS_UUID" ]  || { echo "ERROR: could not get namespace UUID"; exit 1; }
      [ -n "$API_HOST" ] || { echo "ERROR: could not get API host";      exit 1; }
      [ -n "$API_KEY" ]  || { echo "ERROR: could not get API key";       exit 1; }

      # OpenWhisk Basic Auth = base64("uuid:key")
      OW_AUTH=$(printf '%s:%s' "$NS_UUID" "$API_KEY" | base64 | tr -d '\n')

      # === 2. Create / update OpenWhisk package ===
      do_curl -X PUT \
        -H "Authorization: Basic $OW_AUTH" -H "$CT" \
        -d '{}' \
        "$API_HOST/api/v1/namespaces/_/packages/autoscaler?overwrite=true" > /dev/null

      # === 3. Deploy the action ===
      CODE=$(printf '%s' "$FN_CODE_B64" | base64 -d)
      PAYLOAD=$(jq -n --arg code "$CODE" '{
        "exec":  {"kind":"python:default","code":$code},
        "limits":{"timeout":120000,"memory":256},
        "annotations":[{"key":"web-export","value":false}]
      }')

      do_curl -X PUT \
        -H "Authorization: Basic $OW_AUTH" -H "$CT" \
        -d "$PAYLOAD" \
        "$API_HOST/api/v1/namespaces/_/actions/autoscaler/check?overwrite=true" > /dev/null

      echo "Action autoscaler/check deployed."

      # === 4. Create / replace cron trigger (every 4 minutes) ===
      TRIGGER="${var.stackName}-autoscale-cron"
      curl -s -X DELETE -H "$AUTH" \
        "$DO_API/functions/namespaces/$NS_ID/triggers/$TRIGGER" > /dev/null 2>&1 || true

      do_curl -X POST -H "$AUTH" -H "$CT" \
        -d "{
          \"name\":\"$TRIGGER\",
          \"function\":\"autoscaler/check\",
          \"type\":\"SCHEDULED\",
          \"is_enabled\":true,
          \"scheduled_details\":{\"cron\":\"*/4 * * * *\",\"body\":{}}
        }" \
        "$DO_API/functions/namespaces/$NS_ID/triggers" > /dev/null

      echo "Trigger $TRIGGER created. Deployment complete."
    EOT
  }


  depends_on = [
    null_resource.cleanup_media_nodes,
    null_resource.autoscaler_lifecycle,
    digitalocean_droplet.openvidu_master_node,
    digitalocean_vpc.openvidu_vpc,
    digitalocean_tag.media_node_tag,
    digitalocean_tag.draining_tag,
  ]
}

# DigitalOcean Space
resource "digitalocean_spaces_bucket" "openvidu_space" {
  count  = var.spaceName == "" ? 1 : 0
  name   = "${var.stackName}-space-${random_id.bucket_suffix.hex}"
  region = var.spaceRegion
  acl    = "private"
}

resource "digitalocean_spaces_key" "openvidu_space_key" {
  name = "${var.stackName}-space-key"
  grant {
    bucket     = var.spaceName == "" ? digitalocean_spaces_bucket.openvidu_space[0].name : var.spaceName
    permission = "readwrite"
  }
}

locals {
  # Omit only comments, standalone Python docstrings and blank lines from transport.
  # Source stays readable; render tests compare executable ASTs, including Lua strings.
  capacity_python_sources = { for name in ["report-fleet-readiness.py", "recorder_admission.py", "arm-approved-recorder.py", "arm-fresh-recorder.py", "settle-recordings.py", "recorder-storage-probe.py", "report-recording-locations.py", "recording-job-observation.py", "settle-recording-jobs.py", "recorder-capacity-footprint.py", "recorder-isolation.py", "preserve-recorder-ipc.py", "media_drain_guard.py", "prepare-fresh-recorder.py", "prepare-fresh-apt.py"] : name =>
    replace(replace(replace(file("${path.module}/${name}"), "/(?m)^[ \\t]*#[^\\n]*\\n/", ""), "/(?ms)^[ \\t]*\"\"\"[^\"\\r\\n].*?\"\"\"[ \\t]*\\n/", ""), "/(?m)^[ \\t]*\\n/", "")
  }
  # Transport only: preserve the rendered startup scripts byte-for-byte, including
  # their failure handling. Remove the private decoded script on normal exit.
  user_data_master_transport = templatefile("${path.module}/user-data-transport.sh.tftpl", {
    payload = base64gzip(local.user_data_master), checksum = sha256(local.user_data_master)
  })
  user_data_media_transport = templatefile("${path.module}/user-data-transport.sh.tftpl", {
    payload = base64gzip(local.user_data_media), checksum = sha256(local.user_data_media)
  })
  capacity_authority_settings = var.capacityReservationsEnabled ? join("", [
    # jsonencode emits one physical line; the quoted delimiter prevents shell
    # expansion even for credential metacharacters. Avoid inner base64 so the
    # checksum-protected outer gzip can compress repeated profile/settings keys.
    "cat > /etc/courseultra-capacity-drain.json <<'COURSEULTRA_SETTINGS_EOF'\n${jsonencode({ url = var.capacityBackendUrl, token = var.capacityBackendToken, cloudToken = var.autoscalerToken, stackName = var.stackName, mediaTag = digitalocean_tag.media_node_tag.name, drainingTag = digitalocean_tag.draining_tag.name })}\nCOURSEULTRA_SETTINGS_EOF\nchmod 600 /etc/courseultra-capacity-drain.json\n",
    # Bind deployment identity only after Terraform creates the VPC; callers cannot
    # know its UUID in advance. Profile and recorder-policy approval remain supplied.
    "cat > /etc/courseultra-capacity-fleet-profile.json <<'COURSEULTRA_SETTINGS_EOF'\n${jsonencode(merge(jsondecode(var.capacityFleetDescriptorJson), { vpcId = digitalocean_vpc.openvidu_vpc.id, region = var.region }))}\nCOURSEULTRA_SETTINGS_EOF\nchmod 600 /etc/courseultra-capacity-fleet-profile.json\n",
  ]) : ""
  capacity_drain_settings = var.capacityReservationsEnabled ? join("", [local.capacity_authority_settings,
    join("", [for name in ["report-fleet-readiness.py", "recorder_admission.py", "arm-approved-recorder.py", "arm-fresh-recorder.py", "recorder-startup-guard.sh", "settle-recordings.py", "recorder-storage-probe.py"] : "cat > /usr/local/bin/${name} <<'COURSEULTRA_HELPER_EOF'\n${endswith(name, ".py") ? local.capacity_python_sources[name] : file("${path.module}/${name}")}COURSEULTRA_HELPER_EOF\nchmod 700 /usr/local/bin/${name}\n"])
  ]) : ""
  # Group related Python sources so outer gzip can reuse its bounded dictionary.
  # Install every helper before the existing watcher starts; executable ASTs are checked.
  capacity_media_drain_settings = var.capacityReservationsEnabled ? join("", [local.capacity_authority_settings,
    join("", [for name in ["report-fleet-readiness.py", "arm-fresh-recorder.py", "arm-approved-recorder.py", "report-recording-locations.py", "recorder_admission.py", "recorder-capacity-footprint.py", "settle-recordings.py", "settle-recording-jobs.py", "recording-job-observation.py", "recorder-storage-probe.py", "recorder-isolation.py", "preserve-recorder-ipc.py", "recorder-startup-guard.sh"] : "cat > /usr/local/bin/${name} <<'COURSEULTRA_HELPER_EOF'\n${endswith(name, ".py") ? local.capacity_python_sources[name] : file("${path.module}/${name}")}COURSEULTRA_HELPER_EOF\nchmod 700 /usr/local/bin/${name}\n"]),
    "cp /usr/local/bin/courseultra-media-drain-guard /usr/local/bin/media_drain_guard.py\nchmod 700 /usr/local/bin/media_drain_guard.py\n"
  ]) : ""
  capacity_master_drain_settings = var.capacityReservationsEnabled ? "${local.capacity_drain_settings}cat > /usr/local/bin/media_drain_guard.py <<'COURSEULTRA_HELPER_EOF'\n${var.capacityReservationsEnabled ? local.capacity_python_sources["media_drain_guard.py"] : file("${path.module}/media_drain_guard.py")}COURSEULTRA_HELPER_EOF\nchmod 700 /usr/local/bin/media_drain_guard.py\n" : ""
  capacity_fleet_report          = var.capacityReservationsEnabled ? "timeout --kill-after=2s 20s python3 /usr/local/bin/report-fleet-readiness.py /etc/courseultra-capacity-drain.json || echo 'Fleet observation held; existing reservations retained'\n" : ""
  # Two bounded observations per existing cron invocation leave freshness margin
  # without extending evidence TTL or allowing overlapping watcher processes.
  capacity_fleet_report_cycle     = var.capacityReservationsEnabled ? "fleet_tick_started=$SECONDS\n${local.capacity_fleet_report}fleet_tick_delay=$((30 - (SECONDS - fleet_tick_started)))\nif [ \"$fleet_tick_delay\" -gt 0 ]; then sleep \"$fleet_tick_delay\"; fi\n${local.capacity_fleet_report}" : ""
  capacity_recording_report       = var.capacityReservationsEnabled ? "timeout --kill-after=5s 45s python3 /usr/local/bin/report-recording-locations.py /etc/courseultra-capacity-drain.json || echo 'Recording placement reporting held; recording ownership retained'\n" : ""
  capacity_node_reports           = var.capacityReservationsEnabled ? "(${local.capacity_recording_report}) &\n${local.capacity_fleet_report_cycle}wait\n" : ""
  capacity_watcher_lock           = var.capacityReservationsEnabled ? "exec 8>/var/lock/openvidu-tag-watcher.lock\nflock -n 8 || exit 0\n" : ""
  capacity_fresh_arm              = var.capacityReservationsEnabled ? "python3 /usr/local/bin/arm-approved-recorder.py || { echo 'Approved recorder first-start held'; exit 1; }\n" : ""
  capacity_fast_watcher_cron      = var.capacityReservationsEnabled ? "\necho '* * * * * root /usr/local/bin/tag_watcher.sh >> /var/log/tag_watcher.log 2>&1' > /etc/cron.d/tag-watcher\nchmod 644 /etc/cron.d/tag-watcher" : ""
  capacity_master_watcher_install = var.capacityReservationsEnabled ? "${local.capacity_master_drain_settings}printf '%s' '${base64encode("#!/bin/bash\n${local.capacity_watcher_lock}${local.capacity_fleet_report_cycle}")}' | base64 --decode > /usr/local/bin/tag_watcher.sh\nchmod 700 /usr/local/bin/tag_watcher.sh${local.capacity_fast_watcher_cron}\n" : ""
  # Default-disabled qualification-only barrier. Place before vendor service
  # enablement on BOTH roles; a reboot cannot skip unarmed guard installation.
  recorder_guard_barrier = (var.isolatedRecorderGuard ? <<-EOF
if [ "${var.isolatedRecorderGuard}" = "true" ]; then
  install -d -m 755 /etc/systemd/system/openvidu.service.d
  printf '[Unit]\nConditionPathExists=/opt/openvidu/.courseultra-recorder-prepared\n' > /etc/systemd/system/openvidu.service.d/courseultra-recorder.conf
  chmod 644 /etc/systemd/system/openvidu.service.d/courseultra-recorder.conf
fi
EOF
  : "")

  recorder_guard_prepare        = <<-EOF
if [ "${var.isolatedRecorderGuard}" = "true" ]; then
  cat > /usr/local/bin/prepare-fresh-recorder.py <<'COURSEULTRA_HELPER_EOF'
${local.capacity_python_sources["prepare-fresh-recorder.py"]}COURSEULTRA_HELPER_EOF
  cat > /usr/local/share/courseultra-recorder-start.sh <<'COURSEULTRA_HELPER_EOF'
${file("${path.module}/recorder-startup-guard.sh")}COURSEULTRA_HELPER_EOF
  printf '%s' '${filebase64("${path.module}/recorder-startup-guard.override.yaml")}' | base64 --decode > /usr/local/share/courseultra-recorder.override.yaml
  chmod 600 /usr/local/bin/prepare-fresh-recorder.py /usr/local/share/courseultra-recorder-start.sh /usr/local/share/courseultra-recorder.override.yaml
  python3 /usr/local/bin/prepare-fresh-recorder.py "$RECORDER_NODE_ROLE" || { echo "[OpenVidu] unarmed recorder preparation refused"; exit 1; }
  install -m 600 /dev/null /opt/openvidu/.courseultra-recorder-prepared
  systemctl daemon-reload
fi
EOF
  recorder_guard_prepare_master = var.isolatedRecorderGuard ? "RECORDER_NODE_ROLE=master_node\n${local.recorder_guard_prepare}" : ""
  recorder_guard_prepare_media  = var.isolatedRecorderGuard ? "RECORDER_NODE_ROLE=media_node\n${local.recorder_guard_prepare}" : ""
  # One reviewed release contract for both roles. TODO(3.8 integration): update
  # all three values together after reviewing the vendor installers and SDK;
  # also qualify fresh-master Redis persistence, restore and drain readiness.
  # A shared version edit alone must never select an unreviewed installer.
  openvidu_installer_release = {
    version       = "3.8.0"
    master_sha256 = "feae2e1b9fff75edb3c087d7263ce58b553d5f51193046e9359fb0875856d7f2"
    media_sha256  = "8d79aa04f303ef5ace2abda8233960480441591cb130fd48460770f071d41c71"
  }

  # Both fixed and autoscaled nodes share this exact fresh-node preparation.
  # Keep signed APT metadata checks; switching the inconsistent mirror is not
  # permission to ignore hash failures or replay installation on a running node.
  fresh_apt_prepare = <<-EOF
python3 - <<'COURSEULTRA_APT_EOF'
${local.capacity_python_sources["prepare-fresh-apt.py"]}COURSEULTRA_APT_EOF
EOF

  install_script_master = <<-EOF
#!/bin/bash
set -e
umask 077

OPENVIDU_VERSION=${local.openvidu_installer_release.version}
DOMAIN=
echo "DPkg::Lock::Timeout \"-1\";" > /etc/apt/apt.conf.d/99timeout

# Install dependencies
apt-get update && apt-get install -y

# Create counter file for tracking script executions
echo 1 > /usr/local/bin/openvidu_install_counter.txt

mkdir -p /opt/openvidu
touch /opt/openvidu/secrets.env
chmod 600 /opt/openvidu/secrets.env

# Get IPs using DO metadata
PUBLIC_IP=$(curl -s http://169.254.169.254/metadata/v1/floating_ip/ipv4/ip_address)
if [ -z "$PUBLIC_IP" ] || [ "$PUBLIC_IP" == "null" ]; then
  PUBLIC_IP=$(curl -s http://169.254.169.254/metadata/v1/interfaces/public/0/ipv4/address)
fi
MASTER_NODE_PRIVATE_IP=$(curl -s http://169.254.169.254/metadata/v1/interfaces/private/0/ipv4/address)
MASTER_NODE_ID=$(curl -fsS http://169.254.169.254/metadata/v1/id)

if [[ "${var.domainName}" == "" ]]; then
  [ ! -d "/usr/share/openvidu" ] && mkdir -p /usr/share/openvidu
  RANDOM_DOMAIN_STRING=$(tr -dc 'a-z' < /dev/urandom | head -c 8)
  DOMAIN="openvidu-$RANDOM_DOMAIN_STRING-$(echo $PUBLIC_IP | tr '.' '-').sslip.io"
else
  DOMAIN="${var.domainName}"
fi
DOMAIN="$(/usr/local/bin/store_secret.sh save DOMAIN_NAME "$DOMAIN")"

# Meet initial admin user and password
MEET_INITIAL_ADMIN_USER="$(/usr/local/bin/store_secret.sh save MEET_INITIAL_ADMIN_USER "admin")"
if [[ "${var.initialMeetAdminPassword}" != '' ]]; then
  MEET_INITIAL_ADMIN_PASSWORD="$(/usr/local/bin/store_secret.sh save MEET_INITIAL_ADMIN_PASSWORD "${var.initialMeetAdminPassword}")"
else
  MEET_INITIAL_ADMIN_PASSWORD="$(/usr/local/bin/store_secret.sh generate MEET_INITIAL_ADMIN_PASSWORD)"
fi

if [[ "${var.initialMeetApiKey}" != '' ]]; then
  MEET_INITIAL_API_KEY="$(/usr/local/bin/store_secret.sh save MEET_INITIAL_API_KEY "${var.initialMeetApiKey}")"
fi

REDIS_PASSWORD="$(/usr/local/bin/store_secret.sh generate REDIS_PASSWORD)"
MONGO_ADMIN_USERNAME="$(/usr/local/bin/store_secret.sh save MONGO_ADMIN_USERNAME "mongoadmin")"
MONGO_ADMIN_PASSWORD="$(/usr/local/bin/store_secret.sh generate MONGO_ADMIN_PASSWORD)"
MONGO_REPLICA_SET_KEY="$(/usr/local/bin/store_secret.sh generate MONGO_REPLICA_SET_KEY)"
MINIO_ACCESS_KEY="$(/usr/local/bin/store_secret.sh save MINIO_ACCESS_KEY "minioadmin")"
MINIO_SECRET_KEY="$(/usr/local/bin/store_secret.sh generate MINIO_SECRET_KEY)"
DASHBOARD_ADMIN_USERNAME="$(/usr/local/bin/store_secret.sh save DASHBOARD_ADMIN_USERNAME "dashboardadmin")"
DASHBOARD_ADMIN_PASSWORD="$(/usr/local/bin/store_secret.sh generate DASHBOARD_ADMIN_PASSWORD)"
GRAFANA_ADMIN_USERNAME="$(/usr/local/bin/store_secret.sh save GRAFANA_ADMIN_USERNAME "grafanaadmin")"
GRAFANA_ADMIN_PASSWORD="$(/usr/local/bin/store_secret.sh generate GRAFANA_ADMIN_PASSWORD)"
ENABLED_MODULES="$(/usr/local/bin/store_secret.sh save ENABLED_MODULES "${var.enabledModules}")"
LIVEKIT_API_KEY="$(/usr/local/bin/store_secret.sh generate LIVEKIT_API_KEY "API" 12)"
LIVEKIT_API_SECRET="$(/usr/local/bin/store_secret.sh generate LIVEKIT_API_SECRET)"
OPENVIDU_PRO_LICENSE="$(/usr/local/bin/store_secret.sh save OPENVIDU_PRO_LICENSE "${var.openviduLicense}")"
OPENVIDU_RTC_ENGINE="$(/usr/local/bin/store_secret.sh save OPENVIDU_RTC_ENGINE "${var.rtcEngine}")"
OPENVIDU_VERSION="$(/usr/local/bin/store_secret.sh save OPENVIDU_VERSION "$OPENVIDU_VERSION")"
MASTER_NODE_PRIVATE_IP="$(/usr/local/bin/store_secret.sh save MASTER_NODE_PRIVATE_IP "$MASTER_NODE_PRIVATE_IP")"
MASTER_NODE_ID="$(/usr/local/bin/store_secret.sh save MASTER_NODE_ID "$MASTER_NODE_ID")"

ALL_SECRETS_GENERATED="$(/usr/local/bin/store_secret.sh save ALL_SECRETS_GENERATED "true")"

# Fetch the release-pinned installer over TLS and verify the reviewed artifact
# before running it as root. Update the checksum deliberately during upgrades.
INSTALL_SCRIPT=/tmp/install_ov_master_node.sh
INSTALL_SCRIPT_URL="https://s3-eu-west-1.amazonaws.com/get.openvidu.io/pro/elastic/$OPENVIDU_VERSION/install_ov_master_node.sh"
INSTALL_SCRIPT_SHA256="${local.openvidu_installer_release.master_sha256}"
curl -fsSL "$INSTALL_SCRIPT_URL" -o "$INSTALL_SCRIPT"
printf '%s  %s\n' "$INSTALL_SCRIPT_SHA256" "$INSTALL_SCRIPT" | sha256sum --check --status || {
  echo "OpenVidu master installer checksum verification failed"
  exit 1
}
INSTALL_COMMAND="sh $INSTALL_SCRIPT"

# Common arguments
COMMON_ARGS=(
  "--no-tty"
  "--install"
  "--environment=digitalocean"
  "--deployment-type=elastic"
  "--node-role=master-node"
  "--openvidu-pro-license=$OPENVIDU_PRO_LICENSE"
  "--private-ip=$MASTER_NODE_PRIVATE_IP"
  "--domain-name=$DOMAIN"
  "--enabled-modules='$ENABLED_MODULES'"
  "--rtc-engine=$OPENVIDU_RTC_ENGINE"
  "--redis-password=$REDIS_PASSWORD"
  "--mongo-admin-user=$MONGO_ADMIN_USERNAME"
  "--mongo-admin-password=$MONGO_ADMIN_PASSWORD"
  "--mongo-replica-set-key=$MONGO_REPLICA_SET_KEY"
  "--minio-access-key=$MINIO_ACCESS_KEY"
  "--minio-secret-key=$MINIO_SECRET_KEY"
  "--dashboard-admin-user=$DASHBOARD_ADMIN_USERNAME"
  "--dashboard-admin-password=$DASHBOARD_ADMIN_PASSWORD"
  "--grafana-admin-user=$GRAFANA_ADMIN_USERNAME"
  "--grafana-admin-password=$GRAFANA_ADMIN_PASSWORD"
  "--meet-initial-admin-password=$MEET_INITIAL_ADMIN_PASSWORD"
  "--meet-initial-api-key=$MEET_INITIAL_API_KEY"
  "--livekit-api-key=$LIVEKIT_API_KEY"
  "--livekit-api-secret=$LIVEKIT_API_SECRET"
)

# Include additional installer flags provided by the user
if [[ "${var.additionalInstallFlags}" != "" ]]; then
  IFS=',' read -ra EXTRA_FLAGS <<< "${var.additionalInstallFlags}"
  for extra_flag in "$${EXTRA_FLAGS[@]}"; do
    # Trim whitespace around each flag
    extra_flag="$(echo -e "$${extra_flag}" | sed -e 's/^[ \t]*//' -e 's/[ \t]*$//')"
    if [[ "$extra_flag" != "" ]]; then
      COMMON_ARGS+=("$extra_flag")
    fi
  done
fi

# Certificate arguments
if [[ "${var.certificateType}" == "selfsigned" ]]; then
  CERT_ARGS=(
    "--certificate-type=selfsigned"
  )
elif [[ "${var.certificateType}" == "letsencrypt" ]]; then
  CERT_ARGS=(
    "--certificate-type=letsencrypt"
  )
else
  # Use base64 encoded certificates directly
  OWN_CERT_CRT=${var.ownPublicCertificate}
  OWN_CERT_KEY=${var.ownPrivateCertificate}
  CERT_ARGS=(
    "--certificate-type=owncert"
    "--owncert-public-key=$OWN_CERT_CRT"
    "--owncert-private-key=$OWN_CERT_KEY"
  )
fi

# Final command
FINAL_COMMAND="$INSTALL_COMMAND $(printf "%s " "$${COMMON_ARGS[@]}") $(printf "%s " "$${CERT_ARGS[@]}")"

# Execute installation
set +e
MAX_RETRIES=5
RETRY_COUNT=1

until bash -c "$FINAL_COMMAND"; do
  echo "Install command failed (attempt $RETRY_COUNT/$MAX_RETRIES)"
  if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
    echo "Install command failed after $MAX_RETRIES attempts"
    exit 1
  fi
  RETRY_COUNT=$((RETRY_COUNT + 1))
  sleep 10
done
EOF

  config_s3_script_master = <<-EOF
#!/bin/bash
set -euo pipefail
umask 077

# Install dir and config dir
INSTALL_DIR="/opt/openvidu"
CLUSTER_CONFIG_DIR="$${INSTALL_DIR}/config/cluster"
V2_COMPATIBILITY_CONFIG="$${CLUSTER_CONFIG_DIR}/master_node/v2compatibility.env"


# Get DigitalOcean Spaces access keys from environment or metadata
EXTERNAL_S3_ACCESS_KEY="${digitalocean_spaces_key.openvidu_space_key.access_key}"
EXTERNAL_S3_SECRET_KEY="${digitalocean_spaces_key.openvidu_space_key.secret_key}"

# Config S3 bucket
EXTERNAL_S3_ENDPOINT="https://${var.spaceRegion}.digitaloceanspaces.com"
EXTERNAL_S3_REGION="${var.spaceRegion}"
EXTERNAL_S3_PATH_STYLE_ACCESS="true"
EXTERNAL_S3_BUCKET_APP_DATA="${var.spaceName == "" ? digitalocean_spaces_bucket.openvidu_space[0].name : var.spaceName}"

sed -i "s|EXTERNAL_S3_ENDPOINT=.*|EXTERNAL_S3_ENDPOINT=$EXTERNAL_S3_ENDPOINT|" "$${CLUSTER_CONFIG_DIR}/openvidu.env"
sed -i "s|EXTERNAL_S3_REGION=.*|EXTERNAL_S3_REGION=$EXTERNAL_S3_REGION|" "$${CLUSTER_CONFIG_DIR}/openvidu.env"
sed -i "s|EXTERNAL_S3_PATH_STYLE_ACCESS=.*|EXTERNAL_S3_PATH_STYLE_ACCESS=$EXTERNAL_S3_PATH_STYLE_ACCESS|" "$${CLUSTER_CONFIG_DIR}/openvidu.env"
sed -i "s|EXTERNAL_S3_BUCKET_APP_DATA=.*|EXTERNAL_S3_BUCKET_APP_DATA=$EXTERNAL_S3_BUCKET_APP_DATA|" "$${CLUSTER_CONFIG_DIR}/openvidu.env"
sed -i "s|EXTERNAL_S3_ACCESS_KEY=.*|EXTERNAL_S3_ACCESS_KEY=$EXTERNAL_S3_ACCESS_KEY|" "$${CLUSTER_CONFIG_DIR}/openvidu.env"
sed -i "s|EXTERNAL_S3_SECRET_KEY=.*|EXTERNAL_S3_SECRET_KEY=$EXTERNAL_S3_SECRET_KEY|" "$${CLUSTER_CONFIG_DIR}/openvidu.env"

# Capacity readiness observes the actual recorder process. Publish this template
# before media-node creation so every fresh autoscaled node inherits the listener.
if [ "${var.capacityReservationsEnabled}" = "true" ]; then
  EGRESS_TEMPLATE="$${CLUSTER_CONFIG_DIR}/media_node/egress.yaml"
  test "$(grep -c '^health_port:' "$EGRESS_TEMPLATE")" = 1
  if ! grep -q '^prometheus_port:' "$EGRESS_TEMPLATE"; then
    sed -i '/^health_port:/a\
prometheus_port: 9094
' "$EGRESS_TEMPLATE"
  fi
  test "$(grep -c '^prometheus_port: 9094$' "$EGRESS_TEMPLATE")" = 1
  # Exact3.8 exits IO drain when its first worker is idle. A single worker
  # preserves queued terminal acknowledgements before recorder-only graceful exit.
  if ! grep -q '^io_workers:' "$EGRESS_TEMPLATE"; then
    sed -i '/^health_port:/a\
io_workers: 1
' "$EGRESS_TEMPLATE"
  fi
  test "$(grep -c '^io_workers: 1$' "$EGRESS_TEMPLATE")" = 1
fi

# OpenVidu's external S3 settings serve cluster data, but the v2 compatibility layer otherwise
# keeps completed recordings on the master disk. CourseUltra migrates each provider recording to
# managed S3/CDN storage asynchronously, so the provider copy must survive a master replacement
# until that migration and its delayed cleanup have completed.
if [[ ! -f "$V2_COMPATIBILITY_CONFIG" ]]; then
  echo "OpenVidu v2 compatibility configuration is missing" >&2
  exit 1
fi
if ! grep -q '^V2COMPAT_OPENVIDU_PRO_RECORDING_STORAGE=' "$V2_COMPATIBILITY_CONFIG"; then
  echo "OpenVidu v2 recording storage setting is missing" >&2
  exit 1
fi
sed -i \
  's|^V2COMPAT_OPENVIDU_PRO_RECORDING_STORAGE=.*|V2COMPAT_OPENVIDU_PRO_RECORDING_STORAGE=s3|' \
  "$V2_COMPATIBILITY_CONFIG"
grep -qx 'V2COMPAT_OPENVIDU_PRO_RECORDING_STORAGE=s3' "$V2_COMPATIBILITY_CONFIG"
EOF

  after_install_script_master = <<-EOF
#!/bin/bash
set -e
umask 077

# Generate URLs
DOMAIN="$(grep '^DOMAIN_NAME=' /opt/openvidu/secrets.env | cut -d'=' -f2)"
OPENVIDU_URL="https://$${DOMAIN}/"
LIVEKIT_URL="wss://$${DOMAIN}/"
DASHBOARD_URL="https://$${DOMAIN}/dashboard/"
GRAFANA_URL="https://$${DOMAIN}/grafana/"
MINIO_URL="https://$${DOMAIN}/minio-console/"

# Update shared secret
/usr/local/bin/store_secret.sh save OPENVIDU_URL "$OPENVIDU_URL"
/usr/local/bin/store_secret.sh save LIVEKIT_URL "$LIVEKIT_URL"
/usr/local/bin/store_secret.sh save DASHBOARD_URL "$DASHBOARD_URL"
/usr/local/bin/store_secret.sh save GRAFANA_URL "$GRAFANA_URL"
/usr/local/bin/store_secret.sh save MINIO_URL "$MINIO_URL"

# Full save secrets.env to S3 bucket
/usr/local/bin/store_secret.sh fullsave
EOF

  update_config_from_secret_script_master = <<-EOF
#!/bin/bash
set -e
umask 077

export AWS_ACCESS_KEY_ID="${digitalocean_spaces_key.openvidu_space_key.access_key}"
export AWS_SECRET_ACCESS_KEY="${digitalocean_spaces_key.openvidu_space_key.secret_key}"
export AWS_DEFAULT_REGION="${var.spaceRegion}"

INSTALL_DIR="/opt/openvidu"
CLUSTER_CONFIG_DIR="$${INSTALL_DIR}/config/cluster"
MASTER_NODE_CONFIG_DIR="$${INSTALL_DIR}/config/node"
SECRETS_FILE="/opt/openvidu/secrets.env"

# Download secrets.env from S3 bucket
aws s3 cp \
  s3://${var.spaceName == "" ? digitalocean_spaces_bucket.openvidu_space[0].name : var.spaceName}/secrets.env \
  "$SECRETS_FILE" \
  --endpoint-url=https://${var.spaceRegion}.digitaloceanspaces.com \
  --region=${var.spaceRegion}
chmod 600 "$SECRETS_FILE"


# Define which keys belong to meet.env
MEET_KEYS=("MEET_INITIAL_ADMIN_USER" "MEET_INITIAL_ADMIN_PASSWORD" "MEET_INITIAL_API_KEY")
# Define which keys belong to master_node.env
MASTER_NODE_KEYS=("REDIS_PASSWORD")

while IFS='=' read -r key value; do
  # Skip empty values
  if [[ -z "$value" ]]; then
    continue
  fi
  
  # Skip MEET_INITIAL_API_KEY if var.initialMeetApiKey is empty
  if [[ "$key" == "MEET_INITIAL_API_KEY" && "${var.initialMeetApiKey}" == "" ]]; then
    continue
  fi
  
  # Check if the key belongs to master_node.env
  if [[ " $${MASTER_NODE_KEYS[@]} " =~ " $${key} " ]]; then
    TARGET_FILE="$${MASTER_NODE_CONFIG_DIR}/master_node.env"
  # Check if the key belongs to meet.env
  elif [[ " $${MEET_KEYS[@]} " =~ " $${key} " ]]; then
    TARGET_FILE="$${CLUSTER_CONFIG_DIR}/master_node/meet.env"
  else
    TARGET_FILE="$${CLUSTER_CONFIG_DIR}/openvidu.env"
  fi
  
  # Update only if the key already exists
  if grep -q "^$key=" "$TARGET_FILE"; then
    sed -i "s|^$key=.*|$key=$value|" "$TARGET_FILE"
  fi
done < "$SECRETS_FILE"
EOF

  update_secret_from_config_script_master = <<-EOF
#!/bin/bash
set -e
umask 077

# Installation directory
INSTALL_DIR="/opt/openvidu"
CLUSTER_CONFIG_DIR="$${INSTALL_DIR}/config/cluster"
MASTER_NODE_CONFIG_DIR="$${INSTALL_DIR}/config/node"
SECRETS_FILE="/opt/openvidu/secrets.env"

# Get current values of the config
REDIS_PASSWORD="$(/usr/local/bin/get_value_from_config.sh REDIS_PASSWORD "$${MASTER_NODE_CONFIG_DIR}/master_node.env")"
DOMAIN_NAME="$(/usr/local/bin/get_value_from_config.sh DOMAIN_NAME "$${CLUSTER_CONFIG_DIR}/openvidu.env")"
OPENVIDU_RTC_ENGINE="$(/usr/local/bin/get_value_from_config.sh OPENVIDU_RTC_ENGINE "$${CLUSTER_CONFIG_DIR}/openvidu.env")"
OPENVIDU_PRO_LICENSE="$(/usr/local/bin/get_value_from_config.sh OPENVIDU_PRO_LICENSE "$${CLUSTER_CONFIG_DIR}/openvidu.env")"
MONGO_ADMIN_USERNAME="$(/usr/local/bin/get_value_from_config.sh MONGO_ADMIN_USERNAME "$${CLUSTER_CONFIG_DIR}/openvidu.env")"
MONGO_ADMIN_PASSWORD="$(/usr/local/bin/get_value_from_config.sh MONGO_ADMIN_PASSWORD "$${CLUSTER_CONFIG_DIR}/openvidu.env")"
MONGO_REPLICA_SET_KEY="$(/usr/local/bin/get_value_from_config.sh MONGO_REPLICA_SET_KEY "$${CLUSTER_CONFIG_DIR}/openvidu.env")"
MINIO_ACCESS_KEY="$(/usr/local/bin/get_value_from_config.sh MINIO_ACCESS_KEY "$${CLUSTER_CONFIG_DIR}/openvidu.env")"
MINIO_SECRET_KEY="$(/usr/local/bin/get_value_from_config.sh MINIO_SECRET_KEY "$${CLUSTER_CONFIG_DIR}/openvidu.env")"
DASHBOARD_ADMIN_USERNAME="$(/usr/local/bin/get_value_from_config.sh DASHBOARD_ADMIN_USERNAME "$${CLUSTER_CONFIG_DIR}/openvidu.env")"
DASHBOARD_ADMIN_PASSWORD="$(/usr/local/bin/get_value_from_config.sh DASHBOARD_ADMIN_PASSWORD "$${CLUSTER_CONFIG_DIR}/openvidu.env")"
GRAFANA_ADMIN_USERNAME="$(/usr/local/bin/get_value_from_config.sh GRAFANA_ADMIN_USERNAME "$${CLUSTER_CONFIG_DIR}/openvidu.env")"
GRAFANA_ADMIN_PASSWORD="$(/usr/local/bin/get_value_from_config.sh GRAFANA_ADMIN_PASSWORD "$${CLUSTER_CONFIG_DIR}/openvidu.env")"
LIVEKIT_API_KEY="$(/usr/local/bin/get_value_from_config.sh LIVEKIT_API_KEY "$${CLUSTER_CONFIG_DIR}/openvidu.env")"
LIVEKIT_API_SECRET="$(/usr/local/bin/get_value_from_config.sh LIVEKIT_API_SECRET "$${CLUSTER_CONFIG_DIR}/openvidu.env")"
MEET_INITIAL_ADMIN_USER="$(/usr/local/bin/get_value_from_config.sh MEET_INITIAL_ADMIN_USER "$${CLUSTER_CONFIG_DIR}/master_node/meet.env")"
MEET_INITIAL_ADMIN_PASSWORD="$(/usr/local/bin/get_value_from_config.sh MEET_INITIAL_ADMIN_PASSWORD "$${CLUSTER_CONFIG_DIR}/master_node/meet.env")"
if [[ "${var.initialMeetApiKey}" != '' ]]; then
  MEET_INITIAL_API_KEY="$(/usr/local/bin/get_value_from_config.sh MEET_INITIAL_API_KEY "$${CLUSTER_CONFIG_DIR}/master_node/meet.env")"
fi
ENABLED_MODULES="$(/usr/local/bin/get_value_from_config.sh ENABLED_MODULES "$${CLUSTER_CONFIG_DIR}/openvidu.env")"

# Update secrets file
# Function to update or add a key-value pair
update_secret() {
  local key="$1"
  local value="$2"
  if grep -q "^$${key}=" "$SECRETS_FILE"; then
    sed -i "s|^$${key}=.*|$${key}=$${value}|" "$SECRETS_FILE"
  else
    echo "$${key}=$${value}" >> "$SECRETS_FILE"
  fi
}

# Update all secrets
update_secret "REDIS_PASSWORD" "$REDIS_PASSWORD"
update_secret "DOMAIN_NAME" "$DOMAIN_NAME"
update_secret "OPENVIDU_RTC_ENGINE" "$OPENVIDU_RTC_ENGINE"
update_secret "OPENVIDU_PRO_LICENSE" "$OPENVIDU_PRO_LICENSE"
update_secret "MONGO_ADMIN_USERNAME" "$MONGO_ADMIN_USERNAME"
update_secret "MONGO_ADMIN_PASSWORD" "$MONGO_ADMIN_PASSWORD"
update_secret "MONGO_REPLICA_SET_KEY" "$MONGO_REPLICA_SET_KEY"
update_secret "MINIO_ACCESS_KEY" "$MINIO_ACCESS_KEY"
update_secret "MINIO_SECRET_KEY" "$MINIO_SECRET_KEY"
update_secret "DASHBOARD_ADMIN_USERNAME" "$DASHBOARD_ADMIN_USERNAME"
update_secret "DASHBOARD_ADMIN_PASSWORD" "$DASHBOARD_ADMIN_PASSWORD"
update_secret "GRAFANA_ADMIN_USERNAME" "$GRAFANA_ADMIN_USERNAME"
update_secret "GRAFANA_ADMIN_PASSWORD" "$GRAFANA_ADMIN_PASSWORD"
update_secret "LIVEKIT_API_KEY" "$LIVEKIT_API_KEY"
update_secret "LIVEKIT_API_SECRET" "$LIVEKIT_API_SECRET"
update_secret "MEET_INITIAL_ADMIN_USER" "$MEET_INITIAL_ADMIN_USER"
update_secret "MEET_INITIAL_ADMIN_PASSWORD" "$MEET_INITIAL_ADMIN_PASSWORD"
if [[ "${var.initialMeetApiKey}" != '' ]]; then
  update_secret "MEET_INITIAL_API_KEY" "$MEET_INITIAL_API_KEY"
fi
update_secret "ENABLED_MODULES" "$ENABLED_MODULES"

/usr/local/bin/store_secret.sh fullsave
EOF

  get_value_from_config_script_master = <<-EOF
#!/bin/bash
set -e

# Function to get the value of a given key from the environment file
get_value() {
    local key="$1"
    local file_path="$2"
    # Use grep to find the line with the key, ignoring lines starting with #
    # Use awk to split on '=' and print the second field, which is the value
    local value=$(grep -E "^\s*$key\s*=" "$file_path" | awk -F= '{print $2}' | sed 's/#.*//; s/^\s*//; s/\s*$//')
    # If the value is empty, return "none"
    if [ -z "$value" ]; then
        echo "none"
    else
        echo "$value"
    fi
}

# Check if the correct number of arguments are supplied
if [ "$#" -ne 2 ]; then
    echo "Usage: $0 <key> <file_path>"
    exit 1
fi

# Get the key and file path from the arguments
key="$1"
file_path="$2"

# Get and print the value
get_value "$key" "$file_path"
EOF

  store_secret_script_master = <<-EOF
#!/bin/bash
set -e
umask 077

export AWS_ACCESS_KEY_ID="${digitalocean_spaces_key.openvidu_space_key.access_key}"
export AWS_SECRET_ACCESS_KEY="${digitalocean_spaces_key.openvidu_space_key.secret_key}"
export AWS_DEFAULT_REGION="${var.spaceRegion}"

# Modes: generate, save, fullsave
# save mode: save the provided value in secrets.env and return it
# generate mode: generate a random password save it and return it
# fullsave mode: save the secrets.env to S3 bucket
MODE="$1"
if [[ "$MODE" == "generate" ]]; then
    SECRET_KEY_NAME="$2"
    PREFIX="$${3:-}"
    LENGTH="$${4:-44}"
    RANDOM_PASSWORD="$(openssl rand -base64 64 | tr -d '+/=\n' | cut -c -$${LENGTH})"
    RANDOM_PASSWORD="$${PREFIX}$${RANDOM_PASSWORD}"
    # Save to secrets.env in bucket
    echo "$${SECRET_KEY_NAME}=$${RANDOM_PASSWORD}" >> /opt/openvidu/secrets.env
    echo "$RANDOM_PASSWORD"
elif [[ "$MODE" == "save" ]]; then
    SECRET_KEY_NAME="$2"
    SECRET_VALUE="$3"
    # Check if the key already exists
    if grep -q "^$${SECRET_KEY_NAME}=" /opt/openvidu/secrets.env; then
      # Update existing key
      sed -i "s|^$${SECRET_KEY_NAME}=.*|$${SECRET_KEY_NAME}=$${SECRET_VALUE}|" /opt/openvidu/secrets.env
    else
      # Add new key
      echo "$${SECRET_KEY_NAME}=$${SECRET_VALUE}" >> /opt/openvidu/secrets.env
    fi
    echo "$SECRET_VALUE"
elif [[ "$MODE" == "fullsave" ]]; then
      aws s3 cp /opt/openvidu/secrets.env \
        s3://${var.spaceName == "" ? digitalocean_spaces_bucket.openvidu_space[0].name : var.spaceName}/secrets.env \
        --endpoint-url=https://${var.spaceRegion}.digitaloceanspaces.com \
        --acl private \
        --region=${var.spaceRegion}
fi
EOF

  check_app_ready_script_master = <<-EOF
#!/bin/bash
while true; do
  HTTP_STATUS=$(curl -Ik http://localhost:7880/health/caddy | head -n1 | awk '{print $2}')
  if [ $HTTP_STATUS == 200 ]; then
    break
  fi
  sleep 5
done
EOF

  restart_script_master = <<-EOF
#!/bin/bash
set -e

# The installer writes 1 before configuration and Redis persistence are ready.
# A partial installation must never bypass those steps through reboot/retry.
if [ "$(cat /usr/local/bin/openvidu_install_counter.txt 2>/dev/null)" != "installation_complete" ]; then
  echo "[OpenVidu] installation incomplete; inspect bootstrap failure before restarting" >&2
  exit 1
fi

# Stop all services
systemctl stop openvidu

# Update config from secrets
/usr/local/bin/update_config_from_secret.sh

# Start all services
systemctl start openvidu
EOF

  autoscaler_function_code = <<-PYEOF
import base64
import json
import math
import random
import time
import traceback
import urllib.request
import urllib.error
import urllib.parse
import uuid

# ---- Configuration (values baked via Terraform interpolation) ----
DO_TOKEN      = "${var.autoscalerToken}"
MEDIA_TAG     = "${digitalocean_tag.media_node_tag.name}"
DRAINING_TAG  = "${digitalocean_tag.draining_tag.name}"
REGION        = "${var.region}"
SIZE          = "${var.mediaNodeInstanceType}"
VPC_UUID      = "${digitalocean_vpc.openvidu_vpc.id}"
SSH_KEY_ID    = "${digitalocean_ssh_key.openvidu_ssh_key_do.id}"
STACK_NAME    = "${var.stackName}"
MIN_NODES     = int("${var.minNumberOfMediaNodes}")
MAX_NODES     = int("${var.maxNumberOfMediaNodes}")
TARGET_CPU    = float("${var.scaleTargetCPU}")
SCALE_IN_ENABLED = "${var.automaticScaleInEnabled}" == "true"
CAPACITY_ENABLED = "${var.capacityReservationsEnabled}" == "true"
CAPACITY_PROFILE_FINGERPRINT = "${var.capacityProfileFingerprint}"
CAPACITY_BACKEND_URL = base64.b64decode("${base64encode(var.capacityBackendUrl)}").decode().rstrip("/")
CAPACITY_BACKEND_TOKEN = base64.b64decode("${base64encode(var.capacityBackendToken)}").decode()
USER_DATA     = base64.b64decode("${base64encode(local.user_data_media_transport)}").decode()

EXPECTED_CPU_MODES = frozenset({
    "idle", "iowait", "irq", "nice", "softirq", "steal", "system", "user",
})
# I/O wait is not CPU execution. Steal remains capacity pressure because the
# Droplet wanted CPU time that the hypervisor could not provide.
NON_EXECUTING_CPU_MODES = frozenset({"idle", "iowait"})

API = "https://api.digitalocean.com/v2"
HDR = {"Authorization": f"Bearer {DO_TOKEN}", "Content-Type": "application/json"}

# All log lines are collected here and returned in the response body so they
# are visible in the DigitalOcean Functions console (activation result).
_LOGS = []
_DEADLINE = None

def time_left(reserve=0):
    return max(0.0, _DEADLINE - time.monotonic() - reserve) if _DEADLINE is not None else float("inf")

def log(m):
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}] {m}"
    print(line, flush=True)
    _LOGS.append(line)

def apicall(method, path, body=None):
    url = f"{API}{path}" if path.startswith("/") else path
    req = urllib.request.Request(url, headers=HDR, method=method)
    if body is not None:
        req.data = json.dumps(body).encode()
    log(f"  -> {method} {path}")
    if body:
        # Media-node creation carries cloud-init containing runtime credentials.
        # Keep useful request diagnostics without copying those credentials to logs.
        logged_body = dict(body)
        if "user_data" in logged_body:
            logged_body["user_data"] = "[redacted]"
        log(f"     body: {json.dumps(logged_body)}")
    # Only provider reads are replayable. Reserve outcome/alert time within the
    # Function's 120s limit; a timed-out create/tag/delete is never dispatched twice.
    retry_read = method == "GET" and url.startswith(API + "/")
    read_deadline = time.monotonic() + min(12, time_left(20))
    for attempt in range(3 if retry_read else 1):
        timeout = min(4, read_deadline - time.monotonic()) if retry_read else min(60, time_left(20))
        if timeout <= 0:
            log("     <- activation read/mutation budget exhausted; holding")
            return None
        retryable = False
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                d = r.read().decode()
                parsed = json.loads(d) if d.strip() else {}
                log(f"     <- {r.status} OK")
                return parsed
        except urllib.error.HTTPError as e:
            # Status is sufficient for retries; do not spend the remaining read
            # budget fetching an error body (which may also echo cloud-init secrets).
            e.close()
            log(f"     <- HTTP {e.code} ERROR")
            retryable = e.code == 429 or 500 <= e.code <= 599
        except (urllib.error.URLError, TimeoutError) as e:
            reason = getattr(e, "reason", e)
            log(f"     <- URL error: {reason}")
            retryable = isinstance(reason, TimeoutError)
        except Exception as e:
            log(f"     <- unexpected error: {e}")
            log(traceback.format_exc())
            return None
        if not retry_read or not retryable or attempt == 2:
            return None
        delay = random.uniform(0.2, 0.6) * (2 ** attempt)
        if time.monotonic() + delay + 1 > read_deadline:
            return None
        log("     Retrying transient DigitalOcean read")
        time.sleep(delay)

def list_nodes(tag=MEDIA_TAG):
    log("Listing media nodes ...")
    r = apicall("GET", f"/droplets?tag_name={tag}&per_page=200")
    if not isinstance(r, dict):
        raise ReadinessUnavailable("DigitalOcean did not return the media-node inventory")
    nodes = r.get("droplets")
    if not isinstance(nodes, list):
        raise ReadinessUnavailable("DigitalOcean returned an invalid media-node inventory")
    if r.get("links", {}).get("pages", {}).get("next"):
        raise ReadinessUnavailable("Incomplete paginated media-node inventory; holding allocation")
    for d in nodes:
        tags = d.get("tags") if isinstance(d, dict) else None
        if not isinstance(tags, list) or not all(isinstance(tag, str) for tag in tags):
            raise ReadinessUnavailable("DigitalOcean returned invalid media-node tag metadata")
        log(f"  droplet id={d['id']} name={d['name']} status={d['status']} "
            f"region={d.get('region',{}).get('slug','?')} created={d.get('created_at','?')}")
    return nodes

def counter_delta(values, mode, did):
    if not isinstance(values, list) or len(values) < 2:
        log(f"    Missing {mode} CPU samples for {did}")
        return None
    try:
        first = float(values[0][1])
        last = float(values[-1][1])
    except (IndexError, TypeError, ValueError):
        log(f"    Invalid {mode} CPU samples for {did}")
        return None
    if not math.isfinite(first) or not math.isfinite(last):
        log(f"    Non-finite {mode} CPU samples for {did}")
        return None
    delta = last - first
    if delta < 0:
        # DigitalOcean counters can reset after a reboot. A negative interval is
        # not low utilization and must never be used to choose a node to delete.
        log(f"    {mode} CPU counter reset for {did}")
        return None
    return delta

def cpu(did, name):
    now = int(time.time())
    log(f"  Fetching CPU metrics for droplet {did} ({name}) ...")
    r = apicall("GET", f"/monitoring/metrics/droplet/cpu?host_id={did}&start={now - 240}&end={now}")
    if not isinstance(r, dict) or not isinstance(r.get("data"), dict):
        log(f"    CPU metrics request failed for {did}")
        return None
    results = r.get("data", {}).get("result")
    if not isinstance(results, list):
        log(f"    No metrics data for {did}")
        return None

    mode_deltas = {}
    for item in results:
        mode = item.get("metric", {}).get("mode")
        if not isinstance(mode, str) or not mode:
            log(f"    CPU metric without a mode for {did}")
            return None
        delta = counter_delta(item.get("values"), mode, did)
        if delta is None:
            return None
        mode_deltas[mode] = mode_deltas.get(mode, 0.0) + delta

    returned_modes = frozenset(mode_deltas)
    if returned_modes != EXPECTED_CPU_MODES:
        missing = sorted(EXPECTED_CPU_MODES - returned_modes)
        unexpected = sorted(returned_modes - EXPECTED_CPU_MODES)
        log(f"    Unexpected CPU mode set for {did}: missing={missing} unexpected={unexpected}")
        return None

    total_delta = sum(mode_deltas.values())
    if total_delta <= 0:
        log(f"    CPU counters did not advance for {did}")
        return None

    non_executing_delta = sum(mode_deltas[mode] for mode in NON_EXECUTING_CPU_MODES)
    active_delta = total_delta - non_executing_delta
    usage = (active_delta / total_delta) * 100
    log(f"    CPU deltas for {did}: {json.dumps(mode_deltas, sort_keys=True)}")
    log(f"    CPU usage for {did} ({name}): {usage}%")
    return usage

def create_node(name=None, return_receipt=False):
    if len(USER_DATA.encode("utf-8")) > 65536:
        raise RuntimeError("Media startup payload exceeds the 64 KiB user_data limit")
    name = name or f"{STACK_NAME}-media-{int(time.time())}-{random.randint(1000,9999)}"
    log(f"Creating new media node: name={name} region={REGION} size={SIZE} vpc={VPC_UUID}")
    try:
        keys = [int(SSH_KEY_ID)]
    except ValueError:
        keys = [SSH_KEY_ID]
    payload = {
        "name": name, "region": REGION, "size": SIZE,
        "image": "ubuntu-24-04-x64", "vpc_uuid": VPC_UUID,
        "ssh_keys": keys, "tags": [MEDIA_TAG, STACK_NAME] if CAPACITY_ENABLED else [MEDIA_TAG],
        "user_data": USER_DATA, "monitoring": True,
    }
    r = apicall("POST", "/droplets", payload)
    if r and "droplet" in r:
        d = r["droplet"]
        log(f"  Node created: id={d['id']} name={d['name']} status={d['status']}")
        return d if return_receipt else True
    log(f"  Failed to create node {name}")
    return False

def tag_res(did, t):
    log(f"  Tagging droplet {did} with '{t}' ...")
    return apicall(
        "POST",
        f"/tags/{t}/resources",
        {"resources": [{"resource_id": str(did), "resource_type": "droplet"}]},
    ) is not None

def untag_res(did, t):
    log(f"  Removing tag '{t}' from droplet {did} ...")
    return apicall(
        "DELETE",
        f"/tags/{t}/resources",
        {"resources": [{"resource_id": str(did), "resource_type": "droplet"}]},
    ) is not None

def finish(result):
    if CAPACITY_ENABLED:
        codes = {alert["code"] for alert in result.get("alerts", [])}
        provisioning_failed = result.get("error") or result.get("warning", "").startswith("Provision outcome unknown")
        if result.get("readiness_wait"):
            codes.add("READINESS_UNAVAILABLE")
        elif result.get("readiness_verified") and not provisioning_failed:
            codes.add("READINESS_RECOVERED")
        if provisioning_failed:
            codes.add("PROVISIONING_FAILED")
        if result.get("waiting_for_capacity"):
            codes.add("CAPACITY_WAITING")
        # Preserve the urgent family signal before quota/waiting notices can
        # consume the bounded finish budget, especially for an unknown create.
        for code in sorted(codes, key=lambda code: (code not in (
                "PROVISIONING_FAILED", "READINESS_UNAVAILABLE", "READINESS_RECOVERED"), code)):
            try:
                capacity_request("alert", {"stack": STACK_NAME, "code": code,
                                           "observedAt": int(time.time() * 1000)})
            except Exception:
                # Delivery failure is visible and retried next activation, but must not
                # repeat a cloud create or lose a durable provisioning outcome.
                result.setdefault("alert_delivery_failed", []).append(code)
    log("=" * 60)
    result["logs"] = list(_LOGS)
    return {"body": result}

class ReadinessUnavailable(RuntimeError):
    """Known pre-dispatch readiness hold, not a cloud creation failure."""

class NoCapacityRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RuntimeError("Capacity authority redirects are forbidden")

def capacity_request(path, payload):
    parsed = urllib.parse.urlparse(CAPACITY_BACKEND_URL)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username
            or parsed.password or parsed.query or parsed.fragment
            or not CAPACITY_BACKEND_TOKEN or not CAPACITY_PROFILE_FINGERPRINT):
        raise RuntimeError("Capacity authority is not configured")
    request = urllib.request.Request(
        CAPACITY_BACKEND_URL + "/webhooks/openvidu/capacity/" + path,
        data=json.dumps(payload).encode(), method="POST",
        headers={"X-Capacity-Token": CAPACITY_BACKEND_TOKEN, "Content-Type": "application/json"})
    # Never follow a redirect with the dedicated credential, or log the response body on errors.
    try:
        timeout = min(10, time_left())
        if timeout <= 0:
            raise RuntimeError("Capacity request budget exhausted; retain outstanding intent")
        with urllib.request.build_opener(NoCapacityRedirects()).open(request, timeout=timeout) as response:
            body = response.read(65537)
            if len(body) > 65536:
                raise RuntimeError("Capacity response exceeds limit")
            return json.loads(body) if body.strip() else {}
    except urllib.error.HTTPError as error:
        # Only the authority's explicit pre-dispatch 503 is a readiness wait.
        # A timeout, invalid response, or failed outcome receipt stays an error:
        # do not hide an unknown mutation or permit a second cloud creation.
        error.close()
        if error.code == 503 and path in ("claim", "claim-drain"):
            raise ReadinessUnavailable("Capacity readiness unavailable; allocation held") from None
        raise RuntimeError("Capacity authority unavailable; retain outstanding intent") from None
    except Exception:
        raise RuntimeError("Capacity authority unavailable; retain outstanding intent") from None

def account_fleet_limit(allocated, result):
    if MAX_NODES != 0:
        return MAX_NODES
    account = apicall("GET", "/account")
    account_details = account.get("account") if isinstance(account, dict) else None
    quota = account_details.get("droplet_limit") if isinstance(account_details, dict) else None
    if type(quota) is not int or quota < 1:
        raise ReadinessUnavailable("Complete DigitalOcean account quota evidence required")
    inventory = apicall("GET", "/droplets?per_page=1")
    inventory_meta = inventory.get("meta") if isinstance(inventory, dict) else None
    total = inventory_meta.get("total") if isinstance(inventory_meta, dict) else None
    # Account-wide usage includes other stacks and draining Droplets. Never
    # interpret a failed quota lookup as unlimited permission to create machines.
    if type(total) is not int or total < allocated:
        raise ReadinessUnavailable("Complete DigitalOcean account quota evidence required")
    maximum = allocated + max(0, quota - total)
    result["account_quota"] = quota
    result["account_droplets"] = total
    result["effective_media_limit"] = maximum
    if total * 5 >= quota * 4:
        result.setdefault("alerts", []).append({"code": "ACCOUNT_DROPLET_QUOTA_PRESSURE", "used": total, "limit": quota})
        log(f"ALERT: account Droplet quota usage {total}/{quota}")
    return maximum

def reconcile_capacity(allocated, inventory, result, maximum=None):
    maximum = MAX_NODES if maximum is None else maximum
    # Do not consume a durable dispatch grant when insufficient time remains for
    # its one cloud attempt, outcome receipt and alert. This is still pre-dispatch.
    if time_left() < 40:
        raise ReadinessUnavailable("Capacity activation budget low; allocation held")
    if maximum < 1:
        result["waiting_for_capacity"] = True
        result["warning"] = "DigitalOcean account quota has no media-node headroom"
        return finish(result)
    # The backend commits one dispatch grant before returning it. All replays and overlapping
    # activations receive observation-only claims. An unknown create never expires into a retry.
    claim = capacity_request("claim", {
        "profileFingerprint": CAPACITY_PROFILE_FINGERPRINT,
        "nodeType": SIZE,
        "stack": STACK_NAME, "allocatedDropletIds": sorted(str(node["id"]) for node in inventory),
        "maximum": maximum,
        **quota_claim_fields(result),
    })
    if not isinstance(claim, dict) or type(claim.get("createAllowed")) is not bool or claim.get("nodeType") != SIZE:
        raise RuntimeError("Invalid capacity claim")
    result["readiness_verified"] = True
    result["waiting_for_capacity"] = claim.get("waitingForCapacity") is True
    intent = claim.get("intentId")
    name = claim.get("nodeName")
    if intent is None and claim["createAllowed"] is False:
        return reconcile_capacity_drain(inventory, result, maximum)
    try:
        if str(uuid.UUID(intent)) != intent or name != f"{STACK_NAME}-capacity-{intent}":
            raise ValueError()
    except (ValueError, TypeError, AttributeError):
        raise RuntimeError("Invalid provision intent identity")
    matches = [node for node in inventory if node.get("name") == name]
    if len(matches) > 1:
        raise RuntimeError("Duplicate provision outcome; manual reconciliation required")
    receipt = matches[0] if matches else None
    if claim["createAllowed"] and receipt is None:
        if allocated >= maximum:
            raise RuntimeError("Allocation limit reached; retain claim for reconciliation")
        receipt = create_node(name, return_receipt=True)
        result["action"] = "scale-out-capacity" if receipt else "hold"
    if receipt:
        if (not isinstance(receipt, dict) or not str(receipt.get("id", "")).isdigit()
                or receipt.get("name") != name or receipt.get("size_slug") != SIZE):
            raise RuntimeError("Unverified creation receipt; retain intent")
        capacity_request("observed", {"intentId": intent, "dropletId": str(receipt["id"])})
        result["intent_id"] = intent
    else:
        result["warning"] = "Provision outcome unknown; retained intent requires reconciliation"
    return finish(result)

def quota_claim_fields(result):
    if MAX_NODES != 0:
        return {}
    return {"accountDropletQuota": result["account_quota"],
            "accountDropletCount": result["account_droplets"]}

def reconcile_capacity_drain(inventory, result, maximum=None):
    maximum = MAX_NODES if maximum is None else maximum
    if not SCALE_IN_ENABLED:
        result["warning"] = "Capacity mode holds automatic scale-in: switch disabled"
        return finish(result)
    # Inventory includes draining allocations. Retiring a target requires at
    # least MIN_NODES other ready allocations, including for a retained replay.
    if len(inventory) <= MIN_NODES:
        result["warning"] = "Fleet at minimum; no scale-in requested"
        return finish(result)
    # The authority excludes the exact incarnation atomically with reservation checks.
    # This is permission to BEGIN graceful drain, never permission to delete the VM.
    receipt = capacity_request("claim-drain", {
        "profileFingerprint": CAPACITY_PROFILE_FINGERPRINT, "nodeType": SIZE,
        "stack": STACK_NAME, "allocatedDropletIds": sorted(str(node["id"]) for node in inventory),
        "minimum": MIN_NODES, "maximum": maximum,
        **quota_claim_fields(result),
    })
    if receipt == {}:
        result["warning"] = "No idle capacity drain authorized"
        return finish(result)
    if (not isinstance(receipt, dict) or receipt.get("applicationExcluded") is not True
            or receipt.get("applicationObligationsClear") is not False
            or not isinstance(receipt.get("nodeId"), str) or not receipt["nodeId"]
            or not isinstance(receipt.get("generation"), str) or not receipt["generation"]
            or not isinstance(receipt.get("dropletId"), str)):
        raise RuntimeError("Invalid capacity drain receipt")
    matches = [node for node in inventory if str(node["id"]) == receipt["dropletId"]]
    if (len(matches) != 1 or matches[0].get("size_slug") != SIZE
            or matches[0].get("region", {}).get("slug") != REGION
            or matches[0].get("vpc_uuid") != VPC_UUID
            or matches[0].get("status") != "active"):
        raise RuntimeError("Capacity drain target is outside current fleet")
    target = matches[0]
    # A failed tag delivery retains backend exclusion. The next invocation retries
    # this same node; it must not undo the exclusion or choose a replacement target.
    if DRAINING_TAG not in target["tags"] and not tag_res(target["id"], DRAINING_TAG):
        raise RuntimeError("Capacity drain tag unconfirmed; application exclusion retained")
    result["action"] = "scale-in-capacity"
    result["drained_node"] = {"id": target["id"], "name": target["name"]}
    if MEDIA_TAG in target["tags"] and not untag_res(target["id"], MEDIA_TAG):
        result["warning"] = "Drain delivered; active tag removal unconfirmed"
    return finish(result)

def main(args):
    """DO Functions entry point — invoked every 4 minutes by scheduled trigger."""
    # Function containers are reused. Keep each activation response bounded to
    # this invocation instead of accumulating diagnostics from earlier runs.
    global _DEADLINE
    _DEADLINE = time.monotonic() + 115
    _LOGS.clear()
    log("=" * 60)
    log(f"Autoscaler invoked | stack={STACK_NAME} region={REGION}")
    log(f"Config: min={MIN_NODES} max={MAX_NODES} target_cpu={TARGET_CPU}%")
    log(f"Tags: media='{MEDIA_TAG}' draining='{DRAINING_TAG}'")
    log("=" * 60)

    result = {
        "action": "hold",
        "nodes": None,
        "draining_nodes": None,
        "avg_cpu": None,
    }

    if isinstance(args, dict) and "capacity" in args:
        result["error"] = "Push capacity floors are unsupported; use the authoritative claim workflow"
        return finish(result)

    try:
        tagged_nodes = list_nodes()
        # A failed active-tag removal can leave a node with both lifecycle tags while its
        # on-node watcher is already draining it. It is no longer usable capacity and must
        # never mask the configured floor or become a scale-in candidate on the next run.
        # Include draining-only VMs: their active tag may already be removed,
        # but readiness/finalization can legitimately defer deletion. Ignoring
        # these machines would permit unlimited replacement provisioning.
        drain_inventory = list_nodes(DRAINING_TAG)
        draining_by_id = {d['id']: d for d in tagged_nodes + drain_inventory
                          if DRAINING_TAG in d['tags']}
        draining_nodes = list(draining_by_id.values())
        nodes = [d for d in tagged_nodes if d['id'] not in draining_by_id]
        n = len(nodes)
        allocated = len({d['id'] for d in tagged_nodes + drain_inventory})
        result['allocated_nodes'] = allocated
        result["nodes"] = n
        result["draining_nodes"] = len(draining_nodes)
        log(
            f"Non-draining VMs (not a readiness measurement): {n}; "
            f"draining VMs: {len(draining_nodes)}; allocated VMs: {allocated}"
        )

        if CAPACITY_ENABLED:
            # Includes minimum recovery: capacity mode never bypasses durable claims using CPU
            # or MIN_NODES, and never selects a reserved node for automatic scale-in.
            maximum = account_fleet_limit(allocated, result)
            return reconcile_capacity(allocated, list({d['id']: d for d in tagged_nodes + drain_inventory}.values()), result, maximum)

        if MAX_NODES == 0:
            raise RuntimeError("Account-quota scaling requires authoritative capacity mode")

        if n < MIN_NODES:
            if allocated >= MAX_NODES:
                result['error'] = 'Ready-capacity recovery is waiting for the allocated-node limit'
                return finish(result)
            log(f"DECISION: scale-out-min (have {n}, need {MIN_NODES})")
            created = create_node()
            result["action"] = "scale-out-min" if created else "hold"
            result["created"] = created
            if not created:
                result["error"] = "DigitalOcean did not confirm media-node creation"
            return finish(result)

        # Gather CPU for all nodes
        log("Gathering CPU metrics ...")
        cmap = {}  # id -> (usage, name)
        for d in nodes:
            usage = cpu(d["id"], d["name"])
            if usage is not None:
                cmap[d["id"]] = (usage, d["name"])
            else:
                log(f"  Missing CPU data for {d['id']} ({d['name']})")

        result["nodes_with_metrics"] = len(cmap)
        if len(cmap) != n:
            # Missing metrics commonly means a node is still booting or the
            # monitoring API is degraded. Neither state is evidence to add or
            # remove capacity, so wait for a complete sample on the next run.
            raise ReadinessUnavailable(f"CPU metrics available for only {len(cmap)}/{n} media nodes")

        avg = sum(v for v, _ in cmap.values()) / len(cmap)
        result["avg_cpu"] = round(avg, 2)
        log(f"Average CPU across {len(cmap)}/{n} nodes: {avg:.2f}%")
        for did, (usage, name) in sorted(cmap.items(), key=lambda x: x[1][0], reverse=True):
            log(f"  {did} ({name}): {usage}%")

        # Scale out
        if avg > TARGET_CPU and allocated < MAX_NODES:
            log(f"DECISION: scale-out (avg={avg:.2f}% > target={TARGET_CPU}%, allocated={allocated} < max={MAX_NODES})")
            created = create_node()
            result["action"] = "scale-out" if created else "hold"
            result["created"] = created
            if not created:
                result["error"] = "DigitalOcean did not confirm media-node creation"
            return finish(result)

        if avg > TARGET_CPU and allocated >= MAX_NODES:
            log(f"DECISION: hold (avg={avg:.2f}% > target but already at max={MAX_NODES})")

        # Scale-out remains usable while recording-safe scale-in is qualified.
        # Lowering MAX_NODES is not authority to remove an occupied server either.
        # This switch prevents new automatic drains; it does not cancel a drain
        # already accepted by the provider or stop an existing on-node watcher.
        if not SCALE_IN_ENABLED:
            result["warning"] = "Automatic scale-in disabled; existing drains require explicit reconciliation"
            return finish(result)

        # Scale in
        # Keep a dead band between scale-out and scale-in so a cluster near the
        # target does not repeatedly add and drain nodes on consecutive runs.
        thr = TARGET_CPU * 0.7
        log(f"Scale-in threshold: {thr:.2f}%")
        do_in = (avg < thr and n > MIN_NODES) or (n > MAX_NODES)

        if do_in and draining_nodes:
            draining_ids = sorted(str(node["id"]) for node in draining_nodes)
            result["warning"] = (
                "Scale-in deferred while nodes remain draining: "
                + ", ".join(draining_ids)
            )
            log(f"DECISION: hold ({result['warning']})")
        elif do_in:
            log(f"DECISION: scale-in (avg={avg:.2f}% < thr={thr:.2f}% or n={n} > max={MAX_NODES})")
            # Pick the node with lowest CPU usage
            tid = min(cmap, key=lambda x: cmap[x][0])
            tname = cmap[tid][1]
            tcpu = cmap[tid][0]
            log(f"  Selected node to drain: {tid} ({tname}) CPU={tcpu}%")
            # Add the draining tag first. Its firewall coverage and on-node
            # watcher are the safety net even if removing the active tag fails.
            if not tag_res(tid, DRAINING_TAG):
                result["error"] = f"Could not mark media node {tid} as draining"
                log(f"DECISION: hold ({result['error']})")
            else:
                result["action"] = "scale-in"
                result["drained_node"] = {"id": tid, "name": tname, "cpu": tcpu}
                if not untag_res(tid, MEDIA_TAG):
                    result["warning"] = (
                        f"Media node {tid} is draining but still has its active tag; "
                        "the node watcher will retry self-deletion"
                    )
                    log(f"WARNING: {result['warning']}")
        else:
            log(f"DECISION: hold (avg={avg:.2f}% within range, nodes={n} within min/max)")

    except ReadinessUnavailable as e:
        result["readiness_wait"] = True
        result["warning"] = str(e)
        log("DECISION: hold until fresh capacity evidence is available")
    except Exception as e:
        log(f"UNHANDLED EXCEPTION: {e}")
        log(traceback.format_exc())
        result["error"] = str(e)

    return finish(result)
PYEOF

  tag_watcher_script_media = <<-EOF
#!/bin/bash
DRAINING_TAG="${digitalocean_tag.draining_tag.name}"
${local.capacity_watcher_lock}${local.capacity_node_reports}SELF_TAGS=$(curl -sf ${var.capacityReservationsEnabled ? "--connect-timeout 2 --max-time 3 " : ""}http://169.254.169.254/metadata/v1/tags 2>/dev/null || echo "")

if echo "$SELF_TAGS" | grep -qw "$DRAINING_TAG"; then
  echo "$(date): Draining tag detected. Initiating graceful shutdown."
  # Keep the cron entry until deletion succeeds. flock prevents concurrent
  # drains while allowing a later cron run to retry a failed self-delete.
  nohup flock -n /var/lock/openvidu-media-drain.lock \
    /usr/local/bin/graceful_shutdown.sh >> /var/log/graceful_shutdown.log 2>&1${var.capacityReservationsEnabled ? " 8>&-" : ""} &
fi
EOF

  user_data_master = <<-EOF
#!/bin/bash
set -eu -o pipefail
umask 077

# restart.sh
cat > /usr/local/bin/restart.sh << 'RESTART_EOF'
${local.restart_script_master}
RESTART_EOF
  chmod 700 /usr/local/bin/restart.sh

# Check if installation already completed
if [ -f /usr/local/bin/openvidu_install_counter.txt ]; then
  # Launch on reboot
  /usr/local/bin/restart.sh || { echo "[OpenVidu] error restarting OpenVidu"; exit 1; }
else
  # install.sh
  cat > /usr/local/bin/install.sh << 'INSTALL_EOF'
${local.install_script_master}
INSTALL_EOF
  chmod 700 /usr/local/bin/install.sh

  # after_install.sh
  cat > /usr/local/bin/after_install.sh << 'AFTER_INSTALL_EOF'
${local.after_install_script_master}
AFTER_INSTALL_EOF
  chmod 700 /usr/local/bin/after_install.sh

  # update_config_from_secret.sh
  cat > /usr/local/bin/update_config_from_secret.sh << 'UPDATE_CONFIG_EOF'
${local.update_config_from_secret_script_master}
UPDATE_CONFIG_EOF
  chmod 700 /usr/local/bin/update_config_from_secret.sh

  # update_secret_from_config.sh
  cat > /usr/local/bin/update_secret_from_config.sh << 'UPDATE_SECRET_EOF'
${local.update_secret_from_config_script_master}
UPDATE_SECRET_EOF
  chmod 700 /usr/local/bin/update_secret_from_config.sh

  # get_value_from_config.sh
  cat > /usr/local/bin/get_value_from_config.sh << 'GET_VALUE_EOF'
${local.get_value_from_config_script_master}
GET_VALUE_EOF
  chmod 700 /usr/local/bin/get_value_from_config.sh

  # store_secret.sh
  cat > /usr/local/bin/store_secret.sh << 'STORE_SECRET_EOF'
${local.store_secret_script_master}
STORE_SECRET_EOF
  chmod 700 /usr/local/bin/store_secret.sh

  # check_app_ready.sh
  cat > /usr/local/bin/check_app_ready.sh << 'CHECK_APP_EOF'
${local.check_app_ready_script_master}
CHECK_APP_EOF
  chmod 700 /usr/local/bin/check_app_ready.sh

  # config_s3.sh
  cat > /usr/local/bin/config_s3.sh << 'CONFIG_S3_EOF'
${local.config_s3_script_master}
CONFIG_S3_EOF
  chmod 700 /usr/local/bin/config_s3.sh

  echo "DPkg::Lock::Timeout \"-1\";" > /etc/apt/apt.conf.d/99timeout
  ${local.fresh_apt_prepare}apt-get --no-download install -y \
  curl \
  unzip \
  jq \
  ca-certificates \
  gnupg \
  lsb-release \
  openssl

  AWS_CLI_VERSION=2.35.5
  AWS_CLI_SHA256=54b7006cbaf125eca01f72f93010b15c2f819c82e8bc8ea6834ce853f87dc9e7
  [ "$(uname -m)" = "x86_64" ] || { echo "Unsupported AWS CLI architecture"; exit 1; }
  # Install aws-cli
  curl -fsSL "https://awscli.amazonaws.com/awscli-exe-linux-x86_64-$${AWS_CLI_VERSION}.zip" -o "awscliv2.zip"
  printf '%s  %s\n' "$AWS_CLI_SHA256" awscliv2.zip | sha256sum --check --status || {
    echo "AWS CLI checksum verification failed"
    exit 1
  }
  unzip -qq awscliv2.zip
  ./aws/install
  rm -rf awscliv2.zip aws

  DOCTL_VERSION=1.162.0
  DOCTL_SHA256=338ad0796fb7a7e20f2e833d88d6daa40d5d6372b39ca54d327e212ff20bc236
  # Install doctl
  cd ~
  curl -fsSL \
    https://github.com/digitalocean/doctl/releases/download/v$${DOCTL_VERSION}/doctl-$${DOCTL_VERSION}-linux-amd64.tar.gz \
    -o doctl-$${DOCTL_VERSION}-linux-amd64.tar.gz
  printf '%s  %s\n' "$DOCTL_SHA256" doctl-$${DOCTL_VERSION}-linux-amd64.tar.gz \
    | sha256sum --check --status || {
      echo "doctl checksum verification failed"
      exit 1
    }
  tar xf ~/doctl-$${DOCTL_VERSION}-linux-amd64.tar.gz
  mv ~/doctl /usr/local/bin
  rm -f ~/doctl-$${DOCTL_VERSION}-linux-amd64.tar.gz

  export HOME="/root"

  # Terraform attaches the reserved IP and updates Route53 after the Droplet starts.
  # Wait before requesting a Let's Encrypt certificate instead of racing those resources.
  if [ "${var.certificateType}" = "letsencrypt" ] && [ -n "${var.domainName}" ]; then
    DNS_READY=false
    for ATTEMPT in $(seq 1 120); do
      PUBLIC_IP=$(curl -fsS http://169.254.169.254/metadata/v1/floating_ip/ipv4/ip_address || true)
      RESOLVED_IP=$(getent ahostsv4 "${var.domainName}" 2>/dev/null \
        | awk 'NR == 1 { print $1 }' || true)
      if [ -n "$PUBLIC_IP" ] && [ "$RESOLVED_IP" = "$PUBLIC_IP" ]; then
        DNS_READY=true
        break
      fi
      echo "Waiting for ${var.domainName} to resolve to the attached reserved IP ($ATTEMPT/120)"
      sleep 5
    done
    if [ "$DNS_READY" != "true" ]; then
      echo "Route53 did not converge before the OpenVidu certificate installation deadline"
      exit 1
    fi
  fi

  export AWS_ACCESS_KEY_ID="${digitalocean_spaces_key.openvidu_space_key.access_key}"
  export AWS_SECRET_ACCESS_KEY="${digitalocean_spaces_key.openvidu_space_key.secret_key}"
  export AWS_DEFAULT_REGION="${var.spaceRegion}"
  
  # The vendor enables systemd during installation. A reboot before Redis
  # preparation must not start an unprotected datastore via that separate path.
  # Install this before the vendor can enable its unit; it also covers retries.
  install -d -m 755 /etc/systemd/system/openvidu.service.d
  printf '[Unit]\nConditionPathExists=/opt/openvidu/.courseultra-redis-prepared\n' > /etc/systemd/system/openvidu.service.d/courseultra-redis.conf
  chmod 644 /etc/systemd/system/openvidu.service.d/courseultra-redis.conf

  ${local.recorder_guard_barrier}# Install OpenVidu
  /usr/local/bin/install.sh || { echo "[OpenVidu] error installing OpenVidu"; exit 1; }
  
  # Config S3 bucket
  /usr/local/bin/config_s3.sh || { echo "[OpenVidu] error configuring S3 bucket"; exit 1; }

  # Start OpenVidu
  # Fresh initialization only: existing containers/data require the separately
  # reviewed migration. Never mount an empty directory over recording history.
  printf '%s' '${filebase64("${path.module}/prepare-fresh-redis.py")}' | base64 --decode > /usr/local/bin/prepare-fresh-redis.py
  printf '%s' '${filebase64("${path.module}/redis-durability.override.yaml")}' | base64 --decode > /usr/local/share/courseultra-redis.override.yaml
  chmod 600 /usr/local/bin/prepare-fresh-redis.py /usr/local/share/courseultra-redis.override.yaml
  python3 /usr/local/bin/prepare-fresh-redis.py || { echo "[OpenVidu] fresh Redis setup refused"; exit 1; }
  install -m 600 /dev/null /opt/openvidu/.courseultra-redis-prepared
  ${local.recorder_guard_prepare_master}systemctl daemon-reload
  systemctl start openvidu || { echo "[OpenVidu] error starting OpenVidu"; exit 1; }

  # Update shared secrets
  /usr/local/bin/after_install.sh || { echo "[OpenVidu] error updating shared secrets"; exit 1; }

  # restart.sh on reboot
  echo "@reboot /usr/local/bin/restart.sh >> /var/log/openvidu-restart.log 2>&1" | crontab

  # Mark installation as complete
  echo "installation_complete" > /usr/local/bin/openvidu_install_counter.txt
fi

${local.capacity_master_watcher_install}# Wait for the app
/usr/local/bin/check_app_ready.sh
EOF

  # ----- media -----

  install_script_media = <<-EOF
#!/bin/bash
set -e
umask 077

# Install dependencies
echo "DPkg::Lock::Timeout \"-1\";" > /etc/apt/apt.conf.d/99timeout

apt-get update && apt-get install -y

# Get secret from s3 bucket with active wait
export AWS_ACCESS_KEY_ID="${digitalocean_spaces_key.openvidu_space_key.access_key}"
export AWS_SECRET_ACCESS_KEY="${digitalocean_spaces_key.openvidu_space_key.secret_key}"
export AWS_DEFAULT_REGION="${var.spaceRegion}"
EXPECTED_MASTER_NODE_PRIVATE_IP="${digitalocean_droplet.openvidu_master_node.ipv4_address_private}"
EXPECTED_MASTER_NODE_ID="${digitalocean_droplet.openvidu_master_node.id}"
mkdir -p /opt/openvidu

# A master replacement leaves the previous secrets.env in Spaces until the new
# master finishes bootstrapping. Private addresses can be reused, so the
# immutable Droplet ID is the generation guard while the IP remains a topology
# check. Wait for both rather than accepting any existing object.
MAX_RETRIES=200
RETRY_COUNT=0
SECRETS_READY=false
while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
  if aws s3 cp \
    s3://${var.spaceName == "" ? digitalocean_spaces_bucket.openvidu_space[0].name : var.spaceName}/secrets.env \
    /opt/openvidu/secrets.env \
    --endpoint-url=https://${var.spaceRegion}.digitaloceanspaces.com \
    --region=${var.spaceRegion}; then
    chmod 600 /opt/openvidu/secrets.env
    DOWNLOADED_MASTER_NODE_PRIVATE_IP=$(sed -n \
      's/^MASTER_NODE_PRIVATE_IP=//p' /opt/openvidu/secrets.env | tail -1)
    DOWNLOADED_MASTER_NODE_ID=$(sed -n \
      's/^MASTER_NODE_ID=//p' /opt/openvidu/secrets.env | tail -1)
    if [ "$DOWNLOADED_MASTER_NODE_ID" = "$EXPECTED_MASTER_NODE_ID" ] \
      && [ "$DOWNLOADED_MASTER_NODE_PRIVATE_IP" = "$EXPECTED_MASTER_NODE_PRIVATE_IP" ]; then
      echo "Retrieved secrets.env for the current master"
      SECRETS_READY=true
      break
    fi
    echo "Retrieved stale secrets.env; waiting for the replacement master"
  fi

  RETRY_COUNT=$((RETRY_COUNT + 1))
  echo "Waiting for current secrets.env... Attempt $RETRY_COUNT/$MAX_RETRIES"
  sleep 10
done

if [ "$SECRETS_READY" != "true" ]; then
  echo "Failed to retrieve secrets.env for the current master after $MAX_RETRIES attempts"
  exit 1
fi

# Get IPs using DO metadata
PRIVATE_IP=$(curl -s http://169.254.169.254/metadata/v1/interfaces/private/0/ipv4/address)
MASTER_NODE_PRIVATE_IP="$EXPECTED_MASTER_NODE_PRIVATE_IP"

# Get all necessary values from secrets
DOMAIN=$(grep '^DOMAIN_NAME=' /opt/openvidu/secrets.env | cut -d'=' -f2)
REDIS_PASSWORD=$(grep '^REDIS_PASSWORD=' /opt/openvidu/secrets.env | cut -d'=' -f2)
OPENVIDU_VERSION=$(grep '^OPENVIDU_VERSION=' /opt/openvidu/secrets.env | cut -d'=' -f2)
OPENVIDU_PRO_LICENSE=$(grep '^OPENVIDU_PRO_LICENSE=' /opt/openvidu/secrets.env | cut -d'=' -f2)

# Match the master bootstrap's transport and integrity guarantees. A changed
# upstream artifact must be reviewed and repinned rather than executed silently.
if [ "$OPENVIDU_VERSION" != "${local.openvidu_installer_release.version}" ]; then
  echo "OpenVidu shared version does not match the reviewed installer release; update and review deployment code before provisioning media nodes" >&2
  exit 1
fi
INSTALL_SCRIPT=/tmp/install_ov_media_node.sh
INSTALL_SCRIPT_URL="https://s3-eu-west-1.amazonaws.com/get.openvidu.io/pro/elastic/$OPENVIDU_VERSION/install_ov_media_node.sh"
INSTALL_SCRIPT_SHA256="${local.openvidu_installer_release.media_sha256}"
curl -fsSL "$INSTALL_SCRIPT_URL" -o "$INSTALL_SCRIPT"
printf '%s  %s\n' "$INSTALL_SCRIPT_SHA256" "$INSTALL_SCRIPT" | sha256sum --check --status || {
  echo "OpenVidu media installer checksum verification failed"
  exit 1
}
INSTALL_COMMAND="sh $INSTALL_SCRIPT"

# The pinned installer preserves this standard Compose override. Install it
# before the first service start so newly scaled nodes never expose the low
# inherited mediasoup socket limit. Do not overwrite an operator's override.
NOFILE_OVERRIDE=/opt/openvidu/docker-compose.override.yaml
NOFILE_EXPECTED=$(mktemp)
printf '%s' '${filebase64("${path.module}/media-nofile.override.yaml")}' | base64 --decode > "$NOFILE_EXPECTED"
if [ -e "$NOFILE_OVERRIDE" ] && ! cmp -s "$NOFILE_EXPECTED" "$NOFILE_OVERRIDE"; then
  echo "Unexpected Compose override; refusing to replace operator configuration"
  exit 1
fi
install -m 644 "$NOFILE_EXPECTED" "$NOFILE_OVERRIDE"
rm -f "$NOFILE_EXPECTED"

# Media node arguments
COMMON_ARGS=(
  "--no-tty"
  "--install"
  "--environment=digitalocean"
  "--deployment-type=elastic"
  "--node-role=media-node"
  "--master-node-private-ip=$MASTER_NODE_PRIVATE_IP"
  "--private-ip=$PRIVATE_IP"
  "--redis-password=$REDIS_PASSWORD"
)

# Construct the final command
FINAL_COMMAND="$INSTALL_COMMAND $(printf "%s " "$${COMMON_ARGS[@]}")"

# Execute installation
set +e
MAX_RETRIES=5
RETRY_COUNT=1

until bash -c "$FINAL_COMMAND"; do
  echo "Install command failed (attempt $RETRY_COUNT/$MAX_RETRIES)"
  if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
    echo "Install command failed after $MAX_RETRIES attempts"
    exit 1
  fi
  RETRY_COUNT=$((RETRY_COUNT + 1))
  sleep 10
done
EOF

  graceful_shutdown_script_media = <<-EOF
#!/bin/bash
set -euo pipefail

verify_ready_floor() {
  /usr/local/bin/courseultra-media-drain-guard \
    --master-id '${digitalocean_droplet.openvidu_master_node.id}' \
    --master-ip '${digitalocean_droplet.openvidu_master_node.ipv4_address_private}' \
    --vpc '${digitalocean_vpc.openvidu_vpc.id}' \
    --minimum '${var.minNumberOfMediaNodes}' \
    --active-tag '${digitalocean_tag.media_node_tag.name}' \
    --draining-tag '${digitalocean_tag.draining_tag.name}' ${var.capacityReservationsEnabled ? "--capacity-settings /etc/courseultra-capacity-drain.json " : ""}"$@"
}

# A lifecycle tag requests drain; it does not prove replacement readiness.
# Reserve spare ready capacity atomically before any service receives SIGQUIT.
verify_ready_floor --require-idle-media --fence-restarts
# Restart exclusion can take time; recheck serving peers before signaling work.
verify_ready_floor --verify-restart-fence
command -v docker >/dev/null || { echo "Docker state unavailable; holding drain"; exit 1; }

echo "Starting graceful shutdown of OpenVidu Media Node..."

# Execute if docker is installed
if [ -x "$(command -v docker)" ]; then

  echo "Stopping media node services and waiting for termination..."
  # A second signal can force a busy media server to exit. The guard persists
  # one request per exact container/process; watcher retries only observe it.
  verify_ready_floor --signal-graceful

  # Bound one watcher attempt without treating elapsed time as permission to
  # delete a node that still owns live media. The cron watcher retries later.
  DRAIN_DEADLINE=$(( $(date +%s) + 600 ))
  while true; do
    RUNNING_CONTAINERS=$(docker ps --format '{{.Names}}')
    AGENT_CONTAINERS=$(docker ps --filter "label=openvidu-agent=true" -q)
    if [ -z "$AGENT_CONTAINERS" ] && \
       ! printf '%s\n' "$RUNNING_CONTAINERS" | grep -Eq '^(openvidu|ingress|egress)$'; then
      break
    fi
    if [ "$(date +%s)" -ge "$DRAIN_DEADLINE" ]; then
      echo "Media is still active after 10 minutes; leaving the node draining for a later retry"
      exit 1
    fi
    echo "Waiting for containers to stop..."
    sleep 10
  done
fi

# An absent running process is not proof of graceful completion: an OOM kill,
# failed container or missing container can leave recording output unfinished.
# Preserve the VM for recovery in those cases. Clean exit is necessary, not a
# substitute for provider recording-finalization verification.
AGENT_CONTAINERS=$(docker ps -a --filter "label=openvidu-agent=true" --format '{{.Names}}')
for media_container in openvidu ingress egress $AGENT_CONTAINERS; do
  EXIT_STATE=$(docker inspect --format '{{.State.Status}} {{.State.ExitCode}} {{.State.OOMKilled}}' "$media_container")
  if [ "$EXIT_STATE" != "exited 0 false" ]; then
    echo "Drain held: $media_container did not exit cleanly; preserve the node for recovery"
    exit 1
  fi
done

# A long class may have outlived the replacement checked at drain start.
# Clean exits alone do not prove uploaded output or empty recovery storage.
# This additional veto preserves retained artifacts; it is not a substitute for
# provider finalization/idle-only admission fencing before enabling scale-in.
verify_ready_floor --verify-recording-storage --verify-restart-fence

# Self-delete using doctl

# Get droplet ID from metadata
DROPLET_ID=$(curl -fsS http://169.254.169.254/metadata/v1/id)

# Delete this instance using doctl
doctl compute droplet delete "$DROPLET_ID" --force

echo "Graceful shutdown completed."
EOF

  # Capacity transport omits comments and blank lines from pure shell script bodies;
  # command bytes and shebangs are checked. The frozen recorder guard stays exact.
  user_data_media = <<-EOF
#!/bin/bash
set -eu -o pipefail
umask 077

# install.sh (media node)
cat > /usr/local/bin/install.sh << 'INSTALL_MEDIA_EOF'
${var.capacityReservationsEnabled ? replace(local.install_script_media, "/(?m)^[ \\t]*(#[^!\\n][^\\n]*)?\\n/", "") : local.install_script_media}
INSTALL_MEDIA_EOF
chmod 700 /usr/local/bin/install.sh

# graceful_shutdown.sh
cat > /usr/local/bin/graceful_shutdown.sh << 'GRACEFUL_SHUTDOWN_EOF'
${var.capacityReservationsEnabled ? replace(local.graceful_shutdown_script_media, "/(?m)^[ \\t]*(#[^!\\n][^\\n]*)?\\n/", "") : local.graceful_shutdown_script_media}
GRACEFUL_SHUTDOWN_EOF
chmod 700 /usr/local/bin/graceful_shutdown.sh

cat > /usr/local/bin/courseultra-media-drain-guard << 'MEDIA_DRAIN_GUARD_EOF'
${var.capacityReservationsEnabled ? local.capacity_python_sources["media_drain_guard.py"] : file("${path.module}/media_drain_guard.py")}
MEDIA_DRAIN_GUARD_EOF
chmod 700 /usr/local/bin/courseultra-media-drain-guard

${local.capacity_media_drain_settings}# tag_watcher.sh (detects draining tag and triggers graceful shutdown)
cat > /usr/local/bin/tag_watcher.sh << 'TAG_WATCHER_EOF'
${var.capacityReservationsEnabled ? replace(local.tag_watcher_script_media, "/(?m)^[ \\t]*(#[^!\\n][^\\n]*)?\\n/", "") : local.tag_watcher_script_media}
TAG_WATCHER_EOF
chmod 700 /usr/local/bin/tag_watcher.sh

echo "DPkg::Lock::Timeout \"-1\";" > /etc/apt/apt.conf.d/99timeout
${local.fresh_apt_prepare}apt-get --no-download install -y \
  curl \
  unzip \
  jq \
  ca-certificates \
  gnupg \
  lsb-release \
  openssl

AWS_CLI_VERSION=2.35.5
AWS_CLI_SHA256=54b7006cbaf125eca01f72f93010b15c2f819c82e8bc8ea6834ce853f87dc9e7
[ "$(uname -m)" = "x86_64" ] || { echo "Unsupported AWS CLI architecture"; exit 1; }
# Install aws-cli
curl -fsSL "https://awscli.amazonaws.com/awscli-exe-linux-x86_64-$${AWS_CLI_VERSION}.zip" -o "awscliv2.zip"
printf '%s  %s\n' "$AWS_CLI_SHA256" awscliv2.zip | sha256sum --check --status || {
  echo "AWS CLI checksum verification failed"
  exit 1
}
unzip -qq awscliv2.zip
./aws/install
rm -rf awscliv2.zip aws

DOCTL_VERSION=1.162.0
DOCTL_SHA256=338ad0796fb7a7e20f2e833d88d6daa40d5d6372b39ca54d327e212ff20bc236
# Install doctl
cd ~
curl -fsSL \
  https://github.com/digitalocean/doctl/releases/download/v$${DOCTL_VERSION}/doctl-$${DOCTL_VERSION}-linux-amd64.tar.gz \
  -o doctl-$${DOCTL_VERSION}-linux-amd64.tar.gz
printf '%s  %s\n' "$DOCTL_SHA256" doctl-$${DOCTL_VERSION}-linux-amd64.tar.gz \
  | sha256sum --check --status || {
    echo "doctl checksum verification failed"
    exit 1
  }
tar xf ~/doctl-$${DOCTL_VERSION}-linux-amd64.tar.gz
mv ~/doctl /usr/local/bin
rm -f ~/doctl-$${DOCTL_VERSION}-linux-amd64.tar.gz

export HOME="/root"

doctl auth init -t "${var.autoscalerToken}"

# Install OpenVidu Media Node
mkdir -p /etc/systemd/system/openvidu.service.d
cat > /etc/systemd/system/openvidu.service.d/40-courseultra-drain.conf << 'MEDIA_DRAIN_BARRIER_EOF'
${chomp(file("${path.module}/media-drain-start-barrier.conf"))}
MEDIA_DRAIN_BARRIER_EOF
chmod 644 /etc/systemd/system/openvidu.service.d/40-courseultra-drain.conf
systemctl daemon-reload
${local.recorder_guard_barrier}/usr/local/bin/install.sh || { echo "[OpenVidu] error installing OpenVidu Media Node"; exit 1; }
${local.recorder_guard_prepare_media}
${local.capacity_fresh_arm}# Mark installation as complete
echo "installation_complete" > /usr/local/bin/openvidu_install_counter.txt

# Start OpenVidu
systemctl start openvidu || { echo "[OpenVidu] error starting OpenVidu"; exit 1; }

# Tag watcher cron: check every two minutes if this node should be drained
if [ "${var.fixedNumberOfMediaNodes}" -eq 0 ]; then
echo "*/2 * * * * root /usr/local/bin/tag_watcher.sh >> /var/log/tag_watcher.log 2>&1" > /etc/cron.d/tag-watcher
chmod 644 /etc/cron.d/tag-watcher
fi${local.capacity_fast_watcher_cron}
EOF
}
