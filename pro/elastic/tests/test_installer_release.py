"""Exercise release rejection and integrity checks without network or root access."""
import hashlib
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest


SOURCE = Path(__file__).resolve().parents[1] / "tf-do-openvidu-elastic.tf"
TERRAFORM = SOURCE.read_text()
RELEASE = dict(re.findall(r'(\w+)\s*=\s*"([^"\n]+)"',
    TERRAFORM.split("openvidu_installer_release = {", 1)[1].split("}", 1)[0]))


def render(text):
    for key, value in RELEASE.items():
        text = text.replace("${local.openvidu_installer_release." + key + "}", value)
    return text


class InstallerReleaseTest(unittest.TestCase):
    def test_master_renders_the_current_version_and_checksum(self):
        script = TERRAFORM.split("install_script_master = <<-EOF\n", 1)[1].split("\nEOF", 1)[0]
        rendered = render(script)
        self.assertIn("OPENVIDU_VERSION=3.8.0\n", rendered)
        self.assertIn('INSTALL_SCRIPT_SHA256="' + RELEASE["master_sha256"] + '"', rendered)
        self.assertNotIn("${local.openvidu_installer_release.", rendered)

    def test_both_roles_use_the_same_reviewed_release(self):
        self.assertEqual("3.8.0", RELEASE["version"])
        for role in ("master", "media"):
            script = TERRAFORM.split(f"install_script_{role} = <<-EOF\n", 1)[1].split("\nEOF", 1)[0]
            self.assertIn("${local.openvidu_installer_release.version}", script)
            self.assertIn("${local.openvidu_installer_release." + role + "_sha256}", script)
            self.assertRegex(RELEASE[role + "_sha256"], r"^[a-f0-9]{64}$")

    def run_media_download(self, version, valid_checksum=True):
        script = TERRAFORM.split("install_script_media = <<-EOF\n", 1)[1].split("\nEOF", 1)[0]
        script = script[script.index("# Match the master bootstrap"):script.index('INSTALL_COMMAND="sh $INSTALL_SCRIPT"')]
        script = render(script)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            installer = root / "installer.sh"
            body = b"#!/bin/sh\nexit 0\n"
            if valid_checksum:
                script = script.replace(RELEASE["media_sha256"], hashlib.sha256(body).hexdigest())
            script = script.replace("/tmp/install_ov_media_node.sh", str(installer))
            # Test actual hash comparison, not a checksum command that always succeeds.
            commands = {
                "curl": "import pathlib,sys,os\n"
                    "pathlib.Path(os.environ['DOWNLOAD_LOG']).write_text(' '.join(sys.argv[1:]))\n"
                    f"pathlib.Path(sys.argv[sys.argv.index('-o')+1]).write_bytes({body!r})\n",
                "sha256sum": "import hashlib,pathlib,sys\n"
                    "expected,path=sys.stdin.read().strip().split(None,1)\n"
                    "sys.exit(0 if hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()==expected else 1)\n",
            }
            for name, body_text in commands.items():
                path = root / name
                path.write_text(f"#!{sys.executable}\n" + body_text)
                path.chmod(0o700)
            env = dict(os.environ, PATH=str(root) + os.pathsep + os.environ["PATH"],
                OPENVIDU_VERSION=version, DOWNLOAD_LOG=str(root / "download.log"))
            result = subprocess.run(["/bin/bash", "-eu", "-c", script], env=env,
                capture_output=True, text=True, timeout=10)
            download = (root / "download.log").read_text() if (root / "download.log").exists() else None
            return result, download

    def test_matching_release_downloads_pinned_tls_installer(self):
        result, download = self.run_media_download(RELEASE["version"])
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("https://s3-eu-west-1.amazonaws.com/get.openvidu.io/pro/elastic/3.8.0/", download)

    def test_mismatches_are_rejected_before_download(self):
        for version in ("3.7.0", "", "3.7.0\n3.8.0", "../../../unreviewed", "3.8.0 "):
            with self.subTest(version=version):
                result, download = self.run_media_download(version)
                self.assertNotEqual(0, result.returncode)
                self.assertIsNone(download)
                self.assertIn("does not match the reviewed installer release", result.stderr)

    def test_matching_version_with_wrong_artifact_is_rejected(self):
        result, download = self.run_media_download(RELEASE["version"], valid_checksum=False)
        self.assertIsNotNone(download)
        self.assertNotEqual(0, result.returncode)
        self.assertIn("checksum verification failed", result.stdout)


if __name__ == "__main__":
    unittest.main()
