import os
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path


ELASTIC_DIR = Path(__file__).resolve().parents[1]
SCRIPT = ELASTIC_DIR / "drain-courseultra-media-nodes.sh"


class DrainMediaNodesTest(unittest.TestCase):
    def run_script(self, provider_failure=False, malformed_response=False):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        bin_dir = root / "bin"
        bin_dir.mkdir()
        ids_file = root / "media-node-ids"
        ids_file.write_text("101\n202\n")
        event_log = root / "events.log"
        drain_state = root / "draining"

        fake_aws = bin_dir / "aws"
        fake_aws.write_text("#!/usr/bin/env sh\nprintf 'test-token'\n")
        fake_aws.chmod(0o700)

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
                method = args[args.index("-X") + 1]
                output = pathlib.Path(args[args.index("-o") + 1])
                url = args[-1]
                if "Authorization: Bearer test-token" not in args:
                    raise SystemExit("unexpected token")
                with pathlib.Path(os.environ["TEST_EVENT_LOG"]).open("a") as log:
                    log.write(f"{method} {url}\\n")

                code = 204
                payload = {}
                if url.endswith("/droplets/101"):
                    code = 404
                elif url.endswith("/droplets/202"):
                    if os.environ.get("TEST_PROVIDER_FAILURE") == "1":
                        code = 500
                    elif os.environ.get("TEST_MALFORMED_RESPONSE") == "1":
                        code = 200
                    else:
                        tags = ["courseultra-openvidu-media-node-tag"]
                        if pathlib.Path(os.environ["TEST_DRAIN_STATE"]).exists():
                            tags.append("courseultra-openvidu-draining")
                        code = 200
                        payload = {"droplet": {"id": 202, "tags": tags}}
                elif method == "POST" and url.endswith("/courseultra-openvidu-draining/resources"):
                    pathlib.Path(os.environ["TEST_DRAIN_STATE"]).touch()
                elif method == "DELETE" and url.endswith("/courseultra-openvidu-media-node-tag/resources"):
                    pass
                else:
                    raise SystemExit(f"unexpected request: {method} {url}")

                output.write_text(json.dumps(payload))
                print(code, end="")
                """
            )
        )
        fake_curl.chmod(0o700)

        env = os.environ.copy()
        env.update(
            {
                "PATH": f"{bin_dir}:{env['PATH']}",
                "TEST_DRAIN_STATE": str(drain_state),
                "TEST_EVENT_LOG": str(event_log),
                "TEST_MALFORMED_RESPONSE": "1" if malformed_response else "0",
                "TEST_PROVIDER_FAILURE": "1" if provider_failure else "0",
            }
        )
        result = subprocess.run(
            [str(SCRIPT), str(ids_file)],
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        return result, ids_file, event_log

    def test_skips_deleted_node_and_continues_draining_remaining_node(self):
        result, ids_file, event_log = self.run_script()

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("101 is already absent", result.stdout)
        self.assertIn("202 is draining", result.stdout)
        self.assertFalse(ids_file.exists())
        self.assertEqual(
            [
                "GET https://api.digitalocean.com/v2/droplets/101",
                "GET https://api.digitalocean.com/v2/droplets/202",
                "POST https://api.digitalocean.com/v2/tags/courseultra-openvidu-draining/resources",
                "GET https://api.digitalocean.com/v2/droplets/202",
                "DELETE https://api.digitalocean.com/v2/tags/courseultra-openvidu-media-node-tag/resources",
            ],
            event_log.read_text().splitlines(),
        )

    def test_preserves_retry_file_and_tags_on_provider_read_failure(self):
        result, ids_file, event_log = self.run_script(provider_failure=True)

        self.assertNotEqual(0, result.returncode)
        self.assertTrue(ids_file.exists())
        events = event_log.read_text()
        self.assertNotIn("POST", events)
        self.assertNotIn("DELETE", events)

    def test_preserves_retry_file_on_malformed_droplet_response(self):
        result, ids_file, event_log = self.run_script(malformed_response=True)

        self.assertNotEqual(0, result.returncode)
        self.assertTrue(ids_file.exists())
        events = event_log.read_text()
        self.assertNotIn("POST", events)
        self.assertNotIn("DELETE", events)


if __name__ == "__main__":
    unittest.main()
