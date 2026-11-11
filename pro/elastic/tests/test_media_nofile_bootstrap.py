"""Keep new media nodes off Docker's insufficient inherited worker socket limit."""
import base64
import os
import pathlib
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class MediaNofileBootstrapTest(unittest.TestCase):
    def test_real_shell_installs_retries_and_refuses_operator_override(self):
        source = (ROOT / 'tf-do-openvidu-elastic.tf').read_text()
        script = source[source.index('NOFILE_OVERRIDE='):source.index('# Media node arguments')]
        expected = (ROOT / 'media-nofile.override.yaml').read_bytes()
        script = script.replace('${filebase64("${path.module}/media-nofile.override.yaml")}',
                                base64.b64encode(expected).decode())
        with tempfile.TemporaryDirectory() as directory:
            override = pathlib.Path(directory) / 'docker-compose.override.yaml'
            script = script.replace('/opt/openvidu/docker-compose.override.yaml', str(override))
            for initial in (None, expected, b'services:\n  operator: {}\n'):
                with self.subTest(initial=initial):
                    if initial is not None:
                        override.write_bytes(initial)
                    result = subprocess.run(['/bin/bash', '-eu', '-c', script],
                        env=dict(os.environ, TMPDIR=directory), capture_output=True,
                        text=True, timeout=10)
                    if initial not in (None, expected):
                        self.assertNotEqual(0, result.returncode)
                        self.assertIn('refusing to replace operator configuration', result.stdout)
                        self.assertEqual(initial, override.read_bytes())
                    else:
                        self.assertEqual(0, result.returncode, result.stderr)
                        self.assertEqual(expected, override.read_bytes())

    def test_override_is_scoped_to_media_service(self):
        # Deliberately fixed, dependency-free shape: no image/network/volume change.
        body = '\n'.join(line for line in (ROOT / 'media-nofile.override.yaml').read_text().splitlines()
                         if not line.startswith('#'))
        self.assertEqual(body, 'services:\n  openvidu:\n    ulimits:\n      nofile:\n'
                              '        soft: 65536\n        hard: 524288')

    def test_override_precedes_media_install_and_preserves_other_config(self):
        source = (ROOT / 'tf-do-openvidu-elastic.tf').read_text()
        section = source[source.index('INSTALL_SCRIPT=/tmp/install_ov_media_node.sh'):]
        self.assertLess(section.index('NOFILE_OVERRIDE='), section.index('until bash -c "$FINAL_COMMAND"'))
        self.assertIn('filebase64("${path.module}/media-nofile.override.yaml")', section)
        self.assertIn('! cmp -s "$NOFILE_EXPECTED" "$NOFILE_OVERRIDE"', section)
        self.assertIn('refusing to replace operator configuration', section)


if __name__ == '__main__':
    unittest.main()
