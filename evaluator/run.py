"""Execute an unchanged Python submission in Docker and inspect its XML envelope.

The host never imports the candidate. Docker freezes all candidate processes
before artifact retrieval; tar members are read as bytes, never extracted.
"""
import argparse
import ast
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tarfile
import threading
import time
import uuid
import xml.etree.ElementTree as ET

from evaluator.build import IMAGE, DEPENDENCY_ID
from evaluator.inspect import inspect_model, parse_xml

LABEL = 'neutronics-harness-v5.evaluator'
MAX_SOURCE = 1_000_000
MAX_ARCHIVE = 24_000_000
MAX_ARTIFACT = 8_000_000
MAX_LOG = 1_000_000
ROOT = Path(__file__).resolve().parent.parent


def digest(data):
    return hashlib.sha256(data).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def docker(*args):
    result = subprocess.run(['docker', *args], capture_output=True, timeout=30)
    if result.returncode:
        raise RuntimeError('Docker ' + args[0] + ' failed: ' + result.stderr.decode(errors='replace')[:500])
    return result.stdout.decode().strip()


def bounded(args, *, timeout, limit=MAX_LOG, data=None):
    """Drain both pipes while enforcing a shared output cap and wall deadline."""
    process = subprocess.Popen(args, stdin=subprocess.PIPE if data is not None else subprocess.DEVNULL,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    parts = [bytearray(), bytearray()]
    lock, overflow = threading.Lock(), threading.Event()
    def read(pipe, index):
        while chunk := pipe.read1(65536):
            with lock:
                space = max(0, limit - sum(map(len, parts)))
                parts[index].extend(chunk[:space])
                if len(chunk) > space:
                    overflow.set()
    def write():
        try:
            process.stdin.write(data)
            process.stdin.close()
        except (BrokenPipeError, OSError):
            pass
    readers = [threading.Thread(target=read, args=(pipe, i), daemon=True)
               for i, pipe in enumerate((process.stdout, process.stderr))]
    for reader in readers:
        reader.start()
    writer = threading.Thread(target=write, daemon=True) if data is not None else None
    if writer:
        writer.start()
    deadline, stopped = time.monotonic() + timeout, None
    try:
        while process.poll() is None:
            if overflow.is_set():
                stopped = 'output_limit'
                break
            if time.monotonic() >= deadline:
                stopped = 'timeout'
                break
            time.sleep(0.02)
        if stopped:
            process.kill()
        process.wait(timeout=5)
        for reader in readers:
            reader.join(timeout=5)
        if any(reader.is_alive() for reader in readers):
            raise RuntimeError('Docker output pipes did not close')
        if overflow.is_set():
            stopped = 'output_limit'
        return {'exit_code': process.returncode, 'stop_reason': stopped,
                'stdout': bytes(parts[0]), 'stderr': bytes(parts[1])}
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)
        for pipe in (process.stdout, process.stderr):
            pipe.close()
        if writer:
            writer.join(timeout=5)


def source_bytes(path):
    if path.is_symlink() or not path.is_file():
        raise ValueError('Candidate must be a regular file, not a symlink')
    with path.open('rb') as stream:
        data = stream.read(MAX_SOURCE + 1)
    if not data or len(data) > MAX_SOURCE:
        raise ValueError('Candidate source is empty or oversized')
    return data


