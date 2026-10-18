"""Opt-in qualification of lost-particle termination; no historical rescoring."""
from pathlib import Path

from evaluation.candidates import receipts
from evaluation.candidates.phase_evidence import export_outcome, transport_failure
from evaluation.scientific.records import require
from evaluator import run as exporter
from evaluator.profiles import PROFILE
from evaluator.transport_input import accepted_export, read_regular, transport_profile

POLICY = 'native-lost-particle-attribution-v1'
FATAL = 'ERROR: Maximum number of lost particles has been reached.'


def diagnostic(value, folder):
    """Recognize only the qualified serial fatal, not exit 255 or a quoted phrase."""
    if not (value.get('status') == 'failed' and value.get('reason') == 'openmc_abnormal_exit'
            and value.get('xml_load') == 'passed' and value.get('transport') == 'failed'
            and value.get('statepoint_validation') == 'not_run'
            and value.get('cleanup_confirmed') is True):
        return False
    process = receipts.read(folder / 'openmc-process.json')
    if (not isinstance(process, dict) or set(process) != {'exit_code', 'stop_reason'}
            or type(process['exit_code']) is not int or process['exit_code'] != 255
            or process['stop_reason'] is not None):
        return False
    errors = [line.strip() for line in read_regular(folder / 'openmc-stderr.txt').decode().splitlines()
              if line.strip().startswith('ERROR:')]
    return errors == [FATAL]


def review(directory, goal, index):
    """Reconstruct an attributed native failure, without assigning a campaign score.

    goal must come from a verified reference/runtime binding. This is an explicit
    qualification entry point, not an automatic migration of assessment reports.
    """
    directory, index = Path(directory), Path(index)
    require(goal['protocol'] == {k: PROFILE[k] for k in ('export_image', 'transport_image')},
            'Lost-particle policy requires the qualified pinned runtime')
    source_hash = exporter.digest(read_regular(directory / 'candidate.py'))
    require(export_outcome(directory / 'export', goal['protocol']['export_image'], index, source_hash)
            == dict(cause=None, reason=None), 'Independent export was not verified')
    xml, identity = accepted_export(directory / 'export')
    require(identity['candidate_sha256'] == source_hash, 'Export uses another candidate')
    folder = directory / 'transport'
    value = receipts.container_phase(folder, goal['protocol']['transport_image'], index, source_hash, transport=True)
    require(diagnostic(value, folder), 'No qualified lost-particle diagnostic')
    # Existing checks bind contained execution, native identity, data, processes,
    # accepted export, frozen container and artifact bytes. Defaults stay legacy.
    transport_failure(directory, goal, index, source_hash, allow_lost_particles=True)
    for name in ('model.xml', 'artifacts/model.xml'):
        require(read_regular(folder / name) == xml, 'Transport XML bytes changed')
    artifacts = receipts.read(folder / 'artifacts.json')
    for name in ('model.xml', 'xml-load.json'):
        require(name in artifacts, 'Required native artifact is missing: ' + name)
    loaded = receipts.read(folder / 'artifacts/xml-load.json')
    profile = transport_profile(xml, index.name)
    require(loaded.get('status') == 'loaded' and loaded.get('openmc_version') == '0.15.3'
            and loaded.get('model_xml_sha256') == exporter.digest(xml)
            and loaded.get('sampling') == profile['sampling']
            and loaded.get('scientific_inputs_changed') is False
            and loaded.get('boundary_checks') and all(v is True for v in loaded['boundary_checks'].values()),
            'Native XML load evidence changed')
    require((folder / 'solver-version-stdout.txt').read_bytes().startswith(b'OpenMC version 0.15.3\n'),
            'Native version output changed')
    worker = read_regular(folder / 'controller-sources/runtime/transport_worker.py')
    require(exporter.digest(worker) == goal['runtime']['worker_sha256']
            and worker == Path('evaluator/runtime/transport_worker.py').read_bytes(),
            'Unqualified native worker')
    require(receipts.read(folder / 'runtime-identity-stdout.txt') == goal['runtime'],
            'Native runtime output changed')
    require(not any(name.startswith('statepoint.') for name in artifacts),
            'Fatal execution unexpectedly contains a statepoint')
    # Every required collection is read; the evidence is unchanged operator-owned
    # data, not a signed attestation against an operator rewriting all artifacts.
    return dict(format='native-failure-qualification-v1', policy=POLICY,
                evidence_status='coherent', attribution='model', reason='maximum_lost_particles',
                protocol_success=False, campaign_score_assigned=False,
                candidate_sha256=source_hash, model_xml_sha256=exporter.digest(xml),
                diagnostic_sha256=exporter.digest(read_regular(folder / 'openmc-stderr.txt')),
                process=receipts.read(folder / 'openmc-process.json'),
                limitation='Native failure attribution does not identify a Python root cause.')
