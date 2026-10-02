"""Imported identities and new campaign preparation; no provider/native calls."""
import json
from pathlib import Path
import tempfile
import unittest
import contextlib
import io
from unittest.mock import patch

from dashboard.projection import Evidence, snapshot
from dashboard.study_context import read_context
from dashboard.campaign import campaign, read_records
from experiments.dashboard_campaign import prepare_campaign, run_campaign, sha
from tests.test_dashboard_contracts import future_definition
from tests import test_dashboard_campaign as fixtures


class StudyTest(unittest.TestCase):
    def test_import_binding_rejects_changed_plan(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            (root/'plan.json').write_text('{}')
            definition=future_definition()
            value=dict(format='dashboard-study-context-v1',definition=definition,context={'definition':definition['sha256']},
                       bindings={'plan.json':sha(root/'plan.json')})
            (root/'dashboard-study-context.json').write_text(json.dumps(value))
            self.assertIsNotNone(read_context(Evidence(root)))
            (root/'plan.json').write_text('{"model":"changed"}')
            evidence=Evidence(root)
            self.assertIsNone(read_context(evidence))
            self.assertTrue(evidence.warnings)

    def test_pilot_prepares_six_fresh_slots_and_fixed_budgets(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);index=root/'index';index.write_text('synthetic')
            setup=root/'setups.json';setup.write_text(json.dumps({'gpt-5.6-luna':{},'gpt-5.6-sol':{}}))
            def prepared_plan(folder, **kwargs):
                folder.mkdir(parents=True)
                (folder/'plan.json').write_text(json.dumps({'execution_ids':{kwargs['cases'][0]:folder.name}}))
            with patch('experiments.dashboard_campaign.load',return_value={}), patch('experiments.dashboard_campaign.prepare',side_effect=prepared_plan) as prepared:
                result=prepare_campaign(root/'pilot',pilot=True,data_index=index,setup_file=setup,runtime_path=root/'runtime')
            self.assertEqual(result['sessions'],6)
            self.assertEqual(result['maximum_model_requests'],96)
            self.assertEqual(result['automatic_retries'],0)
            self.assertEqual({(r['model'],r['arm']) for r in result['rows']},
                             {(m,a) for m in ['gpt-5.6-luna','gpt-5.6-sol'] for a in ['A','B','C']})
            self.assertEqual(prepared.call_count,6)
            for call in prepared.call_args_list:
                self.assertEqual(call.kwargs['request_budget'],'authoring-requests-16-v1')

    def test_consumed_campaign_cannot_restart(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            (root/'manifest.json').write_text('{}');(root/'launch.json').write_text('{}')
            with self.assertRaisesRegex(ValueError,'already consumed'):
                run_campaign(root)

    def test_changed_source_prevents_first_dispatch(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            (root/'manifest.json').write_text(json.dumps({'source_sha256':{'old':'hash'}}))
            with patch('experiments.dashboard_campaign.execute',side_effect=AssertionError('No dispatch')):
                with self.assertRaisesRegex(ValueError,'Frozen implementation'):
                    run_campaign(root)
            self.assertFalse((root/'launch.json').exists())

    def test_full_preparation_is_150_balanced_slots_without_execution(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);index=root/'index';index.write_text('synthetic')
            setups=root/'setups.json';setups.write_text(json.dumps({'gpt-5.6-luna':{},'gpt-5.6-sol':{}}))
            def prepared_plan(folder, **kwargs):
                folder.mkdir(parents=True)
                (folder/'plan.json').write_text(json.dumps({'execution_ids':{kwargs['cases'][0]:folder.name}}))
            with patch('experiments.dashboard_campaign.prepare',side_effect=prepared_plan), patch('experiments.dashboard_campaign.execute',side_effect=AssertionError('No dispatch')):
                manifest=prepare_campaign(root/'study',pilot=False,data_index=index,setup_file=setups)
            self.assertEqual(manifest['sessions'],150)
            self.assertEqual(manifest['maximum_model_requests'],2400)
            cells={}
            for row in manifest['rows']:
                key=(row['model'],row['arm'],row['case']);cells.setdefault(key,set()).add(row['repeat'])
                self.assertFalse(Path(row['path']).is_absolute())
                self.assertEqual(row['plan_sha256'],sha(root/'study'/row['path']/'plan.json'))
            self.assertEqual(len(cells),30)
            self.assertTrue(all(repeats=={1,2,3,4,5} for repeats in cells.values()))


class RunnerTest(unittest.TestCase):
    def simulate(self, temporary, score, free_bytes=100):
        root=Path(temporary);index=root/'index';index.write_text('data')
        rows=[]
        for i in range(2):
            folder=root/f'run-{i}';(folder/'runs/task').mkdir(parents=True)
            (folder/'runs/task/candidate.py').write_bytes(b'candidate')
            rows.append(dict(id=str(i),path=folder.name,case='task',model='model',state='pending'))
        manifest=dict(source_sha256={'file':'hash'},data_index=str(index),data_index_sha256=sha(index),
            minimum_free_bytes=10,rows=rows,kind='integration_pilot',runtime={},reference='public_demo_only',request_setups={'model':{}})
        (root/'manifest.json').write_text(json.dumps(manifest))
        def evaluate(case, output, **kwargs):
            output.mkdir();return {'status':'assessed'}
        with contextlib.ExitStack() as stack:
            stack.enter_context(patch('experiments.dashboard_campaign.sources',return_value={'file':'hash'}))
            stack.enter_context(patch('experiments.dashboard_campaign.shutil.disk_usage',return_value=type('Usage',(),{'free':free_bytes})()))
            execute=stack.enter_context(patch('experiments.dashboard_campaign.execute',side_effect=lambda *a,**k:{'tasks':[{'builder_status':'completed'}]}))
            stack.enter_context(patch('experiments.dashboard_campaign.submission',return_value=(b'candidate',{})))
            stack.enter_context(patch('experiments.dashboard_campaign.evaluate',side_effect=evaluate))
            stack.enter_context(patch('experiments.dashboard_campaign.review_assessment',return_value={'evidence_status':'coherent' if score is not None else 'insufficient','score':score}))
            stack.enter_context(patch('experiments.dashboard_campaign.assessment_summary',return_value={'overall_success':False}))
            stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
            error=None
            try:run_campaign(root)
            except RuntimeError as exc:error=str(exc)
        return json.loads((root/'progress.json').read_text()),execute.call_count,error

    def test_scientific_zero_is_retained_and_next_slot_runs(self):
        with tempfile.TemporaryDirectory() as temporary:
            progress,calls,error=self.simulate(temporary,0)
            self.assertIsNone(error);self.assertEqual(calls,2)
            self.assertEqual(progress['state'],'complete')
            self.assertEqual([r['score'] for r in progress['rows']],[0,0])

    def test_unscored_incident_stops_without_retry(self):
        with tempfile.TemporaryDirectory() as temporary:
            progress,calls,error=self.simulate(temporary,None)
            self.assertEqual(calls,1);self.assertIn('evaluation incident',error)
            self.assertEqual(progress['state'],'paused_on_incident')
            self.assertEqual([r['state'] for r in progress['rows']],['incident','pending'])

    def test_disk_reserve_prevents_any_dispatch(self):
        with tempfile.TemporaryDirectory() as temporary:
            progress,calls,error=self.simulate(temporary,100,free_bytes=1)
            self.assertEqual(calls,0);self.assertIn('Free disk',error)
            self.assertEqual([r['state'] for r in progress['rows']],['pending','pending'])


class HistoricalIncidentTest(unittest.TestCase):
    setUp = fixtures.CampaignTest.setUp
    tearDown = fixtures.CampaignTest.tearDown
    write = fixtures.CampaignTest.write
    run_fixture = fixtures.CampaignTest.run_fixture

    def incident_fixture(self):
        self.run_fixture()
        template = read_records(self.roots)[0][0]
        root, _, _ = self.run_fixture()
        bindings = {'plan.json': sha(root/'plan.json')}
        for name in ('report.json', 'review.json'):
            path = 'runs/task-one/assessment/'+name
            (root/path).unlink()
            bindings[path] = None
        value = dict(format='dashboard-study-context-v1',
                     definition=template['definition'], context=template['context'],
                     task_signature=template['task_signature'], bindings=bindings,
                     terminal_category='provider_or_stream_incident')
        self.write(root/'dashboard-study-context.json', value)
        return root, value

    def test_imported_incident_remains_unknown_in_comparison(self):
        root, _ = self.incident_fixture()
        result = campaign(self.roots)
        self.assertEqual(len(result['cohorts']), 1)
        stats = result['cohorts'][0]['groups']['A']['domains']['overall']
        self.assertEqual((stats['n'], stats['passed'], stats['unknown']), (2, 1, 1))
        self.assertEqual((stats['rate'], stats['possible_rate']), (.5, 1))
        view = snapshot(root)['tasks'][0]['evaluation']
        self.assertFalse(view['trusted'])
        self.assertEqual(view['operational']['state'], 'interrupted')

    def test_conflicting_declared_context_cannot_merge_models(self):
        root, value = self.incident_fixture()
        value['context']['model'] = 'another-model'
        self.write(root/'dashboard-study-context.json', value)
        records, warnings = read_records(self.roots)
        self.assertEqual(records[1]['context']['model'], 'model-one')
        self.assertFalse(records[1]['task_identity_known'])
        self.assertIsNone(campaign(self.roots)['cohorts'][0]['groups']['A']['domains']['overall']['rate'])
        self.assertTrue(any('conflicts' in w['reason'] for w in warnings))
