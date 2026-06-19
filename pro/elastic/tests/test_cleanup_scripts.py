import os
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path


ELASTIC_DIR = Path(__file__).resolve().parents[1]
TERRAFORM_FILE = ELASTIC_DIR / "tf-do-openvidu-elastic.tf"


def cleanup_script(resource_name):
    terraform = TERRAFORM_FILE.read_text()
    resource = terraform.split(f'resource "null_resource" "{resource_name}"', 1)[1]
    resource = resource.split("\nresource ", 1)[0]
    script = resource.split("command = <<-EOT\n")[-1].split("\n    EOT", 1)[0]
    return (
        textwrap.dedent(script)
        .replace("$${", "${")
        .replace("%%{", "%{")
        .replace("${self.triggers.media_tag}", "active-media")
        .replace("${self.triggers.draining_tag}", "draining-media")
        .replace("${self.triggers.stack_name}", "test-stack")
    )


class CleanupScriptsTest(unittest.TestCase):
    def run_cleanup(
        self,
        resource_name,
        token_name,
        provider_failure=False,
        malformed_response=False,
        null_namespace_inventory=False,
    ):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        bin_dir = root / "bin"
        bin_dir.mkdir()
        curl_log = root / "curl.log"

        fake_curl = bin_dir / "curl"
        fake_curl.write_text(
            textwrap.dedent(
                """\
                #!/usr/bin/env python3
                import json
                import os
                import pathlib
                import sys

                args = sys.argv[1:]
                expected = f"Authorization: Bearer {os.environ['TEST_EXPECTED_TOKEN']}"
                if expected not in args:
                    raise SystemExit("cleanup did not use the current wrapper token")
                with pathlib.Path(os.environ["TEST_CURL_LOG"]).open("a") as log:
                    log.write(" ".join(args) + "\\n")
                if os.environ.get("TEST_PROVIDER_FAILURE") == "1":
                    raise SystemExit(22)
                url = args[-1]
                method = args[args.index("-X") + 1] if "-X" in args else "GET"
                if "droplets?tag_name=" in url and method == "GET":
                    payload = {} if os.environ.get("TEST_MALFORMED_RESPONSE") == "1" else {"droplets": []}
                    print(json.dumps(payload))
                elif url.endswith("/functions/namespaces") and method == "GET":
                    payload = (
                        {"namespaces": [{"label": "test-stack-autoscaler"}]}
                        if os.environ.get("TEST_MALFORMED_RESPONSE") == "1"
                        else {"namespaces": None}
                        if os.environ.get("TEST_NULL_NAMESPACE_INVENTORY") == "1"
                        else {"namespaces": []}
                    )
                    print(json.dumps(payload))
                """
            )
        )
        fake_curl.chmod(0o700)

        fake_sleep = bin_dir / "sleep"
        fake_sleep.write_text(
            textwrap.dedent(
                """\
                #!/usr/bin/env sh
                printf 'sleep %s\n' "$1" >> "$TEST_CURL_LOG"
                """
            )
        )
        fake_sleep.chmod(0o700)

        env = os.environ.copy()
        env.update(
            {
                "PATH": f"{bin_dir}:{env['PATH']}",
                token_name: "rotated-token",
                "TEST_EXPECTED_TOKEN": "rotated-token",
                "TEST_CURL_LOG": str(curl_log),
                "TEST_PROVIDER_FAILURE": "1" if provider_failure else "0",
                "TEST_MALFORMED_RESPONSE": "1" if malformed_response else "0",
                "TEST_NULL_NAMESPACE_INVENTORY": (
                    "1" if null_namespace_inventory else "0"
                ),
            }
        )
        result = subprocess.run(
            ["bash", "-c", cleanup_script(resource_name)],
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        return result, curl_log

    def test_media_cleanup_uses_rotated_token_and_verifies_absence(self):
        result, curl_log = self.run_cleanup(
            "cleanup_media_nodes", "COURSEULTRA_DO_AUTOSCALER_TOKEN"
        )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("Verified removal", result.stdout)
        events = curl_log.read_text().splitlines()
        self.assertEqual("sleep 130", events[0])
        self.assertTrue(any("Bearer rotated-token" in event for event in events[1:]))

    def test_functions_cleanup_uses_current_provisioning_token(self):
        result, curl_log = self.run_cleanup(
            "deploy_autoscaler_function", "COURSEULTRA_DO_PROVISIONING_TOKEN"
        )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("nothing to destroy", result.stdout)
        self.assertIn("Bearer rotated-token", curl_log.read_text())

    def test_functions_cleanup_accepts_provider_null_for_empty_inventory(self):
        result, _ = self.run_cleanup(
            "deploy_autoscaler_function",
            "COURSEULTRA_DO_PROVISIONING_TOKEN",
            null_namespace_inventory=True,
        )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("nothing to destroy", result.stdout)

    def test_cleanup_fails_closed_on_provider_error(self):
        for resource_name, token_name in (
            ("cleanup_media_nodes", "COURSEULTRA_DO_AUTOSCALER_TOKEN"),
            ("deploy_autoscaler_function", "COURSEULTRA_DO_PROVISIONING_TOKEN"),
        ):
            with self.subTest(resource_name=resource_name):
                result, _ = self.run_cleanup(
                    resource_name, token_name, provider_failure=True
                )
                self.assertNotEqual(0, result.returncode)

    def test_cleanup_fails_closed_on_malformed_success_response(self):
        for resource_name, token_name in (
            ("cleanup_media_nodes", "COURSEULTRA_DO_AUTOSCALER_TOKEN"),
            ("deploy_autoscaler_function", "COURSEULTRA_DO_PROVISIONING_TOKEN"),
        ):
            with self.subTest(resource_name=resource_name):
                result, _ = self.run_cleanup(
                    resource_name, token_name, malformed_response=True
                )
                self.assertNotEqual(0, result.returncode)


if __name__ == "__main__":
    unittest.main()
