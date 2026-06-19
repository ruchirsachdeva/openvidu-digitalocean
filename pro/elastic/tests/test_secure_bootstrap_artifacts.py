import os
import stat
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path


ELASTIC_DIR = Path(__file__).resolve().parents[1]
SCRIPT = ELASTIC_DIR / "secure-bootstrap-artifacts.sh"


class SecureBootstrapArtifactsTest(unittest.TestCase):
    def test_refreshes_key_and_is_idempotent_when_legacy_object_is_absent(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            key_path = root / "openvidu.pem"
            key_path.write_text("stale-key")
            key_path.chmod(0o644)
            legacy_state = root / "legacy-object"
            legacy_state.write_text("present")

            wrapper = root / "terraform-wrapper"
            wrapper.write_text(
                textwrap.dedent(
                    """\
                    #!/usr/bin/env python3
                    import os
                    import sys

                    outputs = {
                        "ssh_private_key_openssh": os.environ["TEST_PRIVATE_KEY"],
                        "space_name": "test-space",
                        "space_region": "test-region",
                        "spaces_access_id": "test-access",
                        "spaces_secret_key": "test-secret",
                    }
                    print(outputs[sys.argv[-1]], end="")
                    """
                )
            )
            wrapper.chmod(0o700)

            fake_aws = bin_dir / "aws"
            fake_aws.write_text(
                textwrap.dedent(
                    """\
                    #!/usr/bin/env python3
                    import json
                    import os
                    import pathlib
                    import sys

                    state = pathlib.Path(os.environ["TEST_LEGACY_STATE"])
                    args = sys.argv[1:]
                    if args[:2] == ["s3api", "list-objects-v2"]:
                        payload = {"Contents": [{"Key": "openvidu_ssh_key_elastic.pem"}]} if state.exists() else {}
                        print(json.dumps(payload))
                    elif args[:2] == ["s3", "rm"]:
                        state.unlink(missing_ok=True)
                    else:
                        raise SystemExit(f"unexpected aws arguments: {args}")
                    """
                )
            )
            fake_aws.chmod(0o700)

            env = os.environ.copy()
            env.update(
                {
                    "PATH": f"{bin_dir}:{env['PATH']}",
                    "TERRAFORM_WRAPPER": str(wrapper),
                    "TEST_PRIVATE_KEY": (
                        "-----BEGIN OPENSSH PRIVATE KEY-----\n"
                        "test-key\n"
                        "-----END OPENSSH PRIVATE KEY-----\n"
                    ),
                    "TEST_LEGACY_STATE": str(legacy_state),
                }
            )

            first = subprocess.run(
                [str(SCRIPT), str(key_path)],
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, first.returncode, first.stderr)
            self.assertIn("test-key", key_path.read_text())
            self.assertEqual(0o600, stat.S_IMODE(key_path.stat().st_mode))
            self.assertFalse(legacy_state.exists())

            second = subprocess.run(
                [str(SCRIPT), str(key_path)],
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, second.returncode, second.stderr)
            self.assertIn("test-key", key_path.read_text())
            self.assertIn("no bootstrap copy remains", second.stdout)


if __name__ == "__main__":
    unittest.main()
