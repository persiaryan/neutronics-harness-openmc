"""Portable controls for prospective deferred diagnosis and resume 133."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import confirmation_resume_133 as resume
from builder.context import write_json


def verdict(score=100.,strict=True):
    return dict(decision='unchanged_after_reconstruction',verdict=dict(
        evidence_status='coherent',score=score,strict_correct=strict,
        diagnostic_score={'status':'unscored' if score is None else 'scored'},
        gates={k:{'passed':True} for k in resume.HARD_GATES},
        checks={'geometry':{'boundaries':None if score is None else True},
                'physics_settings':{'source':True}}))


def report():
    return dict(status='assessed',stop=None,cleanup_confirmed=True)


class PolicyTests(unittest.TestCase):
    def test_success_and_demonstrated_failure_are_scored(self):
        for value in (verdict(),verdict(0.,False)):
            with self.subTest(score=value['verdict']['score']):
                self.assertEqual(resume.classify_outcome(report(),value),'scored')

    def test_coherent_null_stays_null_and_is_deferred(self):
        value=verdict(None,False);before=deepcopy(value)
        self.assertEqual(resume.classify_outcome(report(),value),'deferred_unscored')
        self.assertEqual(value,before)
        self.assertIsNone(value['verdict']['score'])

    def test_new_source_limitation_is_eligible_without_message_allowlist(self):
        value=verdict(None,False)
        value['verdict']['checks']={'physics_settings':{'source':None,'sampling':False}}
        self.assertEqual(resume.classify_outcome(report(),value),'deferred_unscored')

    def test_cleanup_uncertain_stops_scored_and_unscored(self):
        for value in (verdict(),verdict(None,False)):
            bad=report();bad['cleanup_confirmed']=False
            with self.subTest(score=value['verdict']['score']),self.assertRaisesRegex(ValueError,'cleanup'):
                resume.classify_outcome(bad,value)

    def test_insufficient_or_contradictory_evidence_stops_even_if_scored(self):
        for status in ('insufficient','contradictory'):
            for score,strict in ((100.,True),(None,False)):
                value=verdict(score,strict);value['verdict']['evidence_status']=status
                with self.subTest(status=status,score=score),self.assertRaisesRegex(ValueError,'coherent'):
                    resume.classify_outcome(report(),value)

    def test_incomplete_native_or_unresolved_hard_gate_is_blocking(self):
        for change in ('stopped','stop','gate_missing','gate_null','gate_false','strict','no_unknown'):
            value=verdict(None,False);r=report()
            if change=='stopped':r['status']='stopped'
            if change=='stop':r['stop']={'stage':'transport'}
            if change=='gate_missing':value['verdict']['gates'].pop('openmc_runs')
            if change=='gate_null':value['verdict']['gates']['openmc_runs']['passed']=None
            if change=='gate_false':value['verdict']['gates']['openmc_runs']['passed']=False
            if change=='strict':value['verdict']['strict_correct']=True
            if change=='no_unknown':value['verdict']['checks']['geometry']['boundaries']=True
            with self.subTest(change=change),self.assertRaises(ValueError):
                resume.classify_outcome(r,value)


class Resume133Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name).resolve()
        self.previous=self.root/'previous';self.previous.mkdir()
        self.output=self.root/'next';self.output.mkdir()
        self.ancestor=self.root/'ancestor';self.ancestor.mkdir()
        write_json(self.ancestor/'manifest.json',{})
        rows=[dict(id=f'{i:03d}',model='model',arm='A',case='case',repeat=1,
            path=f'runs/{i:03d}',state='pending',plan_sha256='plan') for i in range(1,241)]
        rows[131].update(case='wrapped_eight_pin_channel',model='gpt-5.6-luna',arm='D',repeat=4)
        self.m=dict(rows=deepcopy(rows),data_index={'path':'index'},resumption_121=dict(
            previous_manifest=resume.base.binding(self.ancestor/'manifest.json')))
        unknowns={'030','039','050','066','117','118','119','120','132'}
        failures={'012','025','034','038','062','069','080','090','098','102','106','110','111'}
        for row in rows[:132]:
            if row['id'] in unknowns:
                row.update(state='incident',reason='Builder incomplete; slot consumed' if row['id']=='030'
                    else 'Unscored evaluation incident; pause before next slot')
            else:
                success=row['id'] not in failures
                row.update(state='finished',score=100. if success else 0.,strict_correct=success)
        self.ancestor_rows=deepcopy(rows)
        self.progress=dict(state='stopped',reason='Unscored evaluation incident; pause before next slot',rows=rows)
        for row in rows[120:131]:
            a=self.previous/row['path']/'runs'/row['case']/'assessment'
            a.mkdir(parents=True)
            write_json(a/'revised-verdict.json',verdict(row['score'],row['strict_correct']))
        write_json(self.previous/'manifest.json',self.m)
        write_json(self.previous/'progress.json',self.progress)
        self.manifest=dict(self.m,resumption_133=dict(controller=resume.base.binding(resume.CONTROLLER),
            policy_document=resume.base.binding(resume.POLICY_DOCUMENT),
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

    def dispatch(self,assess,guard=None):
        with patch.object(resume,'check',return_value={'status':'passed'}), \
             patch.object(resume.base,'guard',side_effect=guard), \
             patch.object(resume,'assess',side_effect=assess):
            return resume.dispatch(self.output,1728)

    def test_132_consumed_and_all_nine_nulls_preserved(self):
        rows,_=self.terminal()
        self.assertEqual(rows,self.progress['rows'])
        self.assertEqual(sum(r['state']=='pending' for r in rows),108)
        for i in (29,38,49,65,116,117,118,119,131):self.assertNotIn('score',rows[i])
        self.assertEqual(rows[132]['id'],'133')

    def test_changed_prefix_score_or_order_is_rejected(self):
        for change in ('null_score','new_score','earlier','order'):
            p=deepcopy(self.progress)
            if change=='null_score':p['rows'][131]['score']=None
            if change=='new_score':p['rows'][120]['score']=0.
            if change=='earlier':p['rows'][38]['score']=100.
            if change=='order':p['rows'][132],p['rows'][133]=p['rows'][133],p['rows'][132]
            write_json(self.previous/'progress.json',p)
            with self.subTest(change=change),self.assertRaises(ValueError):self.terminal()

    def test_partial_failure_preserved_without_rounding(self):
        self.progress['rows'][105]['score']=96.42857142857143
        self.ancestor_rows[105]['score']=96.42857142857143
        write_json(self.previous/'progress.json',self.progress)
        rows,_=self.terminal()
        self.assertEqual(rows[105]['score'],96.42857142857143)

    def test_133_through_240_once_without_touching_prefix(self):
        seen=[]
        def assess(output,m,row):
            seen.append(row['id']);return verdict(),'scored'
        before=resume.base.migration.inventory(self.previous)
        with patch('builtins.print'):p=self.dispatch(assess)
        self.assertEqual(seen,[f'{i:03d}' for i in range(133,241)])
        self.assertEqual(p['state'],'complete')
        self.assertTrue(p['post_campaign_review_required'])
        self.assertEqual(p['rows'][:132],self.progress['rows'][:132])
        self.assertEqual(resume.base.migration.inventory(self.previous),before)

    def test_deferred_unknown_continues_and_is_not_a_model_failure(self):
        seen=[]
        def assess(output,m,row):
            seen.append(row['id'])
            return (verdict(None,False),'deferred_unscored') if row['id']=='133' else (verdict(),'scored')
        with patch('builtins.print'):p=self.dispatch(assess)
        self.assertEqual(len(seen),108)
        row=p['rows'][132]
        self.assertEqual(row['state'],'incident')
        self.assertEqual(row['disposition'],'deferred_unscored')
        self.assertIsNone(row['score']);self.assertIsNone(row['strict_correct'])
        self.assertFalse(row['stop_required'])
        queue=resume.read(self.output/'deferred-anomalies.json')
        self.assertEqual(queue['unscored_count'],10)
        self.assertEqual(queue['rows'][-1]['id'],'133')

    def test_scored_failure_continues(self):
        def assess(output,m,row):return verdict(0.,False),'scored'
        with patch('builtins.print'):p=self.dispatch(assess)
        self.assertEqual(p['state'],'complete')
        self.assertEqual(p['rows'][132]['score'],0.)
        self.assertIs(p['rows'][132]['strict_correct'],False)

    def test_execution_exception_stops_without_retry(self):
        seen=[]
        def assess(output,m,row):
            seen.append(row['id']);raise RuntimeError('Provider or execution problem')
        p=self.dispatch(assess)
        self.assertEqual(seen,['133'])
        self.assertEqual(p['state'],'stopped')
        self.assertEqual(p['rows'][132]['disposition'],'blocking_incident')
        self.assertTrue(p['rows'][132]['stop_required'])
        self.assertEqual(p['rows'][133]['state'],'pending')

    def test_incoherent_result_blocks_dispatch(self):
        def assess(output,m,row):
            value=verdict();value['verdict']['evidence_status']='contradictory'
            return value,resume.classify_outcome(report(),value)
        p=self.dispatch(assess)
        self.assertEqual(p['state'],'stopped')
        self.assertTrue(p['rows'][132]['stop_required'])
        self.assertEqual(p['rows'][133]['state'],'pending')

    def test_unconfirmed_cleanup_blocks_dispatch(self):
        def assess(output,m,row):
            value=verdict(None,False);bad=report();bad['cleanup_confirmed']=False
            return value,resume.classify_outcome(bad,value)
        p=self.dispatch(assess)
        self.assertEqual(p['state'],'stopped')
        self.assertTrue(p['rows'][132]['stop_required'])
        self.assertEqual(p['rows'][133]['state'],'pending')

    def test_policy_guard_failure_does_not_consume_next_slot(self):
        def guard(*args):raise ValueError('Policy or frozen input changed')
        p=self.dispatch(lambda *args:None,guard)
        self.assertEqual(p['state'],'stopped')
        self.assertEqual(p['rows'][132]['state'],'pending')

    def test_wrong_budget_duplicate_claim_and_replay_rejected(self):
        with self.assertRaisesRegex(ValueError,'1728'):resume.dispatch(self.output,1920)
        write_json(self.previous.parent/(self.previous.name+'-resume-133-claim.json'),{})
        with self.assertRaises(FileExistsError):self.dispatch(lambda *args:None)
        self.assertFalse((self.output/'resumption-133-launch.json').exists())
        write_json(self.output/'resumption-133-launch.json',{})
        with self.assertRaisesRegex(ValueError,'already consumed'):
            resume.fresh_progress(self.output,self.manifest)

    def test_existing_preparation_not_overwritten(self):
        with self.assertRaisesRegex(ValueError,'fresh'):resume.prepare(self.output,self.previous)

    def test_changed_policy_document_is_bound_before_dispatch(self):
        policy=self.root/'policy.md';policy.write_text('frozen')
        self.manifest['resumption_133']['policy_document']=resume.base.binding(policy)
        write_json(self.output/'manifest.json',self.manifest);policy.write_text('changed')
        p=self.dispatch(lambda *args:None)
        self.assertEqual(p['state'],'stopped')
        self.assertEqual(p['rows'][132]['state'],'pending')


class AssessmentPathTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.row={'path':'slot','case':'case','model':'model'}
        self.task=self.root/'slot/runs/case';self.task.mkdir(parents=True)
        (self.task/'assessment').mkdir()
        (self.task/'candidate.py').write_bytes(b'candidate bytes')
        self.m={'request_setups':{'model':{'unchanged':True}},'data_index':{'path':'index'},
                'references':{'case':{'private':'sealed'}}}

    def test_unchanged_evaluation_calls_and_null_evidence_are_retained(self):
        value=verdict(None,False);r=report()
        with patch.object(resume.base,'execute',return_value={'tasks':[{'builder_status':'completed'}]}) as execute, \
             patch.object(resume.base,'submission',return_value=(b'candidate bytes',{'source':'bound'})), \
             patch.object(resume.base,'evaluate',return_value=r) as evaluate, \
             patch.object(resume.base,'review_assessment',return_value={'evidence_status':'coherent'}), \
             patch.object(resume.base.verdict_migration,'revise',return_value=value):
            got,disposition=resume.assess(self.root,self.m,self.row)
        self.assertEqual(got,value);self.assertEqual(disposition,'deferred_unscored')
        self.assertEqual(resume.read(self.task/'assessment/revised-verdict.json'),value)
        self.assertEqual(execute.call_args.kwargs['request_setup'],self.m['request_setups']['model'])
        self.assertEqual(evaluate.call_args.kwargs['evaluator_protocol'],resume.base.CONFIRMATION_PROTOCOL)
        self.assertEqual(evaluate.call_args.kwargs['reference'],{'private':'sealed'})

    def test_cleanup_failure_stops_before_review(self):
        bad=report();bad['cleanup_confirmed']=False
        with patch.object(resume.base,'execute',return_value={'tasks':[{'builder_status':'completed'}]}), \
             patch.object(resume.base,'submission',return_value=(b'candidate bytes',{})), \
             patch.object(resume.base,'evaluate',return_value=bad), \
             patch.object(resume.base,'review_assessment') as review:
            with self.assertRaisesRegex(ValueError,'cleanup'):resume.assess(self.root,self.m,self.row)
        review.assert_not_called()

    def test_read_only_reconstruction_keeps_132_null(self):
        a=self.task/'assessment'
        value=verdict(None,False);write_json(a/'revised-verdict.json',value);write_json(a/'report.json',report())
        for name in ('candidate.py','review.json','export-fidelity.json'):(a/name).write_text('{}')
        before=resume.base.migration.inventory(a)
        with patch.object(resume.base.migration,'reconstruct',return_value=value):
            got=resume.diagnose(self.root,self.m,self.row)
        self.assertIsNone(got['score'])
        self.assertEqual(got['new_native_transports'],0)
        self.assertEqual(resume.base.migration.inventory(a),before)


if __name__=='__main__':unittest.main()
