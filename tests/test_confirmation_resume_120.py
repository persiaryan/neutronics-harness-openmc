"""Portable no-replay and evidence-preservation controls for resume 120."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import confirmation_resume_120 as resume
from builder.context import write_json


class Resume120Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name).resolve()
        self.previous=self.root/'previous';self.previous.mkdir()
        self.output=self.root/'next';self.output.mkdir()
        self.ancestor=self.root/'ancestor';self.ancestor.mkdir()
        write_json(self.ancestor/'manifest.json',{})
        rows=[dict(id=f'{i:03d}',model='model',arm='A',case='case',repeat=1,
            path=f'runs/{i:03d}',state='pending',plan_sha256='plan') for i in range(1,241)]
        rows[118].update(case='wrapped_eight_pin_channel',model='gpt-5.6-sol',arm='D')
        self.m=dict(rows=deepcopy(rows),data_index=dict(path='index'),resumption_119=dict(
            previous_manifest=resume.base.binding(self.ancestor/'manifest.json')))
        for row in rows[:119]:
            if row['id'] in ('030','039','050','066','117','118','119'):
                row.update(state='incident',reason='Builder incomplete; slot consumed' if row['id']=='030'
                           else 'Unscored evaluation incident; pause before next slot')
            else:
                success=row['id'] not in ('012','025','034','038','062','069','080','090','098','102','106','110','111')
                row.update(state='finished',score=100. if success else 0.,strict_correct=success)
        for row in rows[66:116]:
            record=dict(decision='unchanged_after_reconstruction',
                        verdict=dict(score=row['score'],strict_correct=row['strict_correct']))
            path=self.previous/row['path']/'runs'/row['case']/'assessment/revised-verdict.json'
            path.parent.mkdir(parents=True);write_json(path,record)
            row.update(decision=record['decision'],verdict_path=str(path))
        self.ancestor_rows=deepcopy(rows)
        self.progress=dict(state='stopped',reason='Unscored evaluation incident; pause before next slot',rows=rows)
        write_json(self.previous/'manifest.json',self.m);write_json(self.previous/'progress.json',self.progress)
        self.manifest=dict(self.m,resumption_120=dict(controller=resume.base.binding(resume.CONTROLLER),
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

    def test_119_consumed_preserved_with_119_unscored(self):
        rows,diagnosis=self.terminal()
        self.assertEqual(rows,self.progress['rows'])
        self.assertNotIn('score',rows[118])
        self.assertIsNone(diagnosis['score'])
        self.assertEqual(rows[119]['id'],'120')
        self.assertEqual(sum(r['state']=='pending' for r in rows),121)

    def test_reclassification_reordering_or_inherited_change_rejected(self):
        for change in ('score','state','order','earlier'):
            p=deepcopy(self.progress)
            if change=='score':p['rows'][118]['score']=None
            if change=='state':p['rows'][118]['state']='finished'
            if change=='order':p['rows'][119],p['rows'][120]=p['rows'][120],p['rows'][119]
            if change=='earlier':p['rows'][38]['score']=100.
            write_json(self.previous/'progress.json',p)
            with self.subTest(change=change),self.assertRaises(ValueError):self.terminal()

    def test_changed_score_cannot_be_inherited(self):
        self.progress['rows'][66]['score']=0.
        write_json(self.previous/'progress.json',self.progress)
        with self.assertRaisesRegex(ValueError,'Earlier consumed'):self.terminal()

    def test_partial_failure_score_is_preserved_without_rounding(self):
        self.progress['rows'][105]['score']=96.42857142857143
        self.ancestor_rows[105]['score']=96.42857142857143
        write_json(self.previous/'progress.json',self.progress)
        rows,_=self.terminal()
        self.assertEqual(rows[105]['score'],96.42857142857143)
        self.assertIs(rows[105]['strict_correct'],False)

    def test_existing_preparation_is_not_overwritten(self):
        with self.assertRaisesRegex(ValueError,'fresh'):resume.prepare(self.output,self.previous)

    def test_launch_or_execution_refuses_replay(self):
        write_json(self.output/'resumption-120-launch.json',{})
        with self.assertRaisesRegex(ValueError,'already consumed'):
            resume.fresh_progress(self.output,self.manifest)
        (self.output/'resumption-120-launch.json').unlink()
        (self.output/'runs/120/runs').mkdir(parents=True)
        with self.assertRaisesRegex(ValueError,'Execution already'):
            resume.fresh_progress(self.output,self.manifest)

    def test_prepared_progress_preserves_all_seven_unscored_outcomes(self):
        p=resume.fresh_progress(self.output,self.manifest)
        self.assertEqual(p['rows'][:119],self.progress['rows'][:119])
        for index in (29,38,49,65,116,117,118):self.assertNotIn('score',p['rows'][index])

    def dispatch(self,assess,guard=None):
        with patch.object(resume,'check',return_value={'status':'passed'}), \
             patch.object(resume.base,'guard',side_effect=guard), \
             patch.object(resume.base,'assess',side_effect=assess):
            return resume.dispatch(self.output,1936)

    def test_only_120_through_240_execute_once(self):
        seen=[]
        def assess(output,m,row):
            seen.append(row['id'])
            return dict(decision='unchanged_after_reconstruction',
                        verdict=dict(score=100.,strict_correct=True))
        before=resume.base.migration.inventory(self.previous)
        with patch('builtins.print'):p=self.dispatch(assess)
        self.assertEqual(seen,[f'{i:03d}' for i in range(120,241)])
        self.assertEqual(p['state'],'complete')
        self.assertEqual(p['rows'][:119],self.progress['rows'][:119])
        self.assertEqual(resume.base.migration.inventory(self.previous),before)

    def test_new_incident_still_stops_without_retry(self):
        seen=[]
        def assess(output,m,row):
            seen.append(row['id']);raise ValueError('Unscored evaluation incident')
        p=self.dispatch(assess)
        self.assertEqual(seen,['120']);self.assertEqual(p['state'],'stopped')
        self.assertEqual(p['rows'][119]['state'],'incident')
        self.assertEqual(p['rows'][120]['state'],'pending')

    def test_model_failure_continues_to_next_assignment(self):
        def assess(output,m,row):
            if row['id']=='121':raise ValueError('new incident')
            return dict(decision='qualified_lost_particle_model_failure',
                        verdict=dict(score=0.,strict_correct=False))
        with patch('builtins.print'):p=self.dispatch(assess)
        self.assertEqual(p['rows'][119]['score'],0.)
        self.assertEqual(p['rows'][120]['state'],'incident')
        self.assertEqual(p['rows'][121]['state'],'pending')

    def test_wrong_budget_and_duplicate_claim_prevent_dispatch(self):
        with self.assertRaisesRegex(ValueError,'1936'):resume.dispatch(self.output,1952)
        write_json(self.previous.parent/(self.previous.name+'-resume-120-claim.json'),{})
        with self.assertRaises(FileExistsError):self.dispatch(lambda *args:None)
        self.assertFalse((self.output/'resumption-120-launch.json').exists())

    def test_prestart_guard_failure_leaves_120_pending(self):
        def guard(*args):raise ValueError('Frozen source changed')
        p=self.dispatch(lambda *args:None,guard)
        self.assertEqual(p['state'],'stopped');self.assertEqual(p['rows'][119]['state'],'pending')


class Diagnosis119Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.previous=self.root/'previous';self.previous.mkdir()
        self.ancestor=self.root/'ancestor';self.ancestor.mkdir()
        write_json(self.ancestor/'manifest.json',{'rows':[{}]*38+[{'path':'old','case':'case'}]})
        self.row=dict(path='slot',case='wrapped_eight_pin_channel')
        self.a=self.previous/'slot/runs/wrapped_eight_pin_channel/assessment'
        (self.a/'export-boundaries').mkdir(parents=True);(self.a/'transport').mkdir()
        self.m=dict(data_index={'path':'index'},resumption_040=dict(
            previous_manifest=resume.base.binding(self.ancestor/'manifest.json')))
        self.xml=b"""<model><geometry>
