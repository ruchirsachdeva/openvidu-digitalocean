import copy
import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('arming', ROOT / 'arm-fresh-recorder.py')
arming = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(arming)


class ArmingTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.folder = self.root / 'courseultra-recorder-guard'
        self.folder.mkdir()
        (self.root / '.courseultra-recorder-prepared').touch()
        (self.folder / 'start.sh').write_bytes((ROOT / 'recorder-startup-guard.sh').read_bytes())
        (self.folder / 'start.lock').touch()
        (self.folder / 'egress.yaml').write_text('# Unarmed isolated recorder\n')
        (self.folder / 'egress-config.sha256').write_text('UNARMED\n')
        source = self.root / 'data/runtime/config/egress/egress.yaml'
        source.parent.mkdir(parents=True)
        source.write_text('reviewed fixture\n')
        self.digest = hashlib.sha256(source.read_bytes()).hexdigest()
        for name in ('tmp', 'backup_storage'):
            (self.root / 'data/egress_data/home/egress' / name).mkdir(parents=True)
        self.node = {'Id': 'exact', 'Name': '/egress', 'State': {'Status': 'exited', 'Running': False},
                     'Config': {'Image': arming.IMAGE, 'User': 'egress',
                                'Entrypoint': ['/bin/bash', '/courseultra-guard/start.sh'], 'Cmd': [],
                                'Labels': {'com.docker.compose.service': 'egress', 'com.docker.compose.project': 'openvidu'}},
                     'Mounts': [{'Type': 'bind', 'RW': False, 'Source': str(self.folder / name), 'Destination': target}
                                for name, target in [('start.sh', '/courseultra-guard/start.sh'),
                                ('start.lock', '/courseultra-guard/start.lock'),
                                ('egress-config.sha256', '/courseultra-guard/egress-config.sha256'), ('egress.yaml', '/config/egress.yaml')]]}
        self.node['Mounts'].append({'Type': 'bind', 'RW': True, 'Destination': '/home/egress',
                                   'Source': str(self.root / 'data/egress_data/home/egress')})

    def arm(self):
        return arming.arm(self.root, self.digest, lambda: copy.deepcopy(self.node))

    def test_only_snapshot_is_armed_and_second_attempt_refused(self):
        result = self.arm()
        self.assertTrue(result['requiresRecreateAndLiveVerification'])
        self.assertEqual('reviewed fixture\n', (self.folder / 'egress.yaml').read_text())
        self.assertEqual(self.digest + '\n', (self.folder / 'egress-config.sha256').read_text())
        self.assertEqual(0o640, (self.folder / 'egress.yaml').stat().st_mode & 0o777)
        with self.assertRaises(ValueError): self.arm()

    def test_wrong_hash_running_or_unguarded_container_refused(self):
        original = copy.deepcopy(self.node)
        for mutation in [lambda: self.node['State'].update(Status='running', Running=True),
                         lambda: self.node['Config'].update(User='root'),
                         lambda: self.node['Mounts'][0].update(RW=True),
                         lambda: self.node['Config'].update(Entrypoint=['/entrypoint.sh'])]:
            self.node = copy.deepcopy(original)
            mutation()
            with self.assertRaises(ValueError): self.arm()
            self.assertEqual('UNARMED\n', (self.folder / 'egress-config.sha256').read_text())
        self.node = original
        self.digest = '0' * 64
        with self.assertRaises(ValueError): self.arm()

    def test_residue_is_preserved(self):
        residue = self.root / 'data/egress_data/home/egress/tmp/.recovery'
        residue.write_text('preserve')
        with self.assertRaises(ValueError): self.arm()
        self.assertEqual('preserve', residue.read_text())

    def test_missing_or_writable_lock_mount_refused(self):
        original = copy.deepcopy(self.node)
        self.node['Mounts'] = [m for m in self.node['Mounts'] if m['Destination'] != '/courseultra-guard/start.lock']
        with self.assertRaises(ValueError): self.arm()
        self.node = original
        next(m for m in self.node['Mounts'] if m['Destination'] == '/courseultra-guard/start.lock')['RW'] = True
        with self.assertRaises(ValueError): self.arm()
        self.assertEqual('UNARMED\n', (self.folder / 'egress-config.sha256').read_text())

    def test_nonempty_or_hardlinked_lock_refused(self):
        lock = self.folder / 'start.lock'
        lock.write_text('changed')
        with self.assertRaises(ValueError): self.arm()
        lock.write_bytes(b'')
        (self.folder / 'other-lock').hardlink_to(lock)
        with self.assertRaises(ValueError): self.arm()
        self.assertEqual('UNARMED\n', (self.folder / 'egress-config.sha256').read_text())

    def test_missing_wrong_or_shadowed_recovery_mount_refused(self):
        original = copy.deepcopy(self.node)
        for mutation in [lambda: self.node['Mounts'].pop(),
                         lambda: self.node['Mounts'][-1].update(Source='/other-disk'),
                         lambda: self.node['Mounts'].append({'Destination': '/home/egress/tmp', 'Type': 'bind', 'Source': '/other'}),
                         lambda: self.node['Mounts'].append({'Destination': '/home', 'Type': 'bind', 'Source': '/other'})]:
            self.node = copy.deepcopy(original)
            mutation()
            with self.assertRaises(ValueError): self.arm()
            self.assertEqual('UNARMED\n', (self.folder / 'egress-config.sha256').read_text())

    def test_writable_snapshot_directory_refused(self):
        self.folder.chmod(0o777)
        with self.assertRaises(ValueError): self.arm()

    def test_symlink_and_container_change_refused(self):
        target = self.folder / 'egress.yaml'
        target.rename(self.folder / 'old')
        target.symlink_to(self.folder / 'old')
        with self.assertRaises(ValueError): self.arm()
        target.unlink()
        (self.folder / 'old').rename(target)
        samples = iter([self.node, dict(self.node, Id='replacement')])
        with self.assertRaises(ValueError): arming.arm(self.root, self.digest, lambda: next(samples))


if __name__ == '__main__':
    unittest.main()
