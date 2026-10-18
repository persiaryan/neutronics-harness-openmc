"""Explicit derived verdicts under a qualified policy; never edit original evidence."""
from copy import deepcopy
from pathlib import Path

from evaluation.candidates import assessment, lost_particles, receipts, verify, run
from evaluation.benchmark_suite import scoring
from evaluation.scientific.inspection import WORKER
from evaluation.scientific.records import inspection_record, require
from evaluator.run import digest
from evaluator.transport_input import accepted_export, read_regular

VERSION = 'confirmation-verdict-revision-v1-lost-particles'
LEGACY_REASON = 'Native termination has no established model-failure attribution'


def revise(directory, index, reference):
    directory, index = Path(directory), Path(index)
    original = receipts.read(directory / 'report.json')
    legacy = verify.review_assessment(directory, index, reference=reference)
    require(receipts.read(directory / 'review.json') == legacy,
            'Original review contradicts reconstruction')
    revised = deepcopy(original)
    native = None
    if legacy['evidence_status'] == 'coherent':
        decision = 'unchanged_after_reconstruction'
        result = legacy
    else:
        # The frozen verifier has reconstructed assignment, export, inspections,
        # fidelity and native result before reaching this exact unsupported stop.
        require(legacy['evidence_status'] == 'insufficient' and legacy.get('reason') == LEGACY_REASON,
                'Migration does not resolve this missing or contradictory evidence')
        require(original['status'] == 'stopped' and original['stop'] ==
                dict(stage='transport', cause='evaluator', detail='openmc_abnormal_exit'),
                'Migration is restricted to unattributed native termination')
        require(not {'candidate_keff','comparison','leakage'} & original.keys(),
                'Stopped transport claims unavailable numerical results')
        goal = run.target(original['case'], reference=reference)
        native = lost_particles.review(directory, goal, index)
        xml, _ = accepted_export(directory / 'export')
        observation = inspection_record(original['case'], directory / 'export-inspection',
            xml, WORKER.read_bytes(), image=goal['protocol']['export_image'])
        checks = assessment.fidelity_checks(original['case'], original['fidelity'], observation)
        expected = assessment.blank_gates()
        for name in ('required_data','model_builds','valid_geometry'):
            expected[name] = dict(passed=True, cause=None)
        expected['openmc_runs']['detail'] = 'openmc_abnormal_exit'
        reached = {'export','export-inspection','export-boundaries','transport'}
        # Validate the original gate/check accounting too; legacy reconstruction
        # stopped before this comparison. No unassessed property becomes true.
        verify.stopped_verdict(original, expected, checks, reached,
                               'transport', 'evaluator', 'openmc_abnormal_exit')
        revised['gates']['openmc_runs'] = dict(passed=False, cause='model',
                                               detail='openmc_abnormal_exit')
        revised['stop']['cause'] = 'model'
        revised['diagnostic_score'] = scoring.score(revised['gates'], checks)
        expected['openmc_runs'] = dict(passed=False, cause='model')
        result = dict(evidence_status='coherent', **verify.stopped_verdict(
            revised, expected, checks, reached, 'transport', 'model', 'openmc_abnormal_exit'))
        decision = 'qualified_lost_particle_model_failure'
    return dict(format=VERSION, policy=lost_particles.POLICY, decision=decision,
        original_report_file_sha256=digest(read_regular(directory / 'report.json', limit=32_000_000)),
        original_review_file_sha256=digest(read_regular(directory / 'review.json')),
        legacy_reconstruction=legacy, native_failure_evidence=native,
        verdict=dict(evidence_status=result['evidence_status'], score=result['score'],
                     strict_correct=result['strict_correct'],
                     status=result['status'], attribution=result.get('attribution'),
                     stop=revised.get('stop'), gates=revised['gates'], checks=revised['checks'],
                     diagnostic_score=revised['diagnostic_score']),
        original_evidence_modified=False, new_model_calls=0, new_native_transports=0)
