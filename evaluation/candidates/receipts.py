"""Read retained execution evidence; never import candidate code or read credentials."""
import csv
import io
import json
import math
from pathlib import Path
import statistics

from evaluator import run as exporter, transport as solver
from evaluator.transport_input import accepted_export, read_regular, transport_profile
from evaluation.scientific.records import require, reader, validate_keff
from evaluator.contracts import export_contract


def read(path):
    return json.loads(read_regular(Path(path), limit=32_000_000))


def container_phase(folder, image, index, source_hash, *, transport=False):
    """Validate actual recorded containment/staging, not just success booleans."""
    m, r, life = [read(folder / name) for name in ('manifest.json', 'result.json', 'lifecycle.json')]
    require(m['image_id'] == image and m['candidate_sha256'] == source_hash, 'Execution image/source mismatch')
    require(r['cleanup_confirmed'] is True and life['state'] == 'removed', 'Execution cleanup uncertain')
    if not transport:
        export_contract(m)
        require(exporter.digest(read_regular(folder / 'candidate.py')) == source_hash, 'Export source changed')
        require(m['host_candidate_execution'] == 'not_run' and m['reference_access'] is False and
                m['automatic_repair'] is False, 'Unexpected export boundary')
    else:
        require(m['candidate_python_access'] is False and m['reference_access'] is False and
                m['scientific_inputs_changed'] is False, 'Unexpected transport boundary')
    if (folder / 'container.json').exists():
        exporter.verify_container(read(folder / 'container.json'), image, index, m['container_name'],
                                  memory_bytes=solver.MEMORY if transport else 2 * 1024**3)
        require(all(read(folder / 'container-checks.json').values()), 'Recorded container checks failed')
        require(all(read(folder / 'preflight.json')['checks'].values()), 'Execution preflight failed')
        if not transport:
            staging = read(folder / 'staging.json')
            require(staging['exit_code'] == 0 and staging['stop_reason'] is None and
                    staging['stdout'].strip() == source_hash, 'Export staging failed')
    else:
        require(not transport and r.get('reason') in {'invalid_python_syntax'},
                'Missing contained execution evidence')
    return r


def histories(raw, sampling):
    table = csv.DictReader(io.StringIO(raw.decode()))
    require(table.fieldnames == ['generation', 'active', 'k_generation', 'entropy_bits'], 'Invalid history columns')
    rows = list(table)
    n = sampling['batches'] * sampling['generations_per_batch']
    inactive = sampling['inactive'] * sampling['generations_per_batch']
    require(len(rows) == n, 'History length mismatch')
    for i, row in enumerate(rows, 1):
        require(int(row['generation']) == i and row['active'] == str(i > inactive) and
                math.isfinite(float(row['k_generation'])), 'Invalid generation history')
    entropy = [row['entropy_bits'] for row in rows]
    if all(v == '' for v in entropy):
        return dict(statistics={}, entropy_status='not_produced')
    values = [float(v) for v in entropy]
    require(all(math.isfinite(v) for v in values), 'Invalid entropy history')
    active = values[inactive:]
    require(len(active) >= 4, 'Insufficient active histories')
    drift = statistics.mean(active[len(active)//2:]) - statistics.mean(active[:len(active)//2])
    return dict(statistics=dict(entropy_bits=dict(second_minus_first=drift)), entropy_status='produced')


def transport_record(directory, source_hash, image, index):
    folder = directory / 'transport'
    result = container_phase(folder, image, index, source_hash, transport=True)
    require(result['status'] == 'calculated_unreviewed' and result['statepoint_validation'] == 'passed'
            and result['xml_load'] == 'passed' and result['transport'] == 'completed', 'Incomplete transport')
    get, receipts = reader(folder)
    for name in ('result.json', 'manifest.json', 'lifecycle.json', 'container.json', 'container-checks.json',
                 'preflight.json', 'export-provenance.json'):
        get(name)
    # Reconstruct completion from phase receipts, not only result.json flags.
    for phase in ('preflight', 'solver-version', 'runtime-identity', 'staging',
                  'xml-load', 'openmc', 'statepoint'):
        name = phase + '-process.json'
        process = json.loads(get(name))
        require(isinstance(process, dict) and set(process) == {'exit_code', 'stop_reason'} and
                type(process['exit_code']) is int and process['exit_code'] == 0 and
                process['stop_reason'] is None,
                'Successful transport contradicts process receipt: ' + name)
    xml, identity = accepted_export(directory / 'export')
    provenance = read(folder / 'export-provenance.json')
    require(all(identity[k] == provenance[k] for k in ('candidate_sha256', 'model_xml_sha256', 'receipt_sha256')),
            'Export-to-transport provenance changed')
    require(identity['candidate_sha256'] == source_hash, 'Transport uses a different submission')
    profile = transport_profile(xml, index.name)
    manifest = read(folder / 'manifest.json')
    require(manifest['model_xml_sha256'] == exporter.digest(xml), 'Transport XML identity changed')
    frozen = json.loads(get('frozen-container.json'))
    exporter.verify_container(frozen, image, index, manifest['container_name'],
                              memory_bytes=solver.MEMORY)
    require(frozen['State']['Running'] is True and frozen['State']['Paused'] is True,
            'Successful transport artifacts were not frozen')
    artifacts = json.loads(get('artifacts.json')); raw = {}
    for name in ('model.xml', 'xml-load.json', 'calculation.json', 'convergence.csv',
                 f"statepoint.{profile['sampling']['batches']}.h5"):
        raw[name] = get('artifacts/' + name)
        require(artifacts[name] == dict(bytes=len(raw[name]), sha256=exporter.digest(raw[name])), 'Transport artifact changed')
    calculation = solver.validate_calculation(raw, profile, xml)
    require(calculation['sampling'] == result['sampling'] and validate_keff(calculation['keff']) == validate_keff(result['keff']),
            'Transport result mismatch')
    before, after = [json.loads(get(name)) for name in ('data-before.json', 'data-after.json')]
    require(before == after, 'Data changed during execution')
    return dict(xml=xml, sampling=profile['sampling'], keff=validate_keff(calculation['keff']), data=before,
                runtime=json.loads(get('runtime-identity.json')), receipts=receipts,
                convergence=histories(raw['convergence.csv'], profile['sampling']))
