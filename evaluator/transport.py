"""Load an accepted export in a fresh container and run native OpenMC unchanged."""
import hashlib
import json
import math
import os
from pathlib import Path
import time
import uuid

from evaluator import run
from evaluator.build_transport import IMAGE, NATIVE_ID
from evaluator.inspect import parse_xml
from evaluator.transport_input import accepted_export, read_regular, transport_profile

MEMORY = 3 * 1024**3
MAX_ARCHIVE = 128_000_000
MAX_ARTIFACT = 32_000_000
WORK_OPTIONS = {'type': 'tmpfs', 'device': 'tmpfs',
                'o': 'size=268435456,uid=1000,gid=1000,mode=700,nosuid,nodev'}


def data_identity(index, profile):
    """Hash the actual data bytes required by explicit submitted nuclides/S(a,b)."""
    raw = read_regular(index)
    libraries = parse_xml(raw)
    files = {}
    for kind, table in profile['required_tables']:
        matches = [node.get('path') for node in libraries
                   if node.get('type') == kind and table in node.get('materials', '').split()]
        if len(matches) != 1:
            raise ValueError('Nuclear-data table must have one admitted library: ' + table)
        name = matches[0]
        if name not in files:
            path = index.parent / name
            with path.open('rb') as stream:
                sha = hashlib.file_digest(stream, 'sha256').hexdigest()
            files[name] = {'sha256': sha, 'bytes': path.stat().st_size, 'tables': []}
        files[name]['tables'].append([kind, table])
    return {'index_sha256': run.digest(raw), 'files': files,
            'snapshot': 'read_only_host_mount_with_before_after_hash_checks'}


def container_args(name, image_id, index):
    args = run.create_args(name, image_id, index)
    args[args.index('--memory') + 1] = '3g'
    args[args.index('--tmpfs') + 1] = '/input:rw,nosuid,nodev,size=16777216,uid=1000,gid=1000,mode=700'
    return args


def validate_calculation(artifacts, profile, original_xml):
    xml_hash = run.digest(original_xml)
    loaded = json.loads(artifacts['xml-load.json'])
    value = json.loads(artifacts['calculation.json'])
    if (loaded['status'] != 'loaded' or loaded['sampling'] != profile['sampling']
            or loaded['model_xml_sha256'] != xml_hash or not loaded['boundary_checks']
            or not all(loaded['boundary_checks'].values())
            or loaded['scientific_inputs_changed'] is not False
            or loaded['entropy_requested'] != profile['entropy_requested']):
        raise ValueError('Invalid XML-load receipt')
    if (value['status'] != 'calculated_unreviewed' or value['model_xml_sha256'] != xml_hash
            or value['sampling'] != profile['sampling'] or value['openmc_version'] != [0, 15, 3]):
        raise ValueError('Calculation receipt identity mismatch')
    for key in ('mean', 'std_dev'):
        number = value['keff'][key]
        if type(number) not in (int, float) or not math.isfinite(number) or number <= 0:
            raise ValueError('Invalid numerical result')
    statepoint = value['statepoint']
    if statepoint['name'] != f"statepoint.{profile['sampling']['batches']}.h5":
        raise ValueError('Unexpected final statepoint name')
    raw = artifacts[statepoint['name']]
    if run.digest(raw) != statepoint['sha256'] or len(raw) != statepoint['bytes']:
        raise ValueError('Statepoint bytes do not match extraction receipt')
    if artifacts['model.xml'] != original_xml:
        raise ValueError('Transport changed submitted XML')
    return value


class PhaseFailure(Exception):
    pass


