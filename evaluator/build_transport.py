"""Build the separate native transport runtime from pinned local dependencies."""
import json
from pathlib import Path
import subprocess
import uuid

from evaluator.build import DEPENDENCY_ID

NATIVE_ID = 'sha256:973f4f64b0e4df0b32c9e1578bba8de333d3b423e89fae8d29f397bd03a2ce8c'
IMAGE = 'neutronics-v5-transport:openmc-0.15.3'


def main():
    aliases = []
    try:
        arguments = []
        for key, identity in (('DEPENDENCY_IMAGE', DEPENDENCY_ID), ('NATIVE_IMAGE', NATIVE_ID)):
            info = json.loads(subprocess.check_output(['docker', 'image', 'inspect', identity]))[0]
            if info['Id'] != identity:
                raise RuntimeError('Dependency image identity mismatch')
            alias = 'neutronics-v5-dependencies:' + uuid.uuid4().hex
            subprocess.run(['docker', 'tag', identity, alias], check=True)
            aliases.append(alias)
            arguments += ['--build-arg', key + '=' + alias]
        context = Path(__file__).parent / 'runtime'
        subprocess.run(['docker', 'build', '--network=none', '-f', str(context / 'Dockerfile.transport'),
                        *arguments, '-t', IMAGE, str(context)], check=True)
        print(subprocess.check_output(['docker', 'image', 'inspect', IMAGE,
                                       '--format', '{{.Id}}']).decode().strip())
    finally:
        for alias in aliases:
            subprocess.run(['docker', 'image', 'rm', alias], check=True)


if __name__ == '__main__':
    main()
