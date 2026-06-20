import os
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path


ELASTIC_DIR = Path(__file__).resolve().parents[1]
SCRIPT = ELASTIC_DIR / "persist-runtime-secrets.sh"


class PersistRuntimeSecretsTest(unittest.TestCase):
    def test_writes_spaces_credentials_only_to_selected_candidate_prefix(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            aws_log = root / "aws.log"

            wrapper = root / "terraform-wrapper"
            wrapper.write_text(
                textwrap.dedent(
                    """\
                    #!/usr/bin/env sh
                    case "$3" in
                      spaces_access_id) printf 'candidate-access' ;;
                      spaces_secret_key) printf 'candidate-secret' ;;
                      *) exit 1 ;;
                    esac
                    """
                )
            )
            wrapper.chmod(0o700)

            fake_aws = bin_dir / "aws"
            fake_aws.write_text(
                textwrap.dedent(
                    """\
                    #!/usr/bin/env sh
                    printf '%s\n' "$*" >> "$TEST_AWS_LOG"
                    """
                )
            )
            fake_aws.chmod(0o700)

            env = os.environ.copy()
            env.update(
                {
                    "PATH": f"{bin_dir}:{env['PATH']}",
                    "TERRAFORM_WRAPPER": str(wrapper),
                    "TEST_AWS_LOG": str(aws_log),
                    "COURSEULTRA_OPENVIDU_SSM_PREFIX": "/test/openvidu/blr",
                }
            )

            result = subprocess.run(
                [str(SCRIPT)],
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            calls = aws_log.read_text()
            self.assertIn("/test/openvidu/blr/spaces-access-id", calls)
            self.assertIn("/test/openvidu/blr/spaces-secret-key", calls)
            self.assertNotIn("/beinghealer/prod/openvidu/digitalocean/", calls)

    def test_rejects_malformed_candidate_prefix_before_reading_secrets(self):
        for prefix in ("relative/path", "/test//openvidu", "/test/openvidu/"):
            with self.subTest(prefix=prefix), tempfile.TemporaryDirectory() as directory:
                wrapper = Path(directory) / "terraform-wrapper"
                wrapper.write_text("#!/usr/bin/env sh\nexit 99\n")
                wrapper.chmod(0o700)

                env = os.environ.copy()
                env.update(
                    {
                        "TERRAFORM_WRAPPER": str(wrapper),
                        "COURSEULTRA_OPENVIDU_SSM_PREFIX": prefix,
                    }
                )
                result = subprocess.run(
                    [str(SCRIPT)],
                    env=env,
                    text=True,
                    capture_output=True,
                    check=False,
                )

                self.assertEqual(2, result.returncode)
                self.assertIn("COURSEULTRA_OPENVIDU_SSM_PREFIX", result.stderr)


if __name__ == "__main__":
    unittest.main()
