import unittest
from pathlib import Path


ELASTIC_DIR = Path(__file__).resolve().parents[1]
BACKEND = (ELASTIC_DIR / "backend.blr-sgp.hcl.example").read_text()
PROFILE = (ELASTIC_DIR / "courseultra.blr-sgp.tfvars.example").read_text()


class CandidateProfileTest(unittest.TestCase):
    def test_uses_isolated_state_and_resource_identity(self):
        self.assertIn("elastic-3.7.0-blr-sgp.tfstate", BACKEND)
        self.assertIn('stackName = "courseultra-openvidu-blr"', PROFILE)
        self.assertIn('vpcIpRange = "10.10.30.0/24"', PROFILE)
        self.assertIn('domainName       = "openvidu-blr.courseultra.com"', PROFILE)

    def test_keeps_live_compute_in_blr_and_temporary_storage_in_sgp(self):
        self.assertIn('region      = "blr1"', PROFILE)
        self.assertIn('spaceRegion = "sgp1"', PROFILE)
        self.assertIn('spaceName  = ""', PROFILE)

    def test_preserves_openvidu_runtime_shape(self):
        self.assertIn('rtcEngine      = "mediasoup"', PROFILE)
        self.assertIn(
            'enabledModules = "observability,openviduMeet,v2compatibility"',
            PROFILE,
        )
        self.assertIn("minNumberOfMediaNodes   = 1", PROFILE)
        self.assertIn("maxNumberOfMediaNodes   = 4", PROFILE)


if __name__ == "__main__":
    unittest.main()
