import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

MODULE = Path(__file__).resolve().parents[1] / 'media_drain_guard.py'
spec = importlib.util.spec_from_file_location('application_drain_guard', MODULE)
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


class ApplicationDrainExclusionTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name).resolve()
        self.boot = self.root / 'boot-id'
        self.boot.write_text('aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee\n')
        self.settings = self.root / 'settings.json'
        self.settings.write_text(json.dumps({'url': 'https://backend.example', 'token': 'test-only'}))
        self.settings.chmod(0o600)
        self.identity = {'dropletId': '123', 'nodeId': 'ND_example',
                         'generation': self.boot.read_text().strip()}
        self.result = dict(self.identity, applicationExcluded=True)
        self.opener = Mock()
        self.response = Mock()
        self.response.status = 200
        self.response.read.side_effect = lambda limit: json.dumps(self.result).encode()
        self.opener.open.return_value.__enter__ = Mock(return_value=self.response)
        self.opener.open.return_value.__exit__ = Mock(return_value=False)

    def check(self, nodes=None, final=False):
        guard.exclude_application_work(self.settings, '123', [b'ND_example'] if nodes is None else nodes,
                                       self.root, self.boot, self.opener, final_check=final)

    def test_exact_identity_is_durable_and_retries_recheck_after_unregister(self):
        self.check()
        self.check([])
        self.assertEqual(2, self.opener.open.call_count)
        request = self.opener.open.call_args.args[0]
        self.assertEqual(self.identity, json.loads(request.data))
        self.assertEqual('https://backend.example/webhooks/openvidu/capacity/begin-drain', request.full_url)

    def test_final_check_requires_explicit_fresh_clearance_not_begin_ack(self):
        self.check()
        with self.assertRaises(ValueError):
            self.check([], final=True)
        self.result['applicationObligationsClear'] = True
        self.check([], final=True)
        self.assertEqual('https://backend.example/webhooks/openvidu/capacity/exclude-idle',
                         self.opener.open.call_args.args[0].full_url)
        self.result['applicationObligationsClear'] = False
        with self.assertRaises(ValueError):
            self.check([], final=True)

    def test_missing_first_registration_never_calls_authority(self):
        with self.assertRaises(ValueError):
            self.check([])
        self.opener.open.assert_not_called()

    def test_reboot_or_registration_replacement_cannot_reuse_identity(self):
        self.check()
        with self.assertRaises(ValueError):
            self.check([b'ND_replacement'])
        self.boot.write_text('bbbbbbbb-bbbb-cccc-dddd-eeeeeeeeeeee')
        with self.assertRaises(ValueError):
            self.check([])
        self.assertEqual(1, self.opener.open.call_count)

    def test_false_or_mismatched_acknowledgement_holds(self):
        for change in ({'applicationExcluded': False}, {'generation': 'other'}, {'nodeId': 'other'}, {'dropletId': '456'}):
            self.result = dict(self.identity, applicationExcluded=True)
            self.result.update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.check()

    def test_failure_after_exclusion_is_retried_not_assumed_allowed(self):
        self.check()
        self.opener.open.side_effect = TimeoutError('unavailable')
        with self.assertRaises(TimeoutError):
            self.check([])

    def test_credentials_are_not_sent_to_http_or_redirects(self):
        self.settings.write_text(json.dumps({'url': 'http://backend.example', 'token': 'test-only'}))
        with self.assertRaises(ValueError):
            self.check()
        self.opener.open.assert_not_called()
        with self.assertRaises(ValueError):
            guard.NoCapacityRedirects().redirect_request(None, None, 302, '', {}, 'https://other.example')

    def test_public_settings_and_symlinked_identity_hold(self):
        self.settings.chmod(0o644)
        with self.assertRaises(ValueError):
            self.check()
        self.settings.chmod(0o600)
        (self.root / '.courseultra-drain-capacity-identity.json').symlink_to(self.settings)
        with self.assertRaises(ValueError):
            self.check()
        self.opener.open.assert_not_called()

    def test_capacity_mode_wires_guard_into_all_drain_checks(self):
        source = MODULE.with_name('tf-do-openvidu-elastic.tf').read_text()
        self.assertIn('--capacity-settings /etc/courseultra-capacity-drain.json', source)
        self.assertIn('chmod 600 /etc/courseultra-capacity-drain.json', source)
        self.assertLess(source.index('chmod 600 /etc/courseultra-capacity-drain.json'),
                        source.index('${local.recorder_guard_barrier}/usr/local/bin/install.sh'))
        main = MODULE.read_text().split('def main():', 1)[1]
        self.assertLess(main.index('exclude_application_work('), main.index('peers = ready_peers('))
