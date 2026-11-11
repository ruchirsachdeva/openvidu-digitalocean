"""Exercise the real lifecycle condition with Terraform's local built-in resource.

No provider, credentials, backend or cloud resources are used. The master output
is unknown during plan, as a provider's computed private IP is on initial create.
"""
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ELASTIC = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which("terraform"), "Terraform is required for lifecycle checks")
class MasterTopologyTest(unittest.TestCase):
    def apply_topology(self, private_ip):
        source = (ELASTIC / "tf-do-openvidu-elastic.tf").read_text()
        master = source.split('resource "digitalocean_droplet" "openvidu_master_node" {', 1)[1].split('\nresource ', 1)[0]
        match = re.search(r"  lifecycle \{.*?\n  \}", master, re.S)
        lifecycle = match.group(0) if match else ""
        lifecycle = lifecycle.replace("self.ipv4_address_private", "self.output.ipv4_address_private")
        with tempfile.TemporaryDirectory(prefix="cu-master-topology-") as directory:
            root = Path(directory)
            (root / "main.tf").write_text('''
variable "private_ip" { type = string }
locals { user_data_master_transport = "synthetic-small-startup" }
resource "terraform_data" "master" {
  input = { ipv4_address_private = var.private_ip }
''' + lifecycle + '''
}
resource "terraform_data" "media" {
  input = terraform_data.master.output.ipv4_address_private
}
resource "terraform_data" "autoscaler_template" {
  input = terraform_data.master.output.ipv4_address_private
}
''')
            (root / "test.tfvars.json").write_text(json.dumps({"private_ip": private_ip}))
            env = {key: value for key, value in os.environ.items() if not key.startswith("TF_")}
            env.update(TF_DATA_DIR=str(root / ".terraform"), TF_IN_AUTOMATION="1")
            def run(*args):
                return subprocess.run(["terraform", *args], cwd=root, env=env,
                                      text=True, capture_output=True, timeout=40)
            init = run("init", "-backend=false", "-input=false", "-no-color")
            self.assertEqual(0, init.returncode, init.stderr)
            result = run("apply", "-auto-approve", "-input=false", "-no-color", "-var-file=test.tfvars.json")
            state = run("show", "-json")
            self.assertEqual(0, state.returncode, state.stderr)
            resources = json.loads(state.stdout).get("values", {}).get("root_module", {}).get("resources", [])
            return result, {item["address"] for item in resources}

    def test_incomplete_or_invalid_provider_ip_blocks_all_consumers(self):
        for value in ("", None, " ", "not-an-ip", "10.10.40.999", "::1"):
            with self.subTest(private_ip=value):
                result, resources = self.apply_topology(value)
                self.assertNotEqual(0, result.returncode, "Invalid topology created dependent resources")
                self.assertIn("Master private IPv4 is unavailable", result.stderr)
                self.assertNotIn("terraform_data.media", resources)
                self.assertNotIn("terraform_data.autoscaler_template", resources)
                # Failure is not rollback: preserve the successfully created master
                # for reconciliation instead of pretending nothing was provisioned.
                self.assertIn("terraform_data.master", resources)

    def test_valid_computed_ip_allows_existing_consumers(self):
        result, resources = self.apply_topology("10.10.40.2")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual({"terraform_data.master", "terraform_data.media", "terraform_data.autoscaler_template"}, resources)


if __name__ == "__main__":
    unittest.main()
