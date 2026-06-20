import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


ELASTIC_DIR = Path(__file__).resolve().parents[1]
TERRAFORM_FILE = ELASTIC_DIR / "tf-do-openvidu-elastic.tf"


def media_install_script(root):
    terraform = TERRAFORM_FILE.read_text()
    script = terraform.split("install_script_media = <<-EOF\n", 1)[1].split(
        "\nEOF", 1
    )[0]
    replacements = {
        "${digitalocean_spaces_key.openvidu_space_key.access_key}": "test-access",
        "${digitalocean_spaces_key.openvidu_space_key.secret_key}": "test-secret",
        '${var.spaceName == "" ? digitalocean_spaces_bucket.openvidu_space[0].name : var.spaceName}': "test-space",
        "${var.spaceRegion}": "test-region",
        "${digitalocean_droplet.openvidu_master_node.ipv4_address_private}": "10.10.20.8",
        "${digitalocean_droplet.openvidu_master_node.id}": "202",
        "/opt/openvidu": str(root / "openvidu"),
        "/tmp/install_ov_media_node.sh": str(root / "install-media.sh"),
        "/etc/apt/apt.conf.d/99timeout": str(root / "apt-timeout"),
    }
    for placeholder, value in replacements.items():
        script = script.replace(placeholder, value)
    return script.replace("$${", "${")


def master_s3_config_script(root):
    terraform = TERRAFORM_FILE.read_text()
    script = terraform.split("config_s3_script_master = <<-EOF\n", 1)[1].split(
        "\nEOF", 1
    )[0]
    replacements = {
        "${digitalocean_spaces_key.openvidu_space_key.access_key}": "test-access",
        "${digitalocean_spaces_key.openvidu_space_key.secret_key}": "test-secret",
        '${var.spaceName == "" ? digitalocean_spaces_bucket.openvidu_space[0].name : var.spaceName}': "test-space",
        "${var.spaceRegion}": "test-region",
        "/opt/openvidu": str(root / "openvidu"),
    }
    for placeholder, value in replacements.items():
        script = script.replace(placeholder, value)
    script = script.replace("$${", "${")
    if sys.platform == "darwin":
        script = script.replace("sed -i ", "sed -i '' ")
    return script


class MediaBootstrapTest(unittest.TestCase):
    def test_master_persists_v2_recordings_in_external_s3(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cluster = root / "openvidu" / "config" / "cluster"
            master = cluster / "master_node"
            master.mkdir(parents=True)
            (cluster / "openvidu.env").write_text(
                "EXTERNAL_S3_ENDPOINT=old\n"
                "EXTERNAL_S3_REGION=old\n"
                "EXTERNAL_S3_PATH_STYLE_ACCESS=false\n"
                "EXTERNAL_S3_BUCKET_APP_DATA=old\n"
                "EXTERNAL_S3_ACCESS_KEY=old\n"
                "EXTERNAL_S3_SECRET_KEY=old\n"
            )
            compatibility = master / "v2compatibility.env"
            compatibility.write_text("V2COMPAT_OPENVIDU_PRO_RECORDING_STORAGE=local\n")
            script = root / "configure-s3.sh"
            script.write_text(master_s3_config_script(root))

            result = subprocess.run(
                ["/bin/bash", str(script)],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            self.assertIn(
                "V2COMPAT_OPENVIDU_PRO_RECORDING_STORAGE=s3",
                compatibility.read_text(),
            )

    def test_master_fails_when_v2_recording_storage_setting_is_absent(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cluster = root / "openvidu" / "config" / "cluster"
            master = cluster / "master_node"
            master.mkdir(parents=True)
            (cluster / "openvidu.env").write_text("")
            (master / "v2compatibility.env").write_text("OTHER_SETTING=value\n")
            script = root / "configure-s3.sh"
            script.write_text(master_s3_config_script(root))

            result = subprocess.run(
                ["/bin/bash", str(script)],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertNotEqual(0, result.returncode)
            self.assertIn("v2 recording storage setting is missing", result.stderr)

    def test_rejects_stale_secrets_when_private_ip_is_reused(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            attempts = root / "attempts"
            install_log = root / "install.log"

            commands = {
                "apt-get": """\
                    #!/usr/bin/env sh
                    exit 0
                """,
                "aws": """\
                    #!/usr/bin/env python3
                    import os
                    import pathlib
                    import sys

                    state = pathlib.Path(os.environ["TEST_ATTEMPTS"])
                    attempt = int(state.read_text()) + 1 if state.exists() else 1
                    state.write_text(str(attempt))
                    destination = pathlib.Path(sys.argv[4])
                    master_id = "101" if attempt == 1 else "202"
                    destination.write_text(
                        "DOMAIN_NAME=openvidu.example.com\\n"
                        "REDIS_PASSWORD=test-redis\\n"
                        "OPENVIDU_VERSION=3.7.0\\n"
                        "OPENVIDU_PRO_LICENSE=test-license\\n"
                        "MASTER_NODE_PRIVATE_IP=10.10.20.8\\n"
                        f"MASTER_NODE_ID={master_id}\\n"
                    )
                """,
                "curl": """\
                    #!/usr/bin/env python3
                    import pathlib
                    import sys

                    args = sys.argv[1:]
                    if "-o" in args:
                        pathlib.Path(args[args.index("-o") + 1]).write_text("installer")
                    else:
                        print("10.10.20.9")
                """,
                "sha256sum": """\
                    #!/usr/bin/env sh
                    cat >/dev/null
                    exit 0
                """,
                "sleep": """\
                    #!/usr/bin/env sh
                    exit 0
                """,
                "bash": """\
                    #!/usr/bin/env sh
                    printf '%s\\n' "$*" > "$TEST_INSTALL_LOG"
                    exit 0
                """,
            }
            for name, source in commands.items():
                command = bin_dir / name
                command.write_text(textwrap.dedent(source))
                command.chmod(0o700)

            script = root / "install-media-node.sh"
            script.write_text(media_install_script(root))
            script.chmod(0o700)

            env = os.environ.copy()
            env.update(
                {
                    "PATH": f"{bin_dir}:{env['PATH']}",
                    "TEST_ATTEMPTS": str(attempts),
                    "TEST_INSTALL_LOG": str(install_log),
                }
            )
            result = subprocess.run(
                ["/bin/bash", str(script)],
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual("2", attempts.read_text())
            self.assertIn("Retrieved stale secrets.env", result.stdout)
            install_arguments = install_log.read_text()
            self.assertIn("--master-node-private-ip=10.10.20.8", install_arguments)


if __name__ == "__main__":
    unittest.main()
