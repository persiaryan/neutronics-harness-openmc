"""Portable no-replay and retained stream-incident controls for resume 237."""
from copy import deepcopy
from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch

import confirmation_resume_237 as resume
from builder.context import write_json


def value(score=100.,strict=True):
    return dict(decision='unchanged_after_reconstruction',verdict=dict(
        evidence_status='coherent',score=score,strict_correct=strict,
        diagnostic_score={'status':'unscored' if score is None else 'scored'},
        gates={name:{'passed':True} for name in resume.prior.HARD_GATES},
        checks={'geometry':{'boundaries':None if score is None else True}}))


class Resume237Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name).resolve()
        self.previous=self.root/'previous';self.previous.mkdir()
        self.output=self.root/'next';self.output.mkdir()
        self.ancestor=self.root/'ancestor';self.ancestor.mkdir()
        write_json(self.ancestor/'manifest.json',{})
        rows=[dict(id=f'{i:03d}',model='model',arm='A',case='case',repeat=1,
            path=f'runs/{i:03d}',state='pending',plan_sha256='plan') for i in range(1,241)]
        rows[235].update(case='cylindrical_void_sleeve',model='gpt-5.6-sol',arm='D',repeat=5)
        self.m=dict(rows=deepcopy(rows),data_index={'path':'index'},resumption_133=dict(
            previous_manifest=resume.base.binding(self.ancestor/'manifest.json')))
        deferred={'140','184','192','195','202','205','208','224'}
        unknowns={'030','039','050','066','117','118','119','120','132','236'}|deferred
        failures={'012','025','034','038','062','069','080','090','098','102','106','110','111',
                  '143','170','186','188','222','226'}
        for row in rows[:236]:
            if row['id'] in unknowns:
                row.update(state='incident',reason='Builder incomplete; slot consumed')
                if row['id'] in deferred:
                    row.update(disposition='deferred_unscored',score=None,strict_correct=None,
                               stop_required=False)
                elif row['id']=='236':row.update(disposition='blocking_incident',stop_required=True)
            else:
                success=row['id'] not in failures
                score=100. if success else (96.42857142857143 if row['id']=='170' else 0.)
                row.update(state='finished',score=score,strict_correct=success)
        self.inherited=deepcopy(rows)
        for row in rows[132:235]:
            a=self.previous/row['path']/'runs'/row['case']/'assessment';a.mkdir(parents=True)
            v=value(row.get('score'),row.get('strict_correct') if row['state']=='finished' else False)
            write_json(a/'revised-verdict.json',v)
            write_json(a/'report.json',dict(status='assessed',stop=None,cleanup_confirmed=True))
            row.update(decision=v['decision'],verdict_path=str(a/'revised-verdict.json'))
        self.progress=dict(state='stopped',reason='Builder incomplete; slot consumed',rows=rows)
        write_json(self.previous/'manifest.json',self.m);write_json(self.previous/'progress.json',self.progress)
        self.manifest=dict(self.m,resumption_237=dict(controller=resume.base.binding(resume.CONTROLLER),
            policy_document=resume.base.binding(resume.POLICY_DOCUMENT),
            previous_manifest=resume.base.binding(self.previous/'manifest.json')))
        write_json(self.output/'manifest.json',self.manifest)
        write_json(self.output/'progress.json',dict(state='prepared_not_dispatched',rows=rows))

    def terminal(self):
        def reconstruct(previous,m,row,index):
            return resume.read(previous/row['path']/'runs'/row['case']/'assessment/revised-verdict.json')
        with patch.object(resume.prior,'terminal_prefix',return_value=(self.inherited,{})), \
             patch.object(resume.base.migration,'reconstruct',side_effect=reconstruct), \
             patch.object(resume,'diagnose',return_value={'score':None}):
            return resume.terminal_prefix(self.previous,self.m)

    def dispatch(self,assess,guard=None):
        with patch.object(resume,'check',return_value={'status':'passed'}), \
             patch.object(resume.base,'guard',side_effect=guard), \
             patch.object(resume,'assess',side_effect=assess):
            return resume.dispatch(self.output,64)

    def test_prefix_keeps_236_consumed_and_all_eighteen_unknowns(self):
        rows,_=self.terminal()
        self.assertEqual(rows,self.progress['rows'])
        self.assertEqual(sum(r['state']=='incident' for r in rows),18)
        self.assertEqual(sum(r['state']=='pending' for r in rows),4)
        self.assertNotIn('score',rows[235])
        self.assertTrue(rows[235]['stop_required'])
        self.assertEqual(rows[236]['id'],'237')

    def test_changed_scores_nulls_order_or_historical_prefix_are_rejected(self):
        for change in ('new_score','deferred_score','blocking_score','inherited','order'):
            p=deepcopy(self.progress)
            if change=='new_score':p['rows'][132]['score']=0.
            if change=='deferred_score':p['rows'][139]['score']=0.
            if change=='blocking_score':p['rows'][235]['score']=None
            if change=='inherited':p['rows'][38]['score']=100.
            if change=='order':p['rows'][236],p['rows'][237]=p['rows'][237],p['rows'][236]
            write_json(self.previous/'progress.json',p)
            with self.subTest(change=change),self.assertRaises(ValueError):self.terminal()

    def test_partial_score_is_preserved_exactly(self):
        rows,_=self.terminal()
        self.assertEqual(rows[169]['score'],96.42857142857143)
        self.assertFalse(rows[169]['strict_correct'])

    def test_only_last_four_execute_and_old_blocking_flag_stays_historical(self):
        seen=[]
        def assess(output,m,row):seen.append(row['id']);return value(),'scored'
        before=resume.base.migration.inventory(self.previous)
        with patch('builtins.print'):p=self.dispatch(assess)
        self.assertEqual(seen,['237','238','239','240'])
        self.assertEqual(p['state'],'complete')
        self.assertEqual(p['rows'][:236],self.progress['rows'][:236])
        self.assertTrue(p['rows'][235]['stop_required'])
        self.assertEqual(resume.base.migration.inventory(self.previous),before)

    def test_deferred_unknown_continues_without_model_failure(self):
        def assess(output,m,row):
            return (value(None,False),'deferred_unscored') if row['id']=='237' else (value(),'scored')
        with patch('builtins.print'):p=self.dispatch(assess)
        self.assertEqual(p['state'],'complete')
        self.assertEqual(p['rows'][236]['disposition'],'deferred_unscored')
        self.assertIsNone(p['rows'][236]['strict_correct'])
        self.assertEqual(resume.read(self.output/'deferred-anomalies.json')['unscored_count'],19)

    def test_scored_model_failure_continues(self):
        with patch('builtins.print'):p=self.dispatch(lambda *args:(value(0.,False),'scored'))
        self.assertEqual(p['state'],'complete')
        self.assertFalse(p['rows'][236]['strict_correct'])

    def test_new_execution_exception_stops_without_retry(self):
        seen=[]
        def assess(output,m,row):seen.append(row['id']);raise RuntimeError('new provider error')
        p=self.dispatch(assess)
        self.assertEqual(seen,['237'])
        self.assertEqual(p['state'],'stopped')
        self.assertTrue(p['rows'][236]['stop_required'])
        self.assertEqual(p['rows'][237]['state'],'pending')

    def test_guard_failure_does_not_consume_next_slot(self):
        def guard(*args):raise ValueError('frozen identity changed')
        p=self.dispatch(lambda *args:None,guard)
        self.assertEqual(p['state'],'stopped')
        self.assertEqual(p['rows'][236]['state'],'pending')

    def test_budget_exclusive_claim_and_replay_guards(self):
        with self.assertRaisesRegex(ValueError,'64-request'):resume.dispatch(self.output,80)
        write_json(self.previous.parent/(self.previous.name+'-resume-237-claim.json'),{})
        with self.assertRaises(FileExistsError):self.dispatch(lambda *args:None)
        write_json(self.output/'resumption-237-launch.json',{})
        with self.assertRaisesRegex(ValueError,'already consumed'):
            resume.fresh_progress(self.output,self.manifest)

    def test_existing_preparation_is_not_overwritten(self):
        with self.assertRaisesRegex(ValueError,'fresh'):resume.prepare(self.output,self.previous)

    def test_previous_execution_artifacts_refuse_dispatch(self):
        (self.output/'runs/237/runs').mkdir(parents=True)
        with self.assertRaisesRegex(ValueError,'Execution already'):
            resume.fresh_progress(self.output,self.manifest)

    def test_policy_and_evaluation_functions_are_reused_without_change(self):
        self.assertIs(resume.assess,resume.prior.assess)
        self.assertIs(resume.persist,resume.prior.persist)
        self.assertIs(resume.OPERATIONAL_POLICY,resume.prior.OPERATIONAL_POLICY)
        self.assertEqual(resume.POLICY_DOCUMENT,resume.prior.POLICY_DOCUMENT)


