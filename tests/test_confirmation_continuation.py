"""Continuation orchestration controls; execution and physics providers are doubles."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import confirmation_continuation as continuation
from builder.context import write_json


class ContinuationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.output = self.root/'continuation'
        self.output.mkdir()
        self.revision = self.root/'revision'
        self.revision.mkdir()
        self.rows = [dict(id=f'{i:03d}',model='model',arm='A',case='case',repeat=1,
                          path=f'runs/{i:03d}',plan_sha256='plan',state='pending')
                     for i in range(1,241)]
        self.original = dict(rows=self.rows)
        self.revised = dict(rows=[dict(**{k:r[k] for k in continuation.migration.IMMUTABLE_ROW},
            verdict=dict(evidence_status='coherent',score=0. if r['id']=='012' else 100.,
                         strict_correct=r['id']!='012')) for r in self.rows[:12]],
            counts=dict(protocol_success=11,evaluated_failure=1,unscored_incident=0,pending=228))
        write_json(self.root/'original.json',self.original)
        write_json(self.revision/'report.json',self.revised)
        self.manifest = dict(continuation=dict(
            original_manifest=continuation.binding(self.root/'original.json'),
            revision=continuation.binding(self.revision/'report.json')))
        write_json(self.output/'manifest.json',self.manifest)
        self.progress = dict(state='prepared_not_dispatched',rows=continuation.prefix_rows(
            self.original,self.revised,self.revision))
        write_json(self.output/'progress.json',self.progress)

    def test_consumed_prefix_and_original_order_are_preserved(self):
        actual = continuation.fresh_progress(self.output,self.manifest)
        self.assertEqual(actual['rows'][:12],self.progress['rows'][:12])
        self.assertEqual(actual['rows'][11]['score'],0.)
        self.assertEqual([r['id'] for r in actual['rows'][12:]],
                         [f'{i:03d}' for i in range(13,241)])
        self.assertTrue(all(r['state']=='pending' for r in actual['rows'][12:]))

    def test_changed_prefix_or_unresolved_verdict_is_rejected(self):
        for change in ('short','swapped','unresolved','identity','counts'):
            value=deepcopy(self.revised)
            if change=='short':value['rows'].pop()
            if change=='swapped':value['rows'][0],value['rows'][1]=value['rows'][1],value['rows'][0]
            if change=='unresolved':value['rows'][0]['verdict']['score']=None
            if change=='identity':value['rows'][0]['arm']='D'
            if change=='counts':value['counts']['evaluated_failure']=0
            with self.subTest(change=change),self.assertRaises(ValueError):
                continuation.prefix_rows(self.original,value,self.revision)

    def test_started_progress_and_existing_execution_are_never_restarted(self):
        altered=deepcopy(self.progress)
        altered['rows'][12]['state']='started'
        write_json(self.output/'progress.json',altered)
        with self.assertRaisesRegex(ValueError,'not fresh'):
            continuation.fresh_progress(self.output,self.manifest)
        write_json(self.output/'progress.json',self.progress)
        (self.output/'runs/013/runs').mkdir(parents=True)
        with self.assertRaisesRegex(ValueError,'execution evidence'):
            continuation.fresh_progress(self.output,self.manifest)

    def test_existing_launch_rejected(self):
        write_json(self.output/'continuation-launch.json',{})
        with self.assertRaisesRegex(ValueError,'already consumed'):
            continuation.fresh_progress(self.output,self.manifest)

    def test_existing_preparation_is_never_overwritten(self):
        with self.assertRaisesRegex(ValueError,'fresh'):
            continuation.prepare(self.output,self.revision,self.root)
        self.assertEqual(continuation.read(self.output/'progress.json'),self.progress)

    def test_input_copy_inventory_excludes_execution_and_rejects_symlinks(self):
        folder=self.root/'prepared'
        (folder/'inputs/case').mkdir(parents=True)
        for name in ('plan.json','support-matrix.json','inputs/case/prompt.txt'):
            (folder/name).write_text(name)
        (folder/'runs').mkdir()
        (folder/'runs/private.json').write_text('must not copy')
        self.assertEqual(set(continuation.prepared_files(folder)),
                         {'plan.json','support-matrix.json','inputs/case/prompt.txt'})
        (folder/'inputs/case/link').symlink_to(folder/'plan.json')
        with self.assertRaisesRegex(ValueError,'symlink'):
            continuation.prepared_files(folder)

    def run_dispatch(self, assess, guard=None):
        with patch.object(continuation,'check',return_value=dict(status='passed')), \
             patch.object(continuation,'guard',side_effect=guard), \
             patch.object(continuation,'assess',side_effect=assess):
            return continuation.dispatch(self.output,3648)

    def test_model_failure_continues_then_unattributed_incident_stops(self):
        seen=[]
        def assess(output,m,row):
            seen.append(row['id'])
            if row['id']=='014':raise ValueError('Unqualified native error')
            return dict(decision='qualified_lost_particle_model_failure',
                        verdict=dict(score=0.,strict_correct=False))
        result=self.run_dispatch(assess)
        self.assertEqual(seen,['013','014'])
        self.assertEqual(result['rows'][12]['state'],'finished')
        self.assertEqual(result['rows'][12]['score'],0.)
        self.assertEqual(result['rows'][13]['state'],'incident')
        self.assertTrue(all(r['state']=='pending' for r in result['rows'][14:]))
        self.assertEqual(result['rows'][:12],self.progress['rows'][:12])
        self.assertEqual(result['state'],'stopped')
        self.assertTrue((self.revision/'continuation-claim.json').exists())
        with self.assertRaisesRegex(ValueError,'already consumed'):
            continuation.dispatch(self.output,3648)

    def test_guard_failure_does_not_consume_an_unstarted_assignment(self):
        def guard(output,m,row):raise ValueError('Disk reserve below 10 GiB')
        with patch.object(continuation,'assess') as assess:
            result=self.run_dispatch(assess,guard)
            assess.assert_not_called()
        self.assertEqual(result['state'],'stopped')
        self.assertTrue(all(r['state']=='pending' for r in result['rows'][12:]))

    def test_second_directory_cannot_replay_same_suffix(self):
        write_json(self.revision/'continuation-claim.json',dict(output='another directory'))
        with patch.object(continuation,'check',return_value=dict(status='passed')), \
             patch.object(continuation,'assess') as assess:
            with self.assertRaises(FileExistsError):
                continuation.dispatch(self.output,3648)
            assess.assert_not_called()
        self.assertFalse((self.output/'continuation-launch.json').exists())

    def test_wrong_budget_has_no_effect(self):
        with self.assertRaisesRegex(ValueError,'3648'):
            continuation.dispatch(self.output,3840)
        self.assertFalse((self.revision/'continuation-claim.json').exists())

    def test_entire_suffix_is_run_once_and_only_once(self):
        seen=[]
        def assess(output,m,row):
            seen.append(row['id'])
            return dict(decision='unchanged_after_reconstruction',
                        verdict=dict(score=100.,strict_correct=True))
        with patch('builtins.print'):
            result=self.run_dispatch(assess)
        self.assertEqual(seen,[f'{i:03d}' for i in range(13,241)])
        self.assertEqual(result['state'],'complete')
        self.assertEqual(result['rows'][11]['score'],0.)

    def test_bound_evidence_tampering_rejected(self):
        b=continuation.binding(self.root/'original.json')
        (self.root/'original.json').write_text('{}')
        with self.assertRaisesRegex(ValueError,'evidence changed'):
            continuation.bound(b)


class AssessmentPolicyTests(unittest.TestCase):
    def test_same_revision_runs_after_every_baseline_and_retains_legacy_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            output=Path(tmp)
            row=dict(path='assignment',case='case',model='model')
            task=output/'assignment/runs/case'
            (task/'assessment').mkdir(parents=True)
            (task/'candidate.py').write_bytes(b'candidate')
            m=dict(request_setups={'model':{}},data_index={'path':'index'},references={'case':'reference'})
            legacy=dict(evidence_status='insufficient',score=None)
            revised=dict(decision='qualified_lost_particle_model_failure',
                         verdict=dict(evidence_status='coherent',score=0.,strict_correct=False))
            with patch.object(continuation,'execute',return_value={'tasks':[{'builder_status':'completed'}]}), \
                 patch.object(continuation,'submission',return_value=(b'candidate',{'source':'bound'})), \
                 patch.object(continuation,'evaluate',return_value={'cleanup_confirmed':True}), \
                 patch.object(continuation,'review_assessment',return_value=legacy), \
                 patch.object(continuation.verdict_migration,'revise',return_value=revised) as revision:
                self.assertEqual(continuation.assess(output,m,row),revised)
                revision.assert_called_once_with(task/'assessment',Path('index'),'reference')
                self.assertEqual(continuation.read(task/'assessment/review.json'),legacy)
                self.assertEqual(continuation.read(task/'assessment/revised-verdict.json'),revised)
                revision.side_effect=ValueError('Unknown native diagnostic')
                with self.assertRaisesRegex(ValueError,'Unknown native'):
                    continuation.assess(output,m,row)

    def test_unconfirmed_cleanup_stops_before_reclassification(self):
        with tempfile.TemporaryDirectory() as tmp:
            output=Path(tmp);task=output/'assignment/runs/case'
            task.mkdir(parents=True);(task/'candidate.py').write_bytes(b'candidate')
            m=dict(request_setups={'model':{}},data_index={'path':'index'},references={'case':'reference'})
            with patch.object(continuation,'execute',return_value={'tasks':[{'builder_status':'completed'}]}), \
                 patch.object(continuation,'submission',return_value=(b'candidate',{})), \
                 patch.object(continuation,'evaluate',return_value={'cleanup_confirmed':False}), \
                 patch.object(continuation.verdict_migration,'revise') as revision:
                with self.assertRaisesRegex(ValueError,'cleanup'):
                    continuation.assess(output,m,dict(path='assignment',case='case',model='model'))
                revision.assert_not_called()


if __name__=='__main__':
    unittest.main()
