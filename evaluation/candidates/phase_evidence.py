"""Reconstruct export outcomes from contained execution receipts, never verdicts alone."""
import ast
import base64
import json
from pathlib import Path
import tarfile
import xml.etree.ElementTree as ET

from evaluator import run as exporter
from evaluator.evidence import InsufficientEvidence
from evaluator.contracts import FACTORY, export_contract
from evaluator.transport_input import read_regular, transport_profile
from evaluation.candidates import receipts
from evaluation.scientific.records import require


def artifact_inventory(folder):
    """An absent directory represents emptiness only with an explicit empty inventory."""
    inventory = receipts.read(folder / 'artifacts.json')
    require(isinstance(inventory, dict), 'Malformed artifact inventory')
    path = folder / 'artifacts'
    require(not path.is_symlink(), 'Artifact directory is a symlink')
    if not path.exists():
        if inventory:
            raise InsufficientEvidence('Missing nonempty artifact directory: ' + str(path))
        return {}
    require(path.is_dir(), 'Artifact directory is not a directory')
    names = {p.name for p in path.iterdir()}
    require(not names - set(inventory), 'Unrecorded artifacts')
    if set(inventory) - names:
        raise InsufficientEvidence('Missing inventoried artifacts: ' + str(sorted(set(inventory) - names)))
    result = {}
    for name, identity in inventory.items():
        require(Path(name).name == name and name not in ('.', '..'), 'Unsafe artifact name')
        raw = read_regular(path / name, limit=exporter.MAX_ARCHIVE)
        require(identity == dict(bytes=len(raw), sha256=exporter.digest(raw)), 'Artifact content contradicts inventory')
        result[name] = raw
    return result