def data_directory(index):
    """Admit a flat data-only collection, never a repository/home directory."""
    if index.is_symlink():
        raise ValueError('Data index must not be a symlink')
    index = index.resolve(strict=True)
    directory = index.parent
    if directory == Path.home() or directory == Path('/') or directory == ROOT or ROOT in directory.parents:
        raise ValueError('Data collection must be outside the operator repository and home root')
    with index.open('rb') as stream:
        raw = stream.read(MAX_ARTIFACT + 1)
    root = parse_xml(raw)
    if root.tag != 'cross_sections' or not len(root):
        raise ValueError('Invalid data index')
    names = set()
    for library in root:
        name = library.get('path', '')
        if (library.tag != 'library' or library.get('type') not in {'neutron', 'thermal', 'photon'}
                or not re.fullmatch(r'[A-Za-z0-9_.-]+\.h5', name)):
            raise ValueError('Only flat relative HDF5 library entries are supported')
        names.add(name)
    if {p.name for p in directory.iterdir()} != names | {index.name}:
        raise ValueError('Data directory contains unlisted files or directories')
    inventory = []
    for name in sorted(names | {index.name}):
        path = directory / name
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ValueError('Data collection contains links or nonregular files')
        inventory.append({'name': name, 'size': info.st_size, 'mtime_ns': info.st_mtime_ns})
    return index, {'index_sha256': digest(raw), 'files': inventory,
                   'hdf5_content_hashes': 'not_computed', 'transport_data_qualification': 'not_run'}


def create_args(name, image, index):
    return ['create', '--name', name, '--label', LABEL + '=' + name, '--network', 'none',
            '--read-only', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges=true',
            '--user', '1000:1000', '--pids-limit', '128', '--memory', '2g', '--cpus', '2',
            '--init', '--log-driver', 'none',
            '--tmpfs', '/input:rw,nosuid,nodev,size=2097152,uid=1000,gid=1000,mode=700',
            '--tmpfs', '/tmp:rw,nosuid,nodev,size=134217728,uid=1000,gid=1000,mode=700',
            '--mount', f'type=volume,src={name}-work,dst=/work,volume-nocopy',
            '--mount', f'type=bind,src={index.parent},dst=/data,readonly',
            '--env', 'OPENMC_CROSS_SECTIONS=/data/' + index.name, image]


def verify_container(info, image, index, name, *, memory_bytes=2 * 1024**3):
    host, config = info['HostConfig'], info['Config']
    mounts = info['Mounts']
    data_sources = {str(index.parent)}
    if sys.platform == 'darwin':
        # Docker Desktop translates the exact macOS bind path into its VM path.
        data_sources.add('/host_mnt' + str(index.parent))
    checks = {
        'image_matches': info['Image'] == image,
        'network_none': host['NetworkMode'] == 'none',
        'readonly_root': host['ReadonlyRootfs'] is True,
        'unprivileged': not host['Privileged'] and not host.get('CapAdd') and not host.get('Devices'),
        'capabilities_dropped': host['CapDrop'] == ['ALL'],
        'no_new_privileges': 'no-new-privileges=true' in host['SecurityOpt'],
        'nonroot': config['User'] == '1000:1000',
        'no_host_namespaces': host.get('PidMode', '') == '' and host.get('IpcMode') == 'private',
        'bounded_resources': host['Memory'] == memory_bytes and host['NanoCpus'] == 2_000_000_000
                             and host['PidsLimit'] == 128,
        'bounded_tmpfs': set(host['Tmpfs']) == {'/input', '/tmp'},
        'only_data_and_workspace_mounts': len(mounts) == 2 and not host.get('Binds')
            and any(m['Type'] == 'bind' and m['Source'] in data_sources
                    and m['Destination'] == '/data' and m['RW'] is False for m in mounts)
            and any(m['Type'] == 'volume' and m['Name'] == name + '-work'
                    and m['Destination'] == '/work' and m['RW'] is True for m in mounts),
        'trusted_entrypoint': config['Entrypoint'] == ['python', '-I', '-B', '/opt/evaluator/idle.py'],
    }
    if not all(checks.values()):
        raise RuntimeError('Evaluator container boundary mismatch: ' + ', '.join(k for k, v in checks.items() if not v))
    return checks