class Diagnosis236Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.previous=Path(self.tmp.name)
        self.row={'path':'slot','case':'cylindrical_void_sleeve'}
        self.b=self.previous/'slot/runs/cylindrical_void_sleeve/builder';self.b.mkdir(parents=True)
        self.setup={'frozen':True};self.m={'request_setups':{'gpt-5.6-sol':self.setup}}
        self.result=dict(status='failed',error_type='RuntimeError',error=resume.EXPECTED_ERROR,
            request_count=6,cleanup_confirmed=True,host_candidate_execution='not_run',evaluator_validation='not_run')
        self.up=dict(reader_version='responses-completion-deadline-v1',http_status=200,
            content_type='<missing>',stream_validation='failed',completion_observed=False,
            phase='body',stop_reason='invalid_stream',last_event_type='error',response_bytes_read=34210)
        self.manifest=dict(case='cylindrical_void_sleeve',model='gpt-5.6-sol',
            assistance=resume.base.campaign.ARMS['D'],
            condition=resume.CONDITIONS[resume.base.campaign.ARMS['D']],mode='subscription',
            max_requests=16,wall_seconds=600,request_budget_profile='authoring-requests-16-v1',
            image_id=resume.openmc_python.IMAGE_ID,prompt_sha256=resume.sha256(b'preloaded'),
            required_request_setup=self.setup,container_name='container')
        for field,snapshot,source in (
            ('controller_sha256','controller-source.py','builder/run.py'),
            ('relay_sha256','relay-source.py','builder/relay.py'),
            ('entry_sha256','runtime-source.py','builder/runtime/entry.py')):
            (self.b/snapshot).write_bytes(Path(source).read_bytes())
            self.manifest[field]=resume.sha(self.b/snapshot)
        write_json(self.b/'container.json',{'Id':'container-id'})
        write_json(self.b/'environment-probe.json',{})
        write_json(self.b/'lifecycle.json',dict(state='removed',container_name='container',container_id='container-id'))
        (self.b/'prompt.txt').write_bytes(b'preloaded')
        expected_hash=resume.sha256(json.dumps(self.setup,sort_keys=True).encode())
        for i in range(1,7):
            write_json(self.b/f'request-{i:02d}.json',dict(model='gpt-5.6-sol',id=i,setup=self.setup))
            write_json(self.b/f'setup-{i:02d}.json',dict(matched=True,expected_sha256=expected_hash))
            write_json(self.b/f'inventory-{i:02d}.json',{'id':i})
            if i<6:
                raw=f'completed response {i}'.encode();(self.b/f'response-{i:02d}.sse').write_bytes(raw)
                write_json(self.b/f'upstream-{i:02d}.json',dict(stream_validation='passed',
                    completion_observed=True,last_event_type='response.completed',response_bytes_forwarded=len(raw)))
        self.save()

    def save(self):
        write_json(self.b/'result.json',self.result)
        write_json(self.b/'upstream-06.json',self.up)
        write_json(self.b/'manifest.json',self.manifest)

    def diagnose(self):
        with patch.object(resume,'verify_container'), \
             patch.object(resume.openmc_python,'verify_image'), \
             patch.object(resume.openmc_python,'verify_probe'), \
             patch.object(resume.region_skill,'verify'), \
             patch.object(resume,'build_prompt',return_value='public'), \
             patch.object(resume,'condition_prompt',return_value='preloaded'), \
             patch.object(resume.region_skill,'initial_context',return_value=True), \
             patch.object(resume,'validate_request',side_effect=lambda body,name:resume.require(body['model']==name,'model changed')), \
             patch.object(resume,'request_setup',side_effect=lambda body:body['setup']), \
             patch.object(resume,'request_inventory',side_effect=lambda body:{'id':body['id']}):
            return resume.diagnose(self.previous,self.m,self.row)

    def test_failed_stream_stays_unscored_and_original_files_unchanged(self):
        before=resume.base.migration.inventory(self.previous)
        diagnosis=self.diagnose()
        self.assertIsNone(diagnosis['score'])
        self.assertFalse(diagnosis['model_failure_established'])
        self.assertFalse(diagnosis['assessment_executed'])
        self.assertEqual(diagnosis['requests_consumed'],6)
        self.assertEqual(diagnosis['completed_responses'],5)
        self.assertEqual(resume.base.migration.inventory(self.previous),before)

    def test_changed_stream_signature_is_rejected(self):
        for key,new in [('last_event_type','response.completed'),('completion_observed',True),
                        ('response_bytes_read',1),('http_status',255)]:
            old=self.up[key];self.up[key]=new;self.save()
            with self.subTest(key=key),self.assertRaises(ValueError):self.diagnose()
            self.up[key]=old;self.save()

    def test_missing_cleanup_or_wrong_budget_is_rejected(self):
        self.result['cleanup_confirmed']=False;self.save()
        with self.assertRaisesRegex(ValueError,'signature'):self.diagnose()
        self.result['cleanup_confirmed']=True;self.manifest['max_requests']=17;self.save()
        with self.assertRaisesRegex(ValueError,'assignment'):self.diagnose()

    def test_extra_rejected_response_or_assessment_is_rejected(self):
        (self.b/'response-06.sse').write_text('unexpected')
        with self.assertRaisesRegex(ValueError,'inventory'):self.diagnose()
        (self.b/'response-06.sse').unlink()
        (self.b.parent/'assessment').mkdir()
        with self.assertRaisesRegex(ValueError,'inventory'):self.diagnose()

    def test_changed_setup_or_frozen_source_is_rejected(self):
        write_json(self.b/'setup-06.json',{'matched':False})
        with self.assertRaisesRegex(ValueError,'setup'):self.diagnose()
        (self.b/'relay-source.py').write_text('changed')
        with self.assertRaisesRegex(ValueError,'implementation'):self.diagnose()

    def test_container_lifecycle_identity_is_checked(self):
        write_json(self.b/'lifecycle.json',dict(state='removed',container_name='container',container_id='other'))
        with self.assertRaisesRegex(ValueError,'cleanup'):self.diagnose()


if __name__=='__main__':unittest.main()