def export_outcome(folder, image, index, source_hash, *, runtime=None):
    folder = Path(folder)
    value = receipts.container_phase(folder, image, index, source_hash)
    manifest = receipts.read(folder / 'manifest.json')
    contract = export_contract(manifest)
    if 'execution_profile' in manifest:
        from evaluator.profiles import execution_profile
        profile = execution_profile(manifest['execution_profile']['id'], contract, runtime=runtime)
        require(manifest['execution_profile'] == profile and manifest['wall_seconds'] == profile['budgets']['export']
                and image == profile['export_image'], 'Export execution profile changed')
        timing = receipts.read(folder / 'host-timings.json')
        require(timing['authority'] == 'host_monotonic', 'Unexpected timing authority')
    source = read_regular(folder / 'candidate.py')
    reason = None
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        reason = 'invalid_python_syntax'
    if reason:
        require(value['status'] == 'rejected' and value.get('reason') == reason and
                value.get('candidate_execution') == 'not_run', 'Syntax/admission outcome contradicts source')
        return dict(cause='model', reason=reason)

    # Missing child receipts cannot be reconstructed from a reported verdict.
    if manifest.get('execution_evidence_version') != 2:
        raise InsufficientEvidence('Export lacks independent child-process and retrieval receipts')
    observer = read_regular(folder / 'evaluator-process.py')
    require(exporter.digest(observer) == manifest['process_observer_sha256'], 'Changed process observer')
    if observer != Path(exporter.__file__).with_name('process.py').read_bytes():
        raise InsufficientEvidence('Unqualified process observer version')
    driver = read_regular(folder / 'evaluator-factory.py')
    require(exporter.digest(driver) == manifest['driver_sha256'], 'Changed factory driver')
    if driver != Path(exporter.__file__).with_name('factory.py').read_bytes():
        raise InsufficientEvidence('Unqualified factory driver version')
    staged = receipts.read(folder / 'driver-staging.json')
    require(staged['exit_code'] == 0 and staged['stop_reason'] is None and
            staged['stdout'].strip() == exporter.digest(driver), 'Factory driver staging failed')
    require(receipts.read(folder / 'execution-launch.json') == dict(delivery_contract=contract,
            entrypoint='/input/factory.py', candidate_sha256=source_hash, driver_sha256=exporter.digest(driver),
            observer_sha256=manifest['process_observer_sha256']), 'Factory execution path changed')
    limits = manifest['limits']
    require(set(limits) == {'log', 'archive', 'artifact'} and all(type(v) is int and v > 0 for v in limits.values()),
            'Invalid execution limits')
    require(limits['log'] <= exporter.MAX_LOG and limits['archive'] <= exporter.MAX_ARCHIVE and
            limits['artifact'] <= exporter.MAX_ARTIFACT, 'Unsupported execution limits')
    outer = receipts.read(folder / 'observer-process.json')
    raw = read_regular(folder / 'observer-stdout.json', limit=2 * limits['log'] + 10000)
    read_regular(folder / 'observer-stderr.txt', limit=2 * limits['log'] + 10000)
    state = receipts.read(folder / 'post-execution-container.json')
    exporter.verify_container(state, image, index, manifest['container_name'])
    if outer['exit_code'] != 0 or outer['stop_reason'] is not None:
        require(value['status'] == 'failed' and value.get('reason') == 'process_observer_incomplete',
                'Interrupted observer promoted to candidate verdict')
        return dict(cause='indeterminate', reason='process_observer_incomplete')
    proof = json.loads(raw)
    child = receipts.read(folder / 'candidate-process.json')
    require(child == {k: v for k, v in proof.items() if not k.endswith('_b64')}, 'Child receipt contradicts observer output')
    code, stopped = child['returncode'], child['stop_reason']
    require(child['format'] == 'candidate-process-v2' and child['observer_protected'] is True and type(code) is int and
            child['termination'] == ('signal' if code < 0 else 'exit') and
            stopped in (None, 'timeout', 'output_limit'), 'Invalid child completion evidence')
    for stream in ('stdout', 'stderr'):
        require(base64.b64decode(proof[stream + '_b64'], validate=True) == read_regular(folder / ('candidate-' + stream + '.txt')),
                'Candidate log contradicts process evidence')
    require(value.get('candidate_exit_code') == code, 'Candidate return code changed')
    if 'OOMKilled' not in state['State']:
        raise InsufficientEvidence('Missing post-execution OOM state')
    if state['State']['OOMKilled'] or code < 0 and stopped is None:
        require(value['status'] == 'failed' and value.get('reason') == 'candidate_signal_or_oom',
                'Signal/OOM promoted to an attributed failure')
        return dict(cause='indeterminate', reason='candidate_signal_or_oom')
    if stopped:
        reason = 'candidate_' + stopped
        require(value.get('candidate_execution') == stopped, 'Budget stop contradicts execution state')
    else:
        require(value.get('candidate_execution') == 'finished', 'Completed process contradicts execution state')
        frozen = receipts.read(folder / 'frozen-container.json')
        exporter.verify_container(frozen, image, index, manifest['container_name'])
        require(frozen['State']['Running'] is True and frozen['State']['Paused'] is True, 'Artifacts retrieved without freezing')
        retrieval = receipts.read(folder / 'artifact-retrieval.json')
        archive = read_regular(folder / 'artifact-archive.tar', limit=limits['archive'])
        stderr = read_regular(folder / 'retrieval-stderr.txt', limit=limits['archive'])
        require(retrieval['archive_sha256'] == exporter.digest(archive) and retrieval['stdout_bytes'] == len(archive) and
                retrieval['stderr_bytes'] == len(stderr), 'Retrieval bytes contradict receipt')
        if retrieval['stop_reason'] == 'output_limit' and len(archive) == limits['archive'] and not stderr:
            reason = 'candidate_artifact_limit'
        elif retrieval['exit_code'] != 0 or retrieval['stop_reason'] is not None:
            require(value['status'] == 'failed' and value.get('reason') == 'artifact_retrieval_incomplete',
                    'Incomplete retrieval promoted to candidate failure')
            return dict(cause='indeterminate', reason='artifact_retrieval_incomplete')
        else:
            try:
                artifacts = exporter.artifact_bytes(archive, max_artifact=limits['artifact'], max_archive=limits['archive'])
            except (ValueError, tarfile.TarError):
                reason = 'invalid_artifact_archive'
            else:
                require(artifacts == artifact_inventory(folder) and sorted(artifacts) == value['artifacts'],
                        'Retrieved archive differs from retained artifacts')
                if code:
                    reason = 'candidate_exit_nonzero'
                elif set(artifacts) - {'model.xml'}:
                    reason = 'unexpected_factory_artifacts'
                elif 'model.xml' not in artifacts:
                    reason = 'missing_model_xml'
                else:
                    try:
                        inspection = exporter.inspect_model(artifacts['model.xml'])
                    except (ValueError, UnicodeError, ET.ParseError):
                        reason = 'invalid_model_xml'
                    else:
                        require(inspection == receipts.read(folder / 'xml-inspection.json'), 'XML admission changed')
    require(value['status'] == ('rejected' if reason else 'exported') and value.get('reason') == reason,
            'Export verdict contradicts reconstructed execution')
    require(value['xml_validation'] == ('failed' if reason == 'invalid_model_xml' else 'not_run' if reason else 'passed'),
            'XML validation state contradicts execution')
    return dict(cause='model' if reason else None, reason=reason)


