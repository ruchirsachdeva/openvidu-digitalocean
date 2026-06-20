import os
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path


ELASTIC_DIR = Path(__file__).resolve().parents[1]
SCRIPT = ELASTIC_DIR / "persist-openvidu-candidate.sh"


class PersistOpenViduCandidateTest(unittest.TestCase):
    def test_reused_private_ip_does_not_publish_stale_credentials(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            attempts = root / "attempts"
            aws_log = root / "aws.log"

            wrapper = root / "terraform-wrapper"
            wrapper.write_text(
                textwrap.dedent(
                    """\
                    #!/usr/bin/env sh
                    case "$3" in
                      space_name) printf 'test-space' ;;
                      space_region) printf 'test-region' ;;
                      master_private_ip) printf '10.10.20.8' ;;
                      master_droplet_id) printf '202' ;;
                      spaces_access_id) printf 'test-access' ;;
                      spaces_secret_key) printf 'test-secret' ;;
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
                    #!/usr/bin/env python3
                    import os
                    import pathlib
                    import sys

                    args = sys.argv[1:]
                    if args[:2] == ["s3", "cp"]:
                        state = pathlib.Path(os.environ["TEST_ATTEMPTS"])
                        attempt = int(state.read_text()) + 1 if state.exists() else 1
                        state.write_text(str(attempt))
                        master_id = "101" if attempt == 1 else "202"
                        secret = "stale-secret" if attempt == 1 else "current-secret"
                        pathlib.Path(args[3]).write_text(
                            "OPENVIDU_URL=https://openvidu.example.com/\\n"
                            f"LIVEKIT_API_SECRET={secret}\\n"
                            "MASTER_NODE_PRIVATE_IP=10.10.20.8\\n"
                            f"MASTER_NODE_ID={master_id}\\n"
                        )
                    elif args and args[0] == "ssm":
                        with pathlib.Path(os.environ["TEST_AWS_LOG"]).open("a") as log:
                            log.write(" ".join(args) + "\\n")
                    else:
                        raise SystemExit(f"unexpected aws arguments: {args}")
                    """
                )
            )
            fake_aws.chmod(0o700)

            fake_sleep = bin_dir / "sleep"
            fake_sleep.write_text("#!/usr/bin/env sh\nexit 0\n")
            fake_sleep.chmod(0o700)

            env = os.environ.copy()
            env.update(
                {
                    "PATH": f"{bin_dir}:{env['PATH']}",
                    "TERRAFORM_WRAPPER": str(wrapper),
                    "TEST_ATTEMPTS": str(attempts),
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
            self.assertEqual("2", attempts.read_text())
            calls = aws_log.read_text()
            self.assertIn("current-secret", calls)
            self.assertNotIn("stale-secret", calls)
            self.assertIn("/test/openvidu/blr/url", calls)
            self.assertIn("/test/openvidu/blr/elastic-url", calls)
            self.assertIn("/test/openvidu/blr/username", calls)
            self.assertIn("/test/openvidu/blr/secret", calls)
            self.assertNotIn("/beinghealer/prod/openvidu/digitalocean/", calls)

    def test_rejects_malformed_candidate_prefix_before_reading_outputs(self):
        with tempfile.TemporaryDirectory() as directory:
            wrapper = Path(directory) / "terraform-wrapper"
            wrapper.write_text("#!/usr/bin/env sh\nexit 99\n")
            wrapper.chmod(0o700)

            env = os.environ.copy()
            env.update(
                {
                    "TERRAFORM_WRAPPER": str(wrapper),
                    "COURSEULTRA_OPENVIDU_SSM_PREFIX": "/test/openvidu/",
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
