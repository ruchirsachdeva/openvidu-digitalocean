import base64
import os
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path


ELASTIC_DIR = Path(__file__).resolve().parents[1]
SCRIPT = ELASTIC_DIR / "configure-courseultra-webhook.sh"


class WebhookHostKeyTest(unittest.TestCase):
    def test_remote_secret_update_uses_restrictive_umask(self):
        script = SCRIPT.read_text()

        self.assertIn("REMOTE_SCRIPT'\nset -euo pipefail\numask 077", script)
        self.assertIn("if not path.is_file():", script)

    def test_explicit_refresh_uses_dedicated_known_hosts_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            known_hosts = root / "courseultra.known_hosts"
            key_path = root / "courseultra.pem"
            key_path.write_text("test-key")
            key_path.chmod(0o600)
            ssh_log = root / "ssh.log"
            ssh_stdin_log = root / "ssh-stdin.log"
            keygen_log = root / "ssh-keygen.log"

            wrapper = root / "terraform-wrapper"
            wrapper.write_text(
                "#!/usr/bin/env sh\nprintf '188.166.197.209'\n"
            )
            wrapper.chmod(0o700)

            commands = {
                "aws": """\
                    #!/usr/bin/env sh
                    printf 'test-webhook-token'
                """,
                "ssh-keygen": """\
                    #!/usr/bin/env sh
                    printf '%s\n' "$*" > "$TEST_KEYGEN_LOG"
                """,
                "ssh": """\
                    #!/usr/bin/env sh
                    printf '%s\n' "$*" > "$TEST_SSH_LOG"
                    cat > "$TEST_SSH_STDIN_LOG"
                """,
            }
            for name, source in commands.items():
                command = bin_dir / name
                command.write_text(textwrap.dedent(source))
                command.chmod(0o700)

            env = os.environ.copy()
            env.update(
                {
                    "PATH": f"{bin_dir}:{env['PATH']}",
                    "TERRAFORM_WRAPPER": str(wrapper),
                    "COURSEULTRA_KNOWN_HOSTS_PATH": str(known_hosts),
                    "TEST_KEYGEN_LOG": str(keygen_log),
                    "TEST_SSH_LOG": str(ssh_log),
                    "TEST_SSH_STDIN_LOG": str(ssh_stdin_log),
                    "COURSEULTRA_WEBHOOK_ENDPOINT": "https://acceptance.example.test/webhooks/openvidu",
                }
            )
            result = subprocess.run(
                [str(SCRIPT), str(key_path), "--refresh-host-key"],
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual(
                f"-R 188.166.197.209 -f {known_hosts}", keygen_log.read_text().strip()
            )
            ssh_arguments = ssh_log.read_text()
            self.assertIn("StrictHostKeyChecking=accept-new", ssh_arguments)
            self.assertIn(f"UserKnownHostsFile={known_hosts}", ssh_arguments)
            self.assertEqual(0o600, known_hosts.stat().st_mode & 0o777)
            remote_input = ssh_stdin_log.read_text().splitlines()
            self.assertEqual("test-webhook-token", base64.b64decode(remote_input[0]).decode())
            self.assertEqual(
                "https://acceptance.example.test/webhooks/openvidu",
                base64.b64decode(remote_input[1]).decode(),
            )
            self.assertIn(
                '"V2COMPAT_OPENVIDU_WEBHOOK_ENDPOINT": endpoint',
                ssh_stdin_log.read_text(),
            )

    def test_rejects_non_https_endpoint_before_remote_access(self):
        with tempfile.TemporaryDirectory() as directory:
            key_path = Path(directory) / "courseultra.pem"
            key_path.write_text("test-key")
            env = os.environ.copy()
            env["COURSEULTRA_WEBHOOK_ENDPOINT"] = "http://localhost/webhooks/openvidu"

            result = subprocess.run(
                [str(SCRIPT), str(key_path)],
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(2, result.returncode)
            self.assertIn("must be a single HTTPS URL", result.stderr)


if __name__ == "__main__":
    unittest.main()
