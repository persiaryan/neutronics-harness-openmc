"""Trusted pre-execution probe; run before any candidate code is present."""
import importlib.metadata
import json
import os
from pathlib import Path
import socket
import openmc

path = Path('/work/probe')
path.write_text('ok')
writable = path.read_text() == 'ok'
path.unlink()
connection = socket.socket()
connection.settimeout(1)
denied = connection.connect_ex(('1.1.1.1', 443)) != 0
connection.close()
checks = {
    'openmc_0153': openmc.__version__ == '0.15.3',
    'nonroot': os.getuid() == 1000,
    'workspace_writable': writable,
    'no_host_home': not Path('/Users').exists(),
    'no_docker_socket': not Path('/var/run/docker.sock').exists(),
    'no_reference_checkout': not Path('/evaluation').exists(),
    'no_inherited_credentials': not any(k in os.environ for k in
        ('OPENAI_API_KEY', 'CODEX_HOME', 'CODEX_ACCESS_TOKEN')),
    'external_network_denied': denied,
    'data_index_present': Path(os.environ['OPENMC_CROSS_SECTIONS']).is_file(),
}
print(json.dumps({'checks': checks, 'python_packages': sorted(
    (d.metadata['Name'], d.version) for d in importlib.metadata.distributions())}))
