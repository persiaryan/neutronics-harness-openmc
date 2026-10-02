"""Synthetic retained evidence only: no provider calls, candidates or transport."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from dashboard.campaign import campaign, read_records, selected_roots


CHECKS = {
    'geometry': ['interfaces', 'extent_and_map', 'domain', 'boundaries'],
    'materials': ['composition', 'density', 'thermal_scattering', 'temperature'],
    'physics_settings': ['physics', 'sampling', 'source', 'entropy_mesh_and_output'],
    'keff': ['equivalence_demonstrated'],
    'statistical_quality': ['precision', 'entropy_screen'],
    'engineering_consistency': ['leakage_probability', 'leakage_boundary_consistency'],
}
GATES = ['model_builds', 'openmc_runs', 'valid_geometry', 'required_data', 'finite_statepoint', 'required_observables']
CONDITIONS = {'A': ('guided_construction', 'generic_coding_guided_construction_v1'),
              'B': ('guided_boundaries', 'generic_coding_guided_boundaries_v3'),
              'C': ('guided_boundaries_smoke', 'generic_coding_guided_boundaries_smoke_v1')}


class CampaignTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.roots = []
        self.rubric = hashlib.sha256(Path('evaluation/benchmark_suite/scoring.json').read_bytes()).hexdigest()

    def tearDown(self):
        self.temp.cleanup()

    def write(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value))

    def run_fixture(self, config='A', case='task-one', result='pass', model='model-one', protocol='protocol-one', prompt='public-prompt'):
        root = self.root/str(len(self.roots)); self.roots.append(root)
        assistance, condition = CONDITIONS[config]
        plan = dict(cases=[case], model=model, assistance=assistance, condition=condition,
                    evaluator_protocol=protocol, adapter='test-adapter',
                    prompts={case: {'prompt_sha256':prompt}},
                    budgets=dict(model_requests=8, authoring_seconds=600, automatic_retries=0),
                    execution_profile=dict(id='test-profile', export_image='export', transport_image='transport'))
        self.write(root/'plan.json', plan)
        base = root/'runs'/case
        self.write(base/'builder/manifest.json', dict(image_id='builder'))
        self.write(base/'builder/result.json', dict(status='completed', elapsed_seconds=12, request_count=3))
        self.write(root/'summary.json', {'tasks':[dict(case=case, authoring={'effort':dict(token_usage={'total_tokens':200},token_usage_complete=True)})]})
        report = dict(format='private-candidate-diagnostic-v5', status='assessed', assignment=dict(rubric={'sha256':self.rubric}, reference={'case':case,'version':1},sampling={'seed':1}),
                      gates={k:dict(passed=True,cause=None) for k in GATES},
                      checks={k:{n:True for n in v} for k,v in CHECKS.items()},
                      diagnostic_score=dict(status='scored',score=100,strict_correct=True))
        if result == 'fail':
            report['checks']['materials']['density'] = False
            report['diagnostic_score'].update(score=94.64285714285714,strict_correct=False)
        review = dict(evidence_status='coherent', score=report['diagnostic_score']['score'],strict_correct=report['diagnostic_score']['strict_correct'])
        if result == 'unknown':
            review.update(evidence_status='insufficient',score=None)
        self.write(base/'assessment/report.json', report)
        self.write(base/'assessment/review.json', review)
        return root, report, review

    def overview(self):
        return campaign(self.roots)['cohorts'][0]

    def test_unknowns_stay_in_denominator(self):
        for result in ['pass']*18+['fail']*5+['unknown']*2:
            self.run_fixture(result=result)
        stats = self.overview()['groups']['A']['domains']['overall']
        self.assertEqual((stats['n'],stats['passed'],stats['failed'],stats['unknown']),(25,18,5,2))
        self.assertAlmostEqual(stats['rate'],.72)
        self.assertAlmostEqual(stats['possible_rate'],.8)

    def test_equal_task_weights_not_pooled_success(self):
        for _ in range(10): self.run_fixture(case='easy')
        self.run_fixture(case='hard',result='fail')
        stats = self.overview()['groups']['A']['domains']['overall']
        self.assertEqual(stats['rate'],.5)
        self.assertEqual(stats['n'],11)

    def test_missing_task_suppresses_rate_and_absent_arm_not_zero(self):
        self.run_fixture(case='one'); self.run_fixture(case='two')
        self.run_fixture(config='B',case='one')
        cohort = self.overview()
        self.assertIsNone(cohort['groups']['B']['domains']['overall']['rate'])
        self.assertEqual(cohort['groups']['C']['n'],0)
        self.assertIsNone(cohort['groups']['C']['domains']['overall']['rate'])
        self.assertEqual(cohort['by_task']['one']['B']['domains']['overall']['rate'],1)

    def test_domain_requires_all_checks_and_missing_is_unknown(self):
        root, report, review = self.run_fixture()
        report['checks']['geometry'].pop('boundaries')
        report['diagnostic_score']['strict_correct'] = review['strict_correct'] = False
        self.write(root/'runs/task-one/assessment/report.json',report)
        self.write(root/'runs/task-one/assessment/review.json',review)
        record = read_records(self.roots)[0][0]
        self.assertEqual(record['domains']['geometry'],'unknown')
        self.assertEqual(record['domains']['materials'],'pass')
        self.assertEqual(record['domains']['overall'],'unknown')

    def test_model_gate_failure_preserves_zero_and_unreached_domains(self):
        root, report, review = self.run_fixture()
        report.update(status='stopped',checks={})
        report['gates'] = {'model_builds':dict(passed=False,cause='model')}
        report['diagnostic_score'].update(status='model_gate_failure',score=0,strict_correct=False)
        review.update(score=0,strict_correct=False)
        self.write(root/'runs/task-one/assessment/report.json',report)
        self.write(root/'runs/task-one/assessment/review.json',review)
        r = read_records(self.roots)[0][0]
        self.assertEqual(r['score'],0)
        self.assertEqual(r['domains']['hard_gates'],'fail')
        self.assertEqual(r['domains']['overall'],'fail')
        self.assertEqual(r['domains']['geometry'],'unknown')

    def test_infrastructure_failure_is_unknown(self):
        root, report, review = self.run_fixture()
        report['gates']['openmc_runs'] = dict(passed=False,cause='infrastructure')
        report['diagnostic_score'].update(status='unscored',score=None,strict_correct=False)
        review.update(score=None,strict_correct=False)
        self.write(root/'runs/task-one/assessment/report.json',report)
        self.write(root/'runs/task-one/assessment/review.json',review)
        r = read_records(self.roots)[0][0]
        self.assertEqual(r['domains']['hard_gates'],'unknown')
        self.assertEqual(r['domains']['overall'],'unknown')

    def test_unknown_rubric_or_contradictory_review_cannot_pass(self):
        root, report, review = self.run_fixture()
        report['assignment']['rubric']['sha256'] = 'different'
        self.write(root/'runs/task-one/assessment/report.json',report)
        self.assertEqual(read_records(self.roots)[0][0]['domains']['overall'],'unknown')
        report['assignment']['rubric']['sha256'] = self.rubric
        review['score'] = 5
        self.write(root/'runs/task-one/assessment/report.json',report)
        self.write(root/'runs/task-one/assessment/review.json',review)
        self.assertEqual(read_records(self.roots)[0][0]['domains']['overall'],'unknown')

    def test_models_protocols_and_budgets_are_separate(self):
        self.run_fixture(); self.run_fixture(model='model-two'); self.run_fixture(protocol='protocol-two')
        root, _, _ = self.run_fixture()
        plan = json.loads((root/'plan.json').read_text()); plan['budgets']['model_requests'] = 16
        self.write(root/'plan.json',plan)
        self.assertEqual(len(campaign(self.roots)['cohorts']),4)

    def test_changed_task_identity_masks_combined_rates(self):
        self.run_fixture(); self.run_fixture(config='B',prompt='changed-public-prompt')
        cohort = self.overview()
        self.assertFalse(cohort['comparable'])
        self.assertEqual(cohort['conflicting_tasks'],['task-one'])
        self.assertIsNone(cohort['groups']['A']['domains']['overall']['rate'])

    def test_tool_budget_changes_within_one_condition_mask_rates(self):
        self.run_fixture(config='B')
        root, _, _ = self.run_fixture(config='B')
        plan = json.loads((root/'plan.json').read_text())
        plan['budgets']['boundary_calls'] = 4
        self.write(root/'plan.json',plan)
        cohort = self.overview()
        self.assertFalse(cohort['comparable'])
        self.assertEqual(cohort['conflicting_tool_budgets'],['B'])
        self.assertIsNone(cohort['groups']['B']['domains']['geometry']['rate'])

    def test_malformed_score_and_incomplete_tokens_are_not_aggregated(self):
        root, report, review = self.run_fixture()
        report['diagnostic_score']['score'] = review['score'] = '100'
        self.write(root/'runs/task-one/assessment/report.json',report)
        self.write(root/'runs/task-one/assessment/review.json',review)
        self.write(root/'summary.json',{'tasks':[dict(case='task-one',authoring={'effort':dict(token_usage={'total_tokens':200},token_usage_complete=False)})]})
        r = read_records(self.roots)[0][0]
        self.assertEqual(r['domains']['overall'],'unknown')
        self.assertIsNone(r['score'])
        self.assertIsNone(r['tokens'])

    def test_missing_corrupt_and_symlink_evidence_never_pass(self):
        root, _, _ = self.run_fixture()
        path=root/'runs/task-one/assessment/review.json'
        path.write_text('{')
        result=campaign(self.roots)
        self.assertTrue(result['warnings'])
        self.assertEqual(result['records'][0]['domains']['overall'],'unknown')
        path.unlink(); path.symlink_to(self.root/'secret.json')
        self.write(self.root/'secret.json',dict(secret='DO_NOT_READ'))
        result=campaign(self.roots)
        self.assertNotIn('DO_NOT_READ',json.dumps(result))
        self.assertTrue(result['warnings'])

    def test_manifest_relative_paths_and_duplicates(self):
        manifest=self.root/'campaign.json'
        self.write(manifest,{'runs':['one','two']})
        self.assertEqual(selected_roots([],manifest),[self.root/'one',self.root/'two'])
        self.write(manifest,{'runs':['one','./one']})
        with self.assertRaises(ValueError):selected_roots([],manifest)

    def test_full_synthetic_150_assignment_campaign_without_execution(self):
        with patch('subprocess.Popen',side_effect=AssertionError('No execution')):
            for model in ['model-one','model-two']:
                for config in ['A','B','C']:
                    for case in ['one','two','three','four','five']:
                        for repeat in range(5):
                            self.run_fixture(config=config,case=case,model=model,result='fail' if config=='C' and repeat==0 else 'pass')
            value=campaign(self.roots)
        self.assertEqual(value['assignments'],150)
        self.assertEqual(len(value['cohorts']),2)
        for c in value['cohorts']:
            self.assertTrue(c['comparable'])
            self.assertEqual(c['groups']['A']['domains']['overall']['rate'],1)
            self.assertEqual(c['groups']['C']['domains']['overall']['rate'],.8)
            self.assertEqual(c['groups']['C']['n'],25)
            self.assertEqual(c['groups']['C']['domains']['geometry']['rate'],1)
            self.assertEqual(c['groups']['C']['checks']['materials']['density']['rate'],.8)
            self.assertEqual(c['groups']['C']['efforts']['tokens'],dict(mean=200,n=25))


if __name__ == '__main__':
    unittest.main()
