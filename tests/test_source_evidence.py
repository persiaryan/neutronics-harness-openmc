"""Source evidence integration with synthetic execution doubles; no native runs.

Only source comparison, assessment mapping, scoring and retained-report review
are exercised. Material/boundary/phase providers are doubles, not qualification
of those components or a claim that a physical model was executed.
"""
from contextlib import ExitStack
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

from evaluation.benchmark_suite import scoring, suite_checks
from evaluation.benchmark_suite.suite_cases import probes
from evaluation.candidates import assessment, verify
from evaluator.contracts import FACTORY
from evaluator.profiles import BOUNDARY_PROTOCOL, FACTORY_PROFILE, PROFILE, assessment_route
from evaluator.run import digest, write_json
from tests.test_source_space import TASKS, model, cartesian, replace_space
from tests.test_source_angle import polar, replace_angle


class SourceEvidence(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.case = 'reflective_pin_cell'
        self.boundary = dict(status='passed_checks', score_check=True)
        self.observation = dict(status='inspected', cleanup_confirmed=True, materials=[],
            observations=[['ok', [[1, 293.6]]]] * len(probes(self.case)[0]))
        material_checks = [dict(field=name, passed=True) for name in
            ('composition', 'required_material_roles', 'forced_isotropic', 'density', 'thermal_scattering')]
        self.stack.enter_context(patch.object(suite_checks, 'check_materials',
            return_value=({'1': 'fuel'}, material_checks)))
        self.goal = dict(index=dict(manifest_sha256='synthetic-reference-identity'),
            reference=dict(primary_mean=dict(mean=1., std_dev=1e-5)),
            protocol={key: PROFILE[key] for key in ('export_image', 'transport_image')},
            runtime=dict(control='synthetic'), data=dict(index_sha256='synthetic-data', files={}))
        self.record = dict(runtime=self.goal['runtime'], data=self.goal['data'],
            keff=dict(mean=1., std_dev=1e-5),
            convergence=dict(statistics=dict(entropy_bits=dict(second_minus_first=0.))))
        self.phase = dict(status='exported', cleanup_confirmed=True)
        # The verifier reconstructs settings from retained XML; unrelated execution is doubled.
        doubles = [
            patch.object(verify.run, 'target', return_value=self.goal),
            patch.object(verify.receipts, 'container_phase', return_value=self.phase),
            patch.object(verify, 'export_outcome', return_value=dict(cause=None, reason=None)),
            patch.object(verify.receipts, 'accepted_export',
                side_effect=lambda _: ((self.folder/'model.xml').read_bytes(), {})),
            patch.object(verify, 'inspection_record', return_value=self.observation),
            patch.object(verify.boundaries, 'record', return_value={}),
            patch.object(verify.boundary_assessment, 'evaluate', return_value=self.boundary),
            patch.object(verify.receipts, 'transport_record', return_value=self.record),
        ]
        for double in doubles:
            self.stack.enter_context(double)

    def retain(self, *, unknown=False, wrong=False):
        root, sampling = model(self.case)
        space = cartesian(TASKS[self.case])
        if unknown:
            space.find('y').set('type', 'tabular')
        if wrong:
            space.find('x').set('parameters', '-.5 .63')
        replace_space(root, space)
        replace_angle(root, polar())
        xml = ET.tostring(root)
        source = b"raise AssertionError('Synthetic receipt candidate must never execute')\n"
        route = assessment_route(FACTORY, FACTORY_PROFILE, BOUNDARY_PROTOCOL)
        prompt = verify.build_prompt(self.case, contract=FACTORY).encode()
        route['prompt_sha256'] = digest(prompt)
        specification = verify.boundaries.requirements(self.case)
        assignment = dict(case=self.case, rubric=scoring.identity(), delivery_contract=FACTORY,
            assessment_route=route, budgets=PROFILE['budgets'], sampling=sampling,
            scientific_boundary=dict(observer=verify.boundaries.VERSION,
                comparison=verify.boundaries.COMPARISON,
                requirements_sha256=digest(json.dumps(specification, sort_keys=True).encode())),
            source_sha256=digest(source), provenance=dict(source_sha256=digest(source)),
            frozen_index_sha256=self.goal['index']['manifest_sha256'], reference=self.goal['reference'])
        fidelity = suite_checks.assess(self.case, root, self.observation, sampling,
                                       boundary_result=self.boundary)
        checks = assessment.fidelity_checks(self.case, fidelity, self.observation)
        comparison = assessment.complete_checks(checks, self.record,
            self.goal['reference']['primary_mean'],
            dict(leakage_probability=True, leakage_boundary_consistency=True))
        gates = {name: dict(passed=True, cause=None) for name in assessment.blank_gates()}
        phase = dict(status='inspected', cleanup_confirmed=True)
        report = dict(format='private-candidate-diagnostic-v5', grading_enabled=False,
            builder_feedback='not_sent', candidate_repair=False, cleanup_confirmed=True,
            case=self.case, status='assessed', assignment=assignment, gates=gates, checks=checks,
            diagnostic_score=scoring.score(gates, checks), fidelity=fidelity, comparison=comparison,
            candidate_keff=self.record['keff'],
            final_model=dict(path='export/artifacts/model.xml', sha256=digest(xml), bytes=len(xml)),
            phases={'export': self.phase, 'export-inspection': phase,
                    'export-boundaries': phase, 'transport': dict(status='synthetic')})
        objects = {'assignment.json': assignment, 'report.json': report,
            'boundary-requirements.json': specification, 'export-fidelity.json': fidelity,
            'preflight.json': dict(status='passed', data=self.goal['data']),
            'export/manifest.json': dict(format='isolated-export-evaluation-v2',
                delivery_contract=FACTORY, execution_profile=PROFILE),
            'export-inspection/result.json': phase, 'export-boundaries/result.json': phase,
            'transport/result.json': report['phases']['transport']}
        for name, value in objects.items():
            path = self.folder/name
            path.parent.mkdir(parents=True, exist_ok=True)
            write_json(path, value)
        for name, data in {'candidate.py': source, 'prompt.txt': prompt, 'model.xml': xml,
                           'transport/openmc-stdout.txt': b'Leakage Fraction = 0 +/- 0\n'}.items():
            (self.folder/name).write_bytes(data)
        return report

    def review(self):
        return verify.review_assessment(self.folder, self.folder/'unused-data-index.xml')

    def snapshot(self):
        return {p.relative_to(self.folder).as_posix(): p.read_bytes()
                for p in self.folder.rglob('*') if p.is_file()}

    def test_current_source_assessment_reconstructs_without_mutating_evidence(self):
        report = self.retain()
        self.assertIs(report['checks']['physics_settings']['source'], True)
        before = self.snapshot()
        result = self.review()
        self.assertEqual(result['evidence_status'], 'coherent', result)
        self.assertEqual(result['score'], report['diagnostic_score']['score'])
        self.assertIsNotNone(result['score'])
        self.assertEqual(self.snapshot(), before)

    def test_wrong_source_reconstructs_as_false_and_reduces_score(self):
        correct = self.retain()
        report = self.retain(wrong=True)
        self.assertIs(report['checks']['physics_settings']['source'], False)
        result = self.review()
        self.assertEqual(result['evidence_status'], 'coherent', result)
        self.assertAlmostEqual(correct['diagnostic_score']['score'] - result['score'],
                               3.5714285714285716)

    def test_unknown_and_wrong_plus_unknown_keep_null_score_and_detailed_failure(self):
        for wrong in (False, True):
            report = self.retain(unknown=True, wrong=wrong)
            self.assertIsNone(report['checks']['physics_settings']['source'])
            self.assertEqual(report['fidelity']['settings']['status'],
                             'discrepancy' if wrong else 'inconclusive')
            if wrong:
                self.assertTrue(any(c.get('axis') == 'x' and c['passed'] is False
                                    for c in report['fidelity']['settings']['checks']))
            result = self.review()
            self.assertEqual(result['evidence_status'], 'coherent', result)
            self.assertIsNone(result['score'])

    def test_forged_comparison_versions_or_observations_are_rejected(self):
        report = self.retain()
        original = report['fidelity']
        for key in ('spatial_source', 'angular_source'):
            for change in ('version', 'observation'):
                tampered = deepcopy(original)
                if change == 'version':
                    tampered['settings'][key]['comparison_version'] = 'unqualified-v99'
                else:
                    tampered['settings'][key]['observation']['encoding'] = 'relabelled'
                report['fidelity'] = tampered
                write_json(self.folder/'report.json', report)
                write_json(self.folder/'export-fidelity.json', tampered)
                before = self.snapshot()
                result = self.review()
                self.assertEqual(result['evidence_status'], 'contradictory', result)
                self.assertIn('Fidelity observations changed', result['reason'])
                self.assertIsNone(result['score'])
                self.assertEqual(self.snapshot(), before)

    def test_previous_route_is_not_relabelled_even_with_a_retained_score(self):
        report = self.retain()
        assignment = report['assignment']
        for protocol in ('factory-assessment-boundaries-v4-temperature-v1',
                         'factory-assessment-boundaries-v7'):
            assignment['assessment_route']['evaluator_protocol'] = protocol
            write_json(self.folder/'assignment.json', assignment)
            write_json(self.folder/'report.json', report)
            before = self.snapshot()
            result = self.review()
            self.assertEqual(result['evidence_status'], 'contradictory')
            self.assertIn('Unsupported evaluator protocol', result['reason'])
            self.assertEqual(result['reported_score'], report['diagnostic_score']['score'])
            self.assertIsNone(result['score'])
            self.assertEqual(self.snapshot(), before)


if __name__ == '__main__':
    unittest.main()
