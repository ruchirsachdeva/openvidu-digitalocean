"""Filesystem/proc fixtures only; no cloud, Docker, recording deletion or release."""
import importlib.util
import os
from pathlib import Path
import socket
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('recorder_storage_probe', ROOT / 'recorder-storage-probe.py')
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


class RecorderStorageProbeTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        # macOS /var is a symlink; the production collector intentionally refuses that.
        self.base = Path(self.temp.name).resolve()
        self.storage = self.base / 'egress'
        self.proc = self.base / 'proc'
        for name in ('tmp', 'backup_storage'):
            (self.storage / name).mkdir(parents=True)
        boot = self.proc / 'sys/kernel/random/boot_id'
        boot.parent.mkdir(parents=True)
        boot.write_text('campaign-boot\n')
        self.process(1, 'init')

    def process(self, pid, name, links=()):
        path = self.proc / str(pid)
        (path / 'fd').mkdir(parents=True)
        (path / 'comm').write_text(name + '\n')
        # Fields 3..21, then process birth field 22; comm deliberately has parentheses.
        (path / 'stat').write_text(str(pid) + ' (test (process)) ' + ' '.join(['S'] * 19 + ['1234']))
        for index, target in enumerate(links):
            (path / 'fd' / str(index)).symlink_to(target)
        return path

    def observe(self, **kwargs):
        return probe.observe(self.storage, self.proc, **kwargs)

    def socket_process(self, pid=22, namespace='net:[71]', inode=9001, path=None):
        path = path or '/home/egress/tmp/NE_exact/service_ipc.sock'
        process = self.process(pid, 'egress', [f'socket:[{inode}]'])
        (process / 'ns').mkdir()
        (process / 'ns/net').symlink_to(namespace)
        (process / 'ns/mnt').symlink_to('mnt:[81]')
        (process / 'net').mkdir()
        (process / 'net/unix').write_text(
            'Num       RefCount Protocol Flags    Type St Inode Path\n'
            f'00000000: 00000002 00000000 00010000 0001 01 {inode} {path}\n')
        return process

    def test_socket_ownership_joins_kernel_inode_not_filesystem_inode(self):
        self.socket_process()
        sample = self.observe()
        self.assertEqual([], sample['openFiles'])
        sockets = sample['unixSockets']
        self.assertEqual(1, len(sockets))
        self.assertEqual(9001, sockets[0]['kernelInode'])
        self.assertEqual('/home/egress/tmp/NE_exact/service_ipc.sock', sockets[0]['path'])
        self.assertEqual('net:[71]', sockets[0]['netNamespace'])
        self.assertEqual([dict(pid=22, startedTicks=1234, fd='0', mountNamespace='mnt:[81]')], sockets[0]['owners'])
        self.assertNotIn('filesystemInode', sockets[0])
        self.assertNotIn('releasable', sample)

    def test_same_kernel_inode_in_other_namespace_does_not_join(self):
        self.socket_process()
        self.socket_process(pid=23, namespace='net:[72]', path='/unrelated/private.sock')
        sample = self.observe()
        self.assertEqual(1, len(sample['unixSockets']))
        self.assertEqual([22], [owner['pid'] for owner in sample['unixSockets'][0]['owners']])
        self.assertNotIn('/unrelated/private.sock', str(sample))

    def test_socket_table_missing_or_invalid_is_unknown_not_no_listener(self):
        process = self.socket_process()
        for content in (None, 'invalid header\n',
                        'Num RefCount Protocol Flags Type St Inode Path\ninvalid row\n'):
            if content is None:
                (process / 'net/unix').unlink()
            else:
                (process / 'net/unix').write_text(content)
            sample = self.observe()
            self.assertFalse(sample['complete'])
            self.assertIn('unix_socket_inventory_incomplete', sample['issues'])

    def test_relevant_unowned_socket_holds(self):
        process = self.socket_process()
        (process / 'fd/0').unlink()
        (process / 'fd/0').symlink_to('socket:[9999]')
        sample = self.observe()
        self.assertFalse(sample['complete'])
        self.assertIn('unix_socket_owner_unobserved', sample['issues'])
        self.assertEqual([], sample['unixSockets'][0]['owners'])

    def test_socket_descriptor_or_namespace_change_is_not_stable_ownership(self):
        process = self.socket_process()
        original = os.readlink
        for changed in ('fd/0', 'ns/net', 'ns/mnt'):
            counts = {}
            def readlink(path, *args, **kwargs):
                value = original(path, *args, **kwargs)
                key = str(path)
                counts[key] = counts.get(key, 0) + 1
                if key == str(process / changed) and counts[key] > 1:
                    return value.replace('9001', '9002').replace('71', '72').replace('81', '82')
                return value
            with patch.object(probe.os, 'readlink', readlink):
                sample = self.observe()
            self.assertFalse(sample['complete'], changed)
            self.assertTrue({'socket_descriptor_changed', 'process_namespace_changed'} & set(sample['issues']))

    def test_unix_table_changes_after_fd_join_are_explicit(self):
        self.socket_process()
        original = probe.read_unix_sockets
        count = 0
        def read(*args, **kwargs):
            nonlocal count
            value = original(*args, **kwargs)
            count += 1
            return value if count == 1 else {}
        with patch.object(probe, 'read_unix_sockets', read):
            sample = self.observe()
        self.assertFalse(sample['complete'])
        self.assertIn('unix_socket_inventory_changed', sample['issues'])

    def test_unix_table_bounds_and_duplicate_identities_hold(self):
        process = self.socket_process()
        table = process / 'net/unix'
        original = table.read_text()
        for content in (original + original.splitlines(keepends=True)[1],
                        original + 'x' * 5000 + '\n'):
            table.write_text(content)
            sample = self.observe()
            self.assertFalse(sample['complete'])
            self.assertIn('unix_socket_inventory_incomplete', sample['issues'])
        table.write_text(original + ''.join(
            f'00000000: 00000002 00000000 00000000 0001 01 {n}\n'
            for n in range(10000, 10100)))
        sample = self.observe(limit=30)
        self.assertFalse(sample['complete'])
        self.assertIn('observation_limit', sample['issues'])

    @unittest.skipUnless(sys.platform == 'linux', 'Real /proc socket ownership requires Linux')
    def test_real_linux_socket_owner_disappears_on_close_but_storage_remains(self):
        path = self.storage / 'tmp/real-ipc'
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
            listener.bind(str(path))
            listener.listen(1)
            descriptor = str(listener.fileno())
            kernel = int(os.readlink('/proc/self/fd/' + descriptor)[8:-1])
            active = probe.observe(self.storage, Path('/proc'))
            rows = [row for row in active['unixSockets'] if row['path'] == str(path)]
            self.assertEqual(1, len(rows), active['issues'])
            self.assertEqual(kernel, rows[0]['kernelInode'])
            self.assertIn((os.getpid(), descriptor), [(owner['pid'], owner['fd']) for owner in rows[0]['owners']])
            self.assertFalse(active['complete'])
            self.assertEqual(['unresolved_file_type'], active['issues'])
        stopped = probe.observe(self.storage, Path('/proc'))
        self.assertFalse(any(row['path'] == str(path) for row in stopped['unixSockets']))
        self.assertTrue(stat.S_ISSOCK(path.lstat().st_mode))
        self.assertFalse(stopped['complete'])
        self.assertEqual(['unresolved_file_type'], stopped['issues'])

    def test_clean_sample_has_both_roots_and_no_release_flag(self):
        sample = self.observe()
        self.assertTrue(sample['complete'], sample)
        self.assertEqual(['tmp', 'backup_storage'], [root['name'] for root in sample['roots']])
        self.assertTrue(all(root['entries'] == [] for root in sample['roots']))
        self.assertEqual('campaign-boot', sample['bootId'])
        self.assertNotIn('releasable', sample)
        self.assertNotIn('settled', sample)
        self.assertLessEqual(sample['startedAt'], sample['finishedAt'])

    def test_all_files_including_hidden_sidecars_are_retained_and_counted(self):
        job = self.storage / 'tmp/EG_exact'
        job.mkdir()
        media = job / 'video.mp4'
        media.write_bytes(b'preserve original')
        sidecar = self.storage / 'backup_storage/.sidecar'
        sidecar.write_bytes(b'not a media extension')
        sample = self.observe()
        self.assertTrue(sample['complete'])  # Complete inventory is NOT empty/settled.
        files = {entry['path']: entry for root in sample['roots'] for entry in root['entries']}
        self.assertEqual(17, files['EG_exact/video.mp4']['bytes'])
        self.assertEqual('file', files['.sidecar']['kind'])
        self.assertIn('inode', files['EG_exact/video.mp4'])
        self.assertEqual(b'preserve original', media.read_bytes())
        self.assertEqual(b'not a media extension', sidecar.read_bytes())

    def test_symlink_never_traverses_outside_tree(self):
        outside = self.base / 'outside'
        outside.mkdir()
        (outside / 'must-not-enumerate').write_text('private')
        (self.storage / 'tmp/link').symlink_to(outside, target_is_directory=True)
        sample = self.observe()
        self.assertFalse(sample['complete'])
        self.assertIn('unresolved_file_type', sample['issues'])
        self.assertEqual(['link'], [entry['path'] for entry in sample['roots'][0]['entries']])

    def test_missing_root_or_symlinked_ancestor_is_not_empty_proof(self):
        (self.storage / 'tmp').rmdir()
        self.assertFalse(self.observe()['complete'])
        (self.storage / 'tmp').mkdir()
        alias = self.base / 'alias'
        alias.symlink_to(self.storage, target_is_directory=True)
        sample = probe.observe(alias, self.proc)
        self.assertFalse(sample['complete'])
        self.assertIn('storage_inventory_incomplete', sample['issues'])

    def test_open_deleted_files_and_container_path_alias_are_visible(self):
        self.process(22, 'egress', ['/home/egress/tmp/EG_exact/video.mp4 (deleted)',
                     str(self.storage / 'backup_storage/EG_exact.mp4'), '/unrelated/file'])
        sample = self.observe()
        self.assertTrue(sample['complete'])
        self.assertEqual(2, len(sample['openFiles']))
        # Directory enumeration order is not stable across Linux and macOS.
        descriptors = {entry['fd']: entry for entry in sample['openFiles']}
        self.assertEqual(1234, descriptors['0']['startedTicks'])
        self.assertTrue(descriptors['0']['deleted'])
        self.assertFalse(descriptors['1']['deleted'])
        self.assertEqual([dict(pid=22, startedTicks=1234, name='egress')], sample['processes'])

    def test_process_failure_and_missing_boot_identity_hold(self):
        process = self.process(22, 'egress')
        (process / 'stat').unlink()
        (self.proc / 'sys/kernel/random/boot_id').unlink()
        sample = self.observe()
        self.assertFalse(sample['complete'])
        self.assertIn('process_inventory_incomplete', sample['issues'])
        self.assertIn('boot_identity_unavailable', sample['issues'])

    def test_entry_bound_and_time_bound_are_explicit_not_partial_success(self):
        (self.storage / 'tmp/one').touch()
        (self.storage / 'tmp/two').touch()
        for options in (dict(limit=1), dict(seconds=1e-12)):
            with self.subTest(options=options):
                sample = self.observe(**options)
                self.assertFalse(sample['complete'])
                self.assertIn('observation_limit', sample['issues'])

    def test_permission_failure_is_explicit_and_fifo_is_never_opened(self):
        os.mkfifo(self.storage / 'tmp/pipe')
        sample = self.observe()
        self.assertFalse(sample['complete'])
        self.assertEqual('special', sample['roots'][0]['entries'][0]['kind'])
        self.assertEqual('fifo', sample['roots'][0]['entries'][0]['specialType'])
        self.assertEqual(stat.S_IFIFO, sample['roots'][0]['entries'][0]['fileTypeBits'])
        with patch.object(probe.os, 'scandir', side_effect=PermissionError):
            sample = self.observe()
        self.assertFalse(sample['complete'])
        self.assertIn('storage_inventory_incomplete', sample['issues'])
        self.assertIn('process_inventory_incomplete', sample['issues'])

    def test_unix_socket_is_described_but_never_mistaken_for_released_storage(self):
        # Keep the path short enough for macOS's Unix-domain socket limit.
        path = self.storage / 'tmp/ipc'
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as service:
            service.bind(str(path))
            service.listen(1)
            for active in (True, False):
                if not active:
                    service.close()  # A stopped service still leaves its socket inode.
                sample = self.observe()
                self.assertFalse(sample['complete'])
                self.assertIn('unresolved_file_type', sample['issues'])
                entry = sample['roots'][0]['entries'][0]
                self.assertEqual('special', entry['kind'])
                self.assertEqual('socket', entry['specialType'])
                self.assertEqual(stat.S_IFSOCK, entry['fileTypeBits'])
                self.assertTrue(stat.S_ISSOCK(path.lstat().st_mode))
                self.assertNotIn('releasable', sample)

    def test_socket_name_does_not_change_regular_file_or_symlink_classification(self):
        fake = self.storage / 'tmp/service_ipc.sock'
        fake.write_bytes(b'preserve unknown regular data')
        link = self.storage / 'tmp/handler_ipc.sock'
        link.symlink_to(fake)
        sample = self.observe()
        entries = {entry['path']: entry for entry in sample['roots'][0]['entries']}
        self.assertEqual('file', entries[fake.name]['kind'])
        self.assertEqual(stat.S_IFREG, entries[fake.name]['fileTypeBits'])
        self.assertEqual('symlink', entries[link.name]['kind'])
        self.assertEqual(stat.S_IFLNK, entries[link.name]['fileTypeBits'])
        self.assertTrue(all('specialType' not in entry for entry in entries.values()))
        self.assertFalse(sample['complete'])
        self.assertEqual(b'preserve unknown regular data', fake.read_bytes())

    def test_invalid_bounds_are_rejected(self):
        for kwargs in (dict(limit=0), dict(seconds=0)):
            with self.assertRaises(ValueError):
                self.observe(**kwargs)

    def test_last_read_overrunning_deadline_is_not_complete(self):
        # Start, two roots, one process, then final elapsed-time observation.
        with patch.object(probe.time, 'monotonic', side_effect=[0, 0, 0, 0, 20]):
            sample = self.observe(seconds=10)
        self.assertFalse(sample['complete'])
        self.assertIn('observation_limit', sample['issues'])
        self.assertEqual(20, sample['elapsedSeconds'])

    def test_empty_process_inventory_cannot_be_mistaken_for_idle_linux(self):
        process = self.proc / '1'
        (process / 'fd').rmdir()
        (process / 'stat').unlink()
        (process / 'comm').unlink()
        process.rmdir()
        sample = self.observe()
        self.assertFalse(sample['complete'])
        self.assertIn('process_inventory_empty', sample['issues'])

    def test_process_reuse_and_boot_change_make_sample_incomplete(self):
        original = Path.read_text
        counts = {}

        def read(path, *args, **kwargs):
            text = original(path, *args, **kwargs)
            counts[str(path)] = counts.get(str(path), 0) + 1
            if counts[str(path)] > 1:
                if path.name == 'stat':
                    return text.replace('1234', '5678')
                if path.name == 'boot_id':
                    return 'new-boot\n'
            return text

        with patch.object(Path, 'read_text', read):
            sample = self.observe()
        self.assertFalse(sample['complete'])
        self.assertIn('process_changed', sample['issues'])
        self.assertIn('boot_identity_changed', sample['issues'])


if __name__ == '__main__':
    unittest.main()