def transport_failure(directory, goal, index, source_hash):
    """Verify existing native model-rejection receipts; no candidate Python here.

    Other terminations remain insufficient for an attributed model failure. This
    preserves the existing native classification policy, without adding physics.
    """
    from evaluation.candidates.run import native_model_failure
    folder = directory / 'transport'
    value = receipts.container_phase(folder, goal['protocol']['transport_image'], index, source_hash, transport=True)
    if not native_model_failure(value, folder):
        raise InsufficientEvidence('Native termination has no established model-failure attribution')
    xml, identity = receipts.accepted_export(directory / 'export')
    provenance = receipts.read(folder / 'export-provenance.json')
    require(all(identity[k] == provenance[k] for k in ('candidate_sha256', 'model_xml_sha256', 'receipt_sha256')),
            'Stopped transport provenance changed')
    require(receipts.read(folder / 'manifest.json')['model_xml_sha256'] == exporter.digest(xml), 'Stopped transport XML changed')
    require(receipts.read(folder / 'runtime-identity.json') == goal['runtime'], 'Stopped native runtime changed')
    before, after = [receipts.read(folder / name) for name in ('data-before.json', 'data-after.json')]
    require(before == after and before['index_sha256'] == goal['data']['index_sha256'] and
            all(goal['data']['files'].get(n) == v for n, v in before['files'].items()), 'Stopped native data changed')
    profile = transport_profile(xml, index.name)
    require({tuple(t) for v in before['files'].values() for t in v['tables']} == set(map(tuple, profile['required_tables'])),
            'Stopped data identity omits requested tables')
    for name in ('preflight', 'solver-version', 'runtime-identity', 'staging'):
        require(receipts.read(folder / (name + '-process.json')) == dict(exit_code=0, stop_reason=None),
                'Failed transport prerequisite: ' + name)
    require(read_regular(folder / 'staging-stdout.txt').decode().strip() == exporter.digest(xml), 'Stopped XML staging changed')
    label = 'xml-load' if value['reason'].startswith('xml-load') else 'openmc'
    if label == 'openmc':
        require(receipts.read(folder / 'xml-load-process.json') == dict(exit_code=0, stop_reason=None), 'OpenMC stop without successful XML load')
    process = receipts.read(folder / (label + '-process.json'))
    code = process['exit_code']
    require(process['stop_reason'] is None and type(code) is int and code > 0 and
            (code < 128 or code == 255 and label == 'openmc' and value['reason'] == 'openmc_abnormal_exit'),
            'Native model-rejection reason contradicts process receipt')
    frozen = receipts.read(folder / 'frozen-container.json')
    exporter.verify_container(frozen, goal['protocol']['transport_image'], index,
                              receipts.read(folder / 'manifest.json')['container_name'], memory_bytes=receipts.solver.MEMORY)
    require(frozen['State']['Running'] is True and frozen['State']['Paused'] is True, 'Stopped native artifacts were not frozen')
    # The XML-only worker is trusted; retain its output bytes and inventory too.
    inventory = receipts.read(folder / 'artifacts.json')
    for name, record in inventory.items():
        require(Path(name).name == name, 'Invalid stopped native artifact name')
        raw = read_regular(folder / 'artifacts' / name, limit=32_000_000)
        require(record == dict(bytes=len(raw), sha256=exporter.digest(raw)), 'Stopped native artifact changed')
