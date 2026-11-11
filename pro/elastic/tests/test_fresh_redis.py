import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('fresh_redis', ROOT / 'prepare-fresh-redis.py')
fresh = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fresh)
CANDIDATE = (ROOT / 'redis-durability.override.yaml').read_text()


class FreshRedisTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.override = self.root / 'docker-compose.override.yaml'
        self.original = 'services:\n  openvidu-meet:\n    # Preserve this customization.\n    restart: always\n'
        self.override.write_text(self.original)
        self.before = {'services': {'openvidu-meet': {'restart': 'always'}, 'redis': {
            'image': 'docker.io/redis:8.6.2-alpine', 'entrypoint': ['vendor'],
            'volumes': [{'type': 'bind', 'source': '/config', 'target': '/config'}]}}}
        self.after = copy.deepcopy(self.before)
        self.after['services']['redis'].update(entrypoint=['reviewed'], stop_grace_period='1m0s')
        self.after['services']['redis']['volumes'].append({'type': 'bind',
            'source': str(self.root / 'data/redis'), 'target': '/data',
            'bind': {'create_host_path': False}})
        self.containers = ['', '']
        self.named_redis = ''

    def run_command(self, command):
        if command[:3] == ['docker', 'ps', '-aq']:
            if command[-1] == 'name=^/redis$': return self.named_redis
            return self.containers.pop(0)
        return json.dumps(self.after if any('.redis-override-' in arg for arg in command) else self.before)

    def prepare(self):
        fresh.prepare(self.root, CANDIDATE, self.run_command)

    def test_fresh_setup_preserves_meet_and_creates_empty_private_data_directory(self):
        self.prepare()
        self.assertTrue(self.override.read_text().startswith(self.original))
        self.assertIn('--appendonly yes', self.override.read_text())
        self.assertIn('exec docker-entrypoint.sh', self.override.read_text())
        self.assertEqual(0o600, self.override.stat().st_mode & 0o777)
        self.assertEqual(0o700, (self.root / 'data/redis').stat().st_mode & 0o777)

    def test_missing_override_is_supported(self):
        self.override.unlink()
        self.prepare()
        self.assertTrue(self.override.read_text().startswith('services:\n  redis:'))

    def test_existing_stopped_or_running_container_refuses_before_file_changes(self):
        self.containers = ['stopped-container-id']
        with self.assertRaises(ValueError): self.prepare()
        self.assertEqual(self.original, self.override.read_text())
        self.assertFalse((self.root / 'data').exists())

    def test_existing_data_is_never_initialized_or_removed(self):
        data = self.root / 'data/redis'
        data.mkdir(parents=True)
        snapshot = data / 'dump.rdb'
        snapshot.write_bytes(b'existing recording state')
        with self.assertRaises(ValueError): self.prepare()
        self.assertEqual(b'existing recording state', snapshot.read_bytes())
        self.assertEqual(self.original, self.override.read_text())

    def test_unlabelled_redis_container_is_also_refused(self):
        self.named_redis = 'unlabelled-stopped-redis'
        with self.assertRaises(ValueError): self.prepare()
        self.assertEqual(self.original, self.override.read_text())

    def test_quoted_redis_customization_requires_review(self):
        self.override.write_text('services:\n  "redis":\n    restart: always\n')
        with self.assertRaises(ValueError): self.prepare()

    def test_existing_customization_requires_review(self):
        self.override.write_text('services:\n  redis:\n    restart: always\n')
        with self.assertRaises(ValueError): self.prepare()
        self.assertFalse((self.root / 'data').exists())

    def test_unknown_yaml_structure_is_not_rewritten(self):
        self.override.write_text('include:\n  - operator.yaml\nservices:\n')
        with self.assertRaises(ValueError): self.prepare()
        self.assertEqual('include:\n  - operator.yaml\nservices:\n', self.override.read_text())

    def test_symlink_data_parent_is_refused(self):
        elsewhere = self.root / 'other'
        elsewhere.mkdir()
        (self.root / 'data').symlink_to(elsewhere)
        with self.assertRaises(ValueError): self.prepare()
        self.assertEqual([], list(elsewhere.iterdir()))

    def test_concurrent_start_leaves_override_untouched(self):
        self.containers = ['', 'new-container-id']
        with self.assertRaises(ValueError): self.prepare()
        self.assertEqual(self.original, self.override.read_text())
        self.assertEqual([], list(self.root.glob('.redis-override-*')))

    def test_invalid_effective_configs_leave_override_and_data_untouched(self):
        variants = []
        bad = copy.deepcopy(self.after); bad['services']['openvidu-meet']['restart'] = 'no'; variants.append(bad)
        bad = copy.deepcopy(self.after); bad['services']['redis']['image'] = 'redis:other'; variants.append(bad)
        bad = copy.deepcopy(self.after); bad['services']['redis']['volumes'][-1]['bind']['create_host_path'] = True; variants.append(bad)
        bad = copy.deepcopy(self.after); bad['services']['redis']['volumes'][-1]['source'] = '/wrong'; variants.append(bad)
        bad = copy.deepcopy(self.after); bad['services']['redis']['volumes'].pop(0); variants.append(bad)
        for bad in variants:
            with self.subTest(config=bad):
                self.after = bad
                self.containers = ['']
                with self.assertRaises(ValueError): self.prepare()
                self.assertEqual(self.original, self.override.read_text())
                self.assertFalse((self.root / 'data').exists())

    def test_unqualified_base_image_is_refused(self):
        self.before['services']['redis']['image'] = 'redis:latest'
        self.after['services']['redis']['image'] = 'redis:latest'
        with self.assertRaises(ValueError): self.prepare()

    def test_target_redis_patch_version_is_accepted(self):
        self.before['services']['redis']['image'] = 'docker.io/redis:8.6.4-alpine'
        self.after['services']['redis']['image'] = 'docker.io/redis:8.6.4-alpine'
        self.prepare()
        self.assertTrue((self.root / 'data/redis').is_dir())

    def test_bootstrap_runs_between_vendor_install_and_first_start(self):
        text = (ROOT / 'tf-do-openvidu-elastic.tf').read_text().split('user_data_master = <<-EOF', 1)[1].split('\nEOF', 1)[0]
        self.assertLess(text.index('/usr/local/bin/install.sh ||'), text.index('python3 /usr/local/bin/prepare-fresh-redis.py'))
        self.assertLess(text.index('python3 /usr/local/bin/prepare-fresh-redis.py'), text.index('systemctl start openvidu'))

    def test_vendor_autostart_is_gated_before_installation(self):
        text = (ROOT / 'tf-do-openvidu-elastic.tf').read_text().split('user_data_master = <<-EOF', 1)[1].split('\nEOF', 1)[0]
        condition = text.index('ConditionPathExists=/opt/openvidu/.courseultra-redis-prepared')
        vendor = text.index('/usr/local/bin/install.sh ||')
        preparation = text.index('python3 /usr/local/bin/prepare-fresh-redis.py ||')
        marker = text.index('install -m 600 /dev/null /opt/openvidu/.courseultra-redis-prepared')
        reload = text.index('systemctl daemon-reload')
        start = text.index('systemctl start openvidu')
        self.assertLess(condition, vendor)
        self.assertLess(vendor, preparation)
        self.assertLess(preparation, marker)
        self.assertLess(marker, reload)
        self.assertLess(reload, start)


if __name__ == '__main__':
    unittest.main()
