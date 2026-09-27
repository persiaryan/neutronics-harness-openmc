"""Small private controller for a fresh, networkless, mount-free XML inspector."""
import json
from pathlib import Path
import subprocess
import time
import uuid
import xml.etree.ElementTree as ET

from evaluator.inspect import inspect_model, parse_xml
from evaluator.run import bounded, digest, docker, write_json

IMAGE = 'sha256:bb4e5420624725c5c1f6899ed766a50a1e3addc30daa04a0eb1d03f9838f7930'
LABEL = 'neutronics-harness-v5.scientific-inspector'
WORKER = Path(__file__).with_name('worker.py')
TMPFS = {'/tmp': 'rw,nosuid,nodev,size=134217728,uid=1000,gid=1000,mode=700'}


def admit(xml):
    inspect_model(xml)
    root = parse_xml(xml)
    geometry = root.find('geometry')
    if len(geometry.findall('cell')) > 2000 or len(geometry) > 5000:
        raise ValueError('Geometry exceeds inspection limits')
    if any(c.tag not in {'cell','surface','lattice'} for c in geometry):
        raise ValueError('Scientific inspector supports inline CSG and rectangular lattices only')
    materials = root.find('materials')
    if len(materials.findall('material')) > 1000:
        raise ValueError('Too many materials')
    if any(c.tag not in {'material','cross_sections'} for c in materials):
        raise ValueError('Unsupported material input')
    for material in materials.findall('material'):
        if any(c.tag not in {'density','nuclide','sab','isotropic','temperature','volume'} for c in material):
            raise ValueError('Only explicit nuclide materials are supported')
    for section in (geometry, materials):
        for node in section.iter():
            if set(node.attrib) & {'file','filename','path','library','directory'}:
                raise ValueError('External inputs are unsupported')
    for tag in ('cell','surface','lattice'):
        ids = [c.get('id') for c in geometry.findall(tag)]
        if None in ids or len(ids) != len(set(ids)):
            raise ValueError('Missing or duplicate geometry IDs')
    ids = [m.get('id') for m in materials.findall('material')]
    if None in ids or len(ids) != len(set(ids)):
        raise ValueError('Missing or duplicate material IDs')
    tags = [s.tag for s in root.find('settings') if s.tag not in {'source','mesh'}]
    if len(tags) != len(set(tags)):
        raise ValueError('Duplicate settings')
    return root


def create_args(name):
    return ['create','--name',name,'--label',LABEL+'='+name,'--network','none',
            '--read-only','--cap-drop','ALL','--security-opt','no-new-privileges=true',
            '--user','1000:1000','--pids-limit','128','--memory','1g','--cpus','2',
            '--init','--log-driver','none','--tmpfs','/tmp:'+TMPFS['/tmp'], IMAGE]


def verify(info):
    h,c = info['HostConfig'], info['Config']
    checks = {
        'pinned_image': info['Image'] == IMAGE,
        'no_mounts': not info['Mounts'] and not h.get('Binds'),
        'network_none': h['NetworkMode'] == 'none',
        'readonly_root': h['ReadonlyRootfs'] is True,
        'nonroot': c['User'] == '1000:1000',
        'no_privilege': not h['Privileged'] and not h.get('CapAdd') and not h.get('Devices'),
        'capabilities_dropped': h['CapDrop'] == ['ALL'],
        'no_new_privileges': 'no-new-privileges=true' in h['SecurityOpt'],
        'private_namespaces': h.get('PidMode','') == '' and h['IpcMode'] == 'private',
        'resource_limits': h['Memory'] == 1024**3 and h['NanoCpus'] == 2_000_000_000 and h['PidsLimit'] == 128,
        'bounded_tmpfs': h['Tmpfs'] == TMPFS,
        'trusted_idle_entrypoint': c['Entrypoint'] == ['python','-I','-B','/opt/evaluator/idle.py'],
        'no_daemon_log': h['LogConfig']['Type'] == 'none',
    }
    if not all(checks.values()):
        raise RuntimeError('Inspector boundary mismatch: '+', '.join(k for k,v in checks.items() if not v))
    return checks