<cell id="9" name="new" universe="1" material="1" region="-30 -20 10" temperature="293.6"/>
<surface id="10" type="x-plane" coeffs="0"/>
<surface id="20" type="x-plane" coeffs="4"/>
<surface id="30" type="z-cylinder" coeffs="2 2 0.4"/>
</geometry><materials><material id="1"><density value="1" units="g/cm3"/>
<nuclide name="H1" ao="2"/><nuclide name="O16" ao="1"/></material></materials></model>"""
        self.oldxml=b"""<model><geometry>
<cell id="1" universe="1" material="1" region="1 -2 -3"/>
<surface id="1" type="x-plane" coeffs="0"/>
<surface id="2" type="x-plane" coeffs="4"/>
<surface id="3" type="z-cylinder" coeffs="2 2 0.4"/>
</geometry><materials><material id="1"><density value="1" units="g/cm3"/>
<nuclide name="H1" ao="2"/><nuclide name="O16" ao="1"/></material></materials></model>"""
        cause='root_domain_not_resolved_by_supported_abstraction'
        self.observation=dict(domain=dict(status='indeterminate',cause=cause),faces=[],
            limitations=[cause],coverage={'analysis':{'work_units':6591,'elapsed_seconds':0.006}})
        self.old_observation=deepcopy(self.observation)
        self.old_observation['coverage']['analysis']['elapsed_seconds']=0.007
        self.value=dict(verdict=dict(evidence_status='coherent',score=None,strict_correct=False,
            diagnostic_score={'status':'unscored'},gates={'gate':{'passed':True}},
            checks={'geometry':{'boundaries':None,'domain':True},'materials':{'temperature':True}}))
        self.report=dict(status='assessed',stop=None,cleanup_confirmed=True,
            fidelity={'boundaries':{'verdicts':[{'verdict':'indeterminate','cause':cause}]*12}})
        for name in ('candidate.py','review.json','export-fidelity.json',
                     'export-boundaries/stdout.json','export-boundaries/worker.py'):
            (self.a/name).write_text('{}')
        write_json(self.a/'export-boundaries/manifest.json',{'image_id':'image'})
        self.save()

    def save(self):
        write_json(self.a/'revised-verdict.json',self.value)
        write_json(self.a/'report.json',self.report)
        (self.a/'transport/model.xml').write_bytes(self.xml)

    def diagnose(self):
        with patch.object(resume.base.migration,'reconstruct',return_value=self.value), \
             patch.object(resume,'accepted_export',side_effect=[(self.xml,{}),(self.oldxml,{})]), \
             patch.object(resume.boundaries,'record',side_effect=[self.observation,self.old_observation]), \
             patch.object(resume.boundary_prior,'diagnose',return_value={
                 'witness':{'visit':43},'limits':'Local witness only'}):
            return resume.diagnose(self.previous,self.m,self.row)

    def test_null_verdict_and_evidence_remain_unchanged(self):
        before=resume.base.migration.inventory(self.previous)
        value=self.diagnose()
        self.assertIsNone(value['score']);self.assertFalse(value['assessed_model_failure'])
        self.assertTrue(value['same_partition_and_materials_as_039_after_renumbering'])
        self.assertEqual(value['new_native_transports'],0)
        self.assertEqual(resume.base.migration.inventory(self.previous),before)

    def test_numbering_names_and_term_order_are_metadata(self):
        self.assertEqual(resume.canonical_geometry(self.xml),resume.canonical_geometry(self.oldxml))

    def test_changed_partition_material_or_transform_is_rejected(self):
        for old,new in [(b'2 2 0.4',b'2 2 0.5'),(b'ao="2"',b'ao="3"'),
                        (b'universe="1"',b'universe="2"')]:
            xml=self.xml;self.xml=self.xml.replace(old,new);self.save()
            with self.subTest(change=old),self.assertRaises(ValueError):self.diagnose()
            self.xml=xml;self.save()

    def test_score_promotion_and_other_unresolved_obligation_are_rejected(self):
        self.value['verdict']['score']=100.;self.save()
        with self.assertRaises(ValueError):self.diagnose()
        self.value['verdict']['score']=None
        self.value['verdict']['checks']['materials']['temperature']=None;self.save()
        with self.assertRaisesRegex(ValueError,'Another failed'):self.diagnose()

    def test_different_worker_stop_or_budget_exhaustion_is_rejected(self):
        self.observation['coverage']['analysis']['work_units']=7000
        with self.assertRaisesRegex(ValueError,'stopping location differs'):self.diagnose()
        self.observation['coverage']['analysis']['work_units']=6591
        self.observation['coverage']['limit']={'guard':'work_units'}
        with self.assertRaisesRegex(ValueError,'Different boundary failure'):self.diagnose()


if __name__=='__main__':unittest.main()
