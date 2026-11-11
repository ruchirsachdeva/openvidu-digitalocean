"""Fresh-only unarmed preparation; commands are fake or Compose render-only."""
import copy
import hashlib
import importlib.util
import json
import os
import re
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('fresh_recorder', ROOT / 'prepare-fresh-recorder.py')
fresh = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fresh)


class FreshRecorderTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name).resolve()
        self.override = self.root / 'docker-compose.override.yaml'
        self.original = 'services:\n  openvidu:\n    # Existing nofile stays intact\n    ulimits:\n      nofile: 65536\n  redis:\n    restart: always\n  operator:\n    restart: unless-stopped\n'
        self.override.write_text(self.original)
        self.candidate = (ROOT / 'recorder-startup-guard.override.yaml').read_text().replace('/opt/openvidu', str(self.root))
        self.before = {'services': {'operator': {'image': 'operator'}, 'openvidu': {'ulimits': {'nofile': 65536}},
                                   'redis': {'entrypoint': ['preserved']}, 'egress': {
            'image': 'docker.io/openvidu/egress:3.8.0', 'network_mode': 'host', 'restart': 'unless-stopped',
            'volumes': [{'type': 'bind', 'source': '/runtime', 'target': '/config'}]}}}
        self.after = copy.deepcopy(self.before)
        self.after['services']['egress'].update(image=fresh.IMAGE, platform='linux/amd64', user='egress',
            entrypoint=['/bin/bash', '/courseultra-guard/start.sh'], command=[],
            environment={'EGRESS_CONFIG_FILE': '/config/egress.yaml'})
        for name, target in [('start.sh', '/courseultra-guard/start.sh'),
                             ('start.lock', '/courseultra-guard/start.lock'),
                             ('egress-config.sha256', '/courseultra-guard/egress-config.sha256'),
                             ('egress.yaml', '/config/egress.yaml')]:
            self.after['services']['egress']['volumes'].append({'type': 'bind',
                'source': str(self.root / 'courseultra-recorder-guard' / name), 'target': target,
                'read_only': True, 'bind': {'create_host_path': False}})
        self.container_reads = 0
        self.containers = ''
        self.concurrent = False

    def run_command(self, command):
        if command[:3] == ['docker', 'ps', '-aq']:
            self.container_reads += 1
            return 'unexpected' if self.concurrent and self.container_reads > 2 else self.containers
        return json.dumps(self.after if any('.recorder-override-' in p for p in command) else self.before)

    def prepare(self):
        fresh.prepare(self.root, self.candidate, '# inert guard fixture\n', self.run_command)

    def assertUnchanged(self):
        self.assertEqual(self.original, self.override.read_text())
        self.assertFalse((self.root / 'courseultra-recorder-guard').exists())

    def test_fresh_setup_stays_unarmed_and_preserves_other_overrides(self):
        self.prepare()
        self.assertTrue(self.override.read_text().startswith(self.original))
        target = self.root / 'courseultra-recorder-guard'
        self.assertEqual('UNARMED\n', (target / 'egress-config.sha256').read_text())
        self.assertEqual(0o640, (target / 'egress.yaml').stat().st_mode & 0o777)
        self.assertEqual(0o750, target.stat().st_mode & 0o777)
        self.assertEqual(b'', (target / 'start.lock').read_bytes())
        self.assertEqual(0o640, (target / 'start.lock').stat().st_mode & 0o777)
        for name in ('tmp', 'backup_storage'):
            self.assertEqual([], list((self.root / 'data/egress_data/home/egress' / name).iterdir()))
        self.assertFalse((self.root / '.courseultra-recorder-prepared').exists())
        with self.assertRaises(ValueError):
            self.prepare()  # Partial/existing preparation is never silently rewritten.

    def test_recovery_permissions_survive_restrictive_cloud_init_umask(self):
        previous = os.umask(0o077)
        try:
            self.prepare()
        finally:
            os.umask(previous)
        recovery = self.root / 'data/egress_data/home/egress'
        for path in (recovery, recovery / 'tmp', recovery / 'backup_storage'):
            self.assertEqual(0o770, path.stat().st_mode & 0o777, str(path))

    def test_stopped_or_concurrently_started_containers_hold(self):
        self.containers = 'stopped-recorder'
        with self.assertRaises(ValueError): self.prepare()
        self.assertUnchanged()
        self.containers = ''
        self.container_reads = 0
        self.concurrent = True
        with self.assertRaises(ValueError): self.prepare()
        self.assertUnchanged()

    def test_master_verifies_absence_without_adding_recorder_or_changing_override(self):
        del self.before['services']['egress']
        fresh.prepare(self.root, self.candidate, 'guard', self.run_command, 'master_node')
        self.assertUnchanged()
        self.assertFalse((self.root / 'data/egress_data').exists())
        self.before['services']['unexpected'] = {'image': 'docker.io/openvidu/egress:3.8.0'}
        with self.assertRaises(ValueError):
            fresh.prepare(self.root, self.candidate, 'guard', self.run_command, 'master_node')
        self.assertUnchanged()

    def test_existing_hidden_recovery_data_is_not_removed(self):
        data = self.root / 'data/egress_data'
        data.mkdir(parents=True)
        secret = data / '.unfinished'
        secret.write_bytes(b'recovery')
        with self.assertRaises(ValueError): self.prepare()
        self.assertEqual(b'recovery', secret.read_bytes())
        self.assertUnchanged()

    def test_symlink_paths_hold(self):
        outside = self.root / 'outside'
        outside.mkdir()
        (self.root / 'data').symlink_to(outside, target_is_directory=True)
        with self.assertRaises(ValueError): self.prepare()
        self.assertEqual([], list(outside.iterdir()))
        self.assertUnchanged()

    def test_custom_recorder_or_unknown_yaml_is_not_rewritten(self):
        for body in ('services:\n  egress:\n    image: custom\n',
                     'services:\n  "egress":\n    image: custom\n', 'include:\n  - custom\nservices:\n'):
            self.override.write_text(body)
            with self.assertRaises(ValueError): self.prepare()
            self.assertEqual(body, self.override.read_text())

    def test_rendered_changes_are_strictly_scoped(self):
        valid = copy.deepcopy(self.after)
        variants = []
        for key, value in [('user', 'root'), ('image', 'unknown'), ('restart', 'always'), ('command', ['bypass']),
                           ('network_mode', 'bridge')]:
            bad = copy.deepcopy(valid)
            bad['services']['egress'][key] = value
            variants.append(bad)
        bad = copy.deepcopy(valid)
        bad['services']['redis']['entrypoint'] = ['changed']
        variants.append(bad)
        bad = copy.deepcopy(valid)
        bad['services']['egress']['volumes'][-1]['read_only'] = False
        variants.append(bad)
        for bad in variants:
            self.after = bad
            with self.assertRaises(ValueError): self.prepare()
            self.assertUnchanged()

    def test_first_boot_and_reboot_barrier_precede_vendor_enablement_on_both_roles(self):
        source = (ROOT / 'tf-do-openvidu-elastic.tf').read_text()
        for role, section, end in [('master', 'user_data_master = <<-EOF', '# ----- media -----'), ('media', 'user_data_media = <<-EOF', '\nEOF\n}')]:
            body = source.split(section, 1)[1].split(end, 1)[0]
            self.assertLess(body.index('${local.recorder_guard_barrier}'), body.index('/usr/local/bin/install.sh ||'))
            preparation = '${local.recorder_guard_prepare_' + role + '}'
            self.assertLess(body.index('/usr/local/bin/install.sh ||'), body.index(preparation))
            self.assertLess(body.index(preparation), body.index('systemctl start openvidu ||'))
        barrier = source.split('recorder_guard_barrier = (var.isolatedRecorderGuard ? <<-EOF', 1)[1].split('\nEOF', 1)[0]
        self.assertIn('ConditionPathExists=/opt/openvidu/.courseultra-recorder-prepared', barrier)
        prepare = re.split(r'recorder_guard_prepare\s*= <<-EOF', source, maxsplit=1)[1].split('\nEOF', 1)[0]
        self.assertLess(prepare.index('python3 '), prepare.index('install -m 600 /dev/null'))
        self.assertIn('exit 1;', prepare)
        variables = (ROOT / 'variables.tf').read_text().split('variable "isolatedRecorderGuard"', 1)[1].split('\nvariable ', 1)[0]
        self.assertIn('default     = false', variables)
        self.assertIn('var.stackName == "courseultra-openvidu-38-qualification"', variables)

    def test_disabled_guard_preserves_reviewed_cloud_init_bytes(self):
        # Compare guard-disabled bodies against their reviewed baseline, excluding
        # the separately tested September24 fresh APT preparation. Its inclusion
        # is a user-data change requiring replacement review, never a blind apply.
        expected = {'master': '927fba7c59cfe65628bc43d9ab9a5cacc32b949fd1a67b67c5232fedfa243daf',
                    'media': '81bddb7996d533ecf5ff2135ee01271e73278e14e8da88715b7df4ba5c438f81'}
        source = (ROOT / 'tf-do-openvidu-elastic.tf').read_text()
        for role, fingerprint in expected.items():
            body = source.split('user_data_' + role + ' = <<-EOF\n', 1)[1].split('\nEOF', 1)[0]
            for key in ('recorder_guard_barrier', 'recorder_guard_prepare_master', 'recorder_guard_prepare_media', 'capacity_drain_settings', 'capacity_media_drain_settings', 'capacity_recording_report',
                        'capacity_master_watcher_install', 'capacity_fresh_arm', 'capacity_fast_watcher_cron', 'fresh_apt_prepare'):
                body = body.replace('${local.' + key + '}', '')
            for key in ('install_script_media', 'graceful_shutdown_script_media', 'tag_watcher_script_media'):
                conditional = '${var.capacityReservationsEnabled ? replace(local.' + key + ', "/(?m)^[ \\\\t]*(#[^!\\\\n][^\\\\n]*)?\\\\n/", "") : local.' + key + '}'
                body = body.replace(conditional, '${local.' + key + '}')
            body = body.replace('${var.capacityReservationsEnabled ? local.capacity_python_sources["media_drain_guard.py"] : file("${path.module}/media_drain_guard.py")}', '${file("${path.module}/media_drain_guard.py")}')
            # The new IO policy is inside the existing capacity-only shell branch.
            # Non-capacity startup behavior retains the reviewed branch and bytes.
            begin = body.find('  # Exact3.8 exits IO drain')
            if begin >= 0:
                end = body.index('  test "$(grep -c', begin)
                end = body.index('\n', end) + 1
                body = body[:begin] + body[end:]
            # Package staging now lives in the separately tested fresh APT helper;
            # the final install is cache-only, never a whole-bootstrap retry.
            body = body.replace('apt-get --no-download install -y', 'apt-get update && apt-get install -y')
            self.assertEqual(fingerprint, hashlib.sha256(body.encode()).hexdigest(), role)
        self.assertIn('var.isolatedRecorderGuard ? <<-EOF', source)
        for key in ('capacity_master_watcher_install', 'capacity_fresh_arm', 'capacity_fast_watcher_cron', 'capacity_watcher_lock'):
            self.assertRegex(source, key + r'\s*= var.capacityReservationsEnabled \? [^\n]+ : ""')
        for role in expected:
            self.assertRegex(source, 'recorder_guard_prepare_' + role + r'\s*= var.isolatedRecorderGuard \? [^\n]+ : ""')


if __name__ == '__main__':
    unittest.main()
