import os
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path


ELASTIC_DIR = Path(__file__).resolve().parents[1]
TERRAFORM_FILE = ELASTIC_DIR / "tf-do-openvidu-elastic.tf"


def drain_script(capacity=False):
    terraform = TERRAFORM_FILE.read_text()
    return terraform.split("graceful_shutdown_script_media = <<-EOF\n", 1)[1].split(
        "\nEOF", 1
    )[0].replace('${var.capacityReservationsEnabled ? "--capacity-settings /etc/courseultra-capacity-drain.json " : ""}',
                 '--capacity-settings /etc/courseultra-capacity-drain.json ' if capacity else '')


class MediaDrainTest(unittest.TestCase):
    def run_drain(self, media_running, ready=True, docker_fails=False,
                  loses_ready_peer=False, signal_fails=False, failed_exit=False,
                  missing_container=False, retained_recording=False, fence_fails=False,
                  final_fence_fails=False, occupied=False, application_hold=False):
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
                if os.environ.get("TEST_DOCKER_FAILS") == "1":
                    raise SystemExit(1)
                if args[:2] == ["container", "kill"]:
                    raise SystemExit(1 if os.environ["TEST_SIGNAL_FAILS"] == "1" else 0)
                if args and args[0] == "ps":
                    if os.environ["TEST_SIGNAL_FAILS"] == "1" and "--format" in args:
                        print("egress")
                    if "--format" not in args and os.environ["TEST_MEDIA_RUNNING"] == "1":
                        print("running-container")
                    raise SystemExit(0)
                if args and args[0] == "inspect":
                    if os.environ["TEST_MISSING_CONTAINER"] == "1":
                        raise SystemExit(1)
                    print("exited 137 true" if os.environ["TEST_FAILED_EXIT"] == "1" else "exited 0 false")
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
            "courseultra-media-drain-guard": """\
                #!/usr/bin/env python3
                import os
                import pathlib
                import sys
                state = pathlib.Path(os.environ["TEST_GUARD_STATE"])
                calls = int(state.read_text()) if state.exists() else 0
                state.write_text(str(calls + 1))
                allowed = os.environ["TEST_READY"] == "1"
                if "--capacity-settings" in sys.argv and os.environ["TEST_APPLICATION_HOLD"] == "1":
                    allowed = False
                if "--require-idle-media" in sys.argv and os.environ["TEST_OCCUPIED"] == "1":
                    allowed = False
                if calls and os.environ["TEST_LOSES_READY_PEER"] == "1":
                    allowed = False
                if "--verify-recording-storage" in sys.argv and os.environ["TEST_RETAINED_RECORDING"] == "1":
                    allowed = False
                if "--signal-graceful" in sys.argv and os.environ["TEST_SIGNAL_FAILS"] == "1":
                    allowed = False
                if "--fence-restarts" in sys.argv and os.environ["TEST_FENCE_FAILS"] == "1":
                    allowed = False
                if "--verify-recording-storage" in sys.argv and "--verify-restart-fence" in sys.argv and os.environ["TEST_FINAL_FENCE_FAILS"] == "1":
                    allowed = False
                raise SystemExit(0 if allowed else 1)
            """,
        }
        for name, source in commands.items():
            command = bin_dir / name
            command.write_text(textwrap.dedent(source))
            command.chmod(0o700)

        script = root / "graceful_shutdown.sh"
        script.write_text(drain_script(capacity=application_hold).replace(
            "/usr/local/bin/courseultra-media-drain-guard", "courseultra-media-drain-guard"))
        script.chmod(0o700)

        env = os.environ.copy()
        env.update(
            {
                "PATH": f"{bin_dir}:{env['PATH']}",
                "TEST_DATE_STATE": str(date_state),
                "TEST_DELETION_MARKER": str(deletion_marker),
                "TEST_MEDIA_RUNNING": "1" if media_running else "0",
                "TEST_READY": "1" if ready else "0",
                "TEST_DOCKER_FAILS": "1" if docker_fails else "0",
                "TEST_GUARD_STATE": str(root / "guard-state"),
                "TEST_LOSES_READY_PEER": "1" if loses_ready_peer else "0",
                "TEST_SIGNAL_FAILS": "1" if signal_fails else "0",
                "TEST_FAILED_EXIT": "1" if failed_exit else "0",
                "TEST_MISSING_CONTAINER": "1" if missing_container else "0",
                "TEST_RETAINED_RECORDING": "1" if retained_recording else "0",
                "TEST_FENCE_FAILS": "1" if fence_fails else "0",
                "TEST_FINAL_FENCE_FAILS": "1" if final_fence_fails else "0",
                "TEST_OCCUPIED": "1" if occupied else "0",
                "TEST_APPLICATION_HOLD": "1" if application_hold else "0",
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

    def test_application_obligation_prevents_provider_shutdown_and_deletion(self):
        result, deletion_marker = self.run_drain(media_running=False, application_hold=True)
        self.assertNotEqual(0, result.returncode)
        self.assertNotIn('Starting graceful shutdown', result.stdout)
        self.assertFalse(deletion_marker.exists())

    def test_occupied_candidate_refuses_initial_drain(self):
        result, deletion_marker = self.run_drain(media_running=True, occupied=True)
        self.assertNotEqual(0, result.returncode)
        self.assertNotIn('Starting graceful shutdown', result.stdout)
        self.assertFalse(deletion_marker.exists())

    def test_stopped_media_allows_self_deletion(self):
        result, deletion_marker = self.run_drain(media_running=False)

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertTrue(deletion_marker.exists())

    def test_unready_replacement_never_allows_self_deletion(self):
        result, deletion_marker = self.run_drain(media_running=False, ready=False)
        self.assertNotEqual(0, result.returncode)
        self.assertFalse(deletion_marker.exists())

    def test_docker_failure_is_not_evidence_of_stopped_media(self):
        result, deletion_marker = self.run_drain(media_running=False, docker_fails=True)
        self.assertNotEqual(0, result.returncode)
        self.assertFalse(deletion_marker.exists())

    def test_ready_peer_lost_during_drain_prevents_deletion(self):
        result, deletion_marker = self.run_drain(media_running=False, loses_ready_peer=True)
        self.assertNotEqual(0, result.returncode)
        self.assertFalse(deletion_marker.exists())

    def test_failed_egress_shutdown_signal_prevents_deletion(self):
        result, deletion_marker = self.run_drain(media_running=False, signal_fails=True)
        self.assertNotEqual(0, result.returncode)
        self.assertFalse(deletion_marker.exists())

    def test_crashed_container_is_not_a_successful_recording_drain(self):
        result, deletion_marker = self.run_drain(media_running=False, failed_exit=True)
        self.assertNotEqual(0, result.returncode)
        self.assertFalse(deletion_marker.exists())

    def test_missing_container_is_not_proof_of_clean_shutdown(self):
        result, deletion_marker = self.run_drain(media_running=False, missing_container=True)
        self.assertNotEqual(0, result.returncode)
        self.assertFalse(deletion_marker.exists())

    def test_clean_exit_with_retained_recording_prevents_deletion(self):
        result, deletion_marker = self.run_drain(media_running=False, retained_recording=True)
        self.assertNotEqual(0, result.returncode)
        self.assertFalse(deletion_marker.exists())

    def test_unconfirmed_restart_barrier_prevents_deletion(self):
        result, deletion_marker = self.run_drain(media_running=False, fence_fails=True)
        self.assertNotEqual(0, result.returncode)
        self.assertFalse(deletion_marker.exists())

    def test_restart_barrier_changed_before_deletion_retains_node(self):
        result, deletion_marker = self.run_drain(media_running=False, final_fence_fails=True)
        self.assertNotEqual(0, result.returncode)
        self.assertFalse(deletion_marker.exists())


if __name__ == "__main__":
    unittest.main()
