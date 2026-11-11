"""Offline rendering of real startup locals, with synthetic credentials only."""
import ast
import base64
import gzip
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1]


def executable(source):
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.body and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant) and isinstance(node.body[0].value.value, str):
                node.body.pop(0)
    return ast.dump(tree)


def realistic_descriptor():
    digest = lambda label: hashlib.sha256(label.encode()).hexdigest()
    dimensions = ('cpuMillis', 'memoryBytes', 'diskBytes', 'ingressBytesPerSecond', 'egressBytesPerSecond', 'packetsPerSecond')
    vector = lambda values: dict(zip(dimensions, values))
    profile = dict(qualified=True, fingerprint='synthetic-cu-ov38-cpuload-' + digest('capacity'),
        evidenceVersion='synthetic-exact38-20261111', workloadProfile='browser-h264-720p-recorded', nodeType='c-8',
        placementPolicy='PROVIDER', recordingCapacityMode='POOL_ADMISSION_V1', recordingObligationLimitDisabled=True,
        maximumRecordingObligations=4, maxSingleRoomPeople=120,
        resourceBudgets=vector([6400, 12884901888, 268435456000, 250000000, 250000000, 180000]),
        fixedRoomDemand=vector([2000, 805306368, 1073741824, 1800000, 3400000, 2700]),
        smallRecordedRoomDemand=vector([2400, 1073741824, 4294967296, 2500000, 4500000, 3900]),
        perPersonDemand=vector([32, 12582912, 0, 128000, 256000, 120]), roomCpuIncludesRecording=True,
        recordingDemand=vector([2000, 2147483648, 8589934592, 3100000, 1700000, 2800]),
        recordingStorageBudget=dict(bytesPerCopy=8589934592, referenceSeconds=7200, copies=2, graceSeconds=300))
    return dict(operatingProfile=dict(profile=profile, measuredLead='PT3M', maxWait='PT5M', maximumScheduledClasses=100),
        masterDropletId='123456789', region='test-region-1', vpcId='00000000-0000-4000-8000-000000000002',
        mediaImage='sha256:' + digest('media-image'), recorderImage='sha256:' + digest('recorder-image'),
        recorderPolicySha256=digest('recorder-policy'), startupGuardSha256=digest('startup-guard'),
        minimumFreeMemoryBytes=1073741824, minimumFreeDiskBytes=10737418240, maximumLoadAverage=6.4)


