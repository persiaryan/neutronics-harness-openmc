"""Execute unchanged candidate bytes through private, isolated diagnostic grading."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import time

from evaluator import run as exporter, transport as solver
from evaluator.transport_input import accepted_export, read_regular, transport_profile
from evaluation.scientific.inspection import admit, inspect_xml, WORKER
from evaluation.scientific.records import require, unchanged
from evaluation.benchmark_suite import scoring
from evaluation.benchmark_suite.suite_cases import SPECS, probes
from evaluation.benchmark_suite.suite_checks import assess
from evaluation.benchmark_suite.references import expected_data, verify as verify_suite
from evaluation.scientific.records import inspection_record, leakage
from evaluation.candidates import assessment, receipts
from evaluation.candidates.phase_evidence import export_outcome
from evaluator.contracts import CONTRACTS, FACTORY
from prompts.prepare import build_prompt, CASE_FILES
from evaluator.profiles import BOUNDARY_PROTOCOL, FACTORY_PROFILE, assessment_route
from evaluation.scientific import boundaries
from evaluation.candidates import boundary_assessment

ROOT = Path(__file__).resolve().parents[2]
INDEX = ROOT / 'evaluation/benchmark_suite/frozen/pilot-1'


class StopAssessment(Exception):
    pass


def clean_resources():
    require(not exporter.docker('ps', '-aq', '--filter', 'name=neutronics-v5-'), 'Prior project container remains')
    require(not exporter.docker('volume', 'ls', '-q', '--filter', 'name=neutronics-v5-'), 'Prior project volume remains')


def target(case):
    require(case in CASE_FILES, 'Unknown public case')
    checked = verify_suite(INDEX)
    manifest = receipts.read(INDEX / 'manifest.json')
    reference = manifest['references'][case]
    require(reference['technical_status'] == 'technically_qualified', 'Reference is not technically qualified')
    frozen_rubric = receipts.read(INDEX / 'scoring.json')
    scoring.verify_reference_criteria(frozen_rubric)
    protocol = receipts.read(INDEX / 'suite_protocol.json')
    report = receipts.read(ROOT / reference['path'] / 'evidence/qualification.json')
    return dict(index=checked, reference=reference, protocol=protocol, runtime=report['runs'][0]['runtime'],
                data=expected_data(case, receipts.read(ROOT / 'evaluation/benchmark_suite/expected_data.json')))


def preflight(index, goal):
    index, inventory = exporter.data_directory(Path(index))
    clean_resources()
    for name in ('export_image', 'transport_image'):
        image = goal['protocol'][name]
        require(json.loads(exporter.docker('image', 'inspect', image))[0]['Id'] == image, 'Runtime image mismatch')
    tables = [t for item in goal['data']['files'].values() for t in item['tables']]
    actual = solver.data_identity(index, dict(required_tables=tables))
    require(actual == goal['data'], 'Evaluator data differ from frozen reference')
    return index, dict(status='passed', inventory=inventory, data=actual)


def native_model_failure(value, folder):
    """Recognize a bounded set of verified native diagnostics, not arbitrary crashes.

    The pinned serial OpenMC runtime uses exit 255 for the observed fatal source
    constraint diagnostic. Keep unrelated 255 exits and signal exits unscored.
    """
    if value.get('status') == 'rejected' and value.get('reason') in {'xml-load_exit_nonzero', 'openmc_exit_nonzero'}:
        return True
    if value.get('reason') != 'openmc_abnormal_exit':
        return False
    process = receipts.read(folder / 'openmc-process.json')
    diagnostic = read_regular(folder / 'openmc-stderr.txt').decode()
    return (process == dict(exit_code=255, stop_reason=None) and
            'ERROR: Too few source sites satisfied the constraints' in diagnostic)


def markdown(report):
    result = report['diagnostic_score']
    lines = ['# Private candidate diagnostic assessment', '',
             'Case: `' + report['case'] + '`. Status: **' + report['status'] + '**.', '',
             'Diagnostic score: **' + str(result.get('score')) + '** / 100. Official grading disabled; scientific review pending.', '',
             '| Hard gate | Passed | Cause / evidence |', '|---|---|---|']
    for name, value in report['gates'].items():
        lines.append(f"| {name} | {value['passed']} | {value.get('cause')} — {value.get('detail', '')} |")
    lines.extend(['', '| Category | Earned / applicable points |', '|---|---:|'])
    for name, value in result.get('categories', {}).items():
        lines.append(f"| {name} | {value['earned_points']} / {scoring.RUBRIC['categories'][name]['weight']} |")
    if 'comparison' in report:
        c = report['comparison']
        lines.extend(['', f"k-effective comparison: {c['status']}; delta {c['delta_pcm']:+.3f} pcm, "
                      f"approximate 95% interval [{c['interval_pcm'][0]:+.3f}, {c['interval_pcm'][1]:+.3f}] pcm."])
    lines.extend(['', 'See report.json for every named check, phase and provenance record.', '',
                  'No source repair or builder feedback. Finite probes and boundary observations are bounded evidence, '
                  'not exhaustive geometry equivalence. Shared data/model bias is outside Monte Carlo uncertainty.', ''])
    return '\n'.join(lines)


def evaluate(case, output, *, index, candidate, provenance=None, contract=FACTORY,
             execution_profile=FACTORY_PROFILE, evaluator_protocol=BOUNDARY_PROTOCOL):
    route = assessment_route(contract, execution_profile, evaluator_protocol)
    route['prompt_sha256'] = exporter.digest(build_prompt(case, contract=contract).encode())
    budgets = route['execution_profile']['budgets']
    require(case in CASE_FILES, 'Unknown public case')
    boundary_spec = boundaries.requirements(case) if case != 'moderated_cylinder' else None
    output = Path(output).absolute()
    require(not output.exists(), 'Refusing to overwrite candidate evidence')
    output.mkdir(parents=True)
    started = time.monotonic()
    report = dict(format='private-candidate-diagnostic-v5', case=case, status='incomplete',
                  created_utc=datetime.now(timezone.utc).isoformat(), gates=assessment.blank_gates(), checks=assessment.blank_checks(),
                  phases={}, grading_enabled=False, scientific_review='pending_owner_review', builder_feedback='not_sent',
                  candidate_repair=False, host_candidate_execution='not_run', cleanup_confirmed=False)
    stage = 'admission'
    def gate(name, passed, cause=None, detail=''):
        report['gates'][name] = dict(passed=passed, cause=cause, detail=detail)
    def stop(cause, detail, hard_gate=None):
        report['stop'] = dict(stage=stage, cause=cause, detail=detail)
        if hard_gate:
            # The frozen rubric has no indeterminate cause. Keep its gate
            # unassessed; preserve the more precise attribution in stop.cause.
            gate(hard_gate, False if cause == 'model' else None,
                 'evaluator' if cause == 'indeterminate' else cause, detail)
        raise StopAssessment()
    try:
        goal = target(case)
        require(all(goal['protocol'][key] == route['execution_profile'][key] for key in ('export_image', 'transport_image')),
                'Selected execution profile differs from frozen runtime identities')
        source = exporter.source_bytes(Path(candidate))
        provenance = provenance or dict(actor='operator_control', source_sha256=exporter.digest(source),
                                        prompt_sha256=route['prompt_sha256'])
        require(provenance['source_sha256'] == exporter.digest(source), 'Provenance source mismatch')
        source_hash = exporter.digest(source)
        (output / 'candidate.py').write_bytes(source)
        (output / 'prompt.txt').write_text(build_prompt(case, contract=contract))
        snapshots = output / 'implementation'
        snapshots.mkdir()
        for file in Path(__file__).parent.glob('*.py'):
            (snapshots / file.name).write_bytes(file.read_bytes())
        report['assignment'] = dict(case=case, case_version=1, provenance=provenance, source_sha256=source_hash,
                                    frozen_index_sha256=goal['index']['manifest_sha256'], reference=goal['reference'],
                                    rubric=scoring.identity(), budgets=budgets, sampling=dict(particles=10000, batches=SPECS[case]['batches'],
                                                                  inactive=100, generations_per_batch=2, seed=1, source='uniform'))
        report['assignment']['delivery_contract'] = contract
        report['assignment']['assessment_route'] = route
        if boundary_spec is not None:
            report['format'] = 'private-candidate-diagnostic-v5'
            report['assignment']['scientific_boundary'] = dict(observer=boundaries.VERSION,
                comparison=boundaries.COMPARISON,requirements_sha256=exporter.digest(json.dumps(boundary_spec,sort_keys=True).encode()))
            exporter.write_json(output / 'boundary-requirements.json', boundary_spec)
        exporter.write_json(output / 'assignment.json', report['assignment'])
        if boundary_spec is None:
            stage = 'eligibility'
            stop('capability', 'External cylinder boundary requirements are outside the qualified observer scope')
        stage = 'preflight'
        index, checked = preflight(index, goal)
        exporter.write_json(output / 'preflight.json', checked)
        gate('required_data', True, detail='Evaluator-supplied task data match frozen hashes')
        stage = 'export'
        value = exporter.evaluate(output / 'candidate.py', output / 'export', index=index,
                                  image=goal['protocol']['export_image'], wall_seconds=budgets['export'],
                                  contract=contract, execution_profile=execution_profile)
        report['phases']['export'] = value
        if value.get('cleanup_confirmed') is not True:
            stop('infrastructure', 'Export cleanup uncertain')
        receipts.container_phase(output / 'export', goal['protocol']['export_image'], index, source_hash)
        if value['status'] != 'exported':
            cause = export_outcome(output / 'export', goal['protocol']['export_image'], index, source_hash)['cause']
            stop(cause, value.get('reason', value['status']), 'model_builds')
        gate('model_builds', True, detail='Submitted module produced admitted combined XML under ' + contract)
        xml, identity = accepted_export(output / 'export')
        require(identity['candidate_sha256'] == source_hash, 'Export source identity changed')
        report['final_model'] = dict(path='export/artifacts/model.xml', sha256=exporter.digest(xml), bytes=len(xml))
        stage = 'export-inspection'
        observation = inspect_xml(xml, probes(case)[0], output / stage, wall_seconds=budgets['inspection'])
        report['phases'][stage] = {k: observation[k] for k in ('status', 'cleanup_confirmed')}
        observation = inspection_record(case, output / stage, xml, WORKER.read_bytes())
        failure = assessment.inspection_failure(observation)
        if failure:
            if observation['status'] == 'invalid_model':
                report['material_input_findings'] = observation['findings']
                report['checks']['materials']['composition'] = False
            stop(**failure)
        stage = 'export-boundaries'
        value = boundaries.observe(xml, output / stage, wall_seconds=budgets['inspection'])
        report['phases'][stage] = {k: value[k] for k in ('status', 'cleanup_confirmed')}
        if value['status'] != 'inspected' or value['cleanup_confirmed'] is not True:
            stop('evaluator', 'Boundary observation incomplete; no model attribution')
        boundary_observation = boundaries.record(output / stage, xml)
        boundary_result = boundary_assessment.evaluate(boundary_observation, boundary_spec, observation)
        stage = 'export-inspection'
        fidelity = assess(case, admit(xml), observation, report['assignment']['sampling'], boundary_result=boundary_result)
        exporter.write_json(output / 'export-fidelity.json', fidelity)
        report['checks'] = assessment.fidelity_checks(case, fidelity, observation)
        report['fidelity'] = fidelity
        if fidelity['geometry']['invalid_geometry']:
            stop('model', 'Invalid or overlapping geometry detected by finite all-matching-cell probes', 'valid_geometry')
        gate('valid_geometry', True, detail='No invalid geometry detected within finite probe coverage')
        stage = 'transport-admission'
        profile = transport_profile(xml, index.name)
        allowed = {tuple(t) for r in goal['data']['files'].values() for t in r['tables']}
        if not set(map(tuple, profile['required_tables'])) <= allowed:
            stop('model', 'Submission requests nuclear data outside the explicitly specified task collection', 'required_data')
        stage = 'transport'
        value = solver.transport(output / 'export', output / 'transport', index=index,
                                 image=goal['protocol']['transport_image'], wall_seconds=budgets['transport'])
        report['phases']['transport'] = value
        if value.get('cleanup_confirmed') is not True:
            stop('infrastructure', 'Transport cleanup uncertain')
        if value['status'] != 'calculated_unreviewed':
            if native_model_failure(value, output / 'transport'):
                receipts.container_phase(output / 'transport', goal['protocol']['transport_image'], index, source_hash, transport=True)
                before = receipts.read(output / 'transport/data-before.json')
                after = receipts.read(output / 'transport/data-after.json')
                require(before == after, 'Data changed during failed execution')
                report['native_failure_classification'] = ('verified source-constraint fatal diagnostic, exit 255'
                    if value.get('reason') == 'openmc_abnormal_exit' else 'ordinary XML/native model rejection')
                stop('model', value['reason'], 'openmc_runs')
            stop('evaluator', value.get('reason', value['status']), 'openmc_runs')
        stage = 'assessment'
        record = receipts.transport_record(output, source_hash, goal['protocol']['transport_image'], index)
        require(record['runtime'] == goal['runtime'], 'Native runtime differs from frozen reference')
        require(record['data']['index_sha256'] == goal['data']['index_sha256'] and
                all(goal['data']['files'].get(name) == data for name, data in record['data']['files'].items()), 'Candidate data identity mismatch')
        for name in ('openmc_runs', 'finite_statepoint', 'required_observables'):
            gate(name, True, detail='Native completion and finite k-effective/statepoint evidence verified')
        leak = leakage(read_regular(output / 'transport/openmc-stdout.txt').decode())
        leak_checks = dict(leakage_probability=0 <= leak['mean'] <= 1 and leak['std_dev'] >= 0,
                           leakage_boundary_consistency=leak['mean'] == 0 if case == 'reflective_pin_cell' else leak['mean'] > 0)
        report['comparison'] = assessment.complete_checks(report['checks'], record, goal['reference']['primary_mean'],
                                                          leak_checks)
        report['candidate_keff'] = record['keff']
        report['leakage'] = leak
        unchanged(record['receipts'])
        require(read_regular(output / 'candidate.py') == source, 'Submission changed during evaluation')
        require(verify_suite(INDEX) == goal['index'], 'Frozen reference index changed during evaluation')
        report['status'] = 'assessed'
    except StopAssessment:
        report['status'] = 'stopped'
    except Exception as exc:
        report.update(status='incomplete', error_type=type(exc).__name__, error=str(exc)[:2000],
                      stop=dict(stage=stage, cause='evaluator', detail='Missing, unsupported or inconsistent evaluator evidence'))
        # Later integrity failures must invalidate an otherwise complete score.
        gate('required_observables', None, 'evaluator', 'Assessment evidence incomplete or inconsistent')
    finally:
        try:
            clean_resources()
            report['cleanup_confirmed'] = True
        except Exception as exc:
            report['cleanup_error'] = str(exc)
            gate('openmc_runs', None, 'infrastructure', 'Final cleanup unconfirmed')
        report['diagnostic_score'] = scoring.score(report['gates'], report['checks'])
        if not report['cleanup_confirmed']:
            report['diagnostic_score'] = dict(report['diagnostic_score'], status='unscored', score=None,
                                               strict_correct=False, reason='Cleanup or containment uncertainty')
        report['elapsed_seconds'] = round(time.monotonic() - started, 3)
        exporter.write_json(output / 'report.json', report)
        (output / 'report.md').write_text(markdown(report))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', required=True, choices=sorted(CASE_FILES))
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--data-index', required=True, type=Path)
    parser.add_argument('--contract', choices=CONTRACTS, default=FACTORY)
    parser.add_argument('--execution-profile', default=FACTORY_PROFILE)
    parser.add_argument('--evaluator-protocol', default=BOUNDARY_PROTOCOL)
    args = parser.parse_args()
    value = evaluate(args.case, args.output, index=args.data_index, candidate=args.candidate,
                     contract=args.contract, execution_profile=args.execution_profile, evaluator_protocol=args.evaluator_protocol)
    print(json.dumps({k: value[k] for k in ('status', 'diagnostic_score', 'cleanup_confirmed')}, indent=2))