def artifact_bytes(data, *, max_artifact=None, max_archive=None):
    """Read only bounded, flat regular files. Never extract paths from tar."""
    max_artifact = MAX_ARTIFACT if max_artifact is None else max_artifact
    max_archive = MAX_ARCHIVE if max_archive is None else max_archive
    artifacts, total = {}, 0
    with tarfile.open(fileobj=io.BytesIO(data), mode='r:') as archive:
        for i, member in enumerate(archive):
            if i >= 64:
                raise ValueError('Too many artifact entries')
            if member.isdir() and member.name in {'work', 'work/'}:
                continue
            name = member.name.removeprefix('work/')
            if (not member.name.startswith('work/') or not member.isfile()
                    or not re.fullmatch(r'[A-Za-z0-9_.-]{1,128}', name) or name in {'.', '..'}
                    or name in artifacts or member.size > max_artifact or member.size < 0):
                raise ValueError('Unsafe, duplicate, unsupported or oversized artifact')
            total += member.size
            if total > max_archive:
                raise ValueError('Artifacts exceed total byte budget')
            content = archive.extractfile(member).read(max_artifact + 1)
            if len(content) != member.size:
                raise ValueError('Truncated artifact')
            artifacts[name] = content
    return artifacts


def cleanup(name):
    found = docker('ps', '-a', '--filter', 'label=' + LABEL + '=' + name, '--format', '{{.Names}}')
    if found and found != name:
        raise RuntimeError('Unexpected container cleanup identity')
    if found:
        docker('rm', '--force', name)
    if docker('ps', '-a', '--filter', 'label=' + LABEL + '=' + name, '--format', '{{.Names}}'):
        raise RuntimeError('Evaluator container remains')
    volume = name + '-work'
    found = docker('volume', 'ls', '--filter', 'label=' + LABEL + '=' + name, '--format', '{{.Name}}')
    if found and found != volume:
        raise RuntimeError('Unexpected volume cleanup identity')
    if found:
        docker('volume', 'rm', volume)
    if docker('volume', 'ls', '--filter', 'label=' + LABEL + '=' + name, '--format', '{{.Name}}'):
        raise RuntimeError('Evaluator workspace volume remains')


