"""First-start-only arming from an explicit reviewed semantic fleet policy.

Uses vendor init to render configuration, then the existing fresh-recorder armer.
Never restarts an existing recorder, changes policy or recovers/deletes recordings.
"""
import hashlib
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import subprocess
from recorder_admission import parse_config, reviewed_config, validate_combined_cpu_policy


def prepare(root, descriptor, run, arm):
    root = Path(root)
    guard = root / 'courseultra-recorder-guard'
    if (guard / 'egress-config.sha256').read_bytes() != b'UNARMED\n':
        raise ValueError('Only a fresh unarmed node can be prepared automatically')
    if run(['docker', 'ps', '-aq', '--filter', 'name=^/egress$']).strip():
        raise ValueError('Existing recorder requires explicit lifecycle handling')
    for name in ('tmp', 'backup_storage'):
        path = root / 'data/egress_data/home/egress' / name
        if any(p.is_symlink() for p in (path, *path.parents)) or not path.is_dir() or any(path.iterdir()):
            raise ValueError('Preserve existing recovery data')
    compose = ['/usr/local/bin/docker-compose', '-p', 'openvidu', '-f', str(root / 'docker-compose.yaml'),
               '-f', str(root / 'docker-compose.override.yaml')]
    init = json.loads(run(compose + ['config', '--format', 'json']))['services']['openvidu-init']
    if (init.get('image') not in ('openvidu/openvidu-operator:3.8.0', 'docker.io/openvidu/openvidu-operator:3.8.0')
            or init.get('environment', {}).get('MODE') != 'init-elastic-media'
            or init.get('privileged') or init.get('entrypoint') or init.get('command')
            or init.get('pid') or init.get('devices') or init.get('cap_add')):
        raise ValueError('Reviewed config initializer required')
    mounts = init.get('volumes', [])
    expected = {'/opt/openvidu/config': str(root / 'config'), '/opt/openvidu/data/runtime': str(root / 'data/runtime'),
                '/etc/localtime': '/etc/localtime'}
    if len(mounts) != len(expected) or {v.get('target'): v.get('source') for v in mounts} != expected or any(v.get('type') != 'bind' for v in mounts):
        raise ValueError('Unreviewed initializer host access')
    # Only init runs here; the reviewed init service has no Docker socket and
    # cannot start room/recording workers. No independent scheduler is introduced.
    run(compose + ['run', '--rm', '--no-deps', 'openvidu-init'])
    config_path = root / 'data/runtime/config/egress/egress.yaml'
    raw = config_path.read_bytes()
    config = parse_config(raw.decode())
    # Retained masters may still distribute the vendor template without metrics.
    # Complete only the explicit listener and single-worker IO drain contract on
    # a never-started recorder. The separately approved policy must match the
    # entire resulting document; existing frozen configs are never rewritten.
    missing_metrics = 'prometheus_port' not in config
    missing_io_workers = 'io_workers' not in config
    if missing_io_workers:
        config['io_workers'] = 1
    if missing_metrics:
        config['prometheus_port'] = 9094
    reviewed_config(config, descriptor['recorderPolicySha256'])
    validate_combined_cpu_policy(config, descriptor)
    if hashlib.sha256((guard / 'start.sh').read_bytes()).hexdigest() != descriptor['startupGuardSha256']:
        raise ValueError('Unreviewed startup guard')
    if missing_metrics or missing_io_workers:
        if any(path.is_symlink() for path in (config_path, *config_path.parents)):
            raise ValueError('Regular recorder configuration required')
        raw = (json.dumps(config, allow_nan=False) + '\n').encode()
        config_path.write_bytes(raw)
    # `create` has no --no-deps option in the installed Compose version.
    # `up --no-start` creates only this container without running the recorder.
    run(compose + ['up', '--no-start', '--no-deps', 'egress'])
    def inspect():
        values = json.loads(run(['docker', 'inspect', 'egress']))
        if len(values) != 1 or values[0]['State']['Status'] != 'created' or values[0]['Image'] != descriptor['recorderImage']:
            raise ValueError('Exact never-started recorder required')
        return values[0]
    arm(root, hashlib.sha256(raw).hexdigest(), inspect)
    # Existing bootstrap now starts the normal stack. If interrupted before this
    # point, UNARMED/mismatched fingerprints retain the original startup barrier.


def initializer_environment(root):
    # The 3.8 vendor initializer checks the same marker set by openvidu.service.
    # This bounded first-start call renders config only; prepare() still validates
    # the init service and never starts media/recording workers through `run`.
    return dict(os.environ, COMPOSE_ENV_FILES=str(Path(root) / 'config/node/media_node.env'),
                RUNNING_SYSTEMD='true')


def main():
    if os.geteuid() != 0:
        raise ValueError('Root first-start preparation required')
    loader = importlib.machinery.SourceFileLoader('fleet_report', str(Path(__file__).with_name('report-fleet-readiness.py')))
    reporter = importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name, loader))
    loader.exec_module(reporter)
    arm_loader = importlib.machinery.SourceFileLoader('fresh_arm', str(Path(__file__).with_name('arm-fresh-recorder.py')))
    armer = importlib.util.module_from_spec(importlib.util.spec_from_loader(arm_loader.name, arm_loader))
    arm_loader.exec_module(armer)
    descriptor = reporter.private_json('/etc/courseultra-capacity-fleet-profile.json')
    root = Path('/opt/openvidu')
    env = initializer_environment(root)
    def run(args):
        result = subprocess.run(args, cwd=root, env=env, capture_output=True, text=True, timeout=60)
        if result.returncode or len(result.stdout) > 4 * 1024 * 1024:
            raise ValueError('First-start preparation command failed')
        return result.stdout
    prepare(root, descriptor, run, armer.arm)


if __name__ == '__main__':
    try:
        main()
    except Exception:
        raise SystemExit('Approved first-start preparation held; no recovery or cleanup attempted')
