"""Synthetic P3 receipts produced by the real controllers with execution doubles.

No OpenMC, model generation, private reference, factory or transport is executed.
These fixtures qualify receipt handling only, not the underlying observations.
"""
import json
from pathlib import Path
from unittest.mock import patch

from builder import boundary_tool, openmc_python
from evaluation.scientific import boundaries, inspection
from evaluator.run import digest, write_json


def model(material='74'):
    return (
        '<model><materials><material id="1"><density units="sum"/>'
        '<nuclide name="H1" ao="0.02"/></material></materials><geometry>'
        '<surface id="1" type="x-plane" coeffs="-1" boundary="vacuum"/>'
        '<surface id="2" type="x-plane" coeffs="1" boundary="vacuum"/>'
        '<surface id="3" type="y-plane" coeffs="-1" boundary="vacuum"/>'
        '<surface id="4" type="y-plane" coeffs="1" boundary="vacuum"/>'
        '<surface id="5" type="z-plane" coeffs="-1" boundary="vacuum"/>'
        '<surface id="6" type="z-plane" coeffs="1" boundary="vacuum"/>'
        f'<cell id="1" material="{material}" universe="1" region="1 -2 3 -4 5 -6"/>'
        '</geometry><settings/></model>').encode()


def failure(material='74', *, error_type='KeyError'):
    return dict(status='unsupported_or_invalid', error_type=error_type, error=repr(material))


def observation(xml):
    return dict(status='inspected', observer_version=boundaries.VERSION, openmc_version='0.15.3',
        model_xml_sha256=digest(xml), domain=dict(status='indeterminate', cause='synthetic_fixture'),
        faces=[], surfaces=[], coverage={}, limitations=['synthetic_fixture'])


def inspector_info():
    return dict(Image=inspection.IMAGE, Mounts=[], Config=dict(
        User='1000:1000', Entrypoint=['python', '-I', '-B', '/opt/evaluator/idle.py']),
        HostConfig=dict(NetworkMode='none', ReadonlyRootfs=True, Privileged=False,
            CapDrop=['ALL'], SecurityOpt=['no-new-privileges=true'], PidMode='', IpcMode='private',
            Memory=1024**3, NanoCpus=2_000_000_000, PidsLimit=128, Tmpfs=inspection.TMPFS,
            LogConfig=dict(Type='none')))


def retain_inspection(folder, xml, stdout, *, exit_code=0, stop_reason=None):
    """Write genuine controller records, substituting only Docker/process execution."""
    info = inspector_info()

    def docker(*args):
        if args[0] == 'ps':
            return ''
        if args[:2] == ('image', 'inspect'):
            return json.dumps([dict(Id=inspection.IMAGE)])
        if args[0] == 'inspect':
            return json.dumps([info])
        return ''

    with patch.object(inspection, 'docker', side_effect=docker), \
         patch.object(inspection, 'bounded', return_value=dict(
             exit_code=exit_code, stop_reason=stop_reason,
             stdout=json.dumps(stdout).encode(), stderr=b'')):
        return inspection.inspect_xml(xml, [], folder, wall_seconds=120, capability='effective-boundary-v2')


def builder_info():
    info = inspector_info()
    info['Id'] = 'synthetic-owner'
    info['Image'] = openmc_python.IMAGE_ID
    info['Config']['Entrypoint'] = ['python3', '-B', '/opt/builder/entry.py']
    info['HostConfig']['Memory'] = 2 * 1024**3
    info['HostConfig']['Tmpfs'] = {'/work': '', '/tmp': ''}
    return info


def session(folder):
    """Use the real adapter; add synthetic launcher/bridge/owner receipts."""
    folder = Path(folder)
    info = builder_info()
    tool = boundary_tool.Session(folder, dict(container_id=info['Id'], image_id=info['Image']))
    for name, source in [('client.py', boundary_tool.CLIENT), ('bridge.py', boundary_tool.BRIDGE)]:
        (folder/name).write_bytes(source.read_bytes())
    for name, value in {
        'container.json': info,
        'client-staging.json': dict(exit_code=0, stop_reason=None),
        'feedback-staging.json': dict(exit_code=0, stop_reason=None),
        '../manifest.json': dict(mode='mock'),
        '../lifecycle.json': dict(container_id=info['Id'], state='removed'),
    }.items():
        write_json(folder/name, value)
    close_session(tool)
    return tool


def close_session(tool):
    write_json(tool.output/'bridge-cleanup.json', dict(host_bridge_closed=True,
        owner_container_removal_required=True, attempted_calls=tool.calls))


def invoke(tool, xml, stdout, **execution):
    def observe(data, folder, *, wall_seconds):
        assert wall_seconds == 120
        return retain_inspection(folder, data, stdout, **execution)

    with patch.object(boundaries, 'observe', side_effect=observe):
        result = tool.inspect_boundaries(dict(tool='inspect_boundaries', xml=xml.decode()),
                                         remaining_seconds=600)
    close_session(tool)
    return result


def snapshot(folder):
    return {p.relative_to(folder).as_posix(): p.read_bytes()
            for p in folder.rglob('*') if p.is_file()}
