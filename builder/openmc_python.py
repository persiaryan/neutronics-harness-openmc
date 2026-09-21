"""Pinned optional authoring environment; no reference or evaluator code is copied."""
import json
from pathlib import Path
import subprocess
import uuid

IMAGE = 'neutronics-v5-codex:0.153.4-openmc-0.15.3'
IMAGE_ID = 'sha256:8dfbafd6160d9833111ac51d0b066126066f1690d3c315261583baf5f12b81a5'
BUILDER_ID = 'sha256:5d6f2d684f4f74f180c99351803c1c14547720372cc94cd1e56d6c4cf0c1de3a'
PACKAGES_ID = 'sha256:bb4e5420624725c5c1f6899ed766a50a1e3addc30daa04a0eb1d03f9838f7930'
LABEL = 'neutronics-harness-v5.authoring-environment'
ENVIRONMENT = 'openmc-python-0.15.3'
CONDITION = 'codex_client_with_export_contract_feedback_and_openmc_python_v1'

# Run before the model starts. The result stays with the operator, not in the
# prompt, workspace or model tool history. No OpenMC import occurs on the host.
PROBE = '''import hashlib, importlib.util, json, os, shutil, tempfile
from pathlib import Path
spec = importlib.util.find_spec('openmc')
version = source_hash = None
if spec is not None:
    with tempfile.TemporaryDirectory(prefix='openmc-preflight-', dir='/tmp') as cache:
        os.environ['MPLCONFIGDIR'] = cache
        import openmc
        version = openmc.__version__
        source_hash = hashlib.sha256(Path(openmc.__file__).read_bytes()).hexdigest()
print(json.dumps({'openmc_version': version, 'openmc_init_sha256': source_hash,
    'native_openmc_present': shutil.which('openmc') is not None or Path('/opt/openmc').exists(),
    'data_directory_present': Path('/data').exists(),
    'cross_sections_configured': bool(os.environ.get('OPENMC_CROSS_SECTIONS'))}))
'''


def verify_image(info, enabled):
    label = (info.get('Config', {}).get('Labels') or {}).get(LABEL)
    if label != (ENVIRONMENT if enabled else None):
        raise ValueError('Authoring image label does not match --openmc-python condition')


def verify_probe(record, enabled):
    expected = '0.15.3' if enabled else None
    if (record.get('openmc_version') != expected
            or record.get('native_openmc_present') is not False
            or record.get('data_directory_present') is not False
            or record.get('cross_sections_configured') is not False
            or (enabled and not record.get('openmc_init_sha256'))):
        raise ValueError('Authoring package/data probe does not match the declared condition')


def main():
    aliases = []
    try:
        arguments = []
        for key, identity in (('BUILDER_IMAGE', BUILDER_ID), ('PACKAGES_IMAGE', PACKAGES_ID)):
            info = json.loads(subprocess.check_output(['docker', 'image', 'inspect', identity]))[0]
            if info['Id'] != identity:
                raise RuntimeError('Authoring dependency image identity mismatch')
            alias = 'neutronics-v5-authoring-dependencies:' + uuid.uuid4().hex
            subprocess.run(['docker', 'tag', identity, alias], check=True)
            aliases.append(alias)
            arguments += ['--build-arg', key + '=' + alias]
        context = Path(__file__).parent / 'runtime'
        subprocess.run(['docker', 'build', '--network=none', '-f', str(context / 'Dockerfile.openmc'),
                        *arguments, '-t', IMAGE, str(context)], check=True)
        print(subprocess.check_output(['docker', 'image', 'inspect', IMAGE,
                                       '--format', '{{.Id}}']).decode().strip())
    finally:
        failures = []
        for alias in aliases:
            try:
                subprocess.run(['docker', 'image', 'rm', alias], check=True)
            except (OSError, subprocess.CalledProcessError) as error:
                failures.append(f'{alias}: {error}')
        if failures:
            raise RuntimeError('Temporary build alias cleanup uncertain: ' + '; '.join(failures))


if __name__ == '__main__':
    main()
