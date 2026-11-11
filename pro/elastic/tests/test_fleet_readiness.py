"""Local synthetic collector/first-start contracts; no cloud or provider calls."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from recorder_admission import parse_config, reviewed_config, endpoint_owner


def load(name):
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), ROOT / (name + '.py'))
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


fleet = load('report-fleet-readiness')
startup = load('arm-approved-recorder')


class InitializerEnvironmentTest(unittest.TestCase):
    def test_vendor_first_start_receives_service_environment(self):
        environment = startup.initializer_environment(Path('/opt/openvidu'))
        self.assertEqual('true', environment['RUNNING_SYSTEMD'])
        self.assertEqual('/opt/openvidu/config/node/media_node.env', environment['COMPOSE_ENV_FILES'])


def config():
    return dict(redis=dict(address='master-node:6379', username='', password='synthetic', db=0, use_tls=False),
                api_key='synthetic-key', api_secret='synthetic-secret', ws_url='ws://master-node:7880',
                health_port=9093, prometheus_port=9094, io_workers=1, backup=dict(prefix='/home/egress/backup_storage'),
                storage=dict(s3=dict(access_key='synthetic', secret='synthetic', region='test', endpoint='https://example.invalid',
                                     bucket='test', force_path_style=True, sse=dict(type=None, kms_key_id=None, kms_encryption_context=None))),
                cpu_cost=dict(max_cpu_utilization=.8, room_composite_cpu_cost=2, audio_room_composite_cpu_cost=1,
                              web_cpu_cost=2, audio_web_cpu_cost=.5, participant_cpu_cost=1, track_composite_cpu_cost=1, track_cpu_cost=.5),
                openvidu=dict(allocation_strategy='cpuload', use_global_cpu_monitoring=True, disable_cpu_overload_killer=False, min_disk_space_mb=512))


def policy():
    approved = config()
    approved.pop('io_workers', None)
    approved['cpu_cost'] = {key: float(value) for key, value in approved['cpu_cost'].items()}
    for target, keys in ((approved, ('api_key', 'api_secret', 'ws_url')),
                         (approved['redis'], ('address', 'password')),
                         (approved['storage']['s3'], ('access_key', 'secret'))):
        for key in keys:
            target[key] = '<rendered-connection-value>'
    return hashlib.sha256(json.dumps(approved, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


class FleetReadinessTest(unittest.TestCase):
    def test_collector_publishes_admission_separately_from_worker_health(self):
        source = (ROOT / 'report-fleet-readiness.py').read_text()
        self.assertIn("admission = admission_metrics(get(ports[1], '/metrics'), allow_draining=journal is not None)", source)
        self.assertIn("receipt['recorderAcceptingRequests'] = admission['acceptingRequests']", source)
        self.assertIn("receipt['recorderAdmissionVerified'] = not admission.get('disabled', False) and not admission.get('terminating', False)", source)

    def test_mixed_legacy_and_qualified_single_worker_configs_share_only_capacity_policy_fingerprint(self):
        from recorder_admission import config_policy_fingerprint
        legacy = config(); del legacy['io_workers']
        digest = config_policy_fingerprint(legacy)
        self.assertEqual('8d5adc895e486782bb018c3f324f9d30d3667607ad1ca06dbea32ef30b6ee07c', digest)
        self.assertEqual(digest, reviewed_config(legacy, digest))
        self.assertEqual(digest, config_policy_fingerprint(config()))
        self.assertNotEqual(hashlib.sha256(json.dumps(legacy).encode()).hexdigest(), hashlib.sha256(json.dumps(config()).encode()).hexdigest())
        for value in (True, 0, -1, 5, 65):
            with self.assertRaises(ValueError): config_policy_fingerprint(dict(config(), io_workers=value))
        source = (ROOT / 'report-fleet-readiness.py').read_text()
        self.assertIn("receipt['recorderIsolationSupported'] = type(config.get('io_workers')) is int and config['io_workers'] == 1", source)

    def test_semantically_equal_numeric_costs_share_policy_fingerprint(self):
        integers = config()
        floats = copy.deepcopy(integers)
        floats['cpu_cost'] = {key: float(value) for key, value in floats['cpu_cost'].items()}
        self.assertEqual(policy(), fleet.reviewed_config(integers, policy()))
        self.assertEqual(policy(), fleet.reviewed_config(floats, policy()))
        floats['cpu_cost']['participant_cpu_cost'] = 1.01
        with self.assertRaises(ValueError): fleet.reviewed_config(floats, policy())
        for value in (True, '1', float('inf'), float('nan')):
            invalid = copy.deepcopy(integers)
            invalid['cpu_cost']['participant_cpu_cost'] = value
            with self.assertRaises(ValueError): fleet.reviewed_config(invalid, policy())

    def test_existing_watcher_is_bounded_and_first_start_precedes_normal_stack(self):
        source = (ROOT / 'tf-do-openvidu-elastic.tf').read_text()
        self.assertIn('capacity_node_reports', source)
        self.assertIn('--kill-after=2s 20s python3 /usr/local/bin/report-fleet-readiness.py', source)
        self.assertIn('30 - (SECONDS - fleet_tick_started)', source)
        cycle = next(line for line in source.splitlines() if line.strip().startswith('capacity_fleet_report_cycle '))
        self.assertEqual(2, cycle.count('${local.capacity_fleet_report}'))
        self.assertIn('${local.capacity_watcher_lock}${local.capacity_fleet_report_cycle}', source)
        self.assertIn('45s python3 /usr/local/bin/report-recording-locations.py', source)
        self.assertIn('--kill-after=5s 45s', source)
        self.assertLess(max(45 + 5, 30 + 20 + 2) + 3, 60)
        self.assertIn('--connect-timeout 2 --max-time 3 ', source)
        self.assertIn('(${local.capacity_recording_report}) &', source)
        self.assertIn('flock -n 8 || exit 0', source)
        self.assertIn('" 8>&-"', source)  # Detached drain must not retain the reporting lock.
        body = source.split('user_data_media = <<-EOF', 1)[1]
        self.assertLess(body.index('${local.capacity_fresh_arm}'), body.index('systemctl start openvidu ||'))
        self.assertIn('capacity_master_watcher_install', source.split('# ----- media -----', 1)[0])

    def test_half_minute_reports_leave_margin_for_stagger_and_transport(self):
        # Model timestamps, not CPU capacity or a live cron scheduling guarantee.
        def worst_age(cadence):
            worst = 0
            for offset in range(30):
                for duration in range(21):
                    for now in range(120, 241):
                        starts = range(offset, now + 1, cadence)
                        latest = max(start for start in starts if start + duration <= now)
                        worst = max(worst, now - latest)
            return worst
        self.assertLess(worst_age(30), 60)
        self.assertGreaterEqual(worst_age(60), 60)

    def test_existing_compose_parser_preserves_literal_secret_and_rejects_duplicate_yaml(self):
        # Exercises the installed parser in config-only mode; never starts Docker services.
        sample = config()
        sample['api_secret'] = 'literal-${NOT_AN_ENV_LOOKUP}'
        self.assertEqual(sample, parse_config(json.dumps(sample)))
        with self.assertRaises(ValueError):
            parse_config('api_key: one\napi_key: two\n')

    def test_semantic_policy_allows_only_rendered_connections_not_unknown_settings(self):
        sample = config()
        self.assertEqual(policy(), reviewed_config(sample, policy()))
        sample['redis']['password'] = 'rotated-private-value'
        sample['api_secret'] = 'different-node-secret'
        self.assertEqual(policy(), reviewed_config(sample, policy()))
        for changed in (dict(sample, unknown=True), dict(sample, prometheus_port=9999),
                        dict(sample, health_port=9094), dict(sample, cpu_cost=dict(sample['cpu_cost'], web_cpu_cost=1)),
                        dict(sample, openvidu=dict(sample['openvidu'], use_global_cpu_monitoring=False))):
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                reviewed_config(changed, policy())
        with self.assertRaises(ValueError):
            reviewed_config(sample, '')

    def test_complete_cloud_listing_discovers_only_exact_stack_master(self):
        settings = dict(stackName='test', mediaTag='media-test', drainingTag='draining-test')
        def node(identity, tags):
            return dict(id=identity, tags=tags, status='active', size_slug='test-size', region=dict(slug='test'), vpc_uuid='test',
                        networks=dict(v4=[dict(type='private', ip_address='10.0.0.' + str(identity)),
                                          dict(type='public', ip_address='203.0.113.' + str(identity))]))
        pages = {1: dict(droplets=[node(9, ['test', 'master-node'])], meta=dict(total=2),
                         links=dict(pages=dict(next='https://api.digitalocean.com/v2/droplets?page=2&per_page=200'))),
                 2: dict(droplets=[node(1, ['media-test'])], meta=dict(total=2))}
        descriptor = {}
        result = fleet.cloud_inventory(pages.__getitem__, settings, descriptor)
        self.assertEqual('9', descriptor['masterDropletId'])
        self.assertEqual(['1', '9'], [n['dropletId'] for n in result])
        reserved = copy.deepcopy(pages)
        addresses = reserved[1]['droplets'][0]['networks']['v4']
        addresses.append(dict(type='public', ip_address='198.51.100.1'))
        result = fleet.cloud_inventory(reserved.__getitem__, settings, {})
        self.assertEqual('198.51.100.1', next(n for n in result if n['dropletId'] == '9')['publicIp'])
        addresses.reverse()
        self.assertEqual(result, fleet.cloud_inventory(reserved.__getitem__, settings, {}))
        addresses.append(dict(type='public', ip_address='198.51.100.1'))
        self.assertEqual(result, fleet.cloud_inventory(reserved.__getitem__, settings, {}))
        reserved[2]['droplets'][0]['networks']['v4'].append(dict(type='public', ip_address='198.51.100.2'))
        with self.assertRaises(ValueError):
            fleet.cloud_inventory(reserved.__getitem__, settings, {})
        with self.assertRaises(ValueError):
            fleet.cloud_inventory(lambda p: dict(droplets=[], meta=dict(total=2)), settings, {})
        bad = copy.deepcopy(pages)
        bad[1]['links']['pages']['next'] = 'https://evil.invalid/?page=2&per_page=200'
        with self.assertRaises(ValueError):
            fleet.cloud_inventory(bad.__getitem__, settings, {})
        bad = copy.deepcopy(pages)
        bad[2]['droplets'][0]['status'] = 'new'
        with self.assertRaises(ValueError):
            fleet.cloud_inventory(bad.__getitem__, settings, {})

    def test_mount_order_is_not_a_container_identity_change(self):
        before = [dict(Id='container', State=dict(StartedAt='start', Pid=123, Running=True),
                       Mounts=[dict(Source='/a', Destination='/x', RW=False),
                               dict(Source='/b', Destination='/y', RW=False)])]
        after = copy.deepcopy(before)
        after[0]['Mounts'].reverse()
        self.assertEqual(fleet.container_identities(before), fleet.container_identities(after))
        after[0]['Mounts'][0]['RW'] = True
        self.assertNotEqual(fleet.container_identities(before), fleet.container_identities(after))
        after = copy.deepcopy(before)
        after[0]['State']['Pid'] = 124
        self.assertNotEqual(fleet.container_identities(before), fleet.container_identities(after))

    def test_sockets_belong_to_exact_process_not_merely_host_network(self):
        with tempfile.TemporaryDirectory() as directory:
            proc = Path(directory)
            pid = proc / '123'
            (pid / 'fd').mkdir(parents=True)
            (pid / 'net').mkdir()
            (pid / 'comm').write_text('egress\n')
            (pid / 'cgroup').write_text('0::/docker/' + 'a' * 64)
            (pid / 'stat').write_text('123 (egress) ' + ' '.join(['0'] * 19 + ['456']))
            (pid / 'net/tcp').write_text('header\n0: 00000000:2385 00000000:0000 0A 0 0 0 0 0 111\n0: 00000000:2386 00000000:0000 0A 0 0 0 0 0 222\n')
            (pid / 'net/tcp6').write_text('header\n')
            (pid / 'fd/1').symlink_to('socket:[111]')
            (pid / 'fd/2').symlink_to('socket:[222]')
            self.assertEqual(('123', '456'), endpoint_owner('a' * 64, [9093, 9094], proc))
            with self.assertRaises(ValueError):
                endpoint_owner('b' * 64, [9093, 9094], proc)
            (pid / 'fd/2').unlink()
            with self.assertRaises(ValueError):
                endpoint_owner('a' * 64, [9093, 9094], proc)

    def test_stopped_collector_requires_real_restart_fence_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            proc = root / 'proc'
            proc.mkdir()
            (proc / 'meminfo').write_text('MemAvailable: 10000 kB\n')
            (proc / 'loadavg').write_text('0.1 0.1 0.1 1/1 1\n')
            folder = root / 'courseultra-recorder-guard'
            folder.mkdir()
            body = json.dumps(config())
            (folder / 'egress.yaml').write_text(body)
            (folder / 'egress-config.sha256').write_text(hashlib.sha256(body.encode()).hexdigest() + '\n')
            (folder / 'start.sh').write_text('synthetic')
            (folder / 'start.lock').write_text('')
            descriptor = dict(masterDropletId='9', recorderPolicySha256=policy(), minimumFreeMemoryBytes=1,
                              minimumFreeDiskBytes=1, maximumLoadAverage=1)
            worker = dict(Name='/egress', Id='a' * 64, Image='sha256:test',
                Config=dict(Image='openvidu/egress:3.8.0', Entrypoint=['/bin/bash', '/courseultra-guard/start.sh']),
                State=dict(Running=False, Restarting=False, Status='exited', ExitCode=0, OOMKilled=False),
                Mounts=[dict(Destination=destination, Type='bind', RW=False, Source=str(folder / filename)) for destination, filename in
                        [('/config/egress.yaml', 'egress.yaml'), ('/courseultra-guard/start.sh', 'start.sh'),
                         ('/courseultra-guard/egress-config.sha256', 'egress-config.sha256'), ('/courseultra-guard/start.lock', 'start.lock')]])
            calls = []
            run = lambda args: ''
            def fence(path, *, run):
                calls.append((path, run))
            guard = SimpleNamespace(verify_restart_fence=fence, healthy=lambda ip: False)
            result = fleet.local_receipt('1', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
                [dict(dropletId='1', privateIp='10.0.0.1')], [worker, dict(Name='/openvidu', Image='sha256:test', State=dict(Running=False))],
                descriptor, guard, run, root, proc)
            self.assertEqual([(root, run)], calls)
            self.assertTrue(result['recorderExcluded'])
            self.assertFalse(result['recorderAdmissionVerified'])
            self.assertFalse(result['mediaReady'])

    def test_first_start_renders_then_creates_stopped_then_arms_never_starts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            guard = root / 'courseultra-recorder-guard'
            guard.mkdir()
            (guard / 'egress-config.sha256').write_text('UNARMED\n')
            (guard / 'start.sh').write_text('synthetic guard')
            for name in ('tmp', 'backup_storage'):
                (root / 'data/egress_data/home/egress' / name).mkdir(parents=True)
            runtime = root / 'data/runtime/config/egress'
            runtime.mkdir(parents=True)
            (runtime / 'egress.yaml').write_text(json.dumps(config()))
            descriptor = dict(recorderPolicySha256=policy(), recorderImage='sha256:test',
                              startupGuardSha256=hashlib.sha256(b'synthetic guard').hexdigest())
            actions = []
            def run(args):
                actions.append(args)
                if 'config' in args:
                    return json.dumps(dict(services={'openvidu-init': dict(image='docker.io/openvidu/openvidu-operator:3.8.0',
                        environment=dict(MODE='init-elastic-media'), volumes=[dict(type='bind', source=source, target=target) for target, source in
                        [('/opt/openvidu/config', str(root / 'config')), ('/opt/openvidu/data/runtime', str(root / 'data/runtime')), ('/etc/localtime', '/etc/localtime')]])}))
                if args[:2] == ['docker', 'inspect']:
                    return json.dumps([dict(Image='sha256:test', State=dict(Status='created'))])
                return ''
            armed = []
            startup.prepare(root, descriptor, run, lambda path, digest, inspect: armed.append(inspect()))
            self.assertEqual(1, len(armed))
            self.assertTrue(any('run' in a and 'openvidu-init' in a for a in actions))
            self.assertEqual(1, sum(a[-4:] == ['up', '--no-start', '--no-deps', 'egress'] for a in actions))
            self.assertFalse(any(set(a).intersection({'start', 'restart', 'rm', 'down'}) for a in actions))
            self.assertTrue(all('--no-start' in a for a in actions if 'up' in a))
            # Legacy distributed templates lack this listener. Only the reviewed
            # missing field may be completed, never an existing conflicting value.
            missing = config()
            del missing['prometheus_port']
            del missing['io_workers']
            (runtime / 'egress.yaml').write_text(json.dumps(missing))
            startup.prepare(root, descriptor, run, lambda path, digest, inspect: armed.append(inspect()))
            completed = (runtime / 'egress.yaml').read_bytes()
            self.assertEqual(config(), parse_config(completed.decode()))
            for invalid in [dict(config(), io_workers=5), dict(config(), io_workers=True), dict(config(), prometheus_port=9999), dict(missing, unknown=True)]:
                original = json.dumps(invalid)
                (runtime / 'egress.yaml').write_text(original)
                before = len(actions)
                with self.assertRaises(ValueError):
                    startup.prepare(root, descriptor, run, lambda *args: self.fail('must not arm unapproved config'))
                self.assertEqual(original, (runtime / 'egress.yaml').read_text())
                self.assertFalse(any('up' in a for a in actions[before:]))
            (runtime / 'egress.yaml').write_text(json.dumps(config()))
            with self.assertRaises(ValueError):
                startup.prepare(root, descriptor, lambda args: 'existing-container', lambda *args: self.fail('must not arm existing node'))
            def wrong_template(args):
                return run(args).replace('init-elastic-media', 'unknown-mode')
            before = len(actions)
            with self.assertRaises(ValueError):
                startup.prepare(root, descriptor, wrong_template, lambda *args: self.fail('must not arm unknown initializer'))
            self.assertFalse(any('run' in a for a in actions[before:]))
            (guard / 'egress-config.sha256').write_text('already-armed\n')
            with self.assertRaises(ValueError):
                startup.prepare(root, descriptor, run, lambda *args: self.fail('must not rearm restart'))


if __name__ == '__main__':
    unittest.main()