def evaluate(candidate, output, *, index, contract='openmc-model-factory-v1', image=IMAGE, wall_seconds=None, execution_profile='factory-serial-v1'):
    from evaluator.contracts import CONTRACTS, FACTORY
    if contract not in CONTRACTS:
        raise ValueError('Explicit supported delivery contract is required')
    from evaluator.profiles import execution_profile as resolve_profile
    profile = resolve_profile(execution_profile, contract)
    if wall_seconds not in (None, profile['budgets']['export']):
        raise ValueError('Export budget differs from selected execution profile')
    wall_seconds = profile['budgets']['export']
    if output.exists():
        raise FileExistsError('Refusing to overwrite evaluation evidence')
    if not 5 <= wall_seconds <= 300:
        raise ValueError('Candidate wall budget must be 5-300 seconds')
    source = source_bytes(candidate)
    index, data_info = data_directory(index)
    if docker('ps', '-a', '--filter', 'label=' + LABEL, '--format', '{{.Names}}'):
        raise RuntimeError('A prior evaluator container remains; reconcile its lifecycle first')
    if docker('volume', 'ls', '--filter', 'label=' + LABEL, '--format', '{{.Name}}'):
        raise RuntimeError('A prior evaluator volume remains; reconcile its lifecycle first')
    image_info = json.loads(docker('image', 'inspect', image))[0]
    image_id = image_info['Id']
    if image_id != profile['export_image']:
        raise ValueError('Export image differs from execution profile')
    name = 'neutronics-v5-evaluator-' + uuid.uuid4().hex[:16]
    output.mkdir(parents=True)
    (output / 'candidate.py').write_bytes(source)
    for file in ('run.py', 'inspect.py', 'build.py', 'process.py', 'contracts.py', 'factory.py'):
        (output / ('evaluator-' + file)).write_bytes((Path(__file__).parent / file).read_bytes())
    manifest = {'format': 'isolated-export-evaluation-v2', 'candidate_sha256': digest(source),
        'image_id': image_id, 'dependency_image_id': DEPENDENCY_ID, 'container_name': name,
        'wall_seconds': wall_seconds, 'data_directory': str(index.parent),
        'host_candidate_execution': 'not_run', 'scope': 'model_factory_and_xml_envelope',
        'reference_access': False, 'automatic_repair': False, 'transport': 'not_run',
        'execution_evidence_version': 2, 'limits': dict(log=MAX_LOG, archive=MAX_ARCHIVE, artifact=MAX_ARTIFACT),
        'process_observer_sha256': digest(Path(__file__).with_name('process.py').read_bytes())}
    manifest['delivery_contract'] = contract
    manifest['execution_profile'] = profile
    manifest.update(format='isolated-export-evaluation-v2', scope='model_factory_and_xml_envelope',
                    driver_sha256=digest(Path(__file__).with_name('factory.py').read_bytes()),
                    internal_diagnostic_authority='candidate_interpreter_not_independent')
    write_json(output / 'manifest.json', manifest)
    write_json(output / 'data-inventory.json', data_info)
    lifecycle = {'container_name': name, 'volume_name': name + '-work', 'state': 'creating'}
    write_json(output / 'lifecycle.json', lifecycle)
    result = {'status': 'failed', 'candidate_execution': 'not_run', 'xml_validation': 'not_run',
              'transport': 'not_run', 'scientific_fidelity': 'not_checked'}
    started = time.monotonic()
    timings = {}
    def timed(label, args, **kwargs):
        begin = time.monotonic()
        try:
            return bounded(args, **kwargs)
        finally:
            timings[label] = round(time.monotonic() - begin, 6)
    try:
        try:
            tree = ast.parse(source)
        except (SyntaxError, ValueError):
            result.update(status='rejected', reason='invalid_python_syntax')
            return result
        volume_options = {'type': 'tmpfs', 'device': 'tmpfs',
                          'o': 'size=134217728,uid=1000,gid=1000,mode=700,nosuid,nodev'}
        docker('volume', 'create', '--label', LABEL + '=' + name, '--driver', 'local',
               '--opt', 'type=tmpfs', '--opt', 'device=tmpfs', '--opt', 'o=' + volume_options['o'], name + '-work')
        volume_info = json.loads(docker('volume', 'inspect', name + '-work'))[0]
        write_json(output / 'volume.json', volume_info)
        if volume_info['Driver'] != 'local' or volume_info['Options'] != volume_options:
            raise RuntimeError('Workspace is not the bounded tmpfs volume')
        lifecycle['state'] = 'volume_created'
        write_json(output / 'lifecycle.json', lifecycle)
        lifecycle['container_id'] = docker(*create_args(name, image_id, index))
        lifecycle['state'] = 'created'
        write_json(output / 'lifecycle.json', lifecycle)
        info = json.loads(docker('inspect', name))[0]
        write_json(output / 'container.json', info)
        checks = verify_container(info, image_id, index, name)
        write_json(output / 'container-checks.json', checks)
        docker('start', name)
        probe = timed('preflight', ['docker', 'exec', name, 'python', '-I', '-B', '/opt/evaluator/probe.py'], timeout=30)
        if probe['exit_code'] or probe['stop_reason']:
            raise RuntimeError('Evaluator preflight failed: ' + probe['stderr'].decode(errors='replace')[:500])
        probe_info = json.loads(probe['stdout'])
        write_json(output / 'preflight.json', probe_info)
        if not probe_info.get('checks') or not all(probe_info['checks'].values()):
            raise RuntimeError('Evaluator preflight boundary checks failed')
        staging_code = ('import sys,hashlib; from pathlib import Path; '
                        'data=sys.stdin.buffer.read(1000001); '
                        'p=Path("/input/candidate.py"); p.write_bytes(data); p.chmod(0o444); '
                        'print(hashlib.sha256(p.read_bytes()).hexdigest())')
        copied = timed('candidate_staging', ['docker', 'exec', '-i', name, 'python', '-I', '-B', '-c', staging_code],
                         timeout=30, data=source)
        write_json(output / 'staging.json', {'exit_code': copied['exit_code'],
                   'stop_reason': copied['stop_reason'], 'stdout': copied['stdout'].decode(errors='replace'),
                   'stderr': copied['stderr'].decode(errors='replace')})
        if (copied['exit_code'] or copied['stop_reason']
                or copied['stdout'].decode().strip() != digest(source)):
            raise RuntimeError('Candidate staging failed')
        driver = Path(__file__).with_name('factory.py').read_bytes()
        entrypoint = '/input/factory.py'
        staged = timed('driver_staging', ['docker', 'exec', '-i', name, 'python', '-I', '-B', '-c',
                          staging_code.replace('/input/candidate.py', entrypoint)], timeout=30, data=driver)
        write_json(output / 'driver-staging.json', {k: v.decode(errors='replace') if isinstance(v, bytes) else v
                   for k, v in staged.items()})
        if staged['exit_code'] or staged['stop_reason'] or staged['stdout'].decode().strip() != digest(driver):
            raise RuntimeError('Factory driver staging failed')
        write_json(output / 'execution-launch.json', dict(delivery_contract=contract, entrypoint=entrypoint,
                   candidate_sha256=digest(source), driver_sha256=digest(driver), observer_sha256=manifest['process_observer_sha256']))
        result['candidate_execution'] = 'started'
        observer = Path(__file__).with_name('process.py').read_text()
        observed = timed('factory_child_and_observer', ['docker', 'exec', '--workdir', '/work', name, 'python', '-I', '-B', '-c',
                            observer, entrypoint, str(wall_seconds), str(MAX_LOG)],
                           timeout=wall_seconds + 10, limit=2 * MAX_LOG + 10000)
        write_json(output / 'observer-process.json', {k: v for k, v in observed.items() if k not in ('stdout', 'stderr')})
        (output / 'observer-stdout.json').write_bytes(observed['stdout'])
        (output / 'observer-stderr.txt').write_bytes(observed['stderr'])
        state = json.loads(docker('inspect', name))[0]
        write_json(output / 'post-execution-container.json', state)
        if observed['exit_code'] or observed['stop_reason']:
            result.update(status='failed', reason='process_observer_incomplete', failure_cause='indeterminate')
            return result
        proof = json.loads(observed['stdout'])
        if (proof.get('format') != 'candidate-process-v2' or proof.get('observer_protected') is not True
                or type(proof.get('returncode')) is not int or proof.get('stop_reason') not in (None, 'timeout', 'output_limit')
                or proof.get('termination') != ('signal' if proof['returncode'] < 0 else 'exit')):
            raise ValueError('Invalid process observer receipt')
        execution = dict(exit_code=proof['returncode'], stop_reason=proof['stop_reason'],
                         **{c: base64.b64decode(proof[c + '_b64'], validate=True) for c in ('stdout', 'stderr')})
        if sum(len(execution[c]) for c in ('stdout', 'stderr')) > MAX_LOG:
            raise ValueError('Process observer logs exceed budget')
        write_json(output / 'candidate-process.json', {k: v for k, v in proof.items() if not k.endswith('_b64')})
        for channel in ('stdout', 'stderr'):
            (output / ('candidate-' + channel + '.txt')).write_bytes(execution[channel])
        result.update(candidate_exit_code=execution['exit_code'], candidate_execution='finished')
        if state.get('State', {}).get('OOMKilled') is True or execution['exit_code'] < 0 and not execution['stop_reason']:
            result.update(status='failed', reason='candidate_signal_or_oom', failure_cause='indeterminate')
            return result
        if execution['stop_reason']:
            result.update(status='rejected', candidate_execution=execution['stop_reason'],
                          reason='candidate_' + execution['stop_reason'])
            return result
        # Freezing also stops any descendants left behind by the submitted script.
        docker('pause', name)
        frozen = json.loads(docker('inspect', name))[0]
        write_json(output / 'frozen-container.json', frozen)
        if not frozen['State']['Running'] or not frozen['State']['Paused']:
            raise RuntimeError('Candidate processes were not frozen')
        lifecycle['state'] = 'frozen'
        write_json(output / 'lifecycle.json', lifecycle)
        fetched = timed('artifact_retrieval', ['docker', 'cp', name + ':/work', '-'], timeout=30, limit=MAX_ARCHIVE)
        (output / 'artifact-archive.tar').write_bytes(fetched['stdout'])
        (output / 'retrieval-stderr.txt').write_bytes(fetched['stderr'])
        write_json(output / 'artifact-retrieval.json', dict(exit_code=fetched['exit_code'], stop_reason=fetched['stop_reason'],
                   stdout_bytes=len(fetched['stdout']), stderr_bytes=len(fetched['stderr']), archive_sha256=digest(fetched['stdout'])))
        if fetched['exit_code'] or fetched['stop_reason']:
            if fetched['stop_reason'] == 'output_limit' and len(fetched['stdout']) == MAX_ARCHIVE and not fetched['stderr']:
                result.update(status='rejected', reason='candidate_artifact_limit')
            else:
                result.update(status='failed', reason='artifact_retrieval_incomplete', failure_cause='indeterminate')
            return result
        try:
            artifacts = artifact_bytes(fetched['stdout'])
        except (ValueError, tarfile.TarError):
            result.update(status='rejected', reason='invalid_artifact_archive')
            return result
        (output / 'artifacts').mkdir()
        for filename, data in artifacts.items():
            (output / 'artifacts' / filename).write_bytes(data)
        write_json(output / 'artifacts.json', {key: {'bytes': len(data), 'sha256': digest(data)}
                                             for key, data in artifacts.items()})
        result['artifacts'] = sorted(artifacts)
        if execution['exit_code']:
            result.update(status='rejected', reason='candidate_exit_nonzero')
        elif set(artifacts) - {'model.xml'}:
            result.update(status='rejected', reason='unexpected_factory_artifacts')
        elif 'model.xml' not in artifacts:
            result.update(status='rejected', reason='missing_model_xml')
        else:
            try:
                inspection = inspect_model(artifacts['model.xml'])
            except (ValueError, UnicodeError, ET.ParseError) as error:
                # This parser handles data only; never import or repair the candidate.
                result.update(status='rejected', reason='invalid_model_xml', xml_validation='failed',
                              xml_error_type=type(error).__name__)
            else:
                write_json(output / 'xml-inspection.json', inspection)
                result.update(status='exported', xml_validation='passed')
    except Exception as error:
        result.update(status='failed', error_type=type(error).__name__, error=str(error))
    finally:
        try:
            cleanup(name)
            lifecycle['state'] = 'removed'
        except Exception as error:
            lifecycle.update(state='cleanup_uncertain', error=str(error))
            result['status'] = 'cleanup_uncertain'
        result.update(cleanup_confirmed=lifecycle['state'] == 'removed',
                      elapsed_seconds=round(time.monotonic() - started, 3))
        write_json(output / 'lifecycle.json', lifecycle)
        write_json(output / 'result.json', result)
        write_json(output / 'host-timings.json', dict(authority='host_monotonic', stages_seconds=timings))
    return result


def main():
    from evaluator.contracts import CONTRACTS
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--data-index', type=Path, default=os.environ.get('OPENMC_CROSS_SECTIONS'))
    parser.add_argument('--image', default=IMAGE)
    parser.add_argument('--wall-seconds', type=int)
    parser.add_argument('--execution-profile', default='factory-serial-v1')
    parser.add_argument('--contract', choices=CONTRACTS, default='openmc-model-factory-v1')
    args = parser.parse_args()
    if args.data_index is None:
        parser.error('--data-index or OPENMC_CROSS_SECTIONS is required')
    result = evaluate(args.candidate.absolute(), args.output.absolute(), index=args.data_index,
                      image=args.image, wall_seconds=args.wall_seconds, contract=args.contract, execution_profile=args.execution_profile)
    print(json.dumps(result, indent=2))
    return 0 if result['status'] == 'exported' else 1


if __name__ == '__main__':
    raise SystemExit(main())
