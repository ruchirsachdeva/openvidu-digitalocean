"""Offline Terraform contract checks; no provider or cloud credentials used."""
import copy
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1]


class ProductionGuardActivationTest(unittest.TestCase):
    def test_explicit_activation_and_rejection_boundaries(self):
        descriptor = dict(region='blr1', operatingProfile=dict(profile=dict(
            fingerprint='reviewed-v1', nodeType='c-4')))
        base = dict(doToken='synthetic', autoscalerToken='synthetic',
            openviduLicense='synthetic', sshAllowedCidrs=['192.0.2.1/32'],
            stackName='production-example', region='blr1', mediaNodeInstanceType='c-4',
            isolatedRecorderGuard=True, capacityReservationsEnabled=True,
            capacityBackendUrl='https://example.invalid/api', capacityBackendToken='synthetic-dedicated',
            capacityProfileFingerprint='reviewed-v1', capacityFleetDescriptorJson=json.dumps(descriptor))
        cases = [('explicit production', {}, True),
            ('disabled legacy behavior', dict(isolatedRecorderGuard=False, capacityReservationsEnabled=False), True),
            ('qualification standalone guard', dict(stackName='courseultra-openvidu-38-qualification', capacityReservationsEnabled=False), True),
            ('production standalone guard', dict(capacityReservationsEnabled=False), False),
            ('unguarded capacity', dict(isolatedRecorderGuard=False), False),
            ('missing descriptor', dict(capacityFleetDescriptorJson=''), False),
            ('incomplete descriptor', dict(capacityFleetDescriptorJson='{}'), False),
            ('malformed descriptor', dict(capacityFleetDescriptorJson='{'), False),
            ('null descriptor', dict(capacityFleetDescriptorJson='null'), False),
            ('scalar descriptor', dict(capacityFleetDescriptorJson='42'), False),
            ('plain HTTP', dict(capacityBackendUrl='http://example.invalid'), False),
            ('missing hostname', dict(capacityBackendUrl='https://'), False),
            ('embedded credentials', dict(capacityBackendUrl='https://user:secret@example.invalid'), False),
            ('query string', dict(capacityBackendUrl='https://example.invalid/api?token=no'), False),
            ('fragment', dict(capacityBackendUrl='https://example.invalid/#no'), False),
            ('missing credential', dict(capacityBackendToken=' '), False),
            ('missing profile', dict(capacityProfileFingerprint=''), False),
            ('wrong profile', dict(capacityProfileFingerprint='different'), False),
            ('wrong node type', dict(mediaNodeInstanceType='c-8'), False),
            ('wrong region', dict(region='ams3'), False)]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copyfile(MODULE/'variables.tf', root/'variables.tf')
            for name, changes, accepted in cases:
                with self.subTest(name=name):
                    values = copy.deepcopy(base); values.update(changes)
                    (root/'terraform.tfvars.json').write_text(json.dumps(values))
                    result = subprocess.run(['terraform', 'plan', '-input=false', '-refresh=false', '-no-color'],
                        cwd=root, capture_output=True, text=True, timeout=30)
                    if accepted:
                        self.assertEqual(0, result.returncode, result.stderr)
                    else:
                        self.assertNotEqual(0, result.returncode)
                        self.assertIn('Invalid value for variable', result.stderr)


if __name__ == '__main__':
    unittest.main()
