"""Execute the guard against inert local files; never start Docker/provider services."""
import hashlib
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
PIN = 'f2bdec0a85a20a4ee1954c69924549aba24c73b530029a5a8cc0e1579da38ca0'


class RecorderStartupGuardTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.calls = self.root / 'calls'
        self.original = self.root / 'entrypoint.sh'
        self.original.write_text('#!/bin/bash\nprintf "original\\n" >> "$GUARD_TEST_CALLS"\n')
        self.original.chmod(0o755)
        self.config = self.root / 'egress.yaml'
        self.config.write_text('synthetic-config-only\n')
        self.fingerprint = self.root / 'egress-config.sha256'
        self.fingerprint.write_text(hashlib.sha256(self.config.read_bytes()).hexdigest() + '\n')
        self.lock = self.root / 'start.lock'
        self.lock.touch()
        self.recovery = self.root / 'egress'
        (self.recovery / 'tmp').mkdir(parents=True)
        (self.recovery / 'backup_storage').mkdir()
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        self.command('uname', 'printf "x86_64\\n"')
        self.command('id', 'printf "egress\\n"')
        # macOS has no util-linux flock executable. Exercise real kernel locking
        # through fcntl there; Linux and the pinned image use the actual executable.
        if not shutil.which('flock'):
            helper = self.root / 'flock.py'
            helper.write_text('import fcntl, sys\n'
                              'assert sys.argv[1:] == ["--exclusive", "--nonblock", "9"]\n'
                              'try: fcntl.flock(9, fcntl.LOCK_EX | fcntl.LOCK_NB)\n'
                              'except OSError: sys.exit(1)\n')
            self.command('flock', f'exec "{sys.executable}" "{helper}" "$@"')
        if sys.platform != 'linux':
            self.command('stat', f'''exec "{sys.executable}" -c 'import os, sys; s=os.fstat(9) if sys.argv[-1] == "/dev/fd/9" else os.stat(sys.argv[-1]); print(str(s.st_dev)+":"+str(s.st_ino))' "$@"''')
        source = (ROOT / 'recorder-startup-guard.sh').read_text()
        source = source.replace('ENTRYPOINT=/entrypoint.sh', f'ENTRYPOINT="{self.original}"')
        source = source.replace(PIN, hashlib.sha256(self.original.read_bytes()).hexdigest())
        source = source.replace('CONFIG=/config/egress.yaml', f'CONFIG="{self.config}"')
        source = source.replace('CONFIG_HASH=/courseultra-guard/egress-config.sha256', f'CONFIG_HASH="{self.fingerprint}"')
        source = source.replace('START_LOCK=/courseultra-guard/start.lock', f'START_LOCK="{self.lock}"')
        source = source.replace('RECOVERY_ROOT=/home/egress', f'RECOVERY_ROOT="{self.recovery}"')
        if sys.platform != 'linux':
            # BSD /dev/fd metadata is not Linux /proc underlying-file metadata.
            # The stat shim verifies FD identity; use the matched path for size.
            source = source.replace('[[ ! -s /proc/self/fd/9 ]]', '[[ ! -s "$START_LOCK" ]]')
            source = source.replace('/proc/self/fd/9', '/dev/fd/9')
        self.guard = self.root / 'guard.sh'
        self.guard.write_text(source)
        self.env = dict(os.environ, PATH=str(self.bin) + os.pathsep + os.environ['PATH'],
                        EGRESS_CONFIG_FILE='/config/egress.yaml', GUARD_TEST_CALLS=str(self.calls))

    def command(self, name, body):
        path = self.bin / name
        path.write_text('#!/bin/bash\n' + body + '\n')
        path.chmod(0o755)

    def run_guard(self, *args):
        return subprocess.run(['/bin/bash', str(self.guard), *args], env=self.env,
                              capture_output=True, text=True, timeout=5)

    def assertHeld(self, result):
        self.assertNotEqual(0, result.returncode)
        self.assertIn('startup held', result.stderr)
        self.assertFalse(self.calls.exists())

    def test_clean_launch_and_independent_restart_reenter_guard(self):
        self.assertEqual(0, self.run_guard().returncode)
        self.assertEqual(0, self.run_guard().returncode)
        self.assertEqual('original\noriginal\n', self.calls.read_text())
        self.calls.unlink()
        recovery = self.recovery / 'tmp' / 'EG_interrupted'
        recovery.mkdir()
        media = recovery / 'output.mp4'
        media.write_bytes(b'irreplaceable recovery')
        self.assertHeld(self.run_guard())
        self.assertEqual(b'irreplaceable recovery', media.read_bytes())

    def test_hidden_tmp_and_backup_entries_never_get_deleted(self):
        for directory, name in [('tmp', '.partial'), ('backup_storage', 'EG_failed')]:
            with self.subTest(directory=directory):
                entry = self.recovery / directory / name
                entry.write_bytes(b'keep')
                self.assertHeld(self.run_guard())
                self.assertEqual(b'keep', entry.read_bytes())
                entry.unlink()

    def test_recovery_symlink_and_unreadable_inventory_hold(self):
        link = self.recovery / 'tmp' / 'link'
        link.symlink_to(self.config)
        self.assertHeld(self.run_guard())
        link.unlink()
        self.command('find', 'exit 1')
        self.assertHeld(self.run_guard())

    def test_missing_or_symlinked_recovery_directory_holds(self):
        backup = self.recovery / 'backup_storage'
        backup.rmdir()
        self.assertHeld(self.run_guard())
        backup.symlink_to(self.recovery / 'tmp', target_is_directory=True)
        self.assertHeld(self.run_guard())

    def test_config_drift_malformed_proof_and_symlink_hold(self):
        self.config.write_text('changed secret config\n')
        self.assertHeld(self.run_guard())
        self.fingerprint.write_text('not-a-hash')
        self.assertHeld(self.run_guard())
        self.config.unlink()
        self.config.symlink_to(self.fingerprint)
        self.assertHeld(self.run_guard())

    def test_unknown_entrypoint_never_executes(self):
        self.original.write_text('#!/bin/bash\nexit 0\n')
        self.assertHeld(self.run_guard())

    def test_maintenance_lock_blocks_start_without_changing_lock_inode(self):
        before = self.lock.stat()
        with self.lock.open('rb') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.assertHeld(self.run_guard())
        self.assertEqual(0, self.run_guard().returncode)
        after = self.lock.stat()
        self.assertEqual((before.st_dev, before.st_ino, 0), (after.st_dev, after.st_ino, after.st_size))

    def wrap_lock(self, before):
        original = self.bin / 'flock-original'
        if (self.bin / 'flock').exists():
            (self.bin / 'flock').rename(original)
        else:
            original = Path(shutil.which('flock'))
        self.command('flock', before + f'\nexec "{original}" "$@"')

    def test_intent_written_before_acquisition_is_checked_under_lock(self):
        self.wrap_lock(f'printf "pending intent" > "{self.lock}"')
        result = self.run_guard()
        self.assertHeld(result)
        self.assertIn('unfinished recorder preservation', result.stderr)

    def test_replaced_lock_inode_does_not_authorize_start(self):
        self.wrap_lock(f'mv "{self.lock}" "{self.lock}.old"\nprintf "" > "{self.lock}"')
        result = self.run_guard()
        self.assertHeld(result)
        self.assertIn('startup lock replaced', result.stderr)

    def test_missing_symlinked_nonempty_lock_and_unavailable_flock_hold(self):
        self.lock.unlink()
        self.assertHeld(self.run_guard())
        self.lock.symlink_to(self.config)
        self.assertHeld(self.run_guard())
        self.lock.unlink()
        self.lock.write_text('unexpected')
        self.assertHeld(self.run_guard())
        self.lock.write_text('')
        self.command('flock', 'exit 127')
        self.assertHeld(self.run_guard())

    def test_lock_survives_exec_and_excludes_second_guard_until_process_exit(self):
        self.replace_original('trap "exit 42" TERM\nprintf "%s" "$$" > "$GUARD_TEST_CALLS"\n'
                              'while :; do sleep 0.1; done\n')
        process = subprocess.Popen(['/bin/bash', str(self.guard)], env=self.env,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            deadline = time.monotonic() + 4
            while not self.calls.exists() and process.poll() is None and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertTrue(self.calls.exists())
            self.assertEqual(process.pid, int(self.calls.read_text()))
            with self.lock.open('rb') as lock:
                with self.assertRaises(BlockingIOError):
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            result = self.run_guard()
            self.assertNotEqual(0, result.returncode)
            self.assertIn('maintenance already active', result.stderr)
            self.assertEqual(str(process.pid), self.calls.read_text())
            process.terminate()
            self.assertEqual(42, process.wait(timeout=3))
            with self.lock.open('rb') as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        finally:
            if process.poll() is None:
                process.kill()
            process.wait(timeout=3)

    def test_unarmed_bootstrap_placeholder_never_runs_vendor_on_repeated_start(self):
        self.fingerprint.write_text('UNARMED\n')
        self.assertHeld(self.run_guard())
        self.assertHeld(self.run_guard())

    def test_wrong_user_architecture_path_and_arguments_hold(self):
        self.command('id', 'printf "root\\n"')
        self.assertHeld(self.run_guard())
        self.command('id', 'printf "egress\\n"')
        self.command('uname', 'printf "aarch64\\n"')
        self.assertHeld(self.run_guard())
        self.command('uname', 'printf "x86_64\\n"')
        self.assertHeld(self.run_guard('unexpected'))
        self.env['EGRESS_CONFIG_FILE'] = '/other/config'
        self.assertHeld(self.run_guard())

    def test_guard_never_controls_shared_services_or_removes_files(self):
        source = (ROOT / 'recorder-startup-guard.sh').read_text()
        for dangerous in ('systemctl ', 'docker ', 'rm ', 'cp ', 'kill '):
            self.assertNotIn(dangerous, source)
        self.assertIn('exec "$ENTRYPOINT"', source)
        variables = (ROOT / 'variables.tf').read_text().split('variable "isolatedRecorderGuard"', 1)[1].split('\nvariable ', 1)[0]
        self.assertIn('default     = false', variables)

    def replace_original(self, body):
        old = hashlib.sha256(self.original.read_bytes()).hexdigest()
        self.original.write_text('#!/bin/bash\n' + body)
        new = hashlib.sha256(self.original.read_bytes()).hexdigest()
        self.guard.write_text(self.guard.read_text().replace(old, new))

    def test_original_exit_code_and_exec_process_identity_are_preserved(self):
        self.replace_original('exit 37\n')
        self.assertEqual(37, self.run_guard().returncode)
        self.replace_original('trap "exit 42" TERM\nprintf "%s" "$$" > "$GUARD_TEST_CALLS"\n'
                              'while :; do sleep 0.1; done\n')
        process = subprocess.Popen(['/bin/bash', str(self.guard)], env=self.env,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            deadline = time.monotonic() + 4
            while not self.calls.exists() and process.poll() is None and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertTrue(self.calls.exists(), 'Original entrypoint did not start')
            self.assertEqual(process.pid, int(self.calls.read_text()))
            process.terminate()
            self.assertEqual(42, process.wait(timeout=3))
        finally:
            if process.poll() is None:
                process.kill()
            process.wait(timeout=3)

    @unittest.skipUnless(shutil.which('docker-compose'), 'Compose CLI is required for render-only merge test')
    def test_compose_merge_preserves_other_services_and_immutable_mount_precedence(self):
        base = self.root / 'base.yaml'
        base.write_text('''services:
  openvidu:
    image: example/forwarder:inert
  redis:
    image: redis:8.6.4-alpine
  operator:
    image: example/operator:inert
    environment:
      KEEP_OPERATOR_OVERRIDE: yes
    volumes:
      - ./config:/opt/openvidu/config
  egress:
    image: example/egress:inert
    network_mode: host
    restart: unless-stopped
    environment:
      EGRESS_CONFIG_FILE: /config/egress.yaml
    depends_on:
      setup-volumes:
        condition: service_completed_successfully
    volumes:
      - ./data/runtime/config/egress:/config
      - ./data/egress_data/home/egress:/home/egress
  setup-volumes:
    image: busybox:inert
    command: ["true"]
''')
        command = ['docker-compose', '-p', 'guard-render-only', '-f', str(base),
                   '-f', str(ROOT / 'media-nofile.override.yaml'),
                   '-f', str(ROOT / 'redis-durability.override.yaml')]
        def render(extra):
            result = subprocess.run(command + extra + ['config', '--format', 'json'],
                                    capture_output=True, text=True, timeout=10)
            self.assertEqual(0, result.returncode, result.stderr)
            return json.loads(result.stdout)
        before = render([])
        after = render(['-f', str(ROOT / 'recorder-startup-guard.override.yaml')])
        spec = importlib.util.spec_from_file_location('fresh_recorder', ROOT / 'prepare-fresh-recorder.py')
        fresh = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(fresh)
        # Validate real Compose output, not only mocked service dictionaries.
        before['services']['egress']['image'] = 'docker.io/openvidu/egress:3.8.0'
        fresh.validate(before, after, Path('/opt/openvidu'))
        for name, service in before['services'].items():
            if name != 'egress':
                self.assertEqual(service, after['services'][name], name)
        egress = after['services']['egress']
        self.assertEqual('unless-stopped', egress['restart'])
        self.assertEqual('egress', egress['user'])
        self.assertEqual('linux/amd64', egress['platform'])
        self.assertEqual(['/bin/bash', '/courseultra-guard/start.sh'], egress['entrypoint'])
        self.assertEqual([], egress['command'])
        self.assertEqual(before['services']['egress']['depends_on'], egress['depends_on'])
        mounts = {v['target']: v for v in egress['volumes']}
        for old in before['services']['egress']['volumes']:
            self.assertEqual(old, mounts[old['target']])
        for target in ['/config/egress.yaml', '/courseultra-guard/start.sh', '/courseultra-guard/egress-config.sha256', '/courseultra-guard/start.lock']:
            self.assertTrue(mounts[target]['read_only'])
            self.assertFalse(mounts[target]['bind'].get('create_host_path', False))
        self.assertEqual('/opt/openvidu/courseultra-recorder-guard/egress.yaml', mounts['/config/egress.yaml']['source'])
        # Only a render was run. Docker daemon/container restart, nested bind-mount
        # behavior and the actual vendor process still need disposable Linux proof.


if __name__ == '__main__':
    unittest.main()