def inspect_xml(xml, points, output, *, wall_seconds=60, capability='legacy'):
    """No retries. Preserve the failed run and refuse leftovers before a new run."""
    output = Path(output)
    if capability not in ('legacy', 'effective-boundary-v2') or capability != 'legacy' and points:
        raise ValueError('Unknown inspector capability or unexpected boundary query points')
    if not 1 <= wall_seconds <= 120 or len(points) > 12000:
        raise ValueError('Unsupported inspector budget')
    output.mkdir(parents=True, exist_ok=False)
    name = 'neutronics-v5-scientific-'+uuid.uuid4().hex[:16]
    started, attempted, admitted = time.monotonic(), False, False
    result = {'status':'infrastructure_failure','cleanup_confirmed':False,'container_name':name}
    try:
        admit(xml)
        admitted = True
        worker = (WORKER if capability == 'legacy' else Path(__file__).with_name('boundary_worker_v2.py')).read_bytes()
        payload = json.dumps({'xml':xml.decode('utf-8'),'points':points}, separators=(',',':'), allow_nan=False).encode()
        if len(payload) > 4_000_000:
            raise ValueError('Inspector input exceeds byte budget')
        (output/'input.json').write_bytes(payload)
        (output/'worker.py').write_bytes(worker)
        write_json(output/'manifest.json', {'format':('private-scientific-inspection-v3' if capability=='legacy'
                                                     else 'private-boundary-inspection-v2'),'image_id':IMAGE,
            'model_xml_sha256':digest(xml),'worker_sha256':digest(worker),'input_sha256':digest(payload),
            'points':len(points),'wall_seconds':wall_seconds,'candidate_python_access':False,
            'nuclear_data_access':False,'host_mounts':False,'native_transport':'not_run'})
        if docker('ps','-aq','--filter','label='+LABEL):
            raise RuntimeError('Unreconciled scientific inspector container exists')
        image = json.loads(docker('image','inspect',IMAGE))[0]
        if image['Id'] != IMAGE:
            raise RuntimeError('Inspector image mismatch')
        attempted = True
        docker(*create_args(name))
        info = json.loads(docker('inspect',name))[0]
        write_json(output/'container-inspect.json',info)
        write_json(output/'container-checks.json',verify(info))
        docker('start',name)
        execution = bounded(['docker','exec','-i',name,'python','-I','-B','-c',worker.decode()],
                            timeout=wall_seconds, limit=2_000_000, data=payload)
        (output/'stdout.json').write_bytes(execution.pop('stdout'))
        (output/'stderr.txt').write_bytes(execution.pop('stderr'))
        write_json(output/'execution.json',execution)
        if execution['exit_code'] != 0 or execution['stop_reason']:
            raise RuntimeError('Inspector execution failed: '+str(execution))
        observation = json.loads((output/'stdout.json').read_bytes())
        statuses = {'inspected', 'unsupported_or_invalid'}
        if capability == 'legacy':
            statuses.add('invalid_model')
        if observation.get('status') not in statuses:
            raise RuntimeError('Unexpected inspector response')
        result.update(observation)
    except (ValueError, RuntimeError, OSError, ET.ParseError, subprocess.SubprocessError) as exc:
        result.update(error_type=type(exc).__name__, error=str(exc)[:1500])
        if not admitted and isinstance(exc,(ValueError,ET.ParseError)):
            result['status'] = 'unsupported_or_invalid'
    finally:
        try:
            if attempted:
                if docker('ps','-aq','--filter','name=^/'+name+'$'):
                    docker('rm','-f',name)
                if docker('ps','-aq','--filter','name=^/'+name+'$'):
                    raise RuntimeError('Inspector container remains')
            result['cleanup_confirmed'] = True
        except (RuntimeError,OSError,subprocess.SubprocessError) as exc:
            result.update(status='infrastructure_failure',cleanup_error=str(exc))
        result['elapsed_seconds'] = round(time.monotonic()-started,3)
        write_json(output/'result.json',result)
    return result
