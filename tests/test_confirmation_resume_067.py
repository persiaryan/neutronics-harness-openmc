"""Portable no-replay and evidence-preservation controls for resume 067."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import confirmation_resume_067 as resume
from builder.context import write_json


class Resume067Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name).resolve()
        self.previous=self.root/'previous';self.previous.mkdir()
        self.output=self.root/'next';self.output.mkdir()
        self.ancestor=self.root/'ancestor';self.ancestor.mkdir()
        write_json(self.ancestor/'manifest.json',{})
        rows=[dict(id=f'{i:03d}',model='model',arm='A',case='case',repeat=1,
            path=f'runs/{i:03d}',state='pending',plan_sha256='plan') for i in range(1,241)]
        rows[65].update(case='indc107_reflective_pin',model='gpt-5.6-luna',arm='D')
        self.m=dict(rows=deepcopy(rows),data_index=dict(path='index'),resumption_051=dict(
            previous_manifest=resume.base.binding(self.ancestor/'manifest.json')))
        for row in rows[:66]:
            if row['id'] in ('030','039','050','066'):
                row.update(state='incident',reason='Builder incomplete; slot consumed' if row['id']=='030'
                           else 'Unscored evaluation incident; pause before next slot')
            else:
                success=row['id'] not in ('012','025','034','038','062')
                row.update(state='finished',score=100. if success else 0.,strict_correct=success)
        self.ancestor_rows=deepcopy(rows)
        for row in rows[50:65]:
            record=dict(decision='unchanged_after_reconstruction',
                        verdict=dict(score=row['score'],strict_correct=row['strict_correct']))
            path=self.previous/row['path']/'runs'/row['case']/'assessment/revised-verdict.json'
            path.parent.mkdir(parents=True);write_json(path,record)
            row.update(decision=record['decision'],verdict_path=str(path))
        self.progress=dict(state='stopped',reason='Unscored evaluation incident; pause before next slot',rows=rows)
        write_json(self.previous/'manifest.json',self.m);write_json(self.previous/'progress.json',self.progress)
        self.manifest=dict(self.m,resumption_067=dict(controller=resume.base.binding(resume.CONTROLLER),
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

    def test_sixty_six_consumed_preserved_with_066_unscored(self):
        rows,diagnosis=self.terminal()
        self.assertEqual(rows,self.progress['rows'])
        self.assertNotIn('score',rows[65])
        self.assertIsNone(diagnosis['score'])
        self.assertEqual(rows[66]['id'],'067')
        self.assertEqual(sum(r['state']=='pending' for r in rows),174)

    def test_reclassification_reordering_or_inherited_change_rejected(self):
        for change in ('score','state','order','earlier'):
            p=deepcopy(self.progress)
            if change=='score':p['rows'][65]['score']=None
            if change=='state':p['rows'][65]['state']='finished'
            if change=='order':p['rows'][66],p['rows'][67]=p['rows'][67],p['rows'][66]
            if change=='earlier':p['rows'][38]['score']=100.
            write_json(self.previous/'progress.json',p)
            with self.subTest(change=change),self.assertRaises(ValueError):self.terminal()

    def test_changed_score_cannot_be_inherited(self):
        self.progress['rows'][50]['score']=0.
        write_json(self.previous/'progress.json',self.progress)
        with self.assertRaisesRegex(ValueError,'contradicts'):self.terminal()

    def test_existing_preparation_is_not_overwritten(self):
        with self.assertRaisesRegex(ValueError,'fresh'):resume.prepare(self.output,self.previous)

    def test_launch_or_execution_refuses_replay(self):
        write_json(self.output/'resumption-067-launch.json',{})
        with self.assertRaisesRegex(ValueError,'already consumed'):
            resume.fresh_progress(self.output,self.manifest)
        (self.output/'resumption-067-launch.json').unlink()
        (self.output/'runs/067/runs').mkdir(parents=True)
        with self.assertRaisesRegex(ValueError,'Execution already'):
            resume.fresh_progress(self.output,self.manifest)

    def test_prepared_progress_preserves_all_four_unscored_outcomes(self):
        p=resume.fresh_progress(self.output,self.manifest)
        self.assertEqual(p['rows'][:66],self.progress['rows'][:66])
        for index in (29,38,49,65):self.assertNotIn('score',p['rows'][index])

    def dispatch(self,assess,guard=None):
        with patch.object(resume,'check',return_value={'status':'passed'}), \
             patch.object(resume.base,'guard',side_effect=guard), \
             patch.object(resume.base,'assess',side_effect=assess):
            return resume.dispatch(self.output,2784)

    def test_only_067_through_240_execute_once(self):
        seen=[]
        def assess(output,m,row):
            seen.append(row['id'])
            return dict(decision='unchanged_after_reconstruction',
                        verdict=dict(score=100.,strict_correct=True))
        before=resume.base.migration.inventory(self.previous)
        with patch('builtins.print'):p=self.dispatch(assess)
        self.assertEqual(seen,[f'{i:03d}' for i in range(67,241)])
        self.assertEqual(p['state'],'complete')
        self.assertEqual(p['rows'][:66],self.progress['rows'][:66])
        self.assertEqual(resume.base.migration.inventory(self.previous),before)

    def test_new_incident_still_stops_without_retry(self):
        seen=[]
        def assess(output,m,row):
            seen.append(row['id']);raise ValueError('Unscored evaluation incident')
        p=self.dispatch(assess)
        self.assertEqual(seen,['067']);self.assertEqual(p['state'],'stopped')
        self.assertEqual(p['rows'][66]['state'],'incident')
        self.assertEqual(p['rows'][67]['state'],'pending')

    def test_model_failure_continues_to_next_assignment(self):
        def assess(output,m,row):
            if row['id']=='068':raise ValueError('new incident')
            return dict(decision='qualified_lost_particle_model_failure',
                        verdict=dict(score=0.,strict_correct=False))
        with patch('builtins.print'):p=self.dispatch(assess)
        self.assertEqual(p['rows'][66]['score'],0.)
        self.assertEqual(p['rows'][67]['state'],'incident')
        self.assertEqual(p['rows'][68]['state'],'pending')

    def test_wrong_budget_and_duplicate_claim_prevent_dispatch(self):
        with self.assertRaisesRegex(ValueError,'2784'):resume.dispatch(self.output,3040)
        write_json(self.previous.parent/(self.previous.name+'-resume-067-claim.json'),{})
        with self.assertRaises(FileExistsError):self.dispatch(lambda *args:None)
        self.assertFalse((self.output/'resumption-067-launch.json').exists())

    def test_prestart_guard_failure_leaves_067_pending(self):
        def guard(*args):raise ValueError('Frozen source changed')
        p=self.dispatch(lambda *args:None,guard)
        self.assertEqual(p['state'],'stopped');self.assertEqual(p['rows'][66]['state'],'pending')


class Diagnosis066Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.a=self.root/'slot/runs/indc107_reflective_pin/assessment'
        (self.a/'transport').mkdir(parents=True)
        self.row=dict(path='slot',case='indc107_reflective_pin')
        self.m=dict(data_index={'path':'index'})
        self.xml=b"""<model><geometry>
