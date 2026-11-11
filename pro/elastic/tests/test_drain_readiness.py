import importlib.util
import pathlib
import unittest
import tempfile
import copy
import json
from unittest.mock import patch

MODULE = pathlib.Path(__file__).resolve().parents[1] / 'media_drain_guard.py'
spec = importlib.util.spec_from_file_location('drain_guard', MODULE)
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


class DrainRestartFenceTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = pathlib.Path(temporary.name)
        self.unit = self.root / 'drain.conf'
        self.unit.write_text('[Unit]\nConditionPathExists=!/opt/openvidu/.courseultra-draining\n')
        self.calls = []
        self.nodes = [{'Id': str(i) * 64, 'Name': '/' + name,
                       'State': {'Running': True, 'Restarting': False,
                                 'StartedAt': '2026-09-22T10:00:00Z'},
                       'HostConfig': {'RestartPolicy': {'Name': 'unless-stopped'}}}
                      for i, name in enumerate(('openvidu', 'ingress', 'egress'), 1)]

    def run_command(self, args):
        self.calls.append(args)
        if args[:2] == ['docker', 'ps']:
            return ''
        if args[:2] == ['docker', 'inspect']:
            return json.dumps(self.nodes)
        if args[:2] == ['docker', 'update']:
            self.assertTrue((self.root / '.courseultra-draining').is_file())
            for node in self.nodes:
                node['HostConfig']['RestartPolicy']['Name'] = 'no'
            return ''
        if args[:2] == ['docker', 'kill']:
            return ''
        if args == ['systemctl', 'daemon-reload']:
            return ''
        if args[:3] == ['systemctl', 'show', '--property=DropInPaths']:
            return str(self.unit)
        if args[:3] == ['systemctl', 'show', '--property=NeedDaemonReload']:
            return 'no'
        self.fail('Unexpected command: ' + str(args))

    def test_fence_precedes_restart_changes_and_is_retryable(self):
        guard.fence_restarts(self.root, self.unit, self.run_command)
        self.assertEqual('draining\n', (self.root / '.courseultra-draining').read_text())
        guard.fence_restarts(self.root, self.unit, self.run_command)
        guard.verify_restart_fence(self.root, self.unit, self.run_command)
        self.assertFalse(any('stop' in call or 'kill' in call for call in self.calls))

    def test_missing_unloaded_or_modified_service_barrier_refuses(self):
        self.unit.write_text('[Unit]\n')
        with self.assertRaises(ValueError):
            guard.fence_restarts(self.root, self.unit, self.run_command)
        self.assertFalse(self.calls)
        self.unit.write_text('[Unit]\nConditionPathExists=!/opt/openvidu/.courseultra-draining\n')
        def unloaded(args):
            return '' if '--property=DropInPaths' in args else self.run_command(args)
        with self.assertRaises(ValueError):
            guard.fence_restarts(self.root, self.unit, unloaded)
        self.assertFalse(any(call[:2] == ['docker', 'update'] for call in self.calls))

    def test_failed_policy_update_retains_barrier_and_never_verifies(self):
        def failing(args):
            if args[:2] == ['docker', 'update']:
                raise RuntimeError('Docker unavailable')
            return self.run_command(args)
        with self.assertRaises(RuntimeError):
            guard.fence_restarts(self.root, self.unit, failing)
        self.assertTrue((self.root / '.courseultra-draining').is_file())
        with self.assertRaises(ValueError):
            guard.verify_restart_fence(self.root, self.unit, self.run_command)

    def test_fleet_reporter_raw_systemctl_newline_is_accepted_but_reload_is_not(self):
        def raw(args):
            return self.run_command(args) + '\n'
        guard.verify_drain_unit(self.unit, raw)
        for response in ['yes\n', '', 'no\nyes\n']:
            with self.assertRaises(ValueError):
                guard.verify_drain_unit(self.unit, lambda args: response if '--property=NeedDaemonReload' in args else raw(args))

    def test_verification_rejects_removed_marker_or_reenabled_restart(self):
        guard.fence_restarts(self.root, self.unit, self.run_command)
        self.nodes[0]['HostConfig']['RestartPolicy']['Name'] = 'always'
        with self.assertRaises(ValueError):
            guard.verify_restart_fence(self.root, self.unit, self.run_command)
        self.nodes[0]['HostConfig']['RestartPolicy']['Name'] = 'no'
        (self.root / '.courseultra-draining').unlink()
        with self.assertRaises((ValueError, OSError)):
            guard.verify_restart_fence(self.root, self.unit, self.run_command)

    def test_marker_symlink_does_not_overwrite_another_file(self):
        target = self.root / 'recording'
        target.write_text('preserve')
        (self.root / '.courseultra-draining').symlink_to(target)
        with self.assertRaises((ValueError, OSError)):
            guard.fence_restarts(self.root, self.unit, self.run_command)
        self.assertEqual('preserve', target.read_text())

    def test_recreated_container_during_fence_is_not_accepted(self):
        def replacing(args):
            value = self.run_command(args)
            if args[:2] == ['docker', 'update']:
                self.nodes[0]['Id'] = 'a' * 64
            return value
        with self.assertRaises(ValueError):
            guard.fence_restarts(self.root, self.unit, replacing)

    def test_watcher_retry_never_sends_second_shutdown_signal(self):
        guard.fence_restarts(self.root, self.unit, self.run_command)
        guard.signal_gracefully_once(self.root, self.unit, self.run_command)
        guard.signal_gracefully_once(self.root, self.unit, self.run_command)
        signals = [call for call in self.calls if call[:2] == ['docker', 'kill']]
        self.assertEqual(3, len(signals))
        self.assertTrue(all(call[2] == '--signal=SIGQUIT' for call in signals))

    def test_unknown_signal_result_is_not_replayed(self):
        guard.fence_restarts(self.root, self.unit, self.run_command)
        def uncertain(args):
            value = self.run_command(args)
            if args[:2] == ['docker', 'kill']:
                raise RuntimeError('Reply lost after delivery')
            return value
        with self.assertRaises(RuntimeError):
            guard.signal_gracefully_once(self.root, self.unit, uncertain)
        with self.assertRaises(ValueError):
            guard.signal_gracefully_once(self.root, self.unit, self.run_command)
        self.assertEqual(1, sum(call[:2] == ['docker', 'kill'] for call in self.calls))

    def test_restart_after_signal_holds_instead_of_resignaling(self):
        guard.fence_restarts(self.root, self.unit, self.run_command)
        guard.signal_gracefully_once(self.root, self.unit, self.run_command)
        self.nodes[0]['State']['StartedAt'] = '2026-09-22T11:00:00Z'
        with self.assertRaises(ValueError):
            guard.signal_gracefully_once(self.root, self.unit, self.run_command)
        self.assertEqual(3, sum(call[:2] == ['docker', 'kill'] for call in self.calls))


class RecordingStorageDrainTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = pathlib.Path(temporary.name).resolve()
        self.storage = self.root / 'data/egress_data/home/egress'
        for name in ('tmp', 'backup_storage'):
            (self.storage / name).mkdir(parents=True)
        self.node = {'Id': 'recorder-one', 'Name': '/egress',
                     'State': {'Status': 'exited', 'Running': False, 'Restarting': False,
                               'ExitCode': 0, 'OOMKilled': False},
                     'Mounts': [{'Destination': '/home/egress', 'Source': str(self.storage),
                                 'Type': 'bind', 'RW': True}]}

    def check(self, inspect=None):
        guard.verify_recording_storage(self.root, inspect or (lambda: copy.deepcopy(self.node)))

    def test_clean_stopped_recorder_and_empty_storage_pass_local_check(self):
        self.check()

    def test_mount_order_is_not_a_recording_identity_change(self):
        self.node['Mounts'].append({'Destination': '/etc/egress.yaml', 'Source': '/config/egress.yaml',
                                    'Type': 'bind', 'RW': False})
        after = copy.deepcopy(self.node)
        after['Mounts'].reverse()
        snapshots = iter([self.node, after])
        self.check(lambda: next(snapshots))
        self.assertEqual(guard.stable_container(self.node), guard.stable_container(after))
        for key, value in [('Source', '/different'), ('RW', True)]:
            changed = copy.deepcopy(after)
            changed['Mounts'][0][key] = value
            snapshots = iter([self.node, changed])
            with self.assertRaises(ValueError):
                self.check(lambda: next(snapshots))

    def test_stable_container_preserves_duplicate_mounts_and_process_changes(self):
        changed = copy.deepcopy(self.node)
        changed['Mounts'].append(copy.deepcopy(changed['Mounts'][0]))
        self.assertNotEqual(guard.stable_container(self.node), guard.stable_container(changed))
        changed = copy.deepcopy(self.node)
        changed['State']['ExitCode'] = 137
        self.assertNotEqual(guard.stable_container(self.node), guard.stable_container(changed))
        with self.assertRaises(ValueError):
            guard.stable_container({'Mounts': ['invalid']})

    def test_retained_recording_or_hidden_artifact_blocks_removal(self):
        for folder in ('tmp', 'backup_storage'):
            with self.subTest(folder=folder):
                artifact = self.storage / folder / '.failed-upload'
                artifact.write_text('preserve')
                with self.assertRaises(ValueError):
                    self.check()
                self.assertEqual('preserve', artifact.read_text())
                artifact.unlink()

    def test_even_empty_job_directory_is_not_automatic_cleanup_authority(self):
        (self.storage / 'tmp' / 'EG_unknown').mkdir()
        with self.assertRaises(ValueError):
            self.check()

    def test_missing_directory_is_unknown_not_empty(self):
        (self.storage / 'tmp').rmdir()
        with self.assertRaises((ValueError, OSError)):
            self.check()

    def test_symlinked_recovery_path_blocks_removal(self):
        (self.storage / 'tmp').rmdir()
        (self.storage / 'tmp').symlink_to(self.storage / 'backup_storage', target_is_directory=True)
        with self.assertRaises(ValueError):
            self.check()

    def test_wrong_or_shadowed_storage_bind_blocks_removal(self):
        original = copy.deepcopy(self.node)
        for mount in ({'Destination': '/home/egress/tmp', 'Source': '/elsewhere', 'Type': 'bind'},
                      {'Destination': '/home', 'Source': '/elsewhere', 'Type': 'bind'}):
            self.node = copy.deepcopy(original)
            self.node['Mounts'].append(mount)
            with self.assertRaises(ValueError):
                self.check()
        self.node = copy.deepcopy(original)
        self.node['Mounts'][0]['Source'] = '/elsewhere'
        with self.assertRaises(ValueError):
            self.check()

    def test_abnormal_or_running_recorder_blocks_removal(self):
        for changes in ({'Running': True}, {'Restarting': True}, {'ExitCode': 137},
                        {'OOMKilled': True}, {'Status': 'created'}):
            original = copy.deepcopy(self.node)
            self.node['State'].update(changes)
            with self.assertRaises(ValueError):
                self.check()
            self.node = original

    def test_preserved_archive_and_unfinished_intent_block_removal(self):
        folder = self.root / 'courseultra-recorder-guard'
        folder.mkdir()
        lock = folder / 'start.lock'
        lock.write_text('unfinished')
        with self.assertRaises(ValueError):
            self.check()
        lock.write_text('')
        self.check()
        archive = folder / 'preserved'
        archive.mkdir()
        self.check()
        (archive / 'operation').mkdir()
        with self.assertRaises(ValueError):
            self.check()

    def test_recorder_identity_change_during_observation_blocks_removal(self):
        changed = copy.deepcopy(self.node)
        changed['Id'] = 'replacement-recorder'
        snapshots = iter([self.node, changed])
        with self.assertRaises(ValueError):
            self.check(lambda: next(snapshots))

    def test_unreadable_optional_preservation_directory_is_not_absence(self):
        original = pathlib.Path.lstat
        def observe(path):
            if path == self.root / 'courseultra-recorder-guard':
                raise PermissionError('unavailable')
            return original(path)
        with patch.object(pathlib.Path, 'lstat', observe), self.assertRaises(PermissionError):
            self.check()


