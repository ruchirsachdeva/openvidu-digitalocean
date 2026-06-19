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
                    cat >/dev/null
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


if __name__ == "__main__":
    unittest.main()
