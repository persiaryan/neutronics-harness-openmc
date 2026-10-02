"""Evolution checks use synthetic retained files; no model or native execution."""
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from dashboard.campaign import campaign
from dashboard.contracts import configuration_view, normalize_evaluation
from dashboard.projection import snapshot
from observation_contracts import fingerprint, describe_configuration
from observability import tool_observation
from tests import test_dashboard_campaign as fixtures


def seal(value):
    value['sha256'] = fingerprint({k:v for k,v in value.items() if k != 'sha256'})
    return value


def future_definition():
    item = dict(label={'en':'Temperature balance','fr':'Bilan de température'},
                unit='K',rule={'operator':'absolute_error_lte','threshold':2})
    return seal(dict(format='evaluation-definition-v1', protocol='test-evaluator-v2',
        report_format='evaluation-report-v1',rubric_sha256='synthetic-rubric-v2',
        score=dict(maximum=10,applicable_points=10),
        checks={'thermal_balance':{'temperature_balance':item}},
        gates={'runs':dict(label={'en':'Solver ran'},unit=None,rule=None)},
        domain_labels={'thermal_balance':{'en':'Thermal balance','fr':'Bilan thermique'}},
        weights={'thermal_balance':10},rules={'equivalence_margin_pcm':75,'interval_multiplier':2},
        aggregation='all-required-checks-v1'))


def future_report():
    return dict(format='evaluation-report-v1',observation_definition=future_definition(),
        status='assessed',score=dict(value=10,strict_correct=True,status='scored'),
        criteria=[dict(domain='hard_gates',id='runs',verdict='pass'),
                  dict(domain='thermal_balance',id='temperature_balance',verdict='pass',
                       expected=300,observed=301,unit='K',rule={'absolute_error_lte':2},evidence='receipt.json')])


def review(report):
    return dict(evidence_status='coherent',score=report['score']['value'],
                strict_correct=report['score']['strict_correct'],report_sha256=fingerprint(report))


def custom_configuration():
    tool = dict(id='probe-tool',version='1',label={'en':'Thermal probe','fr':'Sonde thermique'},
                directory='probe-tool',budget_key='probe_calls')
    return seal(dict(format='observation-configuration-v1',configuration=dict(id='D',version='1',
        assistance='guided_probe',condition='generic_probe_v1',label={'en':'D'},
        description={'en':'Guided construction with thermal probe','fr':'Construction avec sonde thermique'},
        tools=['probe-tool']),tools=[tool]))


