import os
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path


ELASTIC_DIR = Path(__file__).resolve().parents[1]
TERRAFORM_FILE = ELASTIC_DIR / "tf-do-openvidu-elastic.tf"


def drain_script():
    terraform = TERRAFORM_FILE.read_text()
    return terraform.split("graceful_shutdown_script_media = <<-EOF\n", 1)[1].split(
        "\nEOF", 1
    )[0]


class MediaDrainTest(unittest.TestCase):
    def run_drain(self, media_running):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        bin_dir = root / "bin"
        bin_dir.mkdir()
        deletion_marker = root / "deleted"
        date_state = root / "date-state"

        commands = {
            "docker": """\
                #!/usr/bin/env python3
                import os
                import sys

                args = sys.argv[1:]
                if args[:2] == ["container", "kill"]:
                    raise SystemExit(0)
                if args and args[0] == "ps":
                    if "--format" not in args and os.environ["TEST_MEDIA_RUNNING"] == "1":
                        print("running-container")
                    raise SystemExit(0)
                if args and args[0] == "inspect":
                    print("false")
                    raise SystemExit(0)
                raise SystemExit(f"unexpected docker arguments: {args}")
            """,
            "date": """\
                #!/usr/bin/env python3
                import os
                import pathlib

                state = pathlib.Path(os.environ["TEST_DATE_STATE"])
                calls = int(state.read_text()) if state.exists() else 0
                state.write_text(str(calls + 1))
                print(1000 if calls == 0 else 2000)
            """,
            "sleep": """\
                #!/usr/bin/env sh
                exit 0
            """,
            "curl": """\
                #!/usr/bin/env sh
                printf '123'
            """,
            "doctl": """\
                #!/usr/bin/env sh
                : > "$TEST_DELETION_MARKER"
            """,
        }
        for name, source in commands.items():
            command = bin_dir / name
            command.write_text(textwrap.dedent(source))
            command.chmod(0o700)

        script = root / "graceful_shutdown.sh"
        script.write_text(drain_script())
        script.chmod(0o700)

        env = os.environ.copy()
        env.update(
            {
                "PATH": f"{bin_dir}:{env['PATH']}",
                "TEST_DATE_STATE": str(date_state),
                "TEST_DELETION_MARKER": str(deletion_marker),
                "TEST_MEDIA_RUNNING": "1" if media_running else "0",
            }
        )
        result = subprocess.run(
            [str(script)],
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        return result, deletion_marker

    def test_timeout_never_deletes_node_with_active_media(self):
        result, deletion_marker = self.run_drain(media_running=True)

        self.assertNotEqual(0, result.returncode)
        self.assertIn("leaving the node draining", result.stdout)
        self.assertFalse(deletion_marker.exists())

    def test_stopped_media_allows_self_deletion(self):
        result, deletion_marker = self.run_drain(media_running=False)

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertTrue(deletion_marker.exists())


if __name__ == "__main__":
    unittest.main()
