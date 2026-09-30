"""Reconstruct current assessment verdicts from retained execution evidence."""
import argparse
import json
from pathlib import Path

from evaluator.run import digest
from evaluator.evidence import InsufficientEvidence
from evaluator.contracts import CONTRACTS, FACTORY, export_contract
from evaluation.candidates.phase_evidence import export_outcome
from evaluation.candidates import receipts, assessment, run
from evaluation.benchmark_suite import scoring
from evaluation.benchmark_suite.suite_checks import assess
from evaluation.scientific.records import inspection_record, leakage
from evaluation.scientific.inspection import WORKER, admit
from evaluation.scientific.records import require
from prompts.prepare import build_prompt
from evaluator.profiles import BOUNDARY_PROTOCOL
from evaluation.scientific import boundaries
from evaluation.candidates import boundary_assessment


def stopped_verdict(report, gates, checks, phases, stage, cause, reason):
    """Compare every claimed gate/check against the phases actually reconstructed."""
    require(report['status'] == 'stopped' and report['stop'] == dict(stage=stage, cause=cause, detail=reason),
            'Stopped verdict contradicts phase evidence')
    require(set(report['phases']) == phases, 'Stopped report has unreached or missing phases')
    require({n: (v['passed'], v['cause']) for n, v in report['gates'].items()} ==
            {n: (v['passed'], v['cause']) for n, v in gates.items()}, 'Stopped gates contradict execution')
    computed = scoring.score(gates, checks)
    require(report['checks'] == checks and computed == report['diagnostic_score'], 'Stopped score or checks contradict evidence')
    return dict(status='verified_from_retained_failure', score=computed['score'], strict_correct=False,
                stop=report['stop'], attribution=cause)