class ContractTest(unittest.TestCase):
    setUp = fixtures.CampaignTest.setUp
    tearDown = fixtures.CampaignTest.tearDown
    write = fixtures.CampaignTest.write
    run_fixture = fixtures.CampaignTest.run_fixture

    def interrupted_fixture(self):
        root,report,_=self.run_fixture(case='moderated_cylinder')
        report.pop('assignment')
        report.update(status='incomplete',phases={},error_type='ValueError',
            error='Package root must be a real directory',
            stop=dict(stage='admission',cause='evaluator',detail='Missing evaluator evidence'),
            gates={},checks={},diagnostic_score=dict(status='unscored',score=None,strict_correct=False))
        folder=root/'runs/moderated_cylinder/assessment'
        self.write(folder/'report.json',report)
        self.write(folder/'review.json',dict(evidence_status='insufficient',score=None))
        return root,report

    def test_historical_admission_failure_remains_visible_without_grading(self):
        root,report=self.interrupted_fixture()
        state=snapshot(root)['tasks'][0]
        value=state['evaluation']
        self.assertEqual(value['operational']['state'],'interrupted')
        self.assertEqual(value['operational']['reason'],'reference_unavailable')
        self.assertEqual(value['operational']['stage'],'admission')
        self.assertEqual(value['status'],'unsupported')
        self.assertIn('no recorded rubric identity',value['reason'])
        self.assertIsNone(value['definition'])
        self.assertIsNone(value['report'])
        self.assertFalse(value['trusted'])
        self.assertEqual(state['report'],report)
        self.assertEqual(json.loads((root/'runs/moderated_cylinder/assessment/report.json').read_text()),report)
        record=campaign([root])['records'][0]
        self.assertEqual(record['domains']['overall'],'unknown')
        self.assertIsNone(record['score'])

    def test_execution_state_does_not_guess_unknown_schemas_or_failure_causes(self):
        self.assertEqual(normalize_evaluation(None,None)['operational']['state'],'pending')
        report=future_report()
        self.assertEqual(normalize_evaluation(report,review(report))['operational']['state'],'completed')
        report.update(format='unknown-v9',status='stopped',stop={'stage':'admission'},error='Package root must be a real directory')
        self.assertEqual(normalize_evaluation(report,{})['operational'],{'state':'unavailable'})
        report.update(format='private-candidate-diagnostic-v5',status='incomplete',stop={'stage':'transport','cause':'infrastructure'})
        value=normalize_evaluation(report,{})['operational']
        self.assertEqual(value['state'],'interrupted')
        self.assertNotIn('reason',value)

    def future_fixture(self):
        root, old, _ = self.run_fixture()
        plan=json.loads((root/'plan.json').read_text())
        descriptor=custom_configuration()
        plan.update(assistance='guided_probe',condition='generic_probe_v1',observation_configuration=descriptor)
        self.write(root/'plan.json',plan)
        report=future_report()
        report['assignment']={**old['assignment'],'rubric':{'sha256':'synthetic-rubric-v2'},
            'assessment_route':{'evaluator_protocol':'test-evaluator-v2'}}
        self.write(root/'runs/task-one/assessment/report.json',report)
        self.write(root/'runs/task-one/assessment/review.json',review(report))
        return root,report

    def test_old_report_independent_of_live_rubric_and_catalog(self):
        root, report, retained_review=self.run_fixture()
        with patch('observation_contracts.catalog',side_effect=AssertionError('Live catalog consulted')):
            self.assertEqual(configuration_view(json.loads((root/'plan.json').read_text()))['definition']['configuration']['id'],'A')
        with patch('evaluation.benchmark_suite.scoring.RUBRIC',{'changed':True}):
            value=normalize_evaluation(report,retained_review)
            self.assertTrue(value['trusted'])
            self.assertEqual(value['definition']['rules']['equivalence_margin_pcm'],150)

    def test_two_evaluators_separate_scales_and_dynamic_configuration(self):
        self.run_fixture()
        root,report=self.future_fixture()
        with patch('subprocess.run',side_effect=AssertionError('Dashboard must not execute')):
            value=campaign(self.roots)
        self.assertEqual(len(value['cohorts']),2)
        cohort=next(c for c in value['cohorts'] if c['definition']['score']['maximum']==10)
        self.assertIn('D',cohort['groups'])
        self.assertEqual(cohort['groups']['D']['domains']['thermal_balance']['rate'],1)
        self.assertEqual(cohort['groups']['D']['efforts']['score']['mean'],10)
        self.assertEqual(snapshot(root)['tasks'][0]['report'],report)

    def test_new_criterion_missing_is_unknown(self):
        root,report=self.future_fixture()
        report['criteria'].pop()
        report['score']['strict_correct']=False
        self.write(root/'runs/task-one/assessment/report.json',report)
        self.write(root/'runs/task-one/assessment/review.json',review(report))
        record=campaign([root])['records'][0]
        self.assertEqual(record['domains']['thermal_balance'],'unknown')
        self.assertEqual(record['domains']['overall'],'unknown')

    def test_review_must_bind_exact_report(self):
        report=future_report(); retained_review=review(report)
        report['criteria'][1]['observed']=302
        value=normalize_evaluation(report,retained_review)
        self.assertEqual(value['status'],'supported')
        self.assertFalse(value['trusted'])

    def test_invalid_and_unsupported_are_distinct(self):
        report=future_report()
        for mutation,status in [(dict(format='future-unknown-v9'),'unsupported'),
                                (dict(criteria='bad'),'invalid'),
                                (dict(observation_definition=[]),'invalid')]:
            value=normalize_evaluation({**report,**mutation},{})
            self.assertEqual(value['status'],status)
            self.assertFalse(value['trusted'])
        self.assertEqual(configuration_view({'observation_configuration':[]})['status'],'invalid')

    def test_bad_scale_rule_and_inventory_rejected(self):
        for change in ['score','rule','definition_hash','undeclared','duplicate']:
            report=future_report()
            if change=='score': report['score']['value']=11
            if change=='rule': report['comparison']={'margin_pcm':150}
            if change=='definition_hash': report['observation_definition']['score']['maximum']=20
            if change=='undeclared': report['criteria'][1]['id']='other'
            if change=='duplicate': report['criteria'].append(report['criteria'][1])
            self.assertEqual(normalize_evaluation(report,review(report))['status'],'invalid',change)

    def test_false_strict_success_cannot_be_trusted(self):
        report=future_report();report['criteria'].pop()
        self.assertFalse(normalize_evaluation(report,review(report))['trusted'])

    def test_same_configuration_id_different_versions_are_separate(self):
        first,_=self.future_fixture();second,_=self.future_fixture()
        plan=json.loads((second/'plan.json').read_text())
        plan['observation_configuration']['configuration']['version']='2'
        seal(plan['observation_configuration']);self.write(second/'plan.json',plan)
        groups=campaign([first,second])['cohorts'][0]['groups']
        self.assertEqual(len([k for k in groups if k.startswith('D@')]),2)

    def test_new_tool_budget_conflict_blocks_comparison(self):
        first,_=self.future_fixture();second,_=self.future_fixture()
        for root,limit in [(first,1),(second,3)]:
            plan=json.loads((root/'plan.json').read_text())
            plan['budgets']['probe_calls']=limit
            self.write(root/'plan.json',plan)
        cohort=campaign([first,second])['cohorts'][0]
        self.assertFalse(cohort['comparable'])
        self.assertEqual(cohort['conflicting_tool_budgets'],['D'])
        self.assertIsNone(cohort['groups']['D']['domains']['overall']['rate'])

    def test_prepare_records_configuration_and_execute_rejects_drift(self):
        from experiments import run
        folder=self.root/'prepared'
        plan=run.prepare(folder,assistance='guided_construction',cases=['reflective_pin_cell'])
        self.assertEqual(plan['observation_configuration']['configuration']['id'],'A')
        plan['condition']='different_condition'
        self.write(folder/'plan.json',plan)
        with self.assertRaisesRegex(ValueError,'Plan differs'):
            run.execute(folder)

    def test_evaluator_produces_definition_and_review_binding_on_admission_failure(self):
        from evaluation.candidates import run, verify
        folder=self.root/'assessment'
        with patch.object(run,'target',side_effect=FileNotFoundError('synthetic missing reference')), \
                patch.object(run,'clean_resources'), \
                patch('subprocess.run',side_effect=AssertionError('No native run')):
            report=run.evaluate('reflective_pin_cell',folder,index=self.root/'unused-index',candidate=self.root/'unused-candidate')
            retained_review=verify.review_assessment(folder,self.root/'unused-index')
        self.assertEqual(report['observation_definition']['score']['maximum'],100)
        self.assertEqual(retained_review['report_sha256'],fingerprint(report))
        self.assertIsNone(retained_review['score'])
        self.assertEqual(normalize_evaluation(report,retained_review)['status'],'supported')
        report['observation_definition']['rules']['equivalence_margin_pcm']=999
        seal(report['observation_definition'])
        self.write(folder/'report.json',report)
        changed=verify.review_assessment(folder,self.root/'unused-index')
        self.assertEqual(changed['evidence_status'],'contradictory')
        self.assertIn('Recorded evaluation definition differs',changed['reason'])

    def test_generic_tool_receipt_and_hash_validation(self):
        root,_=self.future_fixture()
        folder=root/'runs/task-one/builder/probe-tool/call-01'
        self.write(folder/'request.json',{'x':1});self.write(folder/'feedback.json',{'temperature':301})
        tool_observation(folder,'probe-tool','1',elapsed_seconds=0.1)
        state=snapshot(root);tool=state['tasks'][0]['builder']['tools'][0]
        self.assertEqual(tool['tool'],'probe-tool')
        self.assertEqual(tool['envelope_status'],'supported')
        self.assertIsNone(tool['projection'])
        self.assertEqual(tool['envelope']['feedback_delivery'],'not_established_by_completion')
        self.write(folder/'feedback.json',{'temperature':999})
        self.assertEqual(snapshot(root)['tasks'][0]['builder']['tools'][0]['envelope_status'],'invalid')

    def test_tool_paths_cannot_escape_and_plan_conflicts_visible(self):
        descriptor=custom_configuration();descriptor['tools'][0]['directory']='../escape';seal(descriptor)
        self.assertEqual(configuration_view({'observation_configuration':descriptor})['status'],'invalid')
        good=custom_configuration()
        self.assertEqual(configuration_view(dict(assistance='wrong',condition='generic_probe_v1',observation_configuration=good))['status'],'invalid')

    def test_producer_description_is_frozen(self):
        descriptor=describe_configuration(dict(assistance='guided_construction',condition='generic_coding_guided_construction_v1'))
        plan=dict(assistance='guided_construction',condition='generic_coding_guided_construction_v1',observation_configuration=descriptor)
        with patch('observation_contracts.catalog',side_effect=AssertionError('Snapshot must suffice')):
            self.assertEqual(describe_configuration(plan),descriptor)

    def test_current_catalog_matches_runtime_permissions_and_tool_versions(self):
        from builder import route, boundary_tool, smoke_tool
        from observation_contracts import catalog
        current=catalog()
        for config in current['configurations']:
            assistance=config['assistance']
            self.assertEqual(config['condition'],route.CONDITIONS[assistance])
            expected=['coding']
            if assistance in route.BOUNDARY_CONDITIONS: expected.append('boundary-tool')
            if assistance in route.SMOKE_CONDITIONS: expected.append('smoke-tool')
            self.assertEqual(config['tools'],expected)
        versions={t['id']:t['version'] for t in current['tools']}
        self.assertEqual(versions['boundary-tool'],boundary_tool.PROFILE['version'])
        self.assertEqual(versions['smoke-tool'],smoke_tool.identity()['version'])

    def test_tool_observation_failure_nonfatal(self):
        with patch.object(Path,'write_text',side_effect=OSError('disk unavailable')):
            with self.assertWarns(RuntimeWarning): tool_observation(self.root,'probe-tool','1')


if __name__ == '__main__':
    # Generate disposable frontend fixtures without provider or solver calls.
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('--fixtures',type=Path,required=True)
    output=parser.parse_args().fixtures
    output.mkdir(parents=True,exist_ok=True)
    test=ContractTest();test.setUp()
    try:
        test.run_fixture()
        root,_=test.future_fixture()
        folder=root/'runs/task-one/builder/probe-tool/call-01'
        test.write(folder/'request.json',{'x':1})
        test.write(folder/'feedback.json',{'temperature':301})
        tool_observation(folder,'probe-tool','1')
        (output/'future-state.json').write_text(json.dumps(snapshot(root)))
        (output/'future-campaign.json').write_text(json.dumps(campaign(test.roots)))
        interrupted,_=test.interrupted_fixture()
        (output/'interrupted-state.json').write_text(json.dumps(snapshot(interrupted)))
    finally:
        test.tearDown()
