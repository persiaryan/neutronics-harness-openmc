"""Portable evidence-preservation and orchestration controls for resume 040."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

import confirmation_resume_040 as resume
from builder.context import write_json


class Resume040Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name).resolve()
        self.previous=self.root/'previous';self.previous.mkdir()
        self.output=self.root/'prepared';self.output.mkdir()
        self.ancestor=self.root/'ancestor';self.ancestor.mkdir()
        write_json(self.ancestor/'manifest.json',{})
        rows=[dict(id=f'{i:03d}',model='model',arm='A',case='case',repeat=1,
                   path=f'runs/{i:03d}',state='pending',plan_sha256='plan')
              for i in range(1,241)]
        rows[38].update(case='wrapped_eight_pin_channel',model='gpt-5.6-sol')
        self.m=dict(rows=deepcopy(rows),data_index=dict(path='index'),resumption=dict(
            previous_manifest=resume.base.binding(self.ancestor/'manifest.json')))
        for row in rows[:39]:
            if row['id'] in ('030','039'):
                row.update(state='incident',reason='Builder incomplete; slot consumed' if row['id']=='030'
                           else 'Unscored evaluation incident; pause before next slot')
            else:
                success=row['id'] not in ('012','025','034','038')
                row.update(state='finished',score=100. if success else 0.,strict_correct=success)
        self.ancestor_rows=deepcopy(rows)
        for row in rows[30:38]:
            record=dict(decision='unchanged_after_reconstruction',
                        verdict=dict(score=row['score'],strict_correct=row['strict_correct']))
            p=self.previous/row['path']/'runs'/row['case']/'assessment/revised-verdict.json'
            p.parent.mkdir(parents=True);write_json(p,record)
            row.update(decision=record['decision'],verdict_path=str(p))
        self.progress=dict(state='stopped',
            reason='Unscored evaluation incident; pause before next slot',rows=rows)
        write_json(self.previous/'manifest.json',self.m)
        write_json(self.previous/'progress.json',self.progress)
        self.manifest=deepcopy(self.m)
        self.manifest['resumption_040']=dict(
            controller=resume.base.binding(resume.CONTROLLER),
            previous_manifest=resume.base.binding(self.previous/'manifest.json'))
        write_json(self.output/'manifest.json',self.manifest)
        write_json(self.output/'progress.json',dict(state='prepared_not_dispatched',rows=rows))

    def terminal(self):
        def reconstruct(previous,m,row,index):
            return resume.read(previous/row['path']/'runs'/row['case']/'assessment/revised-verdict.json')
        with patch.object(resume.prior,'terminal_prefix',return_value=(self.ancestor_rows,{})), \
             patch.object(resume.base.migration,'reconstruct',side_effect=reconstruct), \
             patch.object(resume,'diagnose',return_value={'score':None}):
            return resume.terminal_prefix(self.previous,self.m)

    def test_all_39_consumed_rows_preserved_and_039_unscored(self):
        rows,diagnosis=self.terminal()
        self.assertEqual(rows,self.progress['rows'])
        self.assertNotIn('score',rows[38])
        self.assertIsNone(diagnosis['score'])
        self.assertEqual(rows[39]['id'],'040')
        self.assertEqual(sum(r['state']=='pending' for r in rows),201)

    def test_reclassified_039_or_reordered_suffix_is_rejected(self):
        for change in ('score','state','order','earlier'):
            p=deepcopy(self.progress)
            if change=='score':p['rows'][38]['score']=0.
            if change=='state':p['rows'][38]['state']='finished'
            if change=='order':p['rows'][39],p['rows'][40]=p['rows'][40],p['rows'][39]
            if change=='earlier':p['rows'][11]['score']=100.
            write_json(self.previous/'progress.json',p)
            with self.subTest(change=change),self.assertRaises(ValueError):self.terminal()

    def test_changed_scored_result_cannot_be_inherited(self):
        self.progress['rows'][33]['score']=100.
        write_json(self.previous/'progress.json',self.progress)
        with self.assertRaisesRegex(ValueError,'contradicts'):self.terminal()

    def test_preparation_refuses_overwrite(self):
        with self.assertRaisesRegex(ValueError,'fresh'):
            resume.prepare(self.output,self.previous)

    def test_fresh_progress_does_not_reclassify_prefix(self):
        actual=resume.fresh_progress(self.output,self.manifest)
        self.assertEqual(actual['rows'][:39],self.progress['rows'][:39])
        self.assertNotIn('score',actual['rows'][38])

    def test_started_progress_launch_or_execution_prevents_replay(self):
        altered=dict(state='running',rows=self.progress['rows'])
        write_json(self.output/'progress.json',altered)
        with self.assertRaisesRegex(ValueError,'not fresh'):
            resume.fresh_progress(self.output,self.manifest)
        write_json(self.output/'progress.json',dict(state='prepared_not_dispatched',rows=self.progress['rows']))
        write_json(self.output/'resumption-040-launch.json',{})
        with self.assertRaisesRegex(ValueError,'already consumed'):
            resume.fresh_progress(self.output,self.manifest)
        (self.output/'resumption-040-launch.json').unlink()
        (self.output/'runs/040/runs').mkdir(parents=True)
        with self.assertRaisesRegex(ValueError,'Execution already'):
            resume.fresh_progress(self.output,self.manifest)

    def dispatch(self,assessment,guard=None):
        with patch.object(resume,'check',return_value={'status':'passed'}), \
             patch.object(resume.base,'guard',side_effect=guard), \
             patch.object(resume.base,'assess',side_effect=assessment):
            return resume.dispatch(self.output,3216)

    def test_entire_suffix_once_preserves_both_unscored_rows(self):
        seen=[]
        def assess(output,m,row):
            seen.append(row['id'])
            return dict(decision='unchanged_after_reconstruction',
                        verdict=dict(score=100.,strict_correct=True))
        before=resume.base.migration.inventory(self.previous)
        with patch('builtins.print'):p=self.dispatch(assess)
        self.assertEqual(seen,[f'{i:03d}' for i in range(40,241)])
        self.assertEqual(p['state'],'complete')
        self.assertEqual(p['rows'][:39],self.progress['rows'][:39])
        self.assertEqual(resume.base.migration.inventory(self.previous),before)
        with self.assertRaisesRegex(ValueError,'already consumed'):
            resume.dispatch(self.output,3216)

    def test_new_unscored_incident_still_stops_without_retry(self):
        seen=[]
        def assess(output,m,row):
            seen.append(row['id'])
            raise ValueError('Unscored evaluation incident')
        p=self.dispatch(assess)
        self.assertEqual(seen,['040'])
        self.assertEqual(p['state'],'stopped')
        self.assertEqual(p['rows'][39]['state'],'incident')
        self.assertEqual(p['rows'][40]['state'],'pending')
        self.assertNotIn('score',p['rows'][38])

    def test_model_failure_is_recorded_then_next_slot_is_attempted(self):
        def assess(output,m,row):
            if row['id']=='041':raise ValueError('new incident')
            return dict(decision='qualified_lost_particle_model_failure',
                        verdict=dict(score=0.,strict_correct=False))
        with patch('builtins.print'):p=self.dispatch(assess)
        self.assertEqual(p['rows'][39]['score'],0.)
        self.assertEqual(p['rows'][40]['state'],'incident')
        self.assertEqual(p['rows'][41]['state'],'pending')

    def test_duplicate_claim_and_wrong_budget_do_not_dispatch(self):
        with self.assertRaisesRegex(ValueError,'3216'):
            resume.dispatch(self.output,3360)
        write_json(self.previous.parent/(self.previous.name+'-resume-040-claim.json'),{})
        with self.assertRaises(FileExistsError):self.dispatch(lambda *args:None)
        self.assertFalse((self.output/'resumption-040-launch.json').exists())

    def test_prestart_guard_failure_leaves_next_slot_pending(self):
        def guard(*args):raise ValueError('Frozen source changed')
        p=self.dispatch(lambda *args:None,guard)
        self.assertEqual(p['state'],'stopped')
        self.assertEqual(p['rows'][39]['state'],'pending')


class Diagnosis039Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.previous=Path(self.tmp.name)
        self.a=self.previous/'slot/runs/wrapped_eight_pin_channel/assessment'
        (self.a/'export-boundaries').mkdir(parents=True)
        for name in ('candidate.py','review.json','revised-verdict.json',
                     'export-boundaries/stdout.json','export-boundaries/worker.py'):
            (self.a/name).write_text('{}')
        write_json(self.a/'export-boundaries/manifest.json',{'image_id':'image'})
        self.value=dict(verdict=dict(evidence_status='coherent',score=None,strict_correct=False,
            diagnostic_score={'status':'unscored'},gates={'gate':{'passed':True}},
            checks={'geometry':{'boundaries':None,'domain':True}}))
        self.report=dict(status='assessed',stop=None,cleanup_confirmed=True,
            fidelity={'boundaries':{'verdicts':[dict(verdict='indeterminate',
                cause='root_domain_not_resolved_by_supported_abstraction') for _ in range(12)]}})
        self.observation=dict(domain=dict(status='indeterminate',
            cause='root_domain_not_resolved_by_supported_abstraction'),faces=[],
            limitations=['root_domain_not_resolved_by_supported_abstraction'],
            coverage={'analysis':{'arrangement_cells_visited':43}})
        self.save()
        g=ET.Element('geometry')
        for sid,kind,value in ((1,'x-plane',-6),(2,'x-plane',6),(3,'y-plane',-6),(4,'y-plane',6),
            (5,'z-plane',-25),(6,'z-plane',25),(7,'z-plane',-18),(8,'z-plane',18),
            (35,'x-plane',-2.1),(36,'x-plane',2.1),(37,'y-plane',-2.1),(38,'y-plane',2.1),
            (39,'x-plane',-2.22),(40,'x-plane',2.22),(41,'y-plane',-2.22),(42,'y-plane',2.22)):
            ET.SubElement(g,'surface',id=str(sid),type=kind,coeffs=str(value))
        for sid in (11,14,17,20,23,26,29,32,34):
            ET.SubElement(g,'surface',id=str(sid),type='z-cylinder',coeffs='-1.3 -1.3 0.475')
        ET.SubElement(g,'cell',id='28',region='1 -2 3 -4 5 -6 '+' '.join(
            f'({sid} | -7 | 8)' for sid in (11,14,17,20,23,26,29,32,34)))
        root=ET.Element('model');root.append(g);self.xml=ET.tostring(root)
        self.m={'data_index':{'path':'index'}}
        self.row=dict(path='slot',case='wrapped_eight_pin_channel')

    def save(self):
        write_json(self.a/'revised-verdict.json',self.value)
        write_json(self.a/'report.json',self.report)

    def diagnose(self):
        with patch.object(resume.base.migration,'reconstruct',return_value=self.value), \
             patch.object(resume,'accepted_export',return_value=(self.xml,{})), \
             patch.object(resume.boundaries,'record',return_value=self.observation):
            return resume.diagnose(self.previous,self.m,self.row)

    def test_local_certificate_does_not_create_score_or_global_certification(self):
        value=self.diagnose()
        self.assertIsNone(value['score'])
        self.assertFalse(value['assessed_model_failure'])
        self.assertTrue(value['witness']['physical_water_occupancy_throughout_witness'])
        self.assertEqual(value['witness']['bounds_cm'],[[-6.,-2.22],[-6.,-2.22],[-18.,18.]])
        self.assertAlmostEqual(value['witness']['cylinder_exterior_certificate'][0]['minimum_distance_cm'],
                               1.3010764773832477)
        self.assertEqual(json.loads(json.dumps(value)),value)
        self.assertEqual(value['new_native_transports'],0)

    def test_score_promotion_other_unknowns_and_limits_are_rejected(self):
        for changed in ('score','check','gate','limit'):
            original=deepcopy(self.value);obs=deepcopy(self.observation)
            if changed=='score':self.value['verdict']['score']=100.
            if changed=='check':self.value['verdict']['checks']['geometry']['domain']=None
            if changed=='gate':self.value['verdict']['gates']['gate']['passed']=False
            if changed=='limit':self.observation['coverage']['limit']={'guard':'work_units'}
            self.save()
            with self.subTest(change=changed),self.assertRaises(ValueError):self.diagnose()
            self.value=original;self.observation=obs;self.save()

    def test_an_actual_cylinder_intersection_invalidates_local_certificate(self):
        root=ET.fromstring(self.xml)
        root.find("geometry/surface[@id='11']").set('coeffs','-1.3 -1.3 10')
        self.xml=ET.tostring(root)
        with self.assertRaisesRegex(ValueError,'Exterior condition'):
            self.diagnose()


if __name__=='__main__':unittest.main()