def assessment_report(directory, index, *, reference=None, runtime=None):
    directory = Path(directory)
    report = receipts.read(directory / 'report.json')
    require(report['format'] == 'private-candidate-diagnostic-v5',
            'Incompatible historical report: use its original protocol verifier; never rescore as current')
    require('repeat_export' not in report and not any(n.startswith('repeat-') for n in report['phases']),
            'V2 forbids repeat-export phases or verdicts')
    require(report['grading_enabled'] is False and report['builder_feedback'] == 'not_sent' and
            report['candidate_repair'] is False, 'Invalid private assessment boundary')
    if report['cleanup_confirmed'] is not True:
        require(report['diagnostic_score']['score'] is None, 'Unclean report claims a score')
        raise InsufficientEvidence('Cleanup is not confirmed')
    computed = scoring.score(report['gates'], report['checks'])
    require(computed == report['diagnostic_score'], 'Candidate score or numerical report changed')
    require(report['status'] in ('assessed', 'stopped', 'incomplete'), 'Unknown assessment status')
    if report['status'] != 'assessed':
        stop = report['stop']
        require(not report['diagnostic_score']['strict_correct'], 'Stopped assessment claims strict correctness')
        if stop['stage'] == 'export':
            require(set(report['phases']) <= {'export'} and report['checks'] == assessment.blank_checks(),
                    'Stopped export claims observations from unreached phases')
            require(all(g['passed'] is not True for n, g in report['gates'].items() if n != 'required_data'),
                    'Stopped export claims a passed unreached gate')
        if stop['cause'] != 'model':
            require(report['diagnostic_score']['score'] is None, 'Unattributed stopped assessment claims a score')
    assignment = receipts.read(directory / 'assignment.json')
    require(assignment['rubric'] == scoring.identity(), 'Assessment rubric identity changed')
    contract = assignment['delivery_contract']
    require(contract in CONTRACTS, 'Unknown assessment delivery contract')
    route = assignment['assessment_route']
    boundary_spec = None
    from evaluator.profiles import assessment_route
    expected_route = assessment_route(contract, route['execution_profile']['id'], route['evaluator_protocol'], runtime=runtime)
    expected_route['prompt_sha256'] = digest(build_prompt(assignment['case'], contract=contract).encode())
    require(route == expected_route and assignment['budgets'] == route['execution_profile']['budgets'],
            'Assessment execution profile/protocol changed')
    if assignment['case'] != 'moderated_cylinder':
        boundary_spec=boundaries.requirements(assignment['case'])
        require(report['format']=='private-candidate-diagnostic-v5' and
                receipts.read(directory/'boundary-requirements.json')==boundary_spec and
                assignment['scientific_boundary']==dict(observer=boundaries.VERSION,comparison=boundaries.COMPARISON,
                    requirements_sha256=digest(json.dumps(boundary_spec,sort_keys=True).encode())),
                'Scientific boundary protocol/requirements changed')
    require((boundary_spec is not None)==('scientific_boundary' in assignment), 'Boundary observations require explicit protocol selection')
    if 'export' in report['phases']:
        export_manifest = receipts.read(directory / 'export/manifest.json')
        require(export_contract(export_manifest) == contract, 'Assessment and export delivery contracts differ')
        require(export_manifest.get('execution_profile') == route['execution_profile'],
                'Assessment/export execution profiles differ')
    require(assignment == report['assignment'], 'Assessment assignment changed')
    require(report['case'] == assignment['case'], 'Assessment case changed')
    source = (directory / 'candidate.py').read_bytes()
    require(digest(source) == assignment['source_sha256'], 'Submission changed')
    require(assignment['provenance']['source_sha256'] == assignment['source_sha256'], 'Assignment source provenance changed')
    require((directory / 'prompt.txt').read_bytes() == build_prompt(assignment['case'], contract=contract).encode(), 'Assessment public prompt changed')
    goal = run.target(assignment['case'], reference=reference, runtime=runtime)
    require(assignment['frozen_index_sha256'] == goal['index']['manifest_sha256'] and
            assignment['reference'] == goal['reference'], 'Assessment reference changed')
    require(assignment['sampling'] == dict(particles=10000, batches=run.SPECS[assignment['case']]['batches'],
            inactive=100, generations_per_batch=2, seed=1, source='uniform'), 'Assessment sampling assignment changed')
    if boundary_spec is None:
        require(assignment['case'] == 'moderated_cylinder', 'Unknown unsupported task')
        require(report['cleanup_confirmed'] is True, 'Unconfirmed eligibility cleanup')
        return stopped_verdict(report, assessment.blank_gates(), assessment.blank_checks(), set(),
            'eligibility', 'capability', 'External cylinder boundary requirements are outside the qualified observer scope')
    preflight = receipts.read(directory / 'preflight.json')
    require(preflight['status'] == 'passed' and preflight['data'] == goal['data'], 'Assessment preflight data changed')
    if report['status'] != 'assessed' and report['stop']['stage'] == 'export':
        value = receipts.container_phase(directory / 'export', goal['protocol']['export_image'], index, digest(source))
        require(report['phases'] == {'export': value}, 'Stopped export phase report changed')
        outcome = export_outcome(directory / 'export', goal['protocol']['export_image'], index, digest(source), runtime=runtime)
        cause = outcome['cause']
        require(cause is not None and report['stop']['cause'] == cause and
                report['stop']['detail'] == outcome['reason'], 'Stop contradicts execution attribution')
        expected = assessment.blank_gates()
        expected['required_data'] = dict(passed=True, cause=None)
        expected['model_builds'] = dict(passed=False if cause == 'model' else None,
                                       cause='evaluator' if cause == 'indeterminate' else cause)
        return stopped_verdict(report, expected, assessment.blank_checks(), {'export'}, 'export', cause, outcome['reason'])
    if report['status'] != 'assessed':
        # Other stopped paths are inspected below when their completed phases can
        # be reconstructed. Unsupported termination stages never inherit a score.
        if report['stop']['stage'] not in ('export-inspection',
                                         'transport-admission', 'transport'):
            raise InsufficientEvidence('No qualified reconstruction for stopped stage: ' + report['stop']['stage'])
    expected = assessment.blank_gates()
    expected['required_data'] = dict(passed=True, cause=None)
    value = receipts.container_phase(directory / 'export', goal['protocol']['export_image'], index, digest(source))
    require(value == report['phases']['export'], 'Export phase report changed')
    outcome = export_outcome(directory / 'export', goal['protocol']['export_image'], index, digest(source), runtime=runtime)
    require(outcome == dict(cause=None, reason=None), 'Completed export contradicts process evidence')
    reached = {'export'}
    xml, _ = receipts.accepted_export(directory / 'export')
    require(report['final_model'] == dict(path='export/artifacts/model.xml', sha256=digest(xml), bytes=len(xml)),
            'Final artifact identity changed')
    expected['model_builds'] = dict(passed=True, cause=None)
    inspection_result = receipts.read(directory / 'export-inspection/result.json')
    obs = inspection_record(assignment['case'], directory / 'export-inspection', xml, WORKER.read_bytes(), image=goal['protocol']['export_image'])
    reached.add('export-inspection')
    require(report['phases']['export-inspection'] ==
            {k: inspection_result[k] for k in ('status', 'cleanup_confirmed')}, 'Inspector phase summary changed')
    failure = assessment.inspection_failure(obs)
    if failure:
        require(not {'fidelity','candidate_keff','comparison','leakage'} & report.keys(),
                'Failed inspection claims unreached scientific results')
        checks = assessment.blank_checks()
        if failure['cause'] == 'model':
            require(report.get('material_input_findings') == obs['findings'], 'Material findings changed')
            expected[failure['hard_gate']] = dict(passed=False, cause='model')
            checks['materials']['composition'] = False
        else:
            require('material_input_findings' not in report, 'Inspector exception promoted to material defect')
        return stopped_verdict(report, expected, checks, reached, 'export-inspection',
                               failure['cause'], failure['detail'])
    require('material_input_findings' not in report, 'Successful inspection claims material input failure')
    boundary_observation = boundaries.record(directory / 'export-boundaries', xml, image=goal['protocol']['export_image'])
    summary = receipts.read(directory / 'export-boundaries/result.json')
    require(report['phases']['export-boundaries'] == {k: summary[k] for k in ('status', 'cleanup_confirmed')},
            'Boundary inspection summary changed')
    reached.add('export-boundaries')
    boundary_result = boundary_assessment.evaluate(boundary_observation, boundary_spec, obs)
    fidelity = assess(assignment['case'], admit(xml), obs, assignment['sampling'], boundary_result=boundary_result)
    require(fidelity == receipts.read(directory / 'export-fidelity.json') and fidelity == report['fidelity'],
            'Fidelity observations changed')
    expected_checks = assessment.fidelity_checks(assignment['case'], fidelity, obs)
    if report['status'] != 'assessed' and report['stop']['stage'] == 'export-inspection':
        require(report['checks'] == expected_checks, 'Stopped geometry checks changed')
        require(fidelity['geometry']['invalid_geometry'] > 0 and report['stop']['cause'] == 'model' and
                report['gates']['valid_geometry']['passed'] is False, 'Geometry stop lacks an observed defect')
        expected['valid_geometry'] = dict(passed=False, cause='model')
        return stopped_verdict(report, expected, expected_checks, reached, 'export-inspection', 'model',
            'Invalid or overlapping geometry detected by finite all-matching-cell probes')
    require(fidelity['geometry']['invalid_geometry'] == 0, 'Observed invalid geometry was ignored')
    expected['valid_geometry'] = dict(passed=True, cause=None)
    if report['status'] != 'assessed':
        profile = run.transport_profile(xml, index.name)
        allowed = {tuple(t) for r in goal['data']['files'].values() for t in r['tables']}
        if report['stop']['stage'] == 'transport-admission':
            require(not set(map(tuple, profile['required_tables'])) <= allowed, 'Data-rejection stop has no out-of-task request')
            expected['required_data'] = dict(passed=False, cause='model')
            return stopped_verdict(report, expected, expected_checks, reached, 'transport-admission', 'model',
                'Submission requests nuclear data outside the explicitly specified task collection')
        if report['stop']['stage'] == 'transport':
            from evaluation.candidates.phase_evidence import transport_failure
            value = receipts.container_phase(directory / 'transport', goal['protocol']['transport_image'], index, digest(source), transport=True)
            require(value == report['phases']['transport'], 'Stopped transport phase changed')
            transport_failure(directory, goal, index, digest(source))
            reached.add('transport')
            expected['openmc_runs'] = dict(passed=False, cause='model')
            return stopped_verdict(report, expected, expected_checks, reached, 'transport', 'model', value['reason'])
        raise InsufficientEvidence('No complete termination receipts for stopped stage: ' + report['stop']['stage'])
    require(fidelity['geometry']['invalid_geometry'] == 0, 'Invalid geometry promoted to full assessment')
    require(set(report['phases']) == reached | {'transport'}, 'Full assessment phase inventory changed')
    require(report['phases']['transport'] == receipts.read(directory / 'transport/result.json'), 'Transport phase report changed')
    record = receipts.transport_record(directory, digest(source), goal['protocol']['transport_image'], index)
    require(record['runtime'] == goal['runtime'] and record['data']['index_sha256'] == goal['data']['index_sha256'] and
            all(goal['data']['files'].get(n) == v for n, v in record['data']['files'].items()), 'Native runtime/data changed')
    checks = assessment.fidelity_checks(assignment['case'], fidelity, obs)
    leak = leakage((directory / 'transport/openmc-stdout.txt').read_text())
    leak_checks = dict(leakage_probability=0 <= leak['mean'] <= 1 and leak['std_dev'] >= 0,
                       leakage_boundary_consistency=leak['mean'] == 0 if assignment['case'] == 'reflective_pin_cell' else leak['mean'] > 0)
    comparison = assessment.complete_checks(checks, record, goal['reference']['primary_mean'], leak_checks)
    gates = {name: dict(passed=True, cause=None) for name in scoring.RUBRIC['hard_gates']}
    require(all(v['passed'] is True and v['cause'] is None for v in report['gates'].values()), 'Full assessment has nonpassing gates')
    computed = scoring.score(gates, checks)
    require(checks == report['checks'] and computed == report['diagnostic_score'] and comparison == report['comparison'] and
            record['keff'] == report['candidate_keff'], 'Candidate score or numerical report changed')
    return dict(status='verified_from_retained_execution', score=computed['score'], strict_correct=computed['strict_correct'])


def review_assessment(directory, index, *, reference=None, runtime=None):
    """A new review record; never replace or fill gaps in the historical evidence."""
    annotation = dict(format='evidence-review-v2', reported_score=None)
    try:
        original = receipts.read(Path(directory) / 'report.json')
        require(isinstance(original, dict) and isinstance(original.get('diagnostic_score'), dict), 'Malformed assessment report')
        annotation['reported_score'] = original.get('diagnostic_score', {}).get('score')
        result = assessment_report(directory, index, reference=reference, runtime=runtime)
    except (InsufficientEvidence, FileNotFoundError) as exc:
        return dict(annotation, evidence_status='insufficient', score=None, reason=str(exc))
    except (ValueError, KeyError, TypeError, RuntimeError, UnicodeError) as exc:
        return dict(annotation, evidence_status='contradictory', score=None, reason=str(exc))
    return dict(annotation, evidence_status='coherent', **result)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--assessment', required=True, type=Path)
    parser.add_argument('--data-index', required=True, type=Path)
    args = parser.parse_args()
    result = review_assessment(args.assessment, args.data_index)
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result['evidence_status'] == 'coherent' else 1)
