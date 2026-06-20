import os
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path


ELASTIC_DIR = Path(__file__).resolve().parents[1]
SCRIPT = ELASTIC_DIR / "courseultra-terraform.sh"


class TerraformWrapperTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.bin_dir = self.root / "bin"
        self.bin_dir.mkdir()
        self.command_log = self.root / "commands.log"

        commands = {
            "terraform": """\
                #!/usr/bin/env sh
                printf 'terraform %s\\n' "$*" >> "$TEST_COMMAND_LOG"
                printf '%s|%s|%s|%s|%s\\n' \\
                  "${TF_VAR_doToken:-}" \\
                  "${TF_VAR_autoscalerToken:-}" \\
                  "${TF_VAR_openviduLicense:-}" \\
                  "${TF_VAR_spacesAccessId:-}" \\
                  "${TF_VAR_spacesSecretKey:-}" >> "$TEST_COMMAND_LOG"
                env | sed -n '/^TF_LOG/p' | sort >> "$TEST_COMMAND_LOG"
            """,
            "security": """\
                #!/usr/bin/env sh
                printf 'security %s\\n' "$*" >> "$TEST_COMMAND_LOG"
                [ "${FAIL_CREDENTIAL_SOURCE:-}" != "security" ] || exit 42
                [ "${EMPTY_CREDENTIAL_SOURCE:-}" != "security" ] || exit 0
                case "$*" in
                  *courseultra-do-terraform-token*) printf 'provisioning-token' ;;
                  *courseultra-do-spaces-access-id*) printf 'spaces-access' ;;
                  *courseultra-do-spaces-secret-key*) printf 'spaces-secret' ;;
                  *courseultra-do-blr-bootstrap-access-id*) printf 'blr-spaces-access' ;;
                  *courseultra-do-blr-bootstrap-secret-key*) printf 'blr-spaces-secret' ;;
                  *) exit 1 ;;
                esac
            """,
            "aws": """\
                #!/usr/bin/env sh
                printf 'aws %s\\n' "$*" >> "$TEST_COMMAND_LOG"
                [ "${FAIL_CREDENTIAL_SOURCE:-}" != "aws" ] || exit 42
                [ "${EMPTY_CREDENTIAL_SOURCE:-}" != "aws" ] || exit 0
                case "$*" in
                  */digitalocean/autoscaler-token*) printf 'autoscaler-token' ;;
                  */openvidu/pro-license*) printf 'openvidu-license' ;;
                  *) exit 1 ;;
                esac
            """,
        }
        for name, source in commands.items():
            command = self.bin_dir / name
            command.write_text(textwrap.dedent(source))
            command.chmod(0o700)

        self.env = os.environ.copy()
        self.env.update(
            {
                "PATH": f"{self.bin_dir}:{self.env['PATH']}",
                "TEST_COMMAND_LOG": str(self.command_log),
                "TF_VAR_doToken": "inherited-provisioning-token",
                "TF_VAR_autoscalerToken": "inherited-autoscaler-token",
                "TF_VAR_openviduLicense": "inherited-license",
                "TF_VAR_spacesAccessId": "inherited-spaces-access",
                "TF_VAR_spacesSecretKey": "inherited-spaces-secret",
                "TF_LOG": "TRACE",
                "TF_LOG_PATH": str(self.root / "terraform.log"),
                "TF_LOG_PROVIDER": "TRACE",
                "TF_LOG_SDK": "TRACE",
                "TF_LOG_FUTURE_PROVIDER_CHANNEL": "TRACE",
            }
        )

    def run_wrapper(self, *arguments):
        return subprocess.run(
            [str(SCRIPT), *arguments],
            env=self.env,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_output_does_not_load_temporary_credentials(self):
        result = self.run_wrapper("output", "-raw", "master_public_ip")

        self.assertEqual(0, result.returncode, result.stderr)
        calls = self.command_log.read_text().splitlines()
        self.assertEqual("terraform output -raw master_public_ip", calls[0])
        self.assertEqual("||||", calls[1])
        self.assertFalse(any(call.startswith("security ") for call in calls))
        self.assertFalse(any(call.startswith("aws ") for call in calls))
        self.assertFalse(any(call.startswith("TF_LOG") for call in calls))

    def test_plan_still_loads_all_required_credentials(self):
        result = self.run_wrapper("plan", "-input=false")

        self.assertEqual(0, result.returncode, result.stderr)
        calls = self.command_log.read_text().splitlines()
        self.assertEqual(3, sum(call.startswith("security ") for call in calls))
        self.assertEqual(2, sum(call.startswith("aws ") for call in calls))
        self.assertIn("terraform plan -input=false", calls)
        self.assertIn(
            "provisioning-token|autoscaler-token|openvidu-license|"
            "spaces-access|spaces-secret",
            calls,
        )
        self.assertFalse(any(call.startswith("TF_LOG") for call in calls))

    def test_plan_can_use_isolated_spaces_keychain_services(self):
        self.env["COURSEULTRA_SPACES_ACCESS_ID_KEYCHAIN_SERVICE"] = (
            "courseultra-do-blr-bootstrap-access-id"
        )
        self.env["COURSEULTRA_SPACES_SECRET_KEY_KEYCHAIN_SERVICE"] = (
            "courseultra-do-blr-bootstrap-secret-key"
        )

        result = self.run_wrapper("plan", "-input=false")

        self.assertEqual(0, result.returncode, result.stderr)
        calls = self.command_log.read_text().splitlines()
        self.assertTrue(
            any("courseultra-do-blr-bootstrap-access-id" in call for call in calls)
        )
        self.assertTrue(
            any("courseultra-do-blr-bootstrap-secret-key" in call for call in calls)
        )
        self.assertIn(
            "provisioning-token|autoscaler-token|openvidu-license|"
            "blr-spaces-access|blr-spaces-secret",
            calls,
        )

    def test_plan_never_runs_when_a_credential_lookup_fails(self):
        for source in ("security", "aws"):
            with self.subTest(source=source):
                self.command_log.unlink(missing_ok=True)
                self.env["FAIL_CREDENTIAL_SOURCE"] = source

                result = self.run_wrapper("plan", "-input=false")

                self.assertNotEqual(0, result.returncode)
                calls = self.command_log.read_text().splitlines()
                self.assertFalse(any(call.startswith("terraform ") for call in calls))
                self.env.pop("FAIL_CREDENTIAL_SOURCE")

    def test_plan_never_runs_with_an_empty_credential(self):
        for source in ("security", "aws"):
            with self.subTest(source=source):
                self.command_log.unlink(missing_ok=True)
                self.env["EMPTY_CREDENTIAL_SOURCE"] = source

                result = self.run_wrapper("plan", "-input=false")

                self.assertNotEqual(0, result.returncode)
                self.assertIn("Required credential is empty", result.stderr)
                calls = self.command_log.read_text().splitlines()
                self.assertFalse(any(call.startswith("terraform ") for call in calls))
                self.env.pop("EMPTY_CREDENTIAL_SOURCE")


if __name__ == "__main__":
    unittest.main()