def integer(value):
    data = b''
    while value > 127:
        data += bytes([(value & 127) | 128])
        value >>= 7
    return data + bytes([value])


def field(number, value):
    if isinstance(value, int):
        return integer(number << 3) + integer(value)
    return integer((number << 3) | 2) + integer(len(value)) + value


def native(state=1, updated=100, node_id=b'ND_peer'):
    return (field(1, node_id) + field(2, b'203.0.113.2')
            + field(4, field(2, updated)) + field(6, state))


class DrainReadinessTest(unittest.TestCase):
    def test_occupied_media_is_checked_before_restart_exclusion(self):
        text = (MODULE.parent / 'tf-do-openvidu-elastic.tf').read_text()
        self.assertIn('verify_ready_floor --require-idle-media --fence-restarts', text)

    def test_start_barrier_is_installed_before_media_vendor_start(self):
        text = (MODULE.parent / 'tf-do-openvidu-elastic.tf').read_text()
        bootstrap = text.split('user_data_media = <<-EOF', 1)[1].split('\nEOF', 1)[0]
        self.assertIn('${chomp(file("${path.module}/media-drain-start-barrier.conf"))}', bootstrap)
        self.assertLess(bootstrap.index('/etc/systemd/system/openvidu.service.d/40-courseultra-drain.conf'),
                        bootstrap.index('${local.recorder_guard_barrier}/usr/local/bin/install.sh'))
        self.assertEqual(guard.DRAIN_CONDITION, (MODULE.parent / 'media-drain-start-barrier.conf').read_text())

    def test_guard_is_installed_in_media_bootstrap_before_start(self):
        text = (MODULE.parent / 'tf-do-openvidu-elastic.tf').read_text()
        bootstrap = text.split('user_data_media = <<-EOF', 1)[1].split('\nEOF', 1)[0]
        self.assertIn('${var.capacityReservationsEnabled ? local.capacity_python_sources["media_drain_guard.py"] : file("${path.module}/media_drain_guard.py")}', bootstrap)
        self.assertLess(bootstrap.index('chmod 700 /usr/local/bin/courseultra-media-drain-guard'),
                        bootstrap.index('systemctl start openvidu'))

    def setUp(self):
        self.droplet = {'id': 2, 'status': 'active', 'tags': ['media'], 'vpc_uuid': 'vpc',
                        'networks': {'v4': [{'type': 'private', 'ip_address': '10.10.30.2'},
                                           {'type': 'public', 'ip_address': '203.0.113.2'}]}}
        self.reg = {b'ND_peer': {'nodeId': 'ND_peer', 'privateIp': '10.10.30.2',
                                'nodeIp': '203.0.113.2'}}
        self.nodes = {b'ND_peer': native()}

    def ready(self, health=lambda address: True):
        return guard.ready_peers([self.droplet], self.reg, self.nodes, '1',
                                 'media', 'draining', 'vpc', 105, health)

    def test_registered_serving_healthy_replacement_counts(self):
        self.assertEqual(self.nodes, self.ready())

    def test_cloud_active_unregistered_replacement_does_not_count(self):
        self.reg.clear()
        self.assertEqual({}, self.ready())

    def test_stale_registration_without_native_node_does_not_count(self):
        self.nodes.clear()
        self.assertEqual({}, self.ready())

    def test_stale_or_future_heartbeat_does_not_count(self):
        for updated in [0, 94, 106]:
            with self.subTest(updated=updated):
                self.nodes[b'ND_peer'] = native(updated=updated)
                self.assertEqual({}, self.ready())

    def test_starting_shutting_down_or_suspended_node_does_not_count(self):
        for state in [0, 2, 3]:
            with self.subTest(state=state):
                self.nodes[b'ND_peer'] = native(state=state)
                self.assertEqual({}, self.ready())

    def test_unhealthy_node_does_not_count(self):
        self.assertEqual({}, self.ready(lambda address: False))

    def test_drain_requested_node_cannot_be_spare_capacity(self):
        self.droplet['tags'].append('draining')
        self.assertEqual({}, self.ready())

    def test_wrong_generation_or_identity_does_not_count(self):
        self.nodes[b'ND_peer'] = native(node_id=b'ND_previous')
        self.assertEqual({}, self.ready())
        self.nodes[b'ND_peer'] = native()
        self.reg[b'ND_peer']['nodeIp'] = '203.0.113.9'
        self.assertEqual({}, self.ready())

    def test_other_vpc_fails_closed(self):
        self.droplet['vpc_uuid'] = 'other-vpc'
        with self.assertRaises(ValueError):
            self.ready()

    def test_malformed_protobuf_fails_closed(self):
        for data in [b'\x0a\xff', b'\x00', b'\x08\x01\x08\x02', b'\x0f']:
            with self.subTest(data=data), self.assertRaises(ValueError):
                guard.protobuf_fields(data)

    def test_unknown_well_formed_fields_are_supported(self):
        self.nodes[b'ND_peer'] += field(25, b'future')
        self.assertEqual(self.nodes, self.ready())

    def idle(self, stopped=False, now=105, room_nodes=None, application_fenced=False):
        state = {'Status': 'exited' if stopped else 'running', 'ExitCode': 0,
                 'Running': not stopped, 'Restarting': False, 'OOMKilled': False}
        nodes = [{'Id': str(index) * 64, 'Name': '/' + name, 'State': state}
                 for index, name in enumerate(('openvidu', 'ingress', 'egress'), 1)]
        def run(args):
            if args[:2] == ['docker', 'ps']:
                return ''
            if args[:2] == ['docker', 'inspect']:
                return json.dumps(nodes)
            self.fail('Unexpected mutation: ' + str(args))
        guard.verify_idle_media(self.reg, self.nodes, '10.10.30.2', ['203.0.113.2'], now, run,
                                room_nodes=room_nodes, application_fenced=application_fenced)

    def signaling_clients(self):
        self.nodes[b'ND_peer'] = (field(1, b'ND_peer') + field(2, b'203.0.113.2')
                + field(4, field(2, 100) + field(4, 102)) + field(6, 1))
        self.reg[b'ND_other'] = {'nodeId': 'ND_other', 'nodeIp': '203.0.113.3', 'privateIp': '10.10.30.3'}
        self.nodes[b'ND_other'] = (field(1, b'ND_other') + field(2, b'203.0.113.3')
                + field(4, field(2, 100)) + field(6, 1))

    def test_remote_signaling_clients_hold_even_with_exact_nonlocal_room_map(self):
        self.signaling_clients()
        with self.assertRaisesRegex(ValueError, 'Active signaling clients'):
            self.idle(room_nodes=lambda: [b'class-on-peer', b'ND_other'], application_fenced=True)

    def test_last_remote_client_leaving_allows_idle_retry_while_peer_remains(self):
        self.signaling_clients()
        with self.assertRaisesRegex(ValueError, 'Active signaling clients'):
            self.idle(room_nodes=lambda: [b'class-on-peer', b'ND_other'], application_fenced=True)
        self.nodes[b'ND_peer'] = (field(1, b'ND_peer') + field(2, b'203.0.113.2')
                + field(4, field(2, 100)) + field(6, 1))
        self.idle(room_nodes=lambda: [b'class-on-peer', b'ND_other'], application_fenced=True)

    def test_signaling_clients_hold_regardless_of_authority_or_room_mapping(self):
        self.signaling_clients()
        for mapping in (None, [], [b'class', b'ND_peer'], [b'class', b'ND_unknown'], [b'class'],
                        [b'class', b''], [b'class', b'ND_other', b'class', b'ND_other']):
            with self.subTest(mapping=mapping), self.assertRaises(ValueError):
                self.idle(room_nodes=lambda: mapping, application_fenced=True)
        with self.assertRaises(ValueError):
            self.idle(room_nodes=lambda: [b'class', b'ND_other'])

    def test_signaling_clients_hold_without_querying_peer_mapping(self):
        self.signaling_clients()
        def failed():
            self.fail('Peer mapping cannot waive active signaling occupancy')
        with self.assertRaisesRegex(ValueError, 'Active signaling clients'):
            self.idle(room_nodes=failed, application_fenced=True)

    def test_local_media_and_clients_hold_regardless_of_peer_readiness(self):
        for counter in (3, 5, 6):
            self.signaling_clients()
            self.nodes[b'ND_peer'] = (field(1, b'ND_peer') + field(2, b'203.0.113.2')
                    + field(4, field(2, 100) + field(4, 102) + field(counter, 1)) + field(6, 1))
            with self.subTest(counter=counter), self.assertRaises(ValueError):
                self.idle(room_nodes=lambda: [b'class', b'ND_other'], application_fenced=True)
        self.signaling_clients()
        self.nodes[b'ND_other'] = (field(1, b'ND_other') + field(2, b'203.0.113.3')
                + field(4, field(2, 90)) + field(6, 1))
        with self.assertRaises(ValueError):
            self.idle(room_nodes=lambda: [b'class', b'ND_other'], application_fenced=True)

    def test_fresh_zero_counters_allow_only_media_idle_check(self):
        self.idle()

    def test_any_room_client_or_track_vetoes_initial_drain(self):
        for counter in (3, 4, 5, 6):
            with self.subTest(counter=counter):
                self.nodes[b'ND_peer'] = (field(1, b'ND_peer') + field(2, b'203.0.113.2')
                        + field(4, field(2, 100) + field(counter, 1)) + field(6, 1))
                with self.assertRaises(ValueError):
                    self.idle()

    def test_missing_stale_or_changed_registration_is_not_idle(self):
        for blob in (None, native(updated=90), native(state=2), native(node_id=b'ND_old')):
            with self.subTest(blob=blob):
                self.nodes = {b'ND_peer': blob}
                with self.assertRaises(ValueError):
                    self.idle()

    def test_cleanly_stopped_retry_needs_no_serving_registration(self):
        self.reg.clear()
        self.nodes.clear()
        self.idle(stopped=True)

    def test_running_unregistered_node_does_not_look_idle(self):
        self.reg.clear()
        with self.assertRaises(ValueError):
            self.idle()

    def test_idle_observation_checks_current_time_after_inspection(self):
        with patch.object(guard.time, 'time', return_value=111), self.assertRaises(ValueError):
            self.idle(now=None)

    def test_idle_observation_rejects_wrong_cloud_address(self):
        self.reg[b'ND_peer']['nodeIp'] = '203.0.113.99'
        with self.assertRaises(ValueError):
            self.idle()


if __name__ == '__main__':
    unittest.main()
