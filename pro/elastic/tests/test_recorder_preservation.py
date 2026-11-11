"""Synthetic IPC only. Linux tests use actual renameat2; no provider or cloud."""
import fcntl
import importlib.util
import os
from pathlib import Path
import socket
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('preservation', ROOT / 'preserve-recorder-ipc.py')
recovery = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(recovery)


class Crash(BaseException):
    pass


@unittest.skipUnless(sys.platform == 'linux', 'Actual preservation requires Linux renameat2')
class RecorderPreservationTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.storage = self.base / 'storage'
        self.control = self.base / 'control'
        self.control.mkdir(mode=0o700)
        self.lock = self.control / 'start.lock'
        self.lock.touch(mode=0o640)
        (self.storage / 'tmp').mkdir(parents=True)
        (self.storage / 'backup_storage').mkdir()
        self.plan = dict(version=1, operationId='00000000-0000-4000-8000-000000000001',
            binding=dict(bootId='00000000-0000-4000-8000-000000000002', containerId='1' * 64,
                         imageDigest='sha256:' + '2' * 64, configSha256='3' * 64,
                         evidenceSha256='4' * 64, serviceNodeId='NE_exact', startedTicks=1234), artifacts=[])
        for name in ('NE_exact', 'EGH_exact'):
            directory = self.storage / 'tmp' / name
            directory.mkdir(mode=0o755)
            inode = None
            if name.startswith('NE_'):
                path = directory / 'service_ipc.sock'
                with socket.socket(socket.AF_UNIX) as service:
                    service.bind(str(path))
                path.chmod(0o755)
                inode = recovery.identity(path.lstat())
            self.plan['artifacts'].append(dict(name=name, recordingId=None if inode else 'EG_exact',
                identity=recovery.identity(directory.lstat()), socket=inode))
        self.destination = self.control / 'preserved' / self.plan['operationId']
        self.verifications = 0

    def verify(self, plan):
        self.assertEqual(self.plan, plan)
        self.verifications += 1

    def run_recovery(self):
        return recovery.preserve(self.storage, self.control, self.plan, self.verify)

    def assert_preserved(self):
        self.assertEqual([], list((self.storage / 'tmp').iterdir()))
        for item in self.plan['artifacts']:
            self.assertEqual(item['identity'], recovery.identity((self.destination / item['name']).lstat()))
        self.assertEqual(recovery.encode_plan(self.plan), (self.destination / 'receipt.json').read_bytes())
        self.assertEqual(b'', self.lock.read_bytes())

    def test_preserves_exact_inodes_and_replays_completed_receipt_without_another_move(self):
        inode = self.lock.stat().st_ino
        self.assertTrue(self.run_recovery()['receiptDurable'])
        self.assert_preserved()
        with patch.object(recovery, 'rename_noreplace', side_effect=AssertionError('Replay moved data')):
            self.assertTrue(self.run_recovery()['replayed'])
        self.assertEqual(inode, self.lock.stat().st_ino)
        self.assertGreaterEqual(self.verifications, 4)

    def test_unknown_contents_backup_and_unmapped_handler_hold_before_intent(self):
        for path in (self.storage / 'tmp/NE_exact/recording.mp4', self.storage / 'backup_storage/upload',
                     self.storage / 'tmp/EGH_unknown'):
            path.write_bytes(b'preserve')
            with self.assertRaises(ValueError): self.run_recovery()
            self.assertEqual(b'preserve', path.read_bytes())
            self.assertEqual(b'', self.lock.read_bytes())
            path.unlink()

    def test_untrusted_verifier_or_changed_generation_cannot_move(self):
        with self.assertRaises(ValueError):
            recovery.preserve(self.storage, self.control, self.plan, None)
        def stale(_):
            raise ValueError('Fresh no-writer or generation evidence missing')
        with self.assertRaises(ValueError):
            recovery.preserve(self.storage, self.control, self.plan, stale)
        with self.assertRaises(ValueError):
            recovery.preserve(self.storage, self.control, self.plan, lambda _: False)
        self.assertEqual(b'', self.lock.read_bytes())
        self.assertEqual(2, len(list((self.storage / 'tmp').iterdir())))

    def test_partial_or_different_intent_is_not_overwritten(self):
        for intent in (b'{partial', b'{}', recovery.encode_plan(dict(self.plan, operationId='00000000-0000-4000-8000-000000000009'))):
            self.lock.write_bytes(intent)
            with self.assertRaises(ValueError): self.run_recovery()
            self.assertEqual(intent, self.lock.read_bytes())
            self.assertEqual(2, len(list((self.storage / 'tmp').iterdir())))

    def test_competing_maintenance_holds(self):
        with self.lock.open('rb') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaises(BlockingIOError): self.run_recovery()
        self.assertEqual(b'', self.lock.read_bytes())

    def test_crash_after_each_durability_boundary_resumes_exact_plan(self):
        # Baseline two artifacts: intent, archive, operation, two rename pairs,
        # final parent pair, receipt, receipt parent, cleared intent.
        original = recovery.os.fsync
        for boundary in range(1, 13):
            with self.subTest(boundary=boundary):
                fixture = RecorderPreservationTest()
                fixture.setUp()
                count = 0
                def crash(fd):
                    nonlocal count
                    original(fd)
                    count += 1
                    if count == boundary:
                        raise Crash()
                try:
                    with patch.object(recovery.os, 'fsync', crash):
                        with self.assertRaises(Crash): fixture.run_recovery()
                    fixture.run_recovery()
                    fixture.assert_preserved()
                finally:
                    fixture.doCleanups()

    def test_before_fsync_failures_resume_with_required_flushes_before_moves_and_clear(self):
        original_sync = recovery.os.fsync
        original_move = recovery.rename_noreplace
        original_clear = recovery.os.ftruncate
        for boundary in range(1, 12):  # Final clear has a committed receipt already.
            with self.subTest(boundary=boundary):
                fixture = RecorderPreservationTest()
                fixture.setUp()
                count = 0
                def crash(fd):
                    nonlocal count
                    count += 1
                    if count == boundary:
                        raise Crash()
                    original_sync(fd)
                try:
                    with patch.object(recovery.os, 'fsync', crash):
                        with self.assertRaises(Crash): fixture.run_recovery()
                    events = []
                    def sync(fd):
                        events.append(('sync', os.readlink('/proc/self/fd/' + str(fd))))
                        original_sync(fd)
                    def move(*args):
                        events.append(('move', args[1]))
                        original_move(*args)
                    def clear(fd, size):
                        events.append(('clear', size))
                        original_clear(fd, size)
                    with patch.object(recovery.os, 'fsync', sync), patch.object(recovery, 'rename_noreplace', move), patch.object(recovery.os, 'ftruncate', clear):
                        fixture.run_recovery()
                    cleared = events.index(('clear', 0))
                    first_move = next((i for i, item in enumerate(events) if item[0] == 'move'), cleared)
                    for path in (fixture.lock, fixture.control, fixture.control / 'preserved'):
                        self.assertLess(events.index(('sync', str(path))), first_move, events)
                    receipt = events.index(('sync', str(fixture.destination / 'receipt.json')))
                    self.assertLess(events.index(('sync', str(fixture.storage / 'tmp'))), receipt, events)
                    self.assertLess(events.index(('sync', str(fixture.destination))), receipt, events)
                    self.assertLess(receipt, cleared, events)
                    self.assertIn(('sync', str(fixture.destination)), events[receipt + 1:cleared])
                    fixture.assert_preserved()
                finally:
                    fixture.doCleanups()

    def test_crash_after_rename_before_fsync_recognizes_same_destination(self):
        original = recovery.rename_noreplace
        def crash(*args):
            original(*args)
            raise Crash()
        with patch.object(recovery, 'rename_noreplace', crash):
            with self.assertRaises(Crash): self.run_recovery()
        self.assertNotEqual(b'', self.lock.read_bytes())
        self.run_recovery()
        self.assert_preserved()

    def test_partial_intent_and_failed_move_retain_barrier_without_deleting(self):
        def partial(fd, body):
            os.write(fd, body[:10])
            raise OSError('Simulated disk write failure')
        with patch.object(recovery, 'write_all', partial):
            with self.assertRaises(OSError): self.run_recovery()
        self.assertEqual(recovery.encode_plan(self.plan)[:10], self.lock.read_bytes())
        with self.assertRaises(ValueError): self.run_recovery()
        self.assertEqual(2, len(list((self.storage / 'tmp').iterdir())))
        # Separate synthetic fixture: a valid journal survives a failed rename.
        fixture = RecorderPreservationTest()
        fixture.setUp()
        try:
            with patch.object(recovery, 'rename_noreplace', side_effect=OSError('Simulated no space')):
                with self.assertRaises(OSError): fixture.run_recovery()
            self.assertEqual(recovery.encode_plan(fixture.plan), fixture.lock.read_bytes())
            fixture.run_recovery()
            fixture.assert_preserved()
        finally:
            fixture.doCleanups()

    def test_verifier_rejection_after_intent_keeps_barrier(self):
        count = 0
        def verify(_):
            nonlocal count
            count += 1
            if count > 1:
                raise ValueError('Operator restarted or writer appeared')
        with self.assertRaises(ValueError): recovery.preserve(self.storage, self.control, self.plan, verify)
        self.assertEqual(recovery.encode_plan(self.plan), self.lock.read_bytes())
        self.assertEqual(2, len(list((self.storage / 'tmp').iterdir())))

    def test_special_receipt_and_unexpected_archive_data_are_not_opened_or_cleared(self):
        original = recovery.rename_noreplace
        def crash(*args):
            original(*args)
            raise Crash()
        with patch.object(recovery, 'rename_noreplace', crash):
            with self.assertRaises(Crash): self.run_recovery()
        receipt = self.destination / 'receipt.json'
        os.mkfifo(receipt)
        with self.assertRaises(ValueError): self.run_recovery()
        self.assertNotEqual(b'', self.lock.read_bytes())
        receipt.unlink()
        extra = self.destination / 'unrecognized'
        extra.write_bytes(b'keep')
        with self.assertRaises(ValueError): self.run_recovery()
        self.assertEqual(b'keep', extra.read_bytes())

    def test_replaced_control_lock_and_destination_are_rejected(self):
        # Simulate an external lifecycle contract violation during verification;
        # the primitive must not follow a replaced destination or clear old intent.
        count = 0
        def replaced(_):
            nonlocal count
            count += 1
            if count == 2:
                self.destination.rename(self.destination.with_name('held-original'))
                self.destination.mkdir()
        with self.assertRaises(ValueError): recovery.preserve(self.storage, self.control, self.plan, replaced)
        self.assertNotEqual(b'', self.lock.read_bytes())
        self.assertEqual(2, len(list((self.storage / 'tmp').iterdir())))

    def test_final_receipt_disappearance_and_reappearing_source_prevent_commit(self):
        for fault in ('receipt', 'source'):
            fixture = RecorderPreservationTest()
            fixture.setUp()
            def verify(_):
                receipt = fixture.destination / 'receipt.json'
                if receipt.exists():
                    if fault == 'receipt':
                        receipt.rename(fixture.base / 'retained-receipt')
                    else:
                        (fixture.destination / 'EGH_exact').rename(fixture.storage / 'tmp/EGH_exact')
            try:
                with self.assertRaises((ValueError, OSError)):
                    recovery.preserve(fixture.storage, fixture.control, fixture.plan, verify)
                self.assertNotEqual(b'', fixture.lock.read_bytes())
            finally:
                fixture.doCleanups()

    def test_failed_clear_fsync_is_committed_receipt_uncertainty_not_rollback(self):
        original = recovery.os.fsync
        def fail(fd):
            if os.readlink('/proc/self/fd/' + str(fd)) == str(self.lock) and os.fstat(fd).st_size == 0:
                raise OSError('Simulated commit-point fsync failure')
            original(fd)
        with patch.object(recovery.os, 'fsync', fail):
            with self.assertRaises(OSError): self.run_recovery()
        # No success response and no restart performed. Clearing may already be
        # visible, but exact archived data/receipt remain for fresh reconciliation.
        self.assert_preserved()
        reconciled = []
        def sync(fd):
            reconciled.append(os.readlink('/proc/self/fd/' + str(fd)))
            original(fd)
        with patch.object(recovery.os, 'fsync', sync):
            self.assertTrue(self.run_recovery()['replayed'])
        self.assertIn(str(self.lock), reconciled)

    def test_destination_collision_is_not_overwritten(self):
        self.destination.mkdir(parents=True)
        collision = self.destination / 'NE_exact'
        collision.mkdir()
        (collision / 'keep').write_bytes(b'original')
        with self.assertRaises(ValueError): self.run_recovery()
        self.assertEqual(b'original', (collision / 'keep').read_bytes())
        self.assertEqual(b'', self.lock.read_bytes())
        self.assertTrue((self.storage / 'tmp/NE_exact/service_ipc.sock').exists())

    def test_inode_swap_symlink_and_live_verifier_failure_hold(self):
        path = self.storage / 'tmp/EGH_exact'
        path.rename(self.base / 'old-handler')
        path.mkdir()
        with self.assertRaises(ValueError): self.run_recovery()
        path.rmdir()
        path.symlink_to(self.base / 'old-handler')
        with self.assertRaises(ValueError): self.run_recovery()
        self.assertEqual(b'', self.lock.read_bytes())

    def test_actual_rename_noreplace_refuses_existing_destination(self):
        self.destination.mkdir(parents=True)
        (self.destination / 'EGH_exact').mkdir()
        source = os.open(self.storage / 'tmp', os.O_RDONLY | os.O_DIRECTORY)
        dest = os.open(self.destination, os.O_RDONLY | os.O_DIRECTORY)
        try:
            with self.assertRaises(FileExistsError): recovery.rename_noreplace(source, 'EGH_exact', dest)
            self.assertTrue((self.storage / 'tmp/EGH_exact').is_dir())
        finally:
            os.close(source)
            os.close(dest)

    def test_partial_receipt_resumes_but_wrong_receipt_holds(self):
        original = recovery.write_all
        def partial(fd, body):
            if os.readlink('/proc/self/fd/' + str(fd)).endswith('/receipt.json'):
                os.write(fd, body[:20])
                raise Crash()
            original(fd, body)
        with patch.object(recovery, 'write_all', partial):
            with self.assertRaises(Crash): self.run_recovery()
        self.assertNotEqual(b'', self.lock.read_bytes())
        self.run_recovery()
        self.assert_preserved()
        (self.destination / 'receipt.json').write_bytes(b'wrong receipt')
        with self.assertRaises(ValueError): self.run_recovery()
        self.assertEqual(b'wrong receipt', (self.destination / 'receipt.json').read_bytes())


if __name__ == '__main__':
    unittest.main()
