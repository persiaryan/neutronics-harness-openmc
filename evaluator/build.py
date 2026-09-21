"""Build a v5 runtime using only dependencies from a reviewed, pinned local image."""
import json
from pathlib import Path
import subprocess
import uuid

DEPENDENCY_ID = 'sha256:04365c3292351debb38dbf339ad79136e44b6975d2974c193687c8c579eb87cf'
IMAGE = 'neutronics-v5-evaluator:openmc-0.15.3'


def main():
    # Temporary tag is unique; the immutable local identity is checked first.
    info = json.loads(subprocess.check_output(['docker', 'image', 'inspect', DEPENDENCY_ID]))[0]
    if info['Id'] != DEPENDENCY_ID:
        raise RuntimeError('Dependency image identity mismatch')
    alias = 'neutronics-v5-dependencies:' + uuid.uuid4().hex
    subprocess.run(['docker', 'tag', DEPENDENCY_ID, alias], check=True)
    try:
        subprocess.run(['docker', 'build', '--network=none', '--build-arg',
            'DEPENDENCY_IMAGE=' + alias, '-t', IMAGE,
            str(Path(__file__).parent / 'runtime')], check=True)
    finally:
        subprocess.run(['docker', 'image', 'rm', alias], check=True)
    print(subprocess.check_output(['docker', 'image', 'inspect', IMAGE, '--format', '{{.Id}}']).decode().strip())


if __name__ == '__main__':
    main()
