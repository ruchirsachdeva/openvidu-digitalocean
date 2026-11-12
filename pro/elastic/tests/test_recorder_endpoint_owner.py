"""Synthetic proc races; no service, provider or host-process operations."""
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import recorder_admission as admission


class RecorderEndpointOwnerTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.proc = Path(folder.name)
        self.pid = self.proc / '123'
        (self.pid / 'fd').mkdir(parents=True)
        (self.pid / 'net').mkdir()
        (self.pid / 'comm').write_text('egress\n')
        (self.pid / 'cgroup').write_text('0::/system.slice/docker-' + 'a' * 64 + '.scope\n')
        self.stat()
        self.tcp = 'header\n0: 00000000:2385 00000000:0000 0A 0 0 0 0 0 111\n0: 00000000:2386 00000000:0000 0A 0 0 0 0 0 222\n'
        (self.pid / 'net/tcp').write_text(self.tcp)
        (self.pid / 'net/tcp6').write_text('header\n')
        (self.pid / 'fd/1').symlink_to('socket:[111]')
        (self.pid / 'fd/2').symlink_to('socket:[222]')

    def stat(self, birth='456', state='S'):
        (self.pid / 'stat').write_text('123 (egress worker) ' + ' '.join([state] + ['0'] * 18 + [birth]))

    def owner(self):
        return admission.endpoint_owner('a' * 64, [9093, 9094], self.proc)

    def on_descriptor(self, descriptor, action):
        readlink = os.readlink
        def read(path):
            if path == self.pid / 'fd' / descriptor:
                action()
            return readlink(path)
        return patch.object(admission.os, 'readlink', side_effect=read)

    def test_unrelated_process_disappearing_before_filtering_does_not_hide_live_owner(self):
        (self.proc / '999').mkdir()  # Its comm is already gone after proc enumeration.
        self.assertEqual(('123', '456'), self.owner())

    def test_closed_non_listening_descriptor_does_not_hide_unchanged_live_endpoints(self):
        extra = self.pid / 'fd/99'
        extra.symlink_to('socket:[333]')
        with self.on_descriptor('99', extra.unlink):
            self.assertEqual(('123', '456'), self.owner())

    def test_same_container_non_owning_handler_may_disappear_before_candidate_selection(self):
        for stage in ('stat', 'net', 'fd', 'zombie'):
            with self.subTest(stage=stage):
                handler = self.proc / '124'
                handler.mkdir()
                (handler / 'comm').write_text('egress\n')
                (handler / 'cgroup').write_text((self.pid / 'cgroup').read_text())
                if stage != 'stat':
                    state = 'Z' if stage == 'zombie' else 'S'
                    (handler / 'stat').write_text('124 (egress) ' + ' '.join([state] + ['0'] * 18 + ['789']))
                if stage == 'fd':
                    shutil.copytree(self.pid / 'net', handler / 'net')
                try:
                    self.assertEqual(('123', '456'), self.owner())
                finally:
                    shutil.rmtree(handler)

    def test_closed_required_listener_is_not_ignored_as_descriptor_churn(self):
        calls = []
        def close():
            calls.append(1)
            if len(calls) == 2:
                (self.pid / 'fd/1').unlink()
        with self.on_descriptor('1', close), self.assertRaises(ValueError):
            self.owner()

    def test_replaced_required_descriptor_is_rejected(self):
        calls = []
        def replace():
            calls.append(1)
            if len(calls) == 2:
                descriptor = self.pid / 'fd/1'
                descriptor.unlink(); descriptor.symlink_to('socket:[333]')
        with self.on_descriptor('1', replace), self.assertRaises(ValueError):
            self.owner()

    def test_changed_listening_socket_inode_is_rejected(self):
        def replace():
            (self.pid / 'net/tcp').write_text(self.tcp.replace('111', '333'))
        with self.on_descriptor('1', replace), self.assertRaises(ValueError):
            self.owner()

    def test_reused_pid_birth_is_rejected(self):
        with self.on_descriptor('1', lambda: self.stat(birth='789')), self.assertRaises(ValueError):
            self.owner()

    def test_dead_process_is_rejected(self):
        for state in ('Z', 'X', 'x'):
            with self.subTest(state=state):
                self.stat(state=state)
                with self.assertRaises(ValueError): self.owner()

    def test_owner_disappearing_after_descriptor_scan_is_rejected(self):
        with self.on_descriptor('2', (self.pid / 'stat').unlink), self.assertRaises(ValueError):
            self.owner()

    def test_changed_container_membership_is_rejected(self):
        def change():
            (self.pid / 'cgroup').write_text('0::/system.slice/docker-' + 'b' * 64 + '.scope\n')
        with self.on_descriptor('1', change), self.assertRaises(ValueError):
            self.owner()

    def test_identity_and_listener_checks_follow_final_descriptor_reads(self):
        for change in (lambda: self.stat(birth='789'), lambda: self.stat(state='Z'),
                       lambda: (self.pid / 'net/tcp').write_text(self.tcp.replace('111', '333'))):
            with self.subTest(change=change):
                self.stat()
                (self.pid / 'net/tcp').write_text(self.tcp)
                calls = []
                def mutate():
                    calls.append(1)
                    if len(calls) == 2: change()
                with self.on_descriptor('1', mutate), self.assertRaises(ValueError): self.owner()

    def test_two_live_owners_are_ambiguous(self):
        shutil.copytree(self.pid, self.proc / '124', symlinks=True)
        with self.assertRaises(ValueError): self.owner()

    def test_permission_failure_is_not_treated_as_a_closed_descriptor(self):
        def denied():
            raise PermissionError()
        with self.on_descriptor('1', denied), self.assertRaises(PermissionError):
            self.owner()