def transport(export, output, *, index, image=IMAGE, wall_seconds=300):
    if output.exists():
        raise FileExistsError('Refusing to overwrite transport evidence')
    if not 1 <= wall_seconds <= 1800:
        raise ValueError('Transport wall budget must be 1-1800 seconds')
    # Admission errors still receive a durable result, without starting Docker.
    output.mkdir(parents=True)
    result = {'status': 'failed', 'xml_load': 'not_run', 'transport': 'not_run',
              'statepoint_validation': 'not_run', 'scientific_fidelity': 'not_checked',
              'reference_comparison': 'not_run', 'cleanup_confirmed': True}
    lifecycle = {'state': 'not_created'}
    name, collect, completed, identity = None, False, False, None
    started = time.monotonic()
    try:
        sources = output / 'controller-sources'
        sources.mkdir()
        for relative in ('transport.py', 'transport_input.py', 'run.py', 'inspect.py',
                         'build_transport.py', 'build.py', 'runtime/Dockerfile.transport',
                         'runtime/transport_worker.py', 'runtime/probe.py', 'runtime/idle.py'):
            target = sources / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((Path(__file__).parent / relative).read_bytes())
        run.write_json(output / 'invocation.json', {'export': str(export), 'image': image,
                       'data_index': str(index), 'wall_seconds': wall_seconds})
        try:
            xml, provenance = accepted_export(export)
            (output / 'model.xml').write_bytes(xml)
            run.write_json(output / 'export-provenance.json', provenance)
            profile = transport_profile(xml, index.name)
        except (ValueError, OSError, KeyError, TypeError) as error:
            result.update(status='rejected', reason='input_not_admitted', error=str(error))
            return result
        run.write_json(output / 'input-profile.json', profile)
        index, inventory = run.data_directory(index)
        run.write_json(output / 'data-inventory.json', inventory)
        identity = data_identity(index, profile)
        run.write_json(output / 'data-before.json', identity)
        for command, noun in ((('ps', '-a'), 'container'), (('volume', 'ls'), 'volume')):
            if run.docker(*command, '--filter', 'label=' + run.LABEL, '--format', '{{.Name}}' if noun == 'volume' else '{{.Names}}'):
                raise RuntimeError('A prior evaluator ' + noun + ' remains; reconcile its lifecycle first')
        image_id = json.loads(run.docker('image', 'inspect', image))[0]['Id']
        name = 'neutronics-v5-transport-' + uuid.uuid4().hex[:16]
        lifecycle = {'container_name': name, 'volume_name': name + '-work', 'state': 'creating'}
        run.write_json(output / 'lifecycle.json', lifecycle)
        manifest = {'format': 'isolated-xml-transport-v1', 'image_id': image_id,
                    'native_dependency_image_id': NATIVE_ID, 'model_xml_sha256': run.digest(xml),
                    'candidate_sha256': provenance['candidate_sha256'],
                    'container_name': name, 'wall_seconds': wall_seconds, 'threads': 1,
                    'memory_bytes': MEMORY, 'work_bytes': 268435456,
                    'max_artifact_bytes': MAX_ARTIFACT, 'max_archive_bytes': MAX_ARCHIVE,
                    'scientific_inputs_changed': False, 'candidate_python_access': False,
                    'reference_access': False, 'automatic_feedback': False}
        run.write_json(output / 'manifest.json', manifest)
        run.docker('volume', 'create', '--label', run.LABEL + '=' + name, '--driver', 'local',
                   '--opt', 'type=tmpfs', '--opt', 'device=tmpfs', '--opt', 'o=' + WORK_OPTIONS['o'], name + '-work')
        volume = json.loads(run.docker('volume', 'inspect', name + '-work'))[0]
        run.write_json(output / 'volume.json', volume)
        if volume['Driver'] != 'local' or volume['Options'] != WORK_OPTIONS:
            raise RuntimeError('Transport workspace is not the bounded tmpfs volume')
        lifecycle['container_id'] = run.docker(*container_args(name, image_id, index))
        lifecycle['state'] = 'created'
        run.write_json(output / 'lifecycle.json', lifecycle)
        info = json.loads(run.docker('inspect', name))[0]
        run.write_json(output / 'container.json', info)
        checks = run.verify_container(info, image_id, index, name, memory_bytes=MEMORY)
        checks['bounded_input_tmpfs'] = info['HostConfig']['Tmpfs']['/input'] == (
            'rw,nosuid,nodev,size=16777216,uid=1000,gid=1000,mode=700')
        if not all(checks.values()):
            raise RuntimeError('Transport container boundary mismatch')
        run.write_json(output / 'container-checks.json', checks)
        run.docker('start', name)

        def phase(label, arguments, timeout, data=None):
            nonlocal collect
            execution = run.bounded(['docker', 'exec', '--workdir', '/work',
                                      *(['-i'] if data is not None else []), name, *arguments],
                                     timeout=timeout, data=data)
            for channel in ('stdout', 'stderr'):
                (output / (label + '-' + channel + '.txt')).write_bytes(execution[channel])
            run.write_json(output / (label + '-process.json'),
                           {key: execution[key] for key in ('exit_code', 'stop_reason')})
            if execution['stop_reason']:
                collect = False  # Never collect artifacts from timed-out live processes.
                result.update(status='budget_exceeded', reason=label + '_' + execution['stop_reason'])
                raise PhaseFailure()
            if execution['exit_code']:
                abnormal = execution['exit_code'] < 0 or execution['exit_code'] >= 128
                result.update(status='rejected' if label in {'xml-load', 'openmc'} and not abnormal else 'failed',
                              reason=label + ('_abnormal_exit' if abnormal else '_exit_nonzero'))
                raise PhaseFailure()
            return execution

        probe = phase('preflight', ['python', '-I', '-B', '/opt/evaluator/probe.py'], 30)
        preflight = json.loads(probe['stdout'])
        run.write_json(output / 'preflight.json', preflight)
        if not preflight.get('checks') or not all(preflight['checks'].values()):
            raise RuntimeError('Transport preflight failed')
        version = phase('solver-version', ['/opt/openmc/bin/openmc', '--version'], 30)
        if not version['stdout'].startswith(b'OpenMC version 0.15.3\n'):
            raise RuntimeError('Native solver version mismatch')
        runtime = phase('runtime-identity', ['python', '-I', '-B', '/opt/evaluator/transport_worker.py', 'probe'], 30)
        runtime_identity = json.loads(runtime['stdout'])
        run.write_json(output / 'runtime-identity.json', runtime_identity)
        if runtime_identity['worker_sha256'] != run.digest((sources / 'runtime/transport_worker.py').read_bytes()):
            raise RuntimeError('Runtime worker differs from controller snapshot; rebuild transport image')
        staging = ('import sys,hashlib; from pathlib import Path; data=sys.stdin.buffer.read(8000001); '
                   'a=Path("/input/model.xml"); a.write_bytes(data); a.chmod(0o444); '
                   'b=Path("/work/model.xml"); b.write_bytes(data); b.chmod(0o444); '
                   'print(hashlib.sha256(b.read_bytes()).hexdigest())')
        staged = phase('staging', ['python', '-I', '-B', '-c', staging], 30, data=xml)
        if staged['stdout'].decode().strip() != run.digest(xml):
            raise RuntimeError('XML staging identity mismatch')
        collect = True
        result['xml_load'] = 'started'
        phase('xml-load', ['python', '-I', '-B', '/opt/evaluator/transport_worker.py', 'load'], 30)
        result['xml_load'] = 'passed'
        result['transport'] = 'started'
        phase('openmc', ['/opt/openmc/bin/openmc', '-s', '1'], wall_seconds)
        result['transport'] = 'completed'
        result['statepoint_validation'] = 'started'
        phase('statepoint', ['python', '-I', '-B', '/opt/evaluator/transport_worker.py', 'extract'], 30)
        completed = True
    except PhaseFailure:
        for field in ('xml_load', 'transport', 'statepoint_validation'):
            if result[field] == 'started':
                result[field] = 'budget_exceeded' if result['status'] == 'budget_exceeded' else 'failed'
    except Exception as error:
        result.update(status='failed', error_type=type(error).__name__, error=str(error))
    finally:
        try:
            if name and collect:
                run.docker('pause', name)
                frozen = json.loads(run.docker('inspect', name))[0]
                run.write_json(output / 'frozen-container.json', frozen)
                if not frozen['State']['Running'] or not frozen['State']['Paused']:
                    raise RuntimeError('Transport runtime was not frozen')
                fetched = run.bounded(['docker', 'cp', name + ':/work', '-'], timeout=30, limit=MAX_ARCHIVE)
                if fetched['exit_code'] or fetched['stop_reason']:
                    raise RuntimeError('Transport artifact retrieval failed or exceeded budget')
                artifacts = run.artifact_bytes(fetched['stdout'], max_artifact=MAX_ARTIFACT, max_archive=MAX_ARCHIVE)
                (output / 'artifacts').mkdir()
                for filename, raw in artifacts.items():
                    (output / 'artifacts' / filename).write_bytes(raw)
                run.write_json(output / 'artifacts.json',
                               {key: {'bytes': len(raw), 'sha256': run.digest(raw)} for key, raw in artifacts.items()})
                if completed:
                    calculation = validate_calculation(artifacts, profile, xml)
                    result.update(status='calculated_unreviewed', statepoint_validation='passed',
                                  keff=calculation['keff'], sampling=calculation['sampling'],
                                  convergence_assessment='not_performed')
        except Exception as error:
            result.pop('keff', None)
            result.update(status='failed', error_type=type(error).__name__, error=str(error))
        finally:
            if name:
                try:
                    run.cleanup(name)
                    lifecycle['state'] = 'removed'
                except Exception as error:
                    lifecycle.update(state='cleanup_uncertain', error=str(error))
                    result.pop('keff', None)
                    result.update(status='cleanup_uncertain', cleanup_confirmed=False)
            # Remove the runtime before potentially lengthy host hashing, including
            # when killing the Docker client left a native process running inside.
            if identity is not None and result['cleanup_confirmed']:
                try:
                    run.data_directory(index)
                    after = data_identity(index, profile)
                    run.write_json(output / 'data-after.json', after)
                    if after != identity:
                        result.pop('keff', None)
                        result.update(status='failed', reason='nuclear_data_changed_during_run')
                except Exception as error:
                    result.pop('keff', None)
                    result.update(status='failed', error_type=type(error).__name__, error=str(error))
            result['elapsed_seconds'] = round(time.monotonic() - started, 3)
            run.write_json(output / 'lifecycle.json', lifecycle)
            run.write_json(output / 'result.json', result)
    return result
