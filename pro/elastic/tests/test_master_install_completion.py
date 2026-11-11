"""Execute the rendered restart path without touching services or existing data."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


SOURCE = Path(__file__).resolve().parents[1] / 'tf-do-openvidu-elastic.tf'
SCRIPT = SOURCE.read_text().split('restart_script_master = <<-EOF\n', 1)[1].split('\nEOF', 1)[0]


class MasterInstallCompletionTest(unittest.TestCase):
    def run_restart(self, marker):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            marker_path = root / 'counter'
            if marker is not None:
                marker_path.write_text(marker)
            log = root / 'calls'
            service = root / 'systemctl'
            service.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$CALL_LOG"\n')
            service.chmod(0o700)
            update = root / 'update-config'
            update.write_text('#!/bin/sh\nprintf "update-config\\n" >> "$CALL_LOG"\n')
            update.chmod(0o700)
            script = SCRIPT.replace('/usr/local/bin/openvidu_install_counter.txt', str(marker_path))
            script = script.replace('/usr/local/bin/update_config_from_secret.sh', str(update))
            result = subprocess.run(['bash', '-c', script], capture_output=True, text=True,
                timeout=5, env=dict(os.environ, PATH=str(root) + os.pathsep + os.environ['PATH'],
                    CALL_LOG=str(log)))
            return result, log.read_text().splitlines() if log.exists() else []

    def test_incomplete_markers_refuse_before_any_service_or_configuration_mutation(self):
        for marker in (None, '', '1\n', 'installation_complet', 'installation_complete\n1\n'):
            with self.subTest(marker=marker):
                result, calls = self.run_restart(marker)
                self.assertNotEqual(0, result.returncode)
                self.assertIn('installation incomplete', result.stderr)
                self.assertEqual([], calls)

    def test_completed_installation_preserves_restart_order(self):
        result, calls = self.run_restart('installation_complete\n')
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(['stop openvidu', 'update-config', 'start openvidu'], calls)


if __name__ == '__main__':
    unittest.main()
