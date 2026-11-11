"""Local Terraform state transition test; cloud commands replaced with event markers.

Only disposable local state is applied. No provider credentials or cloud resources.
The actual resource/provisioner structure is retained; unrelated dependencies and
cloud-valued triggers are replaced by local fixture values.
"""
import json
from pathlib import Path
import re
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]
NEW = (ROOT / 'tf-do-openvidu-elastic.tf').read_text()
# Last pre-split safety revision: do not let a later HEAD erase migration coverage.
OLD = subprocess.run(['git', 'show', '7e93682:pro/elastic/tf-do-openvidu-elastic.tf'],
                     cwd=ROOT, check=True, capture_output=True, text=True).stdout


def fixture(source):
    result = '''terraform {
  required_providers {
    null = { source = "hashicorp/null", version = "3.2.4" }
  }
}
variable "revision" { type = string }
resource "null_resource" "cleanup_media_nodes" {
  provisioner "local-exec" {
    when = destroy
    command = "echo media-cleanup >> events.log"
  }
}
'''
    for name in ('autoscaler_lifecycle', 'deploy_autoscaler_function'):
        marker = 'resource "null_resource" "' + name + '"'
        if marker not in source:
            continue
        block = marker + source.split(marker, 1)[1].split('\nresource ', 1)[0]
        block = block.split('\n# DigitalOcean Space', 1)[0]
        block = re.sub(r'count = [^\n]+', 'count = 1', block)
        triggers = 'identity = "fixture"' if name == 'autoscaler_lifecycle' else 'code_hash = var.revision'
        block = re.sub(r'triggers = \{.*?\n  \}', 'triggers = { ' + triggers + ' }', block, flags=re.S)
        block = re.sub(r'environment = \{.*?\n    \}', 'environment = {}', block, flags=re.S)
        # Keep when=destroy and provisioner boundaries; replace only side effects.
        block = re.sub(r'command = <<-EOT\n.*?\n    EOT',
                       lambda m: 'command = "echo ' + ('namespace-cleanup' if 'Destroying autoscaler function' in m[0] else 'action-update') + ' >> events.log"',
                       block, flags=re.S)
        dependencies = 'null_resource.cleanup_media_nodes'
        if name == 'deploy_autoscaler_function' and '"autoscaler_lifecycle"' in source:
            dependencies += ', null_resource.autoscaler_lifecycle'
        block = re.sub(r'depends_on = \[.*?\n  \]', 'depends_on = [' + dependencies + ']', block, flags=re.S)
        if '${' in block or 'digitalocean_' in block or 'curl ' in block:
            raise ValueError('Fixture still contains cloud configuration')
        result += block + '\n'
    return result


def check():
    directory = Path(tempfile.mkdtemp(prefix='cu-lifecycle-'))
    def run(*args):
        result = subprocess.run(['terraform', *args], cwd=directory, capture_output=True,
                                text=True, timeout=90)
        if result.returncode:
            raise RuntimeError(result.stderr[-2000:])
        return result.stdout
    def events():
        return (directory / 'events.log').read_text().splitlines()
    (directory / 'main.tf').write_text(fixture(OLD))
    run('init', '-backend=false', '-input=false', '-no-color')
    run('apply', '-auto-approve', '-input=false', '-no-color', '-var=revision=old')
    (directory / 'main.tf').write_text(fixture(NEW))
    run('plan', '-input=false', '-no-color', '-var=revision=new', '-out=transition.tfplan')
    plan = json.loads(run('show', '-json', 'transition.tfplan'))
    run('apply', '-auto-approve', '-input=false', '-no-color', 'transition.tfplan')
    assert 'namespace-cleanup' not in events(), events()
    run('apply', '-auto-approve', '-input=false', '-no-color', '-var=revision=next')
    assert 'namespace-cleanup' not in events(), events()
    run('destroy', '-auto-approve', '-input=false', '-no-color', '-var=revision=next')
    observed = events()
    assert observed.count('namespace-cleanup') == 1, observed
    assert observed.index('namespace-cleanup') < observed.index('media-cleanup'), observed
    report = {'outcome': 'passed', 'directory': str(directory), 'events': observed,
              'transitionActions': {r['address']: r['change']['actions'] for r in plan['resource_changes']},
              'cloudResourcesUsed': False}
    (directory / 'receipt.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report))


if __name__ == '__main__':
    check()
