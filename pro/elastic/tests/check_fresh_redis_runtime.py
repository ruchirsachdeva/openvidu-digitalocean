"""Explicit local check; no production configuration, credentials or host ports.

Default: real Compose rendering only. --runtime additionally runs disposable Redis
with synthetic state. Keep the temporary directory for inspection, remove only the
uniquely named test project's containers. Never run automatically in unit discovery.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('fresh_redis', ROOT / 'prepare-fresh-redis.py')
fresh = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fresh)


IMAGES = {
    '8.6.2-alpine': 'c5e375abb885e6b2021c0377879e4890bf76f9065b8922ffc113f2b226b9fc17',
    '8.6.4-alpine': '2cc044fc5a07c9b701f8f1255a309ae9ad7856e694ac03513bf3648c01e40763',
}


def check(runtime=False, version='8.6.2-alpine', upgrade_rollback=False):
    if upgrade_rollback and (not runtime or version != '8.6.2-alpine'):
        raise ValueError('Upgrade/rollback requires runtime and the 8.6.2 baseline')
    expected_image = IMAGES[version]
    directory = Path(tempfile.mkdtemp(prefix='cu-fresh-redis-'))
    project = directory.name
    (directory / 'config').mkdir()
    (directory / 'config/redis.env').write_text(
        'REDIS_PASSWORD=synthetic-test-only\nREDIS_INTERNAL_PORT=17000\nREDIS_IO_THREADS=1\n')
    base = {'services': {'redis': {'image': 'docker.io/redis:' + version,
        'network_mode': 'none', 'cpus': 1, 'mem_limit': '256m',
        'volumes': ['./config:/config:ro']}}}
    (directory / 'docker-compose.yaml').write_text(json.dumps(base))
    env = dict(os.environ)
    # Do not inherit a developer's separate application Compose env file.
    env.pop('COMPOSE_ENV_FILES', None)
    report = {'directory': str(directory), 'project': project, 'runtimeRequested': runtime,
              'checks': {}, 'productionDataUsed': False, 'redisVersion': version}
    command = ['docker', 'compose', '-p', project, '-f', str(directory / 'docker-compose.yaml'),
               '-f', str(directory / 'docker-compose.override.yaml')]

    def execute(args, timeout=60):
        # Never inherit a remote engine selected by another task or DOCKER_HOST.
        if args[0] == 'docker':
            args = ['docker', '--context', 'desktop-linux', *args[1:]]
        result = subprocess.run(args, cwd=directory, env=env, capture_output=True,
                                text=True, timeout=timeout)
        if result.returncode:
            raise RuntimeError('Isolated command failed: ' + result.stderr[-1000:])
        return result.stdout

    def prepare_command(args):
        if args[:3] == ['docker', 'ps', '-aq']:
            # This fixture is a unique project with no globally named container.
            # The default mode deliberately does not require a Docker daemon.
            if not runtime: return ''
            return execute(['docker', 'ps', '-aq', '--filter',
                            'label=com.docker.compose.project=' + project])
        args = ['docker', 'compose', *args[1:]]
        args[args.index('-p') + 1] = project
        return execute(args)

    def redis(*args):
        return execute(command + ['exec', '-T', '-e', 'REDISCLI_AUTH=synthetic-test-only',
            'redis', 'redis-cli', '-p', '17000', '--raw', *args]).strip()

    def start():
        execute(command + ['up', '-d'], timeout=120)
        for _ in range(20):
            try:
                if redis('PING') == 'PONG': return
            except RuntimeError: pass
            time.sleep(.25)
        raise RuntimeError('Test Redis did not become ready')

    try:
        fresh.prepare(directory, (ROOT / 'redis-durability.override.yaml').read_text(), prepare_command)
        report['checks']['realComposePreparation'] = True
        if runtime:
            start()
            report['imageId'] = execute(command + ['images', '-q', 'redis']).strip()
            assert report['imageId'].removeprefix('sha256:') == expected_image
            assert redis('CONFIG', 'GET', 'appendonly') == 'appendonly\nyes'
            assert redis('CONFIG', 'GET', 'appendfsync') == 'appendfsync\neverysec'
            assert redis('HSET', 'egress', 'EG_synthetic', 'complete') == '1'
            execute(command + ['stop', '-t', '60'])
            ids = execute(command + ['ps', '-aq']).split()
            assert len(ids) == 1
            assert execute(['docker', 'inspect', ids[0], '--format', '{{.State.ExitCode}}']).strip() == '0'
            execute(command + ['down'])
            start()
            assert redis('HGET', 'egress', 'EG_synthetic') == 'complete'
            report['checks']['freshStartAndRecreationSurvival'] = True
            execute(command + ['stop', '-t', '60'])
            ids = execute(command + ['ps', '-aq']).split()
            assert len(ids) == 1
            assert execute(['docker', 'inspect', ids[0], '--format', '{{.State.ExitCode}}']).strip() == '0'
            # Restore a cleanly stopped COPY into a separate test directory.
            # Never roll a live dataset back or overwrite the original fixture.
            restored = directory / 'restored'
            restored.mkdir()
            shutil.copytree(directory / 'data', restored / 'data')
            shutil.copytree(directory / 'config', restored / 'config')
            for filename in ('docker-compose.yaml', 'docker-compose.override.yaml'):
                shutil.copy2(directory / filename, restored / filename)
            execute(command + ['down'])
            command = ['docker', 'compose', '-p', project,
                '-f', str(restored / 'docker-compose.yaml'),
                '-f', str(restored / 'docker-compose.override.yaml')]
            start()
            assert redis('HGET', 'egress', 'EG_synthetic') == 'complete'
            report['checks']['stoppedBackupRestore'] = True
            if upgrade_rollback:
                # Work only on the restored COPY. Rolling back to the old backup
                # would discard receipts created during the upgraded interval.
                for target in ('8.6.4-alpine', '8.6.2-alpine'):
                    execute(command + ['stop', '-t', '60'])
                    ids = execute(command + ['ps', '-aq']).split()
                    assert len(ids) == 1
                    assert execute(['docker', 'inspect', ids[0], '--format', '{{.State.ExitCode}}']).strip() == '0'
                    execute(command + ['down'])
                    base['services']['redis']['image'] = 'docker.io/redis:' + target
                    (restored / 'docker-compose.yaml').write_text(json.dumps(base))
                    start()
                    actual_image = execute(command + ['images', '-q', 'redis']).strip()
                    assert actual_image.removeprefix('sha256:') == IMAGES[target]
                    assert redis('HGET', 'egress', 'EG_synthetic') == 'complete'
                    if target == '8.6.4-alpine':
                        assert redis('HSET', 'egress', 'EG_after_upgrade', 'complete') == '1'
                        # Exercise the new version's snapshot writer too.
                        assert redis('SAVE') == 'OK'
                    else:
                        assert redis('HGET', 'egress', 'EG_after_upgrade') == 'complete'
                    report['checks']['transitionTo_' + target] = True
                report['checks']['rollbackPreservesNewReceipt'] = True
        report['outcome'] = 'passed'
    except Exception as error:
        report['outcome'] = 'failed'
        report['errorType'] = type(error).__name__
        raise
    finally:
        if runtime:
            try:
                execute(command + ['down', '--timeout', '60'], timeout=90)
                report['containersRemoved'] = True
            except Exception:
                report['containersRemoved'] = False
                report['outcome'] = 'failed'
        (directory / 'verification.json').write_text(json.dumps(report, indent=2))
        print(json.dumps(report), flush=True)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime', action='store_true')
    parser.add_argument('--redis-version', choices=IMAGES, default='8.6.2-alpine')
    parser.add_argument('--upgrade-rollback', action='store_true')
    args = parser.parse_args()
    result = check(args.runtime, args.redis_version, args.upgrade_rollback)
    raise SystemExit(0 if result['outcome'] == 'passed' else 1)
