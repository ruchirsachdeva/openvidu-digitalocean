"""Original alert-code safety after the backend-first source-time rollout.

The same six codes now carry the integer observation time required by the shared
backend. These source contracts do not certify real incident/recovery email
delivery or qualify the old145afac8 process-local alert implementation.
"""
import contextlib
import io
import unittest
from unittest.mock import Mock

from test_autoscaler import load_autoscaler


class AlertProtocolCompatibilityTest(unittest.TestCase):
    # Keep the existing code family while enforcing the deployed shared protocol.
    ACCEPTED_CODES = frozenset({
        'ACCOUNT_DROPLET_QUOTA_PRESSURE', 'PROVISIONING_FAILED', 'CAPACITY_WAITING',
        'DELIVERY_CHECK', 'READINESS_UNAVAILABLE', 'READINESS_RECOVERED',
    })

    def setUp(self):
        self.scaler = load_autoscaler()
        self.scaler.CAPACITY_ENABLED = True
        self.callbacks = []
        self.scaler.capacity_request = self.backend_callback

    def backend_callback(self, path, payload):
        self.assertEqual('alert', path)
        self.assertEqual({'stack', 'code', 'observedAt'}, set(payload))
        self.assertIs(type(payload['observedAt']), int)
        self.assertGreater(payload['observedAt'], 0)
        self.assertEqual('test-stack', payload['stack'])
        self.assertIn(payload['code'], self.ACCEPTED_CODES)
        self.callbacks.append(payload['code'])
        return {}

    def finish(self, result):
        with contextlib.redirect_stdout(io.StringIO()):
            return self.scaler.finish(result)

    def test_pre_dispatch_inventory_failure_uses_existing_readiness_code_only(self):
        self.scaler.apicall = Mock(return_value=None)
        self.scaler.create_node = Mock(side_effect=AssertionError('Creation must remain unreachable'))
        with contextlib.redirect_stdout(io.StringIO()):
            result = self.scaler.main({})['body']
        self.assertEqual('hold', result['action'])
        self.assertTrue(result['readiness_wait'])
        self.assertNotIn('error', result)
        self.assertEqual(['READINESS_UNAVAILABLE'], self.callbacks)
        self.scaler.apicall.assert_called_once_with('GET', '/droplets?tag_name=media&per_page=200')
        self.scaler.create_node.assert_not_called()

    def test_healthy_account_and_capacity_do_not_emit_new_recovery_enum_values(self):
        self.finish({'readiness_verified': True, 'waiting_for_capacity': False,
                     'account_quota': 25, 'account_droplets': 4})
        # Delivery policy belongs to the paired backend, not this Function.
        self.assertEqual(['READINESS_RECOVERED'], self.callbacks)

    def test_failed_or_unknown_mutation_cannot_emit_a_readiness_clear(self):
        for result in ({'readiness_verified': True, 'error': 'synthetic outcome failure'},
                       {'readiness_verified': True, 'warning': 'Provision outcome unknown; retain intent'}):
            with self.subTest(result=result):
                self.callbacks.clear()
                self.finish(result)
                self.assertEqual(['PROVISIONING_FAILED'], self.callbacks)

    def test_existing_wait_and_quota_warnings_remain_compatible(self):
        self.finish({'waiting_for_capacity': True,
                     'alerts': [{'code': 'ACCOUNT_DROPLET_QUOTA_PRESSURE'}]})
        self.assertEqual({'CAPACITY_WAITING', 'ACCOUNT_DROPLET_QUOTA_PRESSURE'}, set(self.callbacks))


if __name__ == '__main__':
    unittest.main()
