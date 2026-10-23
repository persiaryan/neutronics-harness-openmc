"""Portable no-replay and evidence-preservation controls for resume 051."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import confirmation_resume_051 as resume
from builder.context import write_json


class Resume051Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name).resolve()
        self.previous=self.root/'previous';self.previous.mkdir()
        self.output=self.root/'next';self.output.mkdir()
        self.ancestor=self.root/'ancestor';self.ancestor.mkdir()
        write_json(self.ancestor/'manifest.json',{})
        rows=[dict(id=f'{i:03d}',model='model',arm='A',case='case',repeat=1,
            path=f'runs/{i:03d}',state='pending',plan_sha256='plan') for i in range(1,241)]
        rows[49].update(case='wrapped_eight_pin_channel',model='gpt-5.6-sol')
        self.m=dict(rows=deepcopy(rows),data_index=dict(path='index'),resumption_040=dict(
            previous_manifest=resume.base.binding(self.ancestor/'manifest.json')))
        for row in rows[:50]:
            if row['id'] in ('030','039','050'):
                row.update(state='incident',reason='Builder incomplete; slot consumed' if row['id']=='030'
                           else 'Unscored evaluation incident; pause before next slot')
            else:
                success=row['id'] not in ('012','025','034','038')
                row.update(state='finished',score=100. if success else 0.,strict_correct=success)
        self.ancestor_rows=deepcopy(rows)
        for row in rows[39:49]:
            record=dict(decision='unchanged_after_reconstruction',
                        verdict=dict(score=row['score'],strict_correct=row['strict_correct']))
            path=self.previous/row['path']/'runs'/row['case']/'assessment/revised-verdict.json'
            path.parent.mkdir(parents=True);write_json(path,record)
            row.update(decision=record['decision'],verdict_path=str(path))
        self.progress=dict(state='stopped',reason='Unscored evaluation incident; pause before next slot',rows=rows)
        write_json(self.previous/'manifest.json',self.m);write_json(self.previous/'progress.json',self.progress)
        self.manifest=dict(self.m,resumption_051=dict(controller=resume.base.binding(resume.CONTROLLER),
            previous_manifest=resume.base.binding(self.previous/'manifest.json')))
        write_json(self.output/'manifest.json',self.manifest)
        write_json(self.output/'progress.json',dict(state='prepared_not_dispatched',rows=rows))

    def terminal(self):
        def reconstruct(previous,m,row,index):
            return resume.read(previous/row['path']/'runs'/row['case']/'assessment/revised-verdict.json')
        with patch.object(resume.prior,'terminal_prefix',return_value=(self.ancestor_rows,{})), \
             patch.object(resume.base.migration,'reconstruct',side_effect=reconstruct), \
             patch.object(resume,'diagnose',return_value={'score':None}):
            return resume.terminal_prefix(self.previous,self.m)

    def test_fifty_consumed_preserved_with_050_unscored(self):
        rows,diagnosis=self.terminal()
        self.assertEqual(rows,self.progress['rows'])
        self.assertNotIn('score',rows[49])
        self.assertIsNone(diagnosis['score'])
        self.assertEqual(rows[50]['id'],'051')
        self.assertEqual(sum(r['state']=='pending' for r in rows),190)

    def test_reclassification_reordering_or_inherited_change_rejected(self):
        for change in ('score','state','order','earlier'):
            p=deepcopy(self.progress)
            if change=='score':p['rows'][49]['score']=None
            if change=='state':p['rows'][49]['state']='finished'
            if change=='order':p['rows'][50],p['rows'][51]=p['rows'][51],p['rows'][50]
            if change=='earlier':p['rows'][38]['score']=100.
            write_json(self.previous/'progress.json',p)
            with self.subTest(change=change),self.assertRaises(ValueError):self.terminal()

    def test_changed_score_cannot_be_inherited(self):
        self.progress['rows'][39]['score']=0.
        write_json(self.previous/'progress.json',self.progress)
        with self.assertRaisesRegex(ValueError,'contradicts'):self.terminal()

    def test_existing_preparation_is_not_overwritten(self):
        with self.assertRaisesRegex(ValueError,'fresh'):resume.prepare(self.output,self.previous)

    def test_launch_or_execution_refuses_replay(self):
        write_json(self.output/'resumption-051-launch.json',{})
        with self.assertRaisesRegex(ValueError,'already consumed'):
            resume.fresh_progress(self.output,self.manifest)
        (self.output/'resumption-051-launch.json').unlink()
        (self.output/'runs/051/runs').mkdir(parents=True)
        with self.assertRaisesRegex(ValueError,'Execution already'):
            resume.fresh_progress(self.output,self.manifest)

    def test_prepared_progress_preserves_all_three_unscored_outcomes(self):
        p=resume.fresh_progress(self.output,self.manifest)
        self.assertEqual(p['rows'][:50],self.progress['rows'][:50])
        for index in (29,38,49):self.assertNotIn('score',p['rows'][index])

    def dispatch(self,assess,guard=None):
        with patch.object(resume,'check',return_value={'status':'passed'}), \
             patch.object(resume.base,'guard',side_effect=guard), \
             patch.object(resume.base,'assess',side_effect=assess):
            return resume.dispatch(self.output,3040)

    def test_only_051_through_240_execute_once(self):
        seen=[]
        def assess(output,m,row):
            seen.append(row['id'])
            return dict(decision='unchanged_after_reconstruction',
                        verdict=dict(score=100.,strict_correct=True))
        before=resume.base.migration.inventory(self.previous)
        with patch('builtins.print'):p=self.dispatch(assess)
        self.assertEqual(seen,[f'{i:03d}' for i in range(51,241)])
        self.assertEqual(p['state'],'complete')
        self.assertEqual(p['rows'][:50],self.progress['rows'][:50])
        self.assertEqual(resume.base.migration.inventory(self.previous),before)

    def test_new_incident_still_stops_without_retry(self):
        seen=[]
        def assess(output,m,row):
            seen.append(row['id']);raise ValueError('Unscored evaluation incident')
        p=self.dispatch(assess)
        self.assertEqual(seen,['051']);self.assertEqual(p['state'],'stopped')
        self.assertEqual(p['rows'][50]['state'],'incident')
        self.assertEqual(p['rows'][51]['state'],'pending')

    def test_model_failure_continues_to_next_assignment(self):
        def assess(output,m,row):
            if row['id']=='052':raise ValueError('new incident')
            return dict(decision='qualified_lost_particle_model_failure',
                        verdict=dict(score=0.,strict_correct=False))
        with patch('builtins.print'):p=self.dispatch(assess)
        self.assertEqual(p['rows'][50]['score'],0.)
        self.assertEqual(p['rows'][51]['state'],'incident')
        self.assertEqual(p['rows'][52]['state'],'pending')

    def test_wrong_budget_and_duplicate_claim_prevent_dispatch(self):
        with self.assertRaisesRegex(ValueError,'3040'):resume.dispatch(self.output,3216)
        write_json(self.previous.parent/(self.previous.name+'-resume-051-claim.json'),{})
        with self.assertRaises(FileExistsError):self.dispatch(lambda *args:None)
        self.assertFalse((self.output/'resumption-051-launch.json').exists())

    def test_prestart_guard_failure_leaves_051_pending(self):
        def guard(*args):raise ValueError('Frozen source changed')
        p=self.dispatch(lambda *args:None,guard)
        self.assertEqual(p['state'],'stopped');self.assertEqual(p['rows'][50]['state'],'pending')


class Diagnosis050Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.previous=self.root/'previous';self.previous.mkdir()
        self.ancestor=self.root/'ancestor';self.ancestor.mkdir()
        write_json(self.ancestor/'manifest.json',{})
        self.row=dict(path='slot',case='wrapped_eight_pin_channel')
        self.a=self.previous/'slot/runs/wrapped_eight_pin_channel/assessment'
        (self.a/'export-boundaries').mkdir(parents=True)
        for name in ('candidate.py','review.json','revised-verdict.json',
                     'export-boundaries/stdout.json','export-boundaries/worker.py'):
            (self.a/name).write_text('{}')
        write_json(self.a/'export-boundaries/manifest.json',{'image_id':'image'})
        self.value=dict(verdict=dict(evidence_status='coherent',score=None,strict_correct=False,
            diagnostic_score={'status':'unscored'},gates={'gate':{'passed':True}},
            checks={'geometry':{'boundaries':None,'domain':True},'materials':{'temperature':True}}))
        self.report=dict(status='assessed',stop=None,cleanup_confirmed=True)
        self.save()
        self.m=dict(data_index={'path':'index'},rows=[{}]*38+[{'path':'oldslot'}],
            resumption_040={'previous_manifest':resume.base.binding(self.ancestor/'manifest.json')})
        self.xml=b'<model><geometry><surface id="1" type="z-cylinder" coeffs="0 0 0.475"/><cell id="28" material="3" region="1" temperature="293.6"/></geometry></model>'
        self.oldxml=b'<model><geometry><surface id="1" type="z-cylinder" coeffs="0 0 0.475" name="old"/><cell id="28" material="3" region="1" name="old"/></geometry></model>'
        self.observation={'domain':{'status':'indeterminate'},'coverage':{'analysis':{'elapsed_seconds':0.01}},
                          'model_xml_sha256':'new'}
        self.old_observation={'domain':{'status':'indeterminate'},'coverage':{'analysis':{'elapsed_seconds':0.02}},
                              'model_xml_sha256':'old'}

    def save(self):
        write_json(self.a/'revised-verdict.json',self.value);write_json(self.a/'report.json',self.report)

    def diagnose(self):
        with patch.object(resume.base.migration,'reconstruct',return_value=self.value), \
             patch.object(resume.prior,'diagnose',return_value={'witness':{'bounds_cm':[[-6,-2.22]]},
                'cause':'root_domain_not_resolved_by_supported_abstraction','limits':'local witness only'}), \
             patch.object(resume,'accepted_export',side_effect=[(self.xml,{}),(self.oldxml,{})]), \
             patch.object(resume.boundaries,'record',side_effect=[self.observation,self.old_observation]):
            return resume.diagnose(self.previous,self.m,self.row)

    def test_comparison_preserves_null_score_and_separate_temperature_check(self):
        value=self.diagnose()
        self.assertEqual(value['assignment'],'050');self.assertIsNone(value['score'])
        self.assertTrue(value['same_geometry_as_039']);self.assertFalse(value['assessed_model_failure'])
        self.assertEqual(value['new_model_calls'],0)

    def test_changed_geometry_or_observation_is_not_accepted_as_same_limitation(self):
        self.xml=self.xml.replace(b'0.475',b'0.6')
        with self.assertRaisesRegex(ValueError,'geometry differs'):self.diagnose()
        self.xml=self.xml.replace(b'0.6',b'0.475')
        self.observation['domain']['status']='established'
        with self.assertRaisesRegex(ValueError,'observation differs'):self.diagnose()

    def test_score_promotion_and_temperature_failure_are_rejected(self):
        self.value['verdict']['score']=100.;self.save()
        with self.assertRaises(ValueError):self.diagnose()
        self.value['verdict']['score']=None
        self.value['verdict']['checks']['materials']['temperature']=False;self.save()
        with self.assertRaisesRegex(ValueError,'Another failed'):self.diagnose()


if __name__=='__main__':unittest.main()
