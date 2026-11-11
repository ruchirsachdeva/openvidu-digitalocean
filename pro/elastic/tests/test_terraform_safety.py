import unittest
import base64
import json
import shutil
import subprocess
import tempfile
import os
import sys
from pathlib import Path


ELASTIC_DIR = Path(__file__).resolve().parents[1]
TERRAFORM = (ELASTIC_DIR / "tf-do-openvidu-elastic.tf").read_text()
WRAPPER = (ELASTIC_DIR / "courseultra-terraform.sh").read_text()
OUTPUTS = (ELASTIC_DIR / "outputs.tf").read_text()
PERSIST_CANDIDATE = (ELASTIC_DIR / "persist-openvidu-candidate.sh").read_text()


class TerraformSafetyContractTest(unittest.TestCase):
    def test_capacity_recorder_listener_is_inherited_and_idempotent(self):
        marker = 'if [ "${var.capacityReservationsEnabled}" = "true" ]; then'
        block = marker + TERRAFORM.split(marker, 1)[1].split('\n# OpenVidu\'s external S3', 1)[0]
        block = block.replace('$${', '${')
        # The generated bootstrap runs on Linux. BSD sed needs an explicit empty
        # backup suffix to exercise the same in-place edit in the local Mac test.
        if sys.platform == 'darwin': block = block.replace('sed -i ', "sed -i '' ")
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory) / 'media_node'; folder.mkdir()
            template = folder / 'egress.yaml'
            original = 'health_port: ${openvidu.HEALTH:?mandatory}\nbackup:\n  prefix: /retained\n'
            def run(enabled):
                return subprocess.run(['bash', '-eu', '-c', block.replace('${var.capacityReservationsEnabled}', enabled)],
                    env={**os.environ, 'CLUSTER_CONFIG_DIR':directory}, capture_output=True, timeout=5)
            template.write_text(original)
            self.assertEqual(0, run('false').returncode)
            self.assertEqual(original, template.read_text())
            self.assertEqual(0, run('true').returncode)
            expected = original.replace('\nbackup:', '\nio_workers: 1\nprometheus_port: 9094\nbackup:')
            self.assertEqual(expected, template.read_text())
            self.assertEqual(0, run('true').returncode)
            self.assertEqual(expected, template.read_text())
            template.write_text(expected.replace('9094', '9999'))
            self.assertNotEqual(0, run('true').returncode)

    @unittest.skipUnless(shutil.which('terraform'), 'Terraform required for offline descriptor expression test')
    def test_fleet_descriptor_binds_created_vpc_and_region_without_changing_approved_profile(self):
        line = next(line for line in TERRAFORM.splitlines() if '${jsonencode(merge(jsondecode(var.capacityFleetDescriptorJson)' in line)
        expression = line.split('${', 1)[1].split('}\\nCOURSEULTRA_SETTINGS_EOF', 1)[0]
        self.assertIn('vpcId = digitalocean_vpc.openvidu_vpc.id', expression)
        self.assertIn('region = var.region', expression)
        self.assertNotIn('digitalocean_droplet', expression)
        descriptor = dict(vpcId='not-known-before-creation', region='obsolete-region',
                          operatingProfile=dict(profile=dict(fingerprint='explicit-test-only', qualified=False)),
                          recorderPolicySha256='a' * 64, startupGuardSha256='b' * 64)
        actual_id = '12345678-1234-1234-1234-123456789abc'
        expression = expression.replace('var.capacityFleetDescriptorJson', json.dumps(json.dumps(descriptor)))
        expression = expression.replace('digitalocean_vpc.openvidu_vpc.id', json.dumps(actual_id))
        expression = expression.replace('var.region', json.dumps('blr1'))
        # Evaluate the real HCL expression offline with synthetic resource outputs;
        # no provider initialization, plan, credentials or cloud requests.
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(['terraform', 'console', '-no-color'], input=expression + '\n',
                                    text=True, capture_output=True, cwd=directory, check=True, timeout=20)
        decoded = json.loads(json.loads(result.stdout))
        self.assertEqual(dict(descriptor, vpcId=actual_id, region='blr1'), decoded)
        vpc = TERRAFORM.split('resource "digitalocean_vpc" "openvidu_vpc"', 1)[1].split('\n}', 1)[0]
        self.assertNotIn('local.', vpc)
        self.assertNotIn('digitalocean_droplet', vpc)

    def test_code_update_and_namespace_teardown_have_separate_lifecycles(self):
        deployment = TERRAFORM.split('resource "null_resource" "deploy_autoscaler_function"', 1)[1].split('\nresource ', 1)[0]
        lifecycle = TERRAFORM.split('resource "null_resource" "autoscaler_lifecycle"', 1)[1].split('\nresource ', 1)[0]
        self.assertIn('code_hash = sha256(local.autoscaler_function_code)', deployment)
        self.assertNotIn('when    = destroy', deployment)
        self.assertIn('null_resource.autoscaler_lifecycle', deployment)
        self.assertIn('when    = destroy', lifecycle)
        self.assertNotIn('code_hash', lifecycle.split('triggers = {', 1)[1])
        self.assertIn('null_resource.cleanup_media_nodes', lifecycle)

    def test_root_executed_downloads_are_tls_and_checksum_pinned(self):
        self.assertNotIn("http://get.openvidu.io", TERRAFORM)
        for checksum in (
            "feae2e1b9fff75edb3c087d7263ce58b553d5f51193046e9359fb0875856d7f2",
            "8d79aa04f303ef5ace2abda8233960480441591cb130fd48460770f071d41c71",
            "54b7006cbaf125eca01f72f93010b15c2f819c82e8bc8ea6834ce853f87dc9e7",
            "338ad0796fb7a7e20f2e833d88d6daa40d5d6372b39ca54d327e212ff20bc236",
        ):
            self.assertIn(checksum, TERRAFORM)

    def test_draining_nodes_keep_both_firewall_assignments(self):
        assignment = (
            "tags = [digitalocean_tag.media_node_tag.name, "
            "digitalocean_tag.draining_tag.name]"
        )
        self.assertEqual(2, TERRAFORM.count(assignment))

    def test_destroy_cleanup_uses_current_wrapper_credentials(self):
        self.assertIn("COURSEULTRA_DO_PROVISIONING_TOKEN", TERRAFORM)
        self.assertIn("COURSEULTRA_DO_AUTOSCALER_TOKEN", TERRAFORM)
        self.assertIn("COURSEULTRA_DO_PROVISIONING_TOKEN", WRAPPER)
        self.assertIn("COURSEULTRA_DO_AUTOSCALER_TOKEN", WRAPPER)
        self.assertEqual(2, TERRAFORM.count('ignore_changes = [triggers["do_token"]]'))

    def test_autoscaler_is_destroyed_before_dynamic_media_cleanup(self):
        self.assertIn(
            "depends_on = [\n    null_resource.cleanup_media_nodes,", TERRAFORM
        )

    def test_ssh_validation_rejects_world_open_prefixes(self):
        variables = (ELASTIC_DIR / "variables.tf").read_text()
        self.assertIn('tonumber(split("/", cidr)[1]) > 0', variables)

    def test_master_generation_guard_uses_immutable_droplet_id(self):
        self.assertIn(
            "MASTER_NODE_ID=$(curl -fsS http://169.254.169.254/metadata/v1/id)",
            TERRAFORM,
        )
        self.assertIn("save MASTER_NODE_ID", TERRAFORM)
        self.assertIn(
            'EXPECTED_MASTER_NODE_ID="${digitalocean_droplet.openvidu_master_node.id}"',
            TERRAFORM,
        )
        self.assertIn('output "master_droplet_id"', OUTPUTS)
        self.assertIn("output -raw master_droplet_id", PERSIST_CANDIDATE)

    def test_generated_secret_material_is_root_only(self):
        self.assertNotIn("chmod +x /usr/local/bin", TERRAFORM)
        # Both role-specific drain-helper paths retain root-only permissions.
        self.assertIn('chmod 700 /usr/local/bin/${name}', TERRAFORM)
        common = TERRAFORM.split('capacity_drain_settings =', 1)[1].split('capacity_media_drain_settings', 1)[0]
        self.assertNotIn('"report-recording-locations.py"', common)
        media = TERRAFORM.split('capacity_media_drain_settings', 1)[1].split('capacity_master_drain_settings', 1)[0]
        self.assertIn('"report-recording-locations.py"', media)
        self.assertIn('chmod 700 /usr/local/bin/${name}', TERRAFORM)
        self.assertIn('"settle-recordings.py", "recorder-storage-probe.py"', TERRAFORM)
        self.assertEqual(2, TERRAFORM.count("chmod 600 /opt/openvidu/secrets.env"))
        self.assertIn('chmod 600 "$SECRETS_FILE"', TERRAFORM)

        credential_scripts = (
            "install_script_master",
            "config_s3_script_master",
            "after_install_script_master",
            "update_config_from_secret_script_master",
            "update_secret_from_config_script_master",
            "store_secret_script_master",
            "user_data_master",
            "install_script_media",
            "user_data_media",
        )
        for script_name in credential_scripts:
            with self.subTest(script_name=script_name):
                script = TERRAFORM.split(f"{script_name} = <<-EOF", 1)[1].split(
                    "\nEOF", 1
                )[0]
                self.assertIn("umask 077", script)


if __name__ == "__main__":
    unittest.main()
