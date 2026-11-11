"""Offline characterization, NOT a recording-capacity qualification.

Use only the cached, pinned OpenVidu 3.8 image. In this image an obsolete YAML
key can be silently ignored; a successful parse is not proof of a recorder slot
limit. No Redis/provider connection, host mount, recording or cloud VM is used.
Run explicitly with --runtime; keep this out of ordinary unit-test discovery.
"""
import argparse
import json
import subprocess
import uuid


IMAGE = ('openvidu/egress@sha256:'
         '01a31780783080259b7f218f624e654dc30572be5b5f7999123ac0d98c259475')


def probe(*args):
    name = 'cu-recorder-contract-' + uuid.uuid4().hex
    try:
        result = subprocess.run(
            ['docker', 'run', '--name', name, '--rm', '--pull=never', '--network', 'none',
             '--platform', 'linux/amd64', '--cap-drop', 'ALL',
             '--security-opt', 'no-new-privileges', '--read-only',
             '--entrypoint', '/usr/bin/egress', IMAGE, *args],
            capture_output=True, text=True, timeout=30,
        )
        return result.returncode, result.stdout + result.stderr
    finally:
        # A CLI timeout alone does not stop its container. Address only this
        # probe's unique name; never prune other tests or the user's containers.
        subprocess.run(['docker', 'rm', '--force', name], capture_output=True, timeout=10)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime', action='store_true', required=True)
    parser.parse_args()

    code, output = probe('--version')
    if code != 0 or output.strip() != 'egress version 1.12.0':
        raise SystemExit('Pinned recorder could not be identified; no contract established')

    code, output = probe('--config-body', 'cpu_cost: {max_pulse_clients: not-a-number}')
    if code == 0 or 'could not parse config' not in output or 'into int' not in output:
        raise SystemExit('Known integer control did not reject the invalid value')

    code, output = probe('--config-body', 'cpu_cost: {max_concurrent_web: not-a-number}')
    # Deliberately omit Redis. This exact binary reaches service startup and
    # fails there, after ignoring the unknown key. Do not report that failure
    # as successful service startup or as a reproduction of a production crash.
    if code == 0 or 'could not parse config' in output or 'main.runService(' not in output:
        raise SystemExit('Obsolete-key behavior changed or is inconclusive; review the image')

    print(json.dumps({
        'image': IMAGE,
        'version': '1.12.0',
        'checksPassed': 3,
        'obsoleteMaxConcurrentWebIgnored': True,
        'knownMaxPulseClientsTypeValidated': True,
        'recordingSlotLimitEstablished': False,
        'liveQualification': False,
    }, indent=2))


if __name__ == '__main__':
    main()
