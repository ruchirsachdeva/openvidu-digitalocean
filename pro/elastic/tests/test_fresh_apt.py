import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock
from subprocess import CompletedProcess

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('fresh_apt', ROOT / 'prepare-fresh-apt.py')
apt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(apt)


class FreshAptTest(unittest.TestCase):
    def test_deb822_and_legacy_preserve_signing_security_and_comments(self):
        for name, original in [
            ('sources.list.d/ubuntu.sources', 'Types: deb\nURIs: http://mirrors.digitalocean.com/ubuntu/\nSuites: noble noble-updates\nSigned-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg\n'),
            ('sources.list', 'deb [signed-by=/keys/ubuntu.gpg] https://mirrors.digitalocean.com/ubuntu noble main\n')]:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory); source = root / 'etc/apt' / name
                source.parent.mkdir(parents=True)
                original += '# http://mirrors.digitalocean.com/ubuntu/ comment\ndeb http://security.ubuntu.com/ubuntu noble-security main\n'
                source.write_text(original)
                self.assertEqual(1, apt.prepare(root))
                changed = source.read_text()
                self.assertIn('http://archive.ubuntu.com/ubuntu/', changed)
                self.assertIn('# http://mirrors.digitalocean.com/ubuntu/ comment', changed)
                self.assertIn('http://security.ubuntu.com/ubuntu', changed)
                self.assertEqual(original, source.with_name(source.name+'.courseultra-original').read_text())
                self.assertEqual(0, apt.prepare(root))
                self.assertEqual(changed, source.read_text())

    def test_existing_installation_is_not_repaired_or_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); source=root/'etc/apt/sources.list'
            source.parent.mkdir(parents=True); source.write_text('deb http://mirrors.digitalocean.com/ubuntu noble main\n')
            (root/'opt/openvidu/config').mkdir(parents=True)
            with self.assertRaisesRegex(ValueError, 'fresh-bootstrap-only'): apt.prepare(root)
            self.assertIn('mirrors.digitalocean.com', source.read_text())

    def test_unrelated_repository_is_untouched(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); source=root/'etc/apt/sources.list'
            source.parent.mkdir(parents=True)
            original='deb https://mirrors.digitalocean.com.example/ubuntu noble main\n'
            source.write_text(original)
            self.assertEqual(0, apt.prepare(root)); self.assertEqual(original, source.read_text())

    def test_existing_backup_and_symlink_are_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); source=root/'etc/apt/sources.list'
            source.parent.mkdir(parents=True); source.write_text('deb http://mirrors.digitalocean.com/ubuntu noble main\n')
            backup=source.with_name(source.name+'.courseultra-original'); backup.write_text('original')
            with self.assertRaisesRegex(ValueError, 'backup'): apt.prepare(root)
            source.unlink(); source.symlink_to(backup)
            with self.assertRaisesRegex(ValueError, 'Regular'): apt.prepare(root)

    def test_both_bootstraps_run_preparation_before_first_apt(self):
        text=(ROOT/'tf-do-openvidu-elastic.tf').read_text()
        for role in ('master','media'):
            block=text.split('user_data_'+role+' = <<-EOF\n',1)[1].split('\nEOF',1)[0]
            self.assertEqual(1, block.count('${local.fresh_apt_prepare}'))
            self.assertIn('set -eu -o pipefail', block)
            self.assertLess(block.index('${local.fresh_apt_prepare}'), block.index('apt-get --no-download install'))
            self.assertNotIn('apt-get update && apt-get install', block)
            for package in apt.DEPENDENCIES:
                self.assertIn(package, block.split('apt-get --no-download install -y', 1)[1].split('AWS_CLI_VERSION', 1)[0])
        self.assertIn('USER_DATA     = base64.b64decode("${base64encode(local.user_data_media_transport)}")',text)

    def test_download_succeeds_without_retry_or_package_installation(self):
        with tempfile.TemporaryDirectory() as directory:
            run=Mock(return_value=CompletedProcess([], 0, '', ''))
            apt.stage_dependencies(Path(directory), run)
            self.assertEqual(2, run.call_count)
            self.assertEqual(['apt-get', '-o', 'Acquire::http::No-Cache=true',
                              '-o', 'Acquire::https::No-Cache=true', '--error-on=any', 'update'],
                             run.call_args_list[0].args[0])
            self.assertEqual(['apt-get', '--download-only', 'install', '-y', *apt.DEPENDENCIES], run.call_args_list[1].args[0])
            self.assertEqual('C', run.call_args.kwargs['env']['LC_ALL'])

    def test_exact_security_404_refreshes_once_before_any_install(self):
        missing='E: Failed to fetch http://security.ubuntu.com/ubuntu/pool/main/c/curl/curl_8.5.0-2ubuntu10.15_amd64.deb  404  Not Found [IP: 91.189.91.82 80]\nE: Unable to fetch some archives, maybe run apt-get update or try with --fix-missing?'
        ok=CompletedProcess([],0,'',''); failed=CompletedProcess([],100,'',missing)
        with tempfile.TemporaryDirectory() as directory:
            run=Mock(side_effect=[ok,failed,ok,ok])
            apt.stage_dependencies(Path(directory),run)
            commands=[call.args[0] for call in run.call_args_list]
            self.assertEqual(commands[:2],commands[2:])
            self.assertEqual(4,len(commands))
            run=Mock(side_effect=[ok,failed,ok,failed])
            with self.assertRaisesRegex(RuntimeError,'download failed'): apt.stage_dependencies(Path(directory),run)
            self.assertEqual(4,run.call_count)
            run=Mock(side_effect=[ok,failed,CompletedProcess([],100,'','E: metadata failed')])
            with self.assertRaisesRegex(RuntimeError,'metadata update failed'): apt.stage_dependencies(Path(directory),run)
            self.assertEqual(3,run.call_count)

    def test_update_or_non_404_failure_never_retries(self):
        ok=CompletedProcess([],0,'','')
        failures=['E: Hash Sum mismatch','E: Packages cannot be authenticated',
                  'E: Could not get lock /var/lib/dpkg/lock',
                  'E: Failed to fetch https://archive.ubuntu.com/ubuntu/pool/a.deb  503 Unavailable',
                  'E: Failed to fetch https://security.ubuntu.com.evil/ubuntu/pool/a.deb 404 Not Found',
                  'E: Failed to fetch https://security.ubuntu.com/ubuntu/pool/a.deb 404 Not Found\nE: Hash Sum mismatch']
        with tempfile.TemporaryDirectory() as directory:
            run=Mock(return_value=CompletedProcess([],100,'','E: update failed'))
            with self.assertRaisesRegex(RuntimeError,'metadata update failed'): apt.stage_dependencies(Path(directory),run)
            self.assertEqual(1,run.call_count)
            for failure in failures:
                with self.subTest(failure=failure):
                    run=Mock(side_effect=[ok,CompletedProcess([],100,'',failure)])
                    with self.assertRaisesRegex(RuntimeError,'download failed'): apt.stage_dependencies(Path(directory),run)
                    self.assertEqual(2,run.call_count)

    def test_existing_installation_never_fetches_packages(self):
        for marker in ('opt/openvidu/config','opt/openvidu/secrets.env','usr/local/bin/openvidu_install_counter.txt'):
            with self.subTest(marker=marker), tempfile.TemporaryDirectory() as directory:
                root=Path(directory); path=root/marker; path.parent.mkdir(parents=True);path.touch()
                run=Mock()
                with self.assertRaisesRegex(ValueError,'fresh-bootstrap-only'): apt.stage_dependencies(root,run)
                run.assert_not_called()


if __name__ == '__main__': unittest.main()
