import unittest
from pathlib import Path


ELASTIC_DIR = Path(__file__).resolve().parents[1]
TERRAFORM = (ELASTIC_DIR / "tf-do-openvidu-elastic.tf").read_text()
WRAPPER = (ELASTIC_DIR / "courseultra-terraform.sh").read_text()
OUTPUTS = (ELASTIC_DIR / "outputs.tf").read_text()
PERSIST_CANDIDATE = (ELASTIC_DIR / "persist-openvidu-candidate.sh").read_text()


class TerraformSafetyContractTest(unittest.TestCase):
    def test_root_executed_downloads_are_tls_and_checksum_pinned(self):
        self.assertNotIn("http://get.openvidu.io", TERRAFORM)
        for checksum in (
            "fdaebc7a729110049dafbdd9de7bf8bcfe2a687c86f22c54d87c0601413cb9e8",
            "69c15c9ab72de6cb9c49dfecb547be952deacd35dfcd22cc4e26c162693da28b",
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
        self.assertEqual(12, TERRAFORM.count("chmod 700 /usr/local/bin"))
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