<cell id="1" material="1" region="1 -2 3 -4 5 -6 -7" universe="1"/>
<cell id="2" material="2" region="1 -2 3 -4 5 -6 7" universe="1"/>
<surface id="1" type="x-plane" coeffs="-2.54"/>
<surface id="2" type="x-plane" coeffs="2.54"/>
<surface id="3" type="y-plane" coeffs="-2.54"/>
<surface id="4" type="y-plane" coeffs="2.54"/>
<surface id="5" type="z-plane" coeffs="-1"/>
<surface id="6" type="z-plane" coeffs="1"/>
<surface id="7" type="z-cylinder" coeffs="0 0 1.27"/>
</geometry><materials>
<material id="1"><nuclide name="U235"/><nuclide name="U238"/></material>
<material id="2"><nuclide name="H1"/><nuclide name="O16"/></material>
</materials><settings><source><space type="box"><parameters>-1.27 -1.27 -1 1.27 1.27 1</parameters></space>
<constraints><domain_type>cell</domain_type><domain_ids>1</domain_ids></constraints>
</source></settings></model>"""
        self.value=dict(verdict=dict(evidence_status='coherent',score=None,strict_correct=False,
            diagnostic_score=dict(status='unscored',reason='Unassessed evidence: physics_settings'),
            gates={'gate':{'passed':True}},
            checks=dict(geometry={'boundaries':True},physics_settings=dict(physics=None,
                sampling=None,source=None,entropy_mesh_and_output=None))))
        self.settings=dict(unassessed_options=['constraints/domain_type','constraints/domain_ids'],
            checks=[dict(field='synthetic',passed=True)]*29+
                [dict(field='source_fissionable',actual=False,expected=True,passed=False)])
        for name in ('candidate.py','review.json','transport/openmc-process.json'):
            (self.a/name).write_text('{}')
        write_json(self.a/'assignment.json',{'sampling':{}})
        self.save()

    def save(self):
        write_json(self.a/'revised-verdict.json',self.value)
        write_json(self.a/'report.json',dict(status='assessed',stop=None,cleanup_confirmed=True))
        write_json(self.a/'export-fidelity.json',dict(settings=self.settings))
        (self.a/'transport/model.xml').write_bytes(self.xml)

    def diagnose(self):
        with patch.object(resume.base.migration,'reconstruct',return_value=self.value), \
             patch.object(resume,'accepted_export',return_value=(self.xml,{})), \
             patch.object(resume,'settings_checks',return_value=self.settings):
            return resume.diagnose(self.root,self.m,self.row)

    def test_null_score_retained_with_local_domain_witness(self):
        before=resume.base.migration.inventory(self.root)
        value=self.diagnose()
        self.assertIsNone(value['score'])
        self.assertFalse(value['assessed_model_failure'])
        self.assertEqual(value['witness']['selected_cell'],'1')
        self.assertEqual(value['new_native_transports'],0)
        self.assertEqual(resume.base.migration.inventory(self.root),before)

    def test_wrong_selected_cell_material_or_geometry_rejected(self):
        for a,b in [(b'<domain_ids>1',b'<domain_ids>2'),
                    (b'name="U235"',b'name="O16"'),
                    (b'0 0 1.27',b'0 0 1.28'),
                    (b'universe="1"',b'universe="2"')]:
            with self.subTest(change=a),self.assertRaises(ValueError):
                resume.domain_witness(self.xml.replace(a,b))

    def test_score_promotion_or_other_unresolved_checks_rejected(self):
        self.value['verdict']['score']=100.;self.save()
        with self.assertRaises(ValueError):self.diagnose()
        self.value['verdict']['score']=None
        self.value['verdict']['checks']['geometry']['boundaries']=None;self.save()
        with self.assertRaisesRegex(ValueError,'Another failed'):self.diagnose()

    def test_extra_unsupported_option_or_source_discrepancy_rejected(self):
        self.settings['unassessed_options'].append('time');self.save()
        with self.assertRaisesRegex(ValueError,'signature changed'):self.diagnose()
        self.settings['unassessed_options'].pop()
        self.settings['checks'][0]=dict(field='particles',passed=False);self.save()
        with self.assertRaisesRegex(ValueError,'signature changed'):self.diagnose()


if __name__=='__main__':unittest.main()
