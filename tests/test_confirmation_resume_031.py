"""Portable controls for the single bounded restart after assignment 030."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import confirmation_resume_031 as resume
from builder.context import write_json


class ResumeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name).resolve()
        self.previous=self.root/'previous';self.previous.mkdir()
        self.output=self.root/'next';self.output.mkdir()
        self.rows=[dict(id=f'{i:03d}',path=f'runs/{i:03d}',case='case',model='model',
                        arm='A',repeat=1,plan_sha256='plan',state='pending')
                   for i in range(1,241)]
        self.rows[29].update(case='cross_shaped_mixture',model='gpt-5.6-luna')
        original=dict(rows=deepcopy(self.rows))
        revised=dict(rows=[dict(**{k:r[k] for k in resume.base.migration.IMMUTABLE_ROW},
            verdict=dict(evidence_status='coherent',score=0. if r['id']=='012' else 100.,
                         strict_correct=r['id']!='012')) for r in self.rows[:12]],
            counts=dict(protocol_success=11,evaluated_failure=1,unscored_incident=0,pending=228))
        write_json(self.root/'original.json',original)
        write_json(self.root/'revision.json',revised)
        self.m=dict(rows=deepcopy(self.rows),data_index=dict(path='index'),continuation=dict(
            original_manifest=resume.base.binding(self.root/'original.json'),
            revision=resume.base.binding(self.root/'revision.json')))
        initial=resume.base.prefix_rows(original,revised,self.root)
        self.progress=dict(state='stopped',reason='Builder incomplete; slot consumed',rows=initial)
        for row in initial[12:29]:
            success=row['id']!='025'
            record=dict(decision='unchanged_after_reconstruction',
                verdict=dict(score=100. if success else 0.,strict_correct=success))
            path=self.previous/row['path']/'runs'/row['case']/'assessment/revised-verdict.json'
            path.parent.mkdir(parents=True);write_json(path,record)
            row.update(state='finished',score=record['verdict']['score'],
                strict_correct=success,decision=record['decision'],verdict_path=str(path))
        initial[29].update(state='incident',reason='Builder incomplete; slot consumed')
        write_json(self.previous/'manifest.json',self.m)
        write_json(self.previous/'progress.json',self.progress)
        self.manifest=deepcopy(self.m)
        self.manifest['resumption']=dict(previous_manifest=resume.base.binding(self.previous/'manifest.json'),
            controller=resume.base.binding(resume.CONTROLLER))
        write_json(self.output/'manifest.json',self.manifest)
        write_json(self.output/'progress.json',dict(state='prepared_not_dispatched',rows=initial))

    def reconstructed(self,previous,m,row,index):
        return resume.read(previous/row['path']/'runs'/row['case']/'assessment/revised-verdict.json')

    def terminal(self):
        with patch.object(resume.base.migration,'reconstruct',side_effect=self.reconstructed), \
             patch.object(resume,'diagnose',return_value={'classification':'incident'}):
            return resume.terminal_prefix(self.previous,self.m)

    def test_thirty_consumed_slots_include_unscored_incident(self):
        rows,diagnosis=self.terminal()
        self.assertEqual(rows,self.progress['rows'])
        self.assertEqual(rows[29]['state'],'incident')
        self.assertNotIn('score',rows[29])
        self.assertTrue(all(r['state']=='pending' for r in rows[30:]))

    def test_gap_active_row_or_reclassified_incident_rejected(self):
        for change in ('gap','active','reclassified','order'):
            p=deepcopy(self.progress)
            if change=='gap':p['rows'][28]['state']='pending'
            if change=='active':p['rows'][30]['state']='started'
            if change=='reclassified':p['rows'][29]['state']='finished'
            if change=='order':p['rows'][30],p['rows'][31]=p['rows'][31],p['rows'][30]
            write_json(self.previous/'progress.json',p)
            with self.subTest(change=change),self.assertRaises(ValueError):self.terminal()

    def test_changed_scored_result_is_not_inherited(self):
        self.progress['rows'][24]['score']=100.
        write_json(self.previous/'progress.json',self.progress)
        with self.assertRaisesRegex(ValueError,'contradicts'):self.terminal()

    def test_fresh_prefix_keeps_incident_unscored(self):
        p=resume.fresh_progress(self.output,self.manifest)
        self.assertEqual(p['rows'][29]['state'],'incident')
        self.assertEqual(p['rows'][30]['id'],'031')

    def test_restart_and_preexisting_execution_rejected(self):
        write_json(self.output/'resumption-launch.json',{})
        with self.assertRaisesRegex(ValueError,'already consumed'):
            resume.fresh_progress(self.output,self.manifest)
        (self.output/'resumption-launch.json').unlink()
        (self.output/'runs/031/runs').mkdir(parents=True)
        with self.assertRaisesRegex(ValueError,'Execution evidence'):
            resume.fresh_progress(self.output,self.manifest)

    def test_existing_preparation_not_overwritten(self):
        with self.assertRaisesRegex(ValueError,'fresh'):
            resume.prepare(self.output,self.previous)

    def dispatch(self,assess,guard=None):
        with patch.object(resume,'check',return_value={'status':'passed'}), \
             patch.object(resume.base,'guard',side_effect=guard), \
             patch.object(resume.base,'assess',side_effect=assess):
            return resume.dispatch(self.output,3360)

    def test_suffix_runs_once_without_replaying_incident(self):
        seen=[]
        def assess(output,m,row):
            seen.append(row['id'])
            return dict(decision='unchanged_after_reconstruction',
                        verdict=dict(score=100.,strict_correct=True))
        before=resume.base.migration.inventory(self.previous)
        with patch('builtins.print'):p=self.dispatch(assess)
        self.assertEqual(seen,[f'{i:03d}' for i in range(31,241)])
        self.assertEqual(p['state'],'complete')
        self.assertEqual(p['rows'][:30],self.progress['rows'][:30])
        self.assertEqual(resume.base.migration.inventory(self.previous),before)
        with self.assertRaisesRegex(ValueError,'already consumed'):
            resume.dispatch(self.output,3360)

    def test_failure_is_scored_and_next_incident_stops(self):
        seen=[]
        def assess(output,m,row):
            seen.append(row['id'])
            if row['id']=='032':raise ValueError('new unqualified error')
            return dict(decision='qualified_lost_particle_model_failure',
                        verdict=dict(score=0.,strict_correct=False))
        with patch('builtins.print'):p=self.dispatch(assess)
        self.assertEqual(seen,['031','032'])
        self.assertEqual(p['rows'][30]['score'],0.)
        self.assertEqual(p['rows'][31]['state'],'incident')
        self.assertEqual(p['rows'][32]['state'],'pending')
        self.assertEqual(p['rows'][29],self.progress['rows'][29])

    def test_cross_directory_claim_prevents_second_launch(self):
        write_json(self.previous.parent/(self.previous.name+'-resume-031-claim.json'),{})
        with self.assertRaises(FileExistsError):self.dispatch(lambda *args:None)
        self.assertFalse((self.output/'resumption-launch.json').exists())

    def test_wrong_budget_has_no_side_effect(self):
        with self.assertRaisesRegex(ValueError,'3360'):
            resume.dispatch(self.output,3840)
        self.assertFalse((self.output/'resumption-launch.json').exists())

    def test_prestart_guard_failure_leaves_031_pending(self):
        def guard(*args):raise ValueError('source changed')
        with patch('builtins.print'):p=self.dispatch(lambda *args:None,guard)
        self.assertEqual(p['state'],'stopped')
        self.assertEqual(p['rows'][30]['state'],'pending')


class DiagnosisTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.b=self.root/'slot/runs/cross_shaped_mixture/builder';self.b.mkdir(parents=True)
        self.result=dict(status='failed',error_type='RuntimeError',error=resume.EXPECTED_ERROR,
            request_count=1,cleanup_confirmed=True,host_candidate_execution='not_run',
            evaluator_validation='not_run')
        self.upstream=dict(http_status=200,content_type='<missing>',
            reader_version='responses-completion-deadline-v1',phase='body',
            stream_validation='failed',completion_observed=False,stop_reason='invalid_stream',
            last_event_type='response.completed',response_bytes_read=92954)
        self.manifest=dict(case='cross_shaped_mixture',model='gpt-5.6-luna',
            assistance=resume.base.campaign.ARMS['A'],mode='subscription',
            max_requests=16,wall_seconds=600,image_id=resume.IMAGE_ID,
            required_request_setup={},container_name='container')
        for field,snapshot,source in (
            ('controller_sha256','controller-source.py','builder/run.py'),
            ('relay_sha256','relay-source.py','builder/relay.py'),
            ('entry_sha256','runtime-source.py','builder/runtime/entry.py')):
            (self.b/snapshot).write_bytes(Path(source).read_bytes())
            self.manifest[field]=resume.sha(source)
        self.m=dict(rows=[{}]*29+[{'path':'slot'}],request_setups={'gpt-5.6-luna':{}})
        self.save()
        write_json(self.b/'request-01.json',{})
        write_json(self.b/'setup-01.json',{'matched':True})
        write_json(self.b/'lifecycle.json',{'state':'removed','container_name':'container'})

    def save(self):
        for name,value in (('result.json',self.result),('upstream-01.json',self.upstream),
                           ('manifest.json',self.manifest)):
            write_json(self.b/name,value)

    def diagnose(self):
        with patch.object(resume,'validate_request'), \
             patch.object(resume,'request_setup',return_value={}), \
             patch.object(resume.base.region_skill,'initial_context',return_value=True):
            return resume.diagnose(self.root,self.m)

    def test_completed_event_is_not_validated_delivery_or_model_failure(self):
        value=self.diagnose()
        self.assertIsNone(value['score'])
        self.assertFalse(value['completed_response_validated'])
        self.assertFalse(value['offending_event_identified'])
        self.assertFalse(value['model_failure_established'])

    def test_changed_cleanup_forwarding_or_completion_rejected(self):
        for field,value in (('completion_observed',True),('response_bytes_forwarded',92954),
                            ('stream_validation','passed')):
            original=deepcopy(self.upstream)
            self.upstream[field]=value;self.save()
            with self.subTest(field=field),self.assertRaises(ValueError):self.diagnose()
            self.upstream=original
        self.save();self.result['cleanup_confirmed']=False;self.save()
        with self.assertRaisesRegex(ValueError,'Incident signature'):self.diagnose()

    def test_response_file_or_started_assessment_invalidates_diagnosis(self):
        (self.b/'response-01.sse').write_text('unexpected')
        with self.assertRaisesRegex(ValueError,'Unexpected response'):self.diagnose()
        (self.b/'response-01.sse').unlink()
        (self.b.parent/'assessment').mkdir()
        with self.assertRaisesRegex(ValueError,'Unexpected response'):self.diagnose()


if __name__=='__main__':
    unittest.main()
