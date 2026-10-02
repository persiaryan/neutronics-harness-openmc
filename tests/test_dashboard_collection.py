"""Campaign inventories and identities, using synthetic evidence and no model calls."""
import json
import shutil
import unittest
from pathlib import Path

from dashboard.collection import selection, read_studies
from dashboard.campaign import campaign
from tests import test_dashboard_campaign as fixtures
from experiments.dashboard_campaign import sha


class CollectionTest(unittest.TestCase):
    setUp = fixtures.CampaignTest.setUp
    tearDown = fixtures.CampaignTest.tearDown
    write = fixtures.CampaignTest.write
    run_fixture = fixtures.CampaignTest.run_fixture

    def declare(self, roots=None, cid='study-one', scope='private_frozen_suite'):
        rows=[]
        for root in roots or self.roots:
            plan=json.loads((root/'plan.json').read_text())
            case=plan['cases'][0]
            eid='execution-'+root.name
            plan['execution_ids']={case:eid}
            self.write(root/'plan.json',plan)
            rows.append(dict(id=root.name,run_id=eid,case=case,model=plan['model'],
                arm=next(k for k,v in fixtures.CONDITIONS.items() if v[0]==plan['assistance']),
                repeat=1,path=str(root.relative_to(self.root)),plan_sha256=sha(root/'plan.json')))
        manifest=dict(format='dashboard-live-campaign-v2',campaign_id=cid,name=cid,
            sessions=len(rows),reference=scope,rows=rows)
        path=self.root/(cid+'.json');self.write(path,manifest)
        return path,manifest

    def pending(self, root, case='task-one'):
        shutil.rmtree(root/'runs'/case)
        (root/'summary.json').unlink()

    def test_pending_public_runs_have_declared_but_not_observed_scope(self):
        completed,_,_=self.run_fixture()
        folder=completed/'runs/task-one'
        (folder/'assessment').rename(folder/'assessment-public-demo')
        pending,_,_=self.run_fixture(config='B');self.pending(pending)
        manifest,_=self.declare(scope='public_demo_only')
        self.write(self.root/'progress.json',dict(state='paused_on_incident',error='disk reserve'))
        roots,studies=selection(manifest=manifest);result=campaign(roots,studies)
        self.assertEqual(len(result['cohorts']),1)
        self.assertEqual(result['campaigns'][0]['counts'],{'completed':1,'not_started':1})
        self.assertEqual(result['campaigns'][0]['error'],'disk reserve')
        a,b=result['records']
        self.assertEqual(a['observed_reference_scope'],'public_demo')
        self.assertIsNone(b['observed_reference_scope'])
        self.assertEqual(b['declared_reference_scope'],'public_demo')
        self.assertIsNone(b['score']);self.assertFalse(b['trusted'])
        self.assertIsNone(result['cohorts'][0]['groups']['B']['domains']['overall']['rate'])

    def test_two_identical_protocol_campaigns_remain_separate(self):
        a,_,_=self.run_fixture();b,_,_=self.run_fixture()
        one,_=self.declare([a]);two,_=self.declare([b],cid='study-two')
        selection_path=self.root/'selection.json'
        self.write(selection_path,{'campaigns':[one.name,two.name]})
        roots,studies=selection(manifest=selection_path)
        result=campaign(roots,studies)
        self.assertEqual(len(result['campaigns']),2)
        self.assertEqual(len(result['cohorts']),2)

    def test_missing_run_is_retained_in_expected_inventory(self):
        root,_,_=self.run_fixture();path,_=self.declare()
        shutil.rmtree(root)
        roots,studies=selection(manifest=path);result=campaign(roots,studies)
        self.assertEqual(result['assignments'],1)
        self.assertEqual(result['campaigns'][0]['missing'],1)
        self.assertEqual(result['records'][0]['lifecycle'],'missing')
        self.assertIsNone(result['records'][0]['score'])

    def test_changed_plan_blocks_comparison_but_preserves_report(self):
        root,_,_=self.run_fixture();path,_=self.declare()
        plan=json.loads((root/'plan.json').read_text());plan['budgets']['model_requests']=16
        self.write(root/'plan.json',plan)
        result=campaign(*selection(manifest=path))
        self.assertIn('plan_sha256',result['records'][0]['membership_conflicts'])
        self.assertEqual(result['records'][0]['score'],100)
        self.assertFalse(result['cohorts'][0]['comparable'])
        self.assertIsNone(result['cohorts'][0]['groups']['A']['domains']['overall']['rate'])

    def test_observed_reference_disagreement_blocks_rates(self):
        self.run_fixture();path,_=self.declare(scope='public_demo_only')
        result=campaign(*selection(manifest=path))
        self.assertEqual(result['records'][0]['observed_reference_scope'],'private')
        self.assertIn('reference_scope',result['records'][0]['membership_conflicts'])
        self.assertEqual(result['campaigns'][0]['conflicts'],1)
        self.assertIsNone(result['cohorts'][0]['groups']['A']['domains']['overall']['rate'])

    def test_different_observed_protocols_in_campaign_block_rates(self):
        self.run_fixture();self.run_fixture(config='B',protocol='other-protocol')
        path,_=self.declare();result=campaign(*selection(manifest=path))
        self.assertEqual(len(result['cohorts']),1)
        self.assertIn('protocol',result['cohorts'][0]['context_conflicts'])
        self.assertIsNone(result['cohorts'][0]['groups']['A']['domains']['overall']['rate'])

    def test_ids_survive_selection_reordering(self):
        self.run_fixture();self.run_fixture(config='B');path,_=self.declare()
        roots,studies=selection(manifest=path)
        first=campaign(roots,studies)['records'];second=campaign(list(reversed(roots)),studies)['records']
        self.assertEqual({r['run_name']:r['execution_id'] for r in first},
                         {r['run_name']:r['execution_id'] for r in second})

    def test_duplicate_ids_and_paths_are_rejected(self):
        self.run_fixture();self.run_fixture(config='B');path,manifest=self.declare()
        original=manifest['rows'][1]['run_id']
        manifest['rows'][1]['run_id']=manifest['rows'][0]['run_id'];self.write(path,manifest)
        with self.assertRaisesRegex(ValueError,'Duplicate'):read_studies([path])
        manifest['rows'][1]['run_id']=original
        manifest['rows'][1]['path']=manifest['rows'][0]['path'];self.write(path,manifest)
        with self.assertRaisesRegex(ValueError,'multiple campaigns'):read_studies([path])

    def test_launched_manifest_is_immutable(self):
        self.run_fixture();path,manifest=self.declare()
        self.write(self.root/'launch.json',{'manifest_sha256':sha(path)})
        manifest['reference']='public_demo_only';self.write(path,manifest)
        with self.assertRaisesRegex(ValueError,'manifest changed'):read_studies([path])

    def test_symlinks_and_outside_paths_are_rejected(self):
        root,_,_=self.run_fixture();path,manifest=self.declare()
        manifest['rows'][0]['path']='../outside';self.write(path,manifest)
        with self.assertRaises(ValueError):read_studies([path])
        (self.root/'linked').symlink_to(root,target_is_directory=True)
        manifest['rows'][0]['path']='linked';self.write(path,manifest)
        with self.assertRaises(ValueError):read_studies([path])

    def test_duplicate_copied_explicit_execution_cannot_count_twice(self):
        root,_,_=self.run_fixture();self.declare()
        copied=self.root/'copy';shutil.copytree(root,copied)
        with self.assertRaisesRegex(ValueError,'Duplicate execution'):campaign([root,copied])

    def test_legacy_multitask_batch_exposes_separate_execution_ids(self):
        root,_,_=self.run_fixture();second,_,_=self.run_fixture(case='task-two')
        shutil.copytree(second/'runs/task-two',root/'runs/task-two')
        plan=json.loads((root/'plan.json').read_text());plan['cases'].append('task-two')
        plan['prompts']['task-two']={'prompt_sha256':'second-prompt'};self.write(root/'plan.json',plan)
        records=campaign([root])['records']
        self.assertEqual(len(records),2)
        self.assertEqual({r['batch_kind'] for r in records},{'legacy_batch'})
        self.assertEqual(len({r['execution_id'] for r in records}),2)
        self.assertEqual({r['run'] for r in records},{0})

    def test_legacy_v1_ids_are_stable_without_rewriting_manifest(self):
        self.run_fixture();path,manifest=self.declare()
        manifest['format']='dashboard-live-campaign-v1';manifest.pop('campaign_id')
        for row in manifest['rows']:row.pop('run_id')
        self.write(path,manifest);before=path.read_bytes()
        first=read_studies([path]);second=read_studies([path])
        self.assertEqual(first,second);self.assertEqual(before,path.read_bytes())

    def test_no_declared_campaign_is_not_presented_as_complete(self):
        self.run_fixture();result=campaign(self.roots)
        self.assertEqual(result['campaigns'],[])
        self.assertIsNone(result['records'][0]['campaign_id'])

    def test_malformed_rows_are_rejected_before_projection(self):
        self.run_fixture();path,manifest=self.declare()
        for field,value in [('repeat',True),('repeat',0),('repeat','<img src=x>'),
                            ('case','../secret'),('path',None),('run_id',None),('plan_sha256','bad')]:
            with self.subTest(field=field,value=value):
                changed=json.loads(json.dumps(manifest));changed['rows'][0][field]=value
                self.write(path,changed)
                with self.assertRaises(ValueError):read_studies([path])

    def test_unreadable_launch_receipt_cannot_bypass_manifest_binding(self):
        self.run_fixture();path,_=self.declare()
        (self.root/'launch.json').write_text('{')
        with self.assertRaisesRegex(ValueError,'Unreadable'):read_studies([path])

    def test_corrupt_plan_is_missing_not_an_unstarted_valid_run(self):
        root,_,_=self.run_fixture();path,_=self.declare()
        (root/'plan.json').write_text('{')
        result=campaign(*selection(manifest=path))
        self.assertEqual(result['campaigns'][0]['missing'],1)
        self.assertEqual(result['records'][0]['lifecycle'],'missing')

    def test_launcher_finished_without_report_cannot_count_as_assessed(self):
        root,_,_=self.run_fixture();path,_=self.declare()
        (root/'runs/task-one/assessment/report.json').unlink()
        self.write(root/'dashboard-run.json',{'state':'finished'})
        result=campaign(*selection(manifest=path))
        self.assertEqual(result['records'][0]['lifecycle'],'interrupted')
        self.assertIsNone(result['records'][0]['score'])
        self.assertNotIn('completed',result['campaigns'][0]['counts'])


if __name__=='__main__':unittest.main()