class UserDataTransportTest(unittest.TestCase):
    def test_real_rendered_payloads_fit_and_decode_exactly(self):
        source = (MODULE / "tf-do-openvidu-elastic.tf").read_text()
        locals_source = source[source.index("\nlocals {") + 1:]
        resources = {
            "digitalocean_droplet.openvidu_master_node.id": "123",
            "digitalocean_droplet.openvidu_master_node.ipv4_address_private": "10.10.10.2",
            "digitalocean_spaces_bucket.openvidu_space[0].name": "synthetic-bucket",
            "digitalocean_spaces_key.openvidu_space_key.access_key": hashlib.sha256(b"access").hexdigest()[:20],
            "digitalocean_spaces_key.openvidu_space_key.secret_key": hashlib.sha256(b"secret").hexdigest()[:40],
            "digitalocean_ssh_key.openvidu_ssh_key_do.id": "456",
            "digitalocean_tag.draining_tag.name": "synthetic-draining",
            "digitalocean_tag.media_node_tag.name": "synthetic-media",
            "digitalocean_vpc.openvidu_vpc.id": "00000000-0000-4000-8000-000000000001",
            "digitalocean_vpc.openvidu_vpc.ip_range": "10.10.10.0/24",
            "random_id.bucket_suffix.hex": "12345678",
            "tls_private_key.openvidu_ssh_key.public_key_openssh": "ssh-rsa " + base64.b64encode(b"".join(hashlib.sha512(str(i).encode()).digest() for i in range(8))).decode(),
            "path.module": str(MODULE),
        }
        for reference, value in resources.items():
            locals_source = locals_source.replace(reference, json.dumps(value))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "main.tf").write_text(locals_source)
            shutil.copyfile(MODULE / "variables.tf", root / "variables.tf")
            for enabled in (False, True):
                with self.subTest(capacity=enabled):
                    variables = dict(doToken=hashlib.sha256(b"provision").hexdigest(), autoscalerToken=hashlib.sha256(b"autoscale").hexdigest(),
                        sshAllowedCidrs=["192.0.2.1/32"],
                        stackName="courseultra-openvidu-38-qualification", openviduLicense="synthetic",
                        capacityReservationsEnabled=enabled, isolatedRecorderGuard=enabled,
                        capacityBackendUrl="https://example.invalid", capacityBackendToken=hashlib.sha256(b"backend-token").hexdigest() + "synthetic'$(printf expanded)`printf expanded`\\\nCOURSEULTRA_SETTINGS_EOF",
                        capacityProfileFingerprint="synthetic-v1",
                        capacityFleetDescriptorJson=json.dumps(realistic_descriptor()))
                    (root / "terraform.tfvars.json").write_text(json.dumps(variables))
                    expression = 'nonsensitive(jsonencode({master=local.user_data_master,media=local.user_data_media,master_transport=local.user_data_master_transport,media_transport=local.user_data_media_transport,install_media=local.install_script_media,graceful_media=local.graceful_shutdown_script_media,watcher_media=local.tag_watcher_script_media}))'
                    result = subprocess.run(["terraform", "console", "-no-color"], cwd=root,
                        input=expression + "\n", text=True, capture_output=True, timeout=60)
                    self.assertEqual(0, result.returncode, result.stderr)
                    rendered = json.loads(json.loads(result.stdout))
                    for role in ("master", "media"):
                        raw = rendered[role].encode()
                        wrapper = rendered[role + "_transport"]
                        self.assertLessEqual(len(wrapper.encode()), 65536)
                        if enabled:
                            # Exercise complete profile fields, distinct hashes and
                            # representative credential/key lengths, with at least
                            # 2000 bytes of margin. Actual private rendering remains
                            # required; arbitrary configurations need not fit.
                            self.assertLessEqual(len(wrapper.encode()), 63536)
                        payload = re.search(r"printf '%s' '([^']+)'", wrapper).group(1)
                        self.assertEqual(raw, gzip.decompress(base64.b64decode(payload)))
                        self.assertIn(hashlib.sha256(raw).hexdigest(), wrapper)
                        syntax = subprocess.run(["bash", "-n"], input=raw, capture_output=True)
                        self.assertEqual(0, syntax.returncode, syntax.stderr.decode())
                        helpers = re.findall(r"cat > (/usr/local/(?:bin|share)/[^\n]+) <<'COURSEULTRA_HELPER_EOF'\n(.*?)COURSEULTRA_HELPER_EOF\n", raw.decode(), re.S)
                        if enabled:
                            settings = re.findall(r"cat > (/etc/courseultra-capacity-(?:drain|fleet-profile)\.json) <<'COURSEULTRA_SETTINGS_EOF'\n(.*?)\nCOURSEULTRA_SETTINGS_EOF\n", raw.decode(), re.S)
                            self.assertEqual(2, len(settings))
                            for destination, contents in settings:
                                self.assertNotIn('\n', contents, 'JSON must stay on one physical line')
                                saved = root / Path(destination).name
                                fragment = "cat > '" + str(saved) + "' <<'COURSEULTRA_SETTINGS_EOF'\n" + contents + "\nCOURSEULTRA_SETTINGS_EOF\n"
                                write = subprocess.run(['bash'], input=fragment, text=True, capture_output=True)
                                self.assertEqual(0, write.returncode, write.stderr)
                                self.assertEqual('', write.stdout)
                                self.assertEqual(json.loads(contents), json.loads(saved.read_text()))
                                if destination.endswith('drain.json'):
                                    self.assertEqual(variables['capacityBackendToken'], json.loads(saved.read_text())['token'])
                            self.assertGreaterEqual(len(helpers), 10)
                            recorder_report = '/usr/local/bin/report-recording-locations.py'
                            self.assertEqual(role == 'media', any(path == recorder_report for path, _ in helpers))
                            if role == "media":
                                drain = re.search(r"<< 'MEDIA_DRAIN_GUARD_EOF'\n(.*?)\nMEDIA_DRAIN_GUARD_EOF", raw.decode(), re.S).group(1)
                                self.assertEqual(executable((MODULE / "media_drain_guard.py").read_text()), executable(drain))
                                self.assertIn("cp /usr/local/bin/courseultra-media-drain-guard /usr/local/bin/media_drain_guard.py\nchmod 700", raw.decode())
                        if role == 'media':
                            for delimiter, key in [('INSTALL_MEDIA_EOF', 'install_media'), ('GRACEFUL_SHUTDOWN_EOF', 'graceful_media'), ('TAG_WATCHER_EOF', 'watcher_media')]:
                                saved = re.search(r"<< '" + delimiter + r"'\n(.*?)\n" + delimiter, raw.decode(), re.S)[1]
                                expected = rendered[key]
                                if enabled:
                                    expected = re.sub(r'(?m)^[ \t]*(#[^!\n][^\n]*)?\n', '', expected)
                                self.assertEqual(expected, saved)
                                self.assertTrue(saved.startswith('#!/bin/bash\n'))
                        apt = re.search(r"<<'COURSEULTRA_APT_EOF'\n(.*?)COURSEULTRA_APT_EOF", raw.decode(), re.S)
                        self.assertIsNotNone(apt)
                        self.assertEqual(executable((MODULE / 'prepare-fresh-apt.py').read_text()), executable(apt[1]))
                        for destination, contents in helpers:
                            name = Path(destination).name
                            if name == "courseultra-recorder-start.sh":
                                name = "recorder-startup-guard.sh"
                            expected = (MODULE / name).read_text()
                            self.assertTrue(expected.endswith("\n"))
                            self.assertNotIn("COURSEULTRA_HELPER_EOF", expected)
                            if name in ('settle-recording-jobs.py', 'recording-job-observation.py',
                                        'report-recording-locations.py', 'recorder-capacity-footprint.py',
                                        'media_drain_guard.py', 'prepare-fresh-recorder.py', 'recorder-isolation.py', 'preserve-recorder-ipc.py',
                                        'report-fleet-readiness.py', 'recorder_admission.py', 'arm-approved-recorder.py',
                                        'arm-fresh-recorder.py', 'settle-recordings.py', 'recorder-storage-probe.py'):
                                self.assertEqual(executable(expected), executable(contents))
                            else:
                                self.assertEqual(expected, contents)
                        print(f"capacity={enabled} {role}: raw={len(raw)}, transported={len(wrapper.encode())} bytes")
        self.assertIn("user_data = local.user_data_master_transport", source)
        self.assertIn("user_data = local.user_data_media_transport", source)
        self.assertIn("base64encode(local.user_data_media_transport)", source)

    def run_wrapper(self, script, checksum=None, corrupt=False):
        with tempfile.TemporaryDirectory() as directory:
            payload = base64.b64encode(gzip.compress(script.encode())).decode()
            wrapper = (MODULE / "user-data-transport.sh.tftpl").read_text()
            wrapper = wrapper.replace("${payload}", payload[:-8] if corrupt else payload)
            wrapper = wrapper.replace("${checksum}", checksum or hashlib.sha256(script.encode()).hexdigest())
            wrapper = wrapper.replace("$${", "${")
            wrapper = wrapper.replace("/tmp/courseultra-bootstrap.XXXXXXXX", directory + "/bootstrap.XXXXXXXX")
            result = subprocess.run(["bash"], input=wrapper, text=True, capture_output=True, timeout=10)
            self.assertEqual([], list(Path(directory).iterdir()), "Decoded script must be removed")
            return result

    def test_success_and_child_exit_status(self):
        for status in (0, 37):
            result = self.run_wrapper(f"printf 'executed'; exit {status}\n")
            self.assertEqual(status, result.returncode, result.stderr)
            self.assertEqual("executed", result.stdout)

    def test_checksum_and_decode_failure_never_execute(self):
        for kwargs in ({"checksum": "0" * 64}, {"corrupt": True}):
            result = self.run_wrapper("printf 'must-not-execute'\n", **kwargs)
            self.assertNotEqual(0, result.returncode)
            self.assertEqual("", result.stdout)


if __name__ == "__main__":
    unittest.main()
